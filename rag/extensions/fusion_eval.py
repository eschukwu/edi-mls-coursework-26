"""Can we keep the reranker's rescues without its breaks? Compares pure reranking, score fusion, RRF,
gating and top-m protection on enc_a's top-N. Parameters are chosen on one half of the queries and
evaluated on the other half (2-fold), so the reported numbers are out-of-fold. No ELM calls."""
import argparse, csv, json, random, statistics, sys, time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # .../rag
sys.path.insert(0, str(ROOT))
from src.data import CourseData                           # supplied
from src.encoder import LocalEncoder                      # supplied
from src.metrics import recall_at_k, mrr_at_k, ndcg_at_k  # supplied

ap = argparse.ArgumentParser()
ap.add_argument('--split', default='practice')
ap.add_argument('--transcript-cache', type=Path, default=ROOT / '.cache/practice_transcripts.jsonl')
ap.add_argument('--n-cand', type=int, default=20, help='rerank enc_a top-N')
ap.add_argument('--model', default='cross-encoder/ms-marco-MiniLM-L-6-v2')
ap.add_argument('--device', default=None)
ap.add_argument('--select-metric', default='R@5', help='metric used to choose parameters on the training half')
ap.add_argument('--seed', type=int, default=0)
ap.add_argument('--out-dir', type=Path, required=True)
args = ap.parse_args()
if (args.out_dir / 'summary.txt').exists():
    ap.error('out-dir already has results; choose a new folder')
args.out_dir.mkdir(parents=True, exist_ok=True)
N = args.n_cand
METRICS = ['R@5', 'R@10', 'MRR@10', 'NDCG@10']

# ---- same setup as rerank_eval.py ----
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
top = np.argsort(-scores, axis=1)[:, :100]
base = {q: [ids[j] for j in top[i]] for i, q in enumerate(qids)}
enc_s = {q: scores[i, top[i][:N]].astype(float) for i, q in enumerate(qids)}

# ---- cross-encoder scores for the top-N (saved for reuse) ----
from sentence_transformers import CrossEncoder
t0 = time.perf_counter()
ce = CrossEncoder(args.model, device=args.device)
ce.predict([('warm up', 'warm up')])
load_s = time.perf_counter() - t0
ce_s, lat = {}, []
with open(args.out_dir / 'ce_scores.jsonl', 'w', encoding='utf-8') as f:
    for q in qids:
        cand = base[q][:N]
        t = time.perf_counter()
        s = ce.predict([(trans[q], data.record_text(r)) for r in cand], batch_size=64)
        lat.append((time.perf_counter() - t) * 1000)
        ce_s[q] = np.asarray(s, dtype=float)
        f.write(json.dumps({'query_id': q, 'cand_ids': cand, 'enc_scores': enc_s[q].tolist(),
                            'ce_scores': ce_s[q].tolist()}) + '\n')

# ---- ranking methods: each reorders the top-N, ranks N+1..100 stay as enc_a ----
def minmax(x):
    r = x.max() - x.min()
    return (x - x.min()) / r if r > 0 else np.zeros_like(x)

def reorder(q, order):
    cand = base[q][:N]
    return [cand[i] for i in order] + base[q][N:]

def fusion(q, a):  # a = weight on enc_a; a=1 -> baseline, a=0 -> pure rerank
    s = a * minmax(enc_s[q]) + (1 - a) * minmax(ce_s[q])
    return reorder(q, np.argsort(-s, kind='stable'))

def rrf(q, c):  # reciprocal rank fusion, uses ranks only
    ce_rank = np.empty(N); ce_rank[np.argsort(-ce_s[q], kind='stable')] = np.arange(N)
    s = 1 / (c + 1 + np.arange(N)) + 1 / (c + 1 + ce_rank)
    return reorder(q, np.argsort(-s, kind='stable'))

def margin(q):  # how confident enc_a is: top-1 minus top-2 cosine
    return enc_s[q][0] - enc_s[q][1]

def gate(q, t):  # keep enc_a order when confident, otherwise pure rerank
    return base[q] if margin(q) >= t else fusion(q, 0.0)

def protect(q, m):  # keep enc_a's top-m, rerank the rest
    rest = sorted(range(m, N), key=lambda i: -ce_s[q][i])
    return reorder(q, list(range(m)) + rest)

taus = sorted(set(float(np.percentile([margin(q) for q in qids], p)) for p in range(0, 101, 10)))
FAMILIES = {
    'rerank': (lambda q, p: fusion(q, 0.0), [None]),
    'fusion': (fusion, [round(a, 1) for a in np.arange(0, 1.01, 0.1)]),
    'rrf': (rrf, [10, 30, 60]),
    'gate': (gate, taus),
    'protect': (protect, [1, 2, 3]),
}

def metrics(ranked, rel):
    return {'R@5': recall_at_k(ranked, rel, 5), 'R@10': recall_at_k(ranked, rel, 10),
            'MRR@10': mrr_at_k(ranked, rel, 10), 'NDCG@10': ndcg_at_k(ranked, rel, 10)}

def mean_of(per_q, qs):
    return {m: statistics.mean(per_q[q][m] for q in qs) for m in METRICS}

res_base = {q: metrics(base[q], qrels[q]) for q in qids}
res = {(fam, p): {q: metrics(fn(q, p), qrels[q]) for q in qids}
       for fam, (fn, params) in FAMILIES.items() for p in params}

# ---- 2-fold: choose p on one half, apply to the other half ----
order = sorted(qids); random.Random(args.seed).shuffle(order)
half = len(order) // 2
folds = [(order[:half], order[half:]), (order[half:], order[:half])]
oof, chosen = {}, {}
for fam, (fn, params) in FAMILIES.items():
    oof[fam], chosen[fam] = {}, []
    for train, test in folds:
        best = max(params, key=lambda p: mean_of(res[(fam, p)], train)[args.select_metric])
        chosen[fam].append(best)
        for q in test:
            oof[fam][q] = res[(fam, best)][q]

def churn(per_q):
    rescued = sum(res_base[q]['R@10'] == 0 and per_q[q]['R@10'] > 0 for q in qids)
    broken = sum(res_base[q]['R@10'] > 0 and per_q[q]['R@10'] == 0 for q in qids)
    return rescued, broken

def fmt(p):
    return '-' if p is None else f'{p:.4g}'

L = [f'queries: {len(qids)}   rerank top-{N}   reranker: {args.model}   device: {ce.device}   load {load_s:.1f} s   '
     f'CE ms/query median {statistics.median(lat):.0f}',
     'sanity: baseline should equal Step 5 (R@5 0.4213, R@10 0.4796, MRR@10 0.4887, NDCG@10 0.4205)', '',
     f'== A. Out-of-fold results (parameters chosen on the other half by {args.select_metric}, seed {args.seed}) ==',
     f'{"method":<10}{"R@5":>8}{"R@10":>8}{"MRR@10":>8}{"NDCG@10":>9}{"rescued":>9}{"broken":>8}  chosen (fold1, fold2)']
m = mean_of(res_base, qids)
L.append(f'{"baseline":<10}' + ''.join(f'{m[k]:>{8 if k != "NDCG@10" else 9}.4f}' for k in METRICS) + f'{"-":>9}{"-":>8}')
for fam in FAMILIES:
    m = mean_of(oof[fam], qids); r, b = churn(oof[fam])
    L.append(f'{fam:<10}' + ''.join(f'{m[k]:>{8 if k != "NDCG@10" else 9}.4f}' for k in METRICS)
             + f'{r:>9}{b:>8}  {", ".join(fmt(p) for p in chosen[fam])}')

g = res[('rerank', None)]
gold_rank = {}
for q in qids:
    rel = set(qrels[q])
    gold_rank[q] = next((i + 1 for i, d in enumerate(base[q]) if d in rel), None)
groups = {
    'broken by rerank': [q for q in qids if res_base[q]['R@10'] > 0 and g[q]['R@10'] == 0],
    'rescued by rerank': [q for q in qids if res_base[q]['R@10'] == 0 and g[q]['R@10'] > 0],
    'hit both': [q for q in qids if res_base[q]['R@10'] > 0 and g[q]['R@10'] > 0],
    'all queries': qids,
}
L += ['', '== B. Diagnosis: what do broken vs rescued queries look like under enc_a? ==',
      f'{"group":<20}{"n":>5}{"gold at rank 1":>16}{"median gold rank":>18}{"median margin":>15}']
for name, qs in groups.items():
    if not qs:
        L.append(f'{name:<20}{0:>5}'); continue
    r1 = sum(gold_rank[q] == 1 for q in qs) / len(qs)
    ranks = [gold_rank[q] if gold_rank[q] else 101 for q in qs]
    L.append(f'{name:<20}{len(qs):>5}{r1:>16.0%}{statistics.median(ranks):>18.0f}'
             f'{statistics.median(margin(q) for q in qs):>15.4f}')
L.append('(gold rank 101 = not in enc_a top 100; margin = enc_a top-1 minus top-2 cosine)')

L += ['', f'== C. All parameters on all {len(qids)} queries (in-sample, for illustration only) ==',
      f'{"method":<10}{"param":>8}{"R@5":>8}{"R@10":>8}{"MRR@10":>8}{"NDCG@10":>9}{"rescued":>9}{"broken":>8}{"reranked":>10}']
for (fam, p), per_q in res.items():
    m = mean_of(per_q, qids); r, b = churn(per_q)
    rr = sum(margin(q) < p for q in qids) / len(qids) if fam == 'gate' else (0.0 if fam == 'fusion' and p == 1.0 else 1.0)
    L.append(f'{fam:<10}{fmt(p):>8}' + ''.join(f'{m[k]:>{8 if k != "NDCG@10" else 9}.4f}' for k in METRICS)
             + f'{r:>9}{b:>8}{rr:>10.0%}')
L.append('(reranked = share of queries that need cross-encoder calls)')

summary = '\n'.join(L)
print(summary)
(args.out_dir / 'summary.txt').write_text(summary + '\n', encoding='utf-8')
with open(args.out_dir / 'per_query.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['query_id', 'enc_gold_rank', 'enc_margin', 'baseline_R@10'] + [f'{fam}_oof_R@10' for fam in FAMILIES] + ['transcript'])
    for q in qids:
        w.writerow([q, gold_rank[q] or '>100', f'{margin(q):.4f}', res_base[q]['R@10']]
                   + [oof[fam][q]['R@10'] for fam in FAMILIES] + [trans[q]])
