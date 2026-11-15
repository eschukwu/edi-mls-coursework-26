"""Pilot: rerank enc_a top-N candidates with a cross-encoder and compare retrieval metrics with the baseline."""
import argparse, csv, json, statistics, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # .../rag
sys.path.insert(0, str(ROOT))
from src.data import CourseData                         # supplied
from src.encoder import LocalEncoder                    # supplied
from src.metrics import recall_at_k, mrr_at_k, ndcg_at_k  # supplied

ap = argparse.ArgumentParser()
ap.add_argument('--split', default='practice')
ap.add_argument('--transcript-cache', type=Path, default=ROOT / '.cache/practice_transcripts.jsonl')
ap.add_argument('--candidates', type=int, nargs='+', default=[20, 50, 100])
ap.add_argument('--model', default='cross-encoder/ms-marco-MiniLM-L-6-v2')
ap.add_argument('--device', default=None)
ap.add_argument('--out-dir', type=Path, required=True)
args = ap.parse_args()
args.out_dir.mkdir(parents=True, exist_ok=True)

data_dir = ROOT / 'data/rag_corpus'
data = CourseData(data_dir)
qrels = data.load_qrels(args.split)
trans = {}
for line in open(args.transcript_cache, encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        trans[row['query_id']] = row['transcript']
qids = [q for q in trans if q in qrels]

emb = np.load(data_dir / 'embeddings/corpus_enc_a.npy').astype(np.float32)
ids = json.loads((data_dir / 'embeddings/corpus_enc_a_ids.json').read_text(encoding='utf-8'))
enc = LocalEncoder(ROOT / 'models/enc_a', device=args.device)
Q = enc.encode_many([trans[q] for q in qids])
scores = Q @ emb.T
nmax = max(args.candidates + [100])
top = np.argsort(-scores, axis=1)[:, :nmax]
base = {q: [ids[j] for j in top[i]] for i, q in enumerate(qids)}

def metrics(ranked, rel):
    return {'R@5': recall_at_k(ranked, rel, 5), 'R@10': recall_at_k(ranked, rel, 10),
            'MRR@10': mrr_at_k(ranked, rel, 10), 'NDCG@10': ndcg_at_k(ranked, rel, 10)}

def mean_of(per_query):
    return {m: statistics.mean(r[m] for r in per_query.values()) for m in ['R@5', 'R@10', 'MRR@10', 'NDCG@10']}

results = {'baseline': {q: metrics(base[q], qrels[q]) for q in qids}}
timing = {}

from sentence_transformers import CrossEncoder
t0 = time.perf_counter()
ce = CrossEncoder(args.model, device=args.device)
ce.predict([('warm up', 'warm up')])
load_s = time.perf_counter() - t0

for n in args.candidates:
    per_q, lat = {}, []
    for q in qids:
        cand = base[q][:n]
        t = time.perf_counter()
        s = ce.predict([(trans[q], data.record_text(r)) for r in cand], batch_size=64)
        lat.append((time.perf_counter() - t) * 1000)
        reranked = [cand[i] for i in np.argsort(-np.asarray(s))]
        per_q[q] = metrics(reranked, qrels[q])
    results[f'rerank_top{n}'] = per_q
    timing[f'rerank_top{n}'] = lat

lines = [f'queries: {len(qids)}   reranker: {args.model}   device: {ce.device}   model load + warm-up: {load_s:.1f} s',
         'sanity check: baseline should equal Step 5 (R@5 0.4213, R@10 0.4796, MRR@10 0.4887, NDCG@10 0.4205)', '',
         f'{"config":<16}{"R@5":>8}{"R@10":>8}{"MRR@10":>8}{"NDCG@10":>9}{"rescued":>9}{"ms/query (median)":>19}']
base_fail = {q for q in qids if results['baseline'][q]['R@10'] == 0}
for name, per_q in results.items():
    m = mean_of(per_q)
    rescued = sum(per_q[q]['R@10'] > 0 for q in base_fail) if name != 'baseline' else 0
    ms = f'{statistics.median(timing[name]):.0f}' if name in timing else '-'
    lines.append(f'{name:<16}{m["R@5"]:>8.4f}{m["R@10"]:>8.4f}{m["MRR@10"]:>8.4f}{m["NDCG@10"]:>9.4f}'
                 f'{f"{rescued}/{len(base_fail)}":>9}{ms:>19}')
summary = '\n'.join(lines)
print(summary)
(args.out_dir / 'summary.txt').write_text(summary + '\n', encoding='utf-8')

with open(args.out_dir / 'per_query.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['query_id'] + [f'{name}_R@10' for name in results] + ['transcript'])
    for q in qids:
        w.writerow([q] + [results[name][q]['R@10'] for name in results] + [trans[q]])