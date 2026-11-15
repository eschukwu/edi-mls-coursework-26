"""Direct test of the core claim "combine (RRF) beats replace (pure rerank)": paired comparison of RRF and pure
reranking on practice (out-of-fold RRF parameter, same 2-fold split as fusion_followup.py) and on held-out dev
(rankings saved by heldout_eval.py). Reports metric differences with paired bootstrap CIs, and per-query wins and
losses on hit@5 / hit@10 with an exact sign test. No encoder, reranker or ELM calls."""
import argparse, math
from pathlib import Path

import common as C

ap = argparse.ArgumentParser()
ap.add_argument('--practice-ce', type=Path, required=True, help='ce_scores.jsonl from fusion_eval.py (practice)')
ap.add_argument('--dev-dir', type=Path, required=True, help='heldout_eval.py out-dir with rankings_dev_rerank/rrf.jsonl')
ap.add_argument('--dev-enc', type=Path, required=True, help='enc_rankings.py output for dev (baseline order)')
ap.add_argument('--rrf-c', type=int, nargs='+', default=[0, 1, 2, 3, 5, 10, 20, 30, 60, 100])
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()
if args.output.exists():
    ap.error('output exists; choose a new filename')

data = C.CourseData(C.DATA_DIR)

def sign_test(wins, losses):
    """exact two-sided binomial test, ties excluded"""
    n, k = wins + losses, min(wins, losses)
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)

def hit(ranked, rel, k):
    return any(d in set(rel) for d in ranked[:k])

def compare(name, qrels, qids, base, rerank, rrf, L):
    M = {m: {q: C.metrics(r[q], qrels[q]) for q in qids} for m, r in [('base', base), ('rerank', rerank), ('rrf', rrf)]}
    mean = {m: C.mean_of(M[m], qids) for m in M}
    L += [f'== {name}: {len(qids)} queries ==',
          f'{"":<10}' + ''.join(f'{k:>9}' for k in C.METRICS) + f'{"rescued":>9}{"broken":>8}']
    for m in ['base', 'rerank', 'rrf']:
        rb = C.churn(M[m], M['base'], qids) if m != 'base' else ('-', '-')
        L.append(f'{m:<10}' + ''.join(f'{mean[m][k]:>9.4f}' for k in C.METRICS) + f'{rb[0]:>9}{rb[1]:>8}')
    L += ['', 'RRF minus pure rerank (paired bootstrap over queries, 10,000 resamples):']
    for k in C.METRICS:
        d, lo, hi, p = C.paired_bootstrap(M['rrf'], M['rerank'], qids, k)
        L.append(f'  {k:<8}{d:+.4f}  95% CI [{lo:+.4f}, {hi:+.4f}]  p = {p:.3f}')
    L += ['', 'per-query hits (RRF vs pure rerank; exact sign test, ties excluded):']
    for k in (5, 10):
        w = sum(hit(rrf[q], qrels[q], k) and not hit(rerank[q], qrels[q], k) for q in qids)
        l = sum(hit(rerank[q], qrels[q], k) and not hit(rrf[q], qrels[q], k) for q in qids)
        L.append(f'  hit@{k:<3} RRF only {w:>3} | rerank only {l:>3} | sign test p = {sign_test(w, l):.3f}')
    L.append('')

L = []
# practice: rebuild orders from saved reranker scores; RRF parameter chosen out-of-fold
qrels = data.load_qrels('practice')
rows = {r['query_id']: r for r in C.load_jsonl(args.practice_ce)}
qids = [q for q in rows if q in qrels]
base = {q: rows[q]['cand_ids'] for q in qids}
rerank = {q: C.apply_order(base[q], C.order_rerank(rows[q]['ce_scores'])) for q in qids}
per_c = {c: {q: C.metrics(C.apply_order(base[q], C.order_rrf(rows[q]['ce_scores'], c)), qrels[q]) for q in qids}
         for c in args.rrf_c}
_, chosen = C.two_fold_oof(per_c, qids)
order = sorted(qids); import random; random.Random(0).shuffle(order); h = len(order) // 2
fold_c = {q: chosen[1] for q in order[:h]}; fold_c.update({q: chosen[0] for q in order[h:]})  # each half uses c chosen on the other
rrf = {q: C.apply_order(base[q], C.order_rrf(rows[q]['ce_scores'], fold_c[q])) for q in qids}
L.append(f'practice RRF c chosen out-of-fold: {chosen} (fold 1, fold 2)')
compare('practice (out-of-fold)', qrels, qids, base, rerank, rrf, L)

# dev: parameters fixed on practice, rankings saved by heldout_eval.py
qrels = data.load_qrels('dev')
load = lambda p: {r['query_id']: r['ranked_ids'] for r in C.load_jsonl(p)}
base, rerank, rrf = load(args.dev_enc), load(args.dev_dir / 'rankings_dev_rerank.jsonl'), load(args.dev_dir / 'rankings_dev_rrf.jsonl')
qids = [q for q in rrf if q in qrels and q in rerank and q in base]
compare('dev (held out)', qrels, qids, base, rerank, rrf, L)

summary = '\n'.join(L)
print(summary)
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text(summary + '\n', encoding='utf-8')
