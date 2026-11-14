"""Quality vs cost of reranking: for each reranker model and candidate depth N, measure retrieval quality
(pure rerank and RRF with enc_a, RRF parameter chosen out-of-fold) and cost (latency per query,
model load time, peak GPU memory, model size). Run once per device (--device cuda / cpu). No ELM calls."""
import argparse, csv, json, statistics, time
from pathlib import Path

import numpy as np

import common as C

ap = argparse.ArgumentParser()
ap.add_argument('--rankings', type=Path, required=True, help='enc_a top-100 rankings.jsonl')
ap.add_argument('--split', default='practice')
ap.add_argument('--transcript-cache', type=Path, default=C.TRANSCRIPTS)
ap.add_argument('--models', nargs='+', default=['cross-encoder/ms-marco-MiniLM-L-6-v2',
                                                 'cross-encoder/ms-marco-MiniLM-L-12-v2'])
ap.add_argument('--n-cand', type=int, nargs='+', default=[10, 20, 30, 50])
ap.add_argument('--device', required=True, help='cuda or cpu')
ap.add_argument('--batch-size', type=int, default=64)
ap.add_argument('--rrf-c', type=int, nargs='+', default=[0, 1, 2, 3, 5, 10, 20, 30, 60, 100])
ap.add_argument('--out-dir', type=Path, required=True)
args = ap.parse_args()
if (args.out_dir / 'summary.txt').exists():
    ap.error('out-dir already has results; choose a new folder')
args.out_dir.mkdir(parents=True, exist_ok=True)

import torch
from sentence_transformers import CrossEncoder

data = C.CourseData(C.DATA_DIR)
qrels = data.load_qrels(args.split)
trans = C.load_transcripts(args.transcript_cache)
base = C.load_rankings(args.rankings)
qids = [q for q in trans if q in qrels and q in base]
nmax = max(args.n_cand)
text = {d: data.record_text(d) for q in qids for d in base[q][:nmax]}  # looked up once, outside timing
res_base = {q: C.metrics(base[q], qrels[q]) for q in qids}
cuda = args.device.startswith('cuda')
gpu_name = torch.cuda.get_device_name(0) if cuda else 'cpu'

def load(name):
    t = time.perf_counter()
    ce = CrossEncoder(name, device=args.device)
    ce.predict([('warm up', 'warm up')])
    return ce, time.perf_counter() - t

rows = []
for name in args.models:
    load(name)                       # first load may download the model; not timed
    if cuda:
        torch.cuda.empty_cache(); torch.cuda.reset_peak_memory_stats()
    ce, load_s = load(name)          # timed load from local cache
    try:
        params_m = sum(p.numel() for p in ce.model.parameters()) / 1e6
    except AttributeError:
        params_m = float('nan')
    scores = {}
    for n in sorted(args.n_cand):
        lat = []
        for q in qids:
            pairs = [(trans[q], text[d]) for d in base[q][:n]]
            t = time.perf_counter()
            s = ce.predict(pairs, batch_size=args.batch_size)
            lat.append((time.perf_counter() - t) * 1000)
            scores[(q, n)] = np.asarray(s, dtype=float)
        rerank = {q: C.metrics(C.apply_order(base[q], C.order_rerank(scores[(q, n)])), qrels[q]) for q in qids}
        per_c = {c: {q: C.metrics(C.apply_order(base[q], C.order_rrf(scores[(q, n)], c)), qrels[q]) for q in qids}
                 for c in args.rrf_c}
        rrf, chosen = C.two_fold_oof(per_c, qids)
        mr, mf = C.mean_of(rerank, qids), C.mean_of(rrf, qids)
        resc, brok = C.churn(rrf, res_base, qids)
        rows.append({'model': name.split('/')[-1], 'device': gpu_name, 'N': n,
                     'rerank_R@5': mr['R@5'], 'rerank_R@10': mr['R@10'],
                     'rrf_R@5': mf['R@5'], 'rrf_R@10': mf['R@10'], 'rrf_MRR@10': mf['MRR@10'],
                     'rrf_rescued': resc, 'rrf_broken': brok, 'rrf_c': '/'.join(map(str, chosen)),
                     'ms_median': statistics.median(lat), 'ms_p90': float(np.percentile(lat, 90)),
                     'load_s': load_s, 'peak_gpu_mb': torch.cuda.max_memory_allocated() / 1e6 if cuda else float('nan'),
                     'params_m': params_m})
        print(f'{name.split("/")[-1]}  N={n}  rrf R@5 {mf["R@5"]:.4f}  median {rows[-1]["ms_median"]:.0f} ms', flush=True)
    with open(args.out_dir / f'ce_scores_{name.split("/")[-1]}.jsonl', 'w', encoding='utf-8') as f:
        for q in qids:
            f.write(json.dumps({'query_id': q, 'cand_ids': base[q][:nmax], 'ce_scores': scores[(q, nmax)].tolist()}) + '\n')
    del ce
    if cuda:
        torch.cuda.empty_cache()

mb = C.mean_of(res_base, qids)
L = [f'queries: {len(qids)}   device: {gpu_name}   batch size {args.batch_size}   '
     f'latency = cross-encoder predict() per query (text lookup excluded); RRF c chosen out-of-fold by R@5',
     f'sanity: baseline R@5 {mb["R@5"]:.4f} R@10 {mb["R@10"]:.4f} (Step 5: 0.4213 / 0.4796)', '',
     f'{"model":<26}{"N":>4}{"rerank R@5":>11}{"R@10":>7}{"RRF R@5":>9}{"R@10":>7}{"MRR":>7}'
     f'{"resc/brok":>10}{"c":>7}{"ms med":>8}{"p90":>6}{"load s":>8}{"GPU MB":>8}{"params M":>9}']
for r in rows:
    rb = f'{r["rrf_rescued"]}/{r["rrf_broken"]}'
    L.append(f'{r["model"]:<26}{r["N"]:>4}{r["rerank_R@5"]:>11.4f}{r["rerank_R@10"]:>7.4f}{r["rrf_R@5"]:>9.4f}'
             f'{r["rrf_R@10"]:>7.4f}{r["rrf_MRR@10"]:>7.4f}{rb:>10}{r["rrf_c"]:>7}'
             f'{r["ms_median"]:>8.0f}{r["ms_p90"]:>6.0f}{r["load_s"]:>8.1f}{r["peak_gpu_mb"]:>8.0f}{r["params_m"]:>9.1f}')
summary = '\n'.join(L)
print('\n' + summary)
(args.out_dir / 'summary.txt').write_text(summary + '\n', encoding='utf-8')
with open(args.out_dir / 'results.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
