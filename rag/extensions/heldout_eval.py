"""Held-out check: choose each method's parameter on one split (practice), then apply it unchanged to another
split (dev) and compare with the enc_a baseline there. Also times the reranker on the held-out split. No ELM calls."""
import argparse, json, statistics, time
from pathlib import Path

import numpy as np

import common as C

ap = argparse.ArgumentParser()
ap.add_argument('--tune-split', default='practice')
ap.add_argument('--tune-rankings', type=Path, required=True, help='enc_rankings.py output for the tuning split')
ap.add_argument('--tune-transcripts', type=Path, default=C.TRANSCRIPTS)
ap.add_argument('--test-split', default='dev')
ap.add_argument('--test-rankings', type=Path, required=True)
ap.add_argument('--test-transcripts', type=Path, required=True)
ap.add_argument('--model', default='cross-encoder/ms-marco-MiniLM-L-6-v2')
ap.add_argument('--n-cand', type=int, default=20)
ap.add_argument('--device', default=None)
ap.add_argument('--select-metric', default='R@5')
ap.add_argument('--out-dir', type=Path, required=True)
args = ap.parse_args()
if (args.out_dir / 'summary.txt').exists():
    ap.error('out-dir already has results; choose a new folder')
args.out_dir.mkdir(parents=True, exist_ok=True)
N = args.n_cand

from sentence_transformers import CrossEncoder
data = C.CourseData(C.DATA_DIR)
ce = CrossEncoder(args.model, device=args.device)
ce.predict([('warm up', 'warm up')])

def prepare(split, rankings_path, trans_path):
    qrels = data.load_qrels(split)
    trans = C.load_transcripts(trans_path)
    rows = {r['query_id']: r for r in C.load_jsonl(rankings_path)}
    qids = [q for q in trans if q in qrels and q in rows]
    base = {q: rows[q]['ranked_ids'] for q in qids}
    enc = {q: np.asarray(rows[q]['scores'][:N], float) for q in qids}
    ces, lat = {}, []
    for q in qids:
        pairs = [(trans[q], data.record_text(d)) for d in base[q][:N]]
        t = time.perf_counter()
        ces[q] = np.asarray(ce.predict(pairs, batch_size=64), float)
        lat.append((time.perf_counter() - t) * 1000)
    return dict(qrels=qrels, qids=qids, base=base, enc=enc, ce=ces, lat=lat,
                res_base={q: C.metrics(base[q], qrels[q]) for q in qids})

tune = prepare(args.tune_split, args.tune_rankings, args.tune_transcripts)
test = prepare(args.test_split, args.test_rankings, args.test_transcripts)

FAMILIES = {
    'rerank': (lambda S, q, p: C.order_rerank(S['ce'][q]), [None]),
    'fusion': (lambda S, q, a: C.order_fusion(S['enc'][q], S['ce'][q], a), [round(a, 1) for a in np.arange(0, 1.01, 0.1)]),
    'rrf': (lambda S, q, c: C.order_rrf(S['ce'][q], c), [0, 1, 2, 3, 5, 10, 20, 30, 60, 100]),
    'protect': (lambda S, q, m: C.order_protect(S['ce'][q], m), [1, 2, 3, 4, 5, 6, 8, 10]),
}
def evaluate(S, fn, p):
    return {q: C.metrics(C.apply_order(S['base'][q], fn(S, q, p)), S['qrels'][q]) for q in S['qids']}

mt, ms = C.mean_of(tune['res_base'], tune['qids']), C.mean_of(test['res_base'], test['qids'])
L = [f'reranker {args.model}  top-{N}  device {ce.device}  parameters chosen by {args.select_metric} on all of '
     f'{args.tune_split} ({len(tune["qids"])} q), applied unchanged to {args.test_split} ({len(test["qids"])} q)',
     f'baseline {args.tune_split}: R@5 {mt["R@5"]:.4f} R@10 {mt["R@10"]:.4f} (Step 5: 0.4213 / 0.4796)',
     f'baseline {args.test_split}: ' + '  '.join(f'{k} {v:.4f}' for k, v in ms.items()),
     f'rerank latency on {args.test_split}: median {statistics.median(test["lat"]):.0f} ms, p90 {np.percentile(test["lat"], 90):.0f} ms', '',
     f'{"method":<9}{"param":>6}{"tune R@5":>10}{"test R@5":>10}{"R@10":>8}{"MRR@10":>8}{"NDCG@10":>9}{"resc/brok":>10}'
     f'{"dR@5 [95% CI], p":>34}{"dR@10 [95% CI], p":>34}']
L.append(f'{"baseline":<9}{"-":>6}{mt["R@5"]:>10.4f}{ms["R@5"]:>10.4f}{ms["R@10"]:>8.4f}{ms["MRR@10"]:>8.4f}{ms["NDCG@10"]:>9.4f}')
for fam, (fn, params) in FAMILIES.items():
    best = max(params, key=lambda p: C.mean_of(evaluate(tune, fn, p), tune['qids'])[args.select_metric])
    tr = C.mean_of(evaluate(tune, fn, best), tune['qids'])
    per = evaluate(test, fn, best)
    m = C.mean_of(per, test['qids'])
    r, b = C.churn(per, test['res_base'], test['qids'])
    cis = []
    for k in ['R@5', 'R@10']:
        d, lo, hi, p = C.paired_bootstrap(per, test['res_base'], test['qids'], k)
        cis.append(f'{d:+.4f} [{lo:+.4f}, {hi:+.4f}], {p:.3f}')
    rb = f'{r}/{b}'
    L.append(f'{fam:<9}{"-" if best is None else str(best):>6}{tr["R@5"]:>10.4f}{m["R@5"]:>10.4f}{m["R@10"]:>8.4f}'
             f'{m["MRR@10"]:>8.4f}{m["NDCG@10"]:>9.4f}{rb:>10}{cis[0]:>34}{cis[1]:>34}')
    with open(args.out_dir / f'rankings_{args.test_split}_{fam}.jsonl', 'w', encoding='utf-8') as f:
        for q in test['qids']:
            f.write(json.dumps({'query_id': q, 'ranked_ids': C.apply_order(test['base'][q], fn(test, q, best))}) + '\n')
L.append('(tune R@5 is in-sample on the tuning split; all test columns use parameters fixed before seeing the test split)')
summary = '\n'.join(L)
print(summary)
(args.out_dir / 'summary.txt').write_text(summary + '\n', encoding='utf-8')
