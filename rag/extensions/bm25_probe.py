"""Probe: how much could lexical BM25 add to enc_a? Builds a BM25 index over the corpus (pure Python/numpy,
no extra packages), evaluates BM25 alone and RRF(enc_a, BM25), and checks whether BM25 finds the gold docs
that enc_a misses entirely. Reuses saved enc_a top-100 rankings, so no encoder, no GPU and no ELM calls."""
import argparse, json, math, random, re, statistics, sys, time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # .../rag
sys.path.insert(0, str(ROOT))
from src.data import CourseData                           # supplied
from src.metrics import recall_at_k, mrr_at_k, ndcg_at_k  # supplied

ap = argparse.ArgumentParser()
ap.add_argument('--enc-rankings', type=Path, required=True, help='enc_a top-100 rankings.jsonl (query_id, ranked_ids)')
ap.add_argument('--split', default='practice')
ap.add_argument('--transcript-cache', type=Path, default=ROOT / '.cache/practice_transcripts.jsonl')
ap.add_argument('--k1', type=float, default=1.2)
ap.add_argument('--b', type=float, default=0.75)
ap.add_argument('--depth', type=int, default=100, help='list depth used for fusion')
ap.add_argument('--select-metric', default='R@5')
ap.add_argument('--out-dir', type=Path, required=True)
args = ap.parse_args()
if (args.out_dir / 'summary.txt').exists():
    ap.error('out-dir already has results; choose a new folder')
args.out_dir.mkdir(parents=True, exist_ok=True)

STOP = set('a an the and or of to in on for with by at from as is are was were be been it its this that these those '
           'i you he she we they me my your our their what which who whom how why when where do does did can could '
           'would should will shall may might must not no so if than then there here about into over under up down '
           'out just also any some such very more most other only own same too s t'.split())
def tok(text):
    return [w for w in re.findall(r'[a-z0-9]+', text.lower()) if w not in STOP]

data_dir = ROOT / 'data/rag_corpus'
data = CourseData(data_dir)
qrels = data.load_qrels(args.split)
ids = json.loads((data_dir / 'embeddings/corpus_enc_a_ids.json').read_text(encoding='utf-8'))
trans = {}
for line in open(args.transcript_cache, encoding='utf-8'):
    if line.strip():
        r = json.loads(line); trans[r['query_id']] = r['transcript']
enc = {}
for line in open(args.enc_rankings, encoding='utf-8'):
    r = json.loads(line); enc[r['query_id']] = r['ranked_ids'][:args.depth]
qids = [q for q in trans if q in qrels and q in enc]

# ---- build BM25 index (inverted index: term -> doc indices, term frequencies) ----
t0 = time.perf_counter()
post_d, post_tf = defaultdict(list), defaultdict(list)
dl = np.zeros(len(ids), dtype=np.float32)
for i, rid in enumerate(ids):
    toks = tok(data.record_text(rid))
    dl[i] = len(toks)
    for w, c in Counter(toks).items():
        post_d[w].append(i); post_tf[w].append(c)
post = {w: (np.asarray(post_d[w], dtype=np.int32), np.asarray(post_tf[w], dtype=np.float32)) for w in post_d}
del post_d, post_tf
avgdl = float(dl.mean())
idf = {w: math.log(1 + (len(ids) - len(d) + 0.5) / (len(d) + 0.5)) for w, (d, _) in post.items()}
norm = args.k1 * (1 - args.b + args.b * dl / avgdl)
build_s = time.perf_counter() - t0
index_mb = sum(d.nbytes + t.nbytes for d, t in post.values()) / 1e6

def bm25(query, depth):
    s = np.zeros(len(ids), dtype=np.float32)
    for w in set(tok(query)):
        if w in post:
            d, tf = post[w]
            s[d] += idf[w] * tf * (args.k1 + 1) / (tf + norm[d])
    top = np.argpartition(-s, depth)[:depth]
    top = top[np.argsort(-s[top], kind='stable')]
    return [ids[j] for j in top if s[j] > 0]

lat, bm = [], {}
for q in qids:
    t = time.perf_counter()
    bm[q] = bm25(trans[q], args.depth)
    lat.append((time.perf_counter() - t) * 1000)

def rrf(a, b, c):
    s = defaultdict(float)
    for lst in (a, b):
        for r, d in enumerate(lst):
            s[d] += 1 / (c + 1 + r)
    return sorted(s, key=lambda d: -s[d])

METRICS = ['R@5', 'R@10', 'R@20', 'R@100', 'MRR@10', 'NDCG@10']
def metrics(ranked, rel):
    return {'R@5': recall_at_k(ranked, rel, 5), 'R@10': recall_at_k(ranked, rel, 10),
            'R@20': recall_at_k(ranked, rel, 20), 'R@100': recall_at_k(ranked, rel, 100),
            'MRR@10': mrr_at_k(ranked, rel, 10), 'NDCG@10': ndcg_at_k(ranked, rel, 10)}
def mean_of(per_q, qs):
    return {m: statistics.mean(per_q[q][m] for q in qs) for m in METRICS}

CS = [0, 5, 10, 20, 60]
res = {'enc_a': {q: metrics(enc[q], qrels[q]) for q in qids},
       'bm25': {q: metrics(bm[q], qrels[q]) for q in qids}}
fused = {c: {q: rrf(enc[q], bm[q], c) for q in qids} for c in CS}
for c in CS:
    res[f'rrf c={c}'] = {q: metrics(fused[c][q], qrels[q]) for q in qids}

# out-of-fold RRF (c chosen on the other half, same 2-fold split as fusion_eval.py)
order = sorted(qids); random.Random(0).shuffle(order); h = len(order) // 2
oof, chosen = {}, []
for train, test in [(order[:h], order[h:]), (order[h:], order[:h])]:
    best = max(CS, key=lambda c: mean_of(res[f'rrf c={c}'], train)[args.select_metric])
    chosen.append(best)
    for q in test:
        oof[q] = res[f'rrf c={best}'][q]
res['rrf (out-of-fold)'] = oof

def hit(ranked, rel, k):
    return any(d in set(rel) for d in ranked[:k])

L = [f'queries: {len(qids)}   docs: {len(ids)}   BM25 k1={args.k1} b={args.b}   index build {build_s:.1f} s   '
     f'postings {index_mb:.0f} MB   BM25 ms/query median {statistics.median(lat):.1f}',
     'sanity: enc_a should equal Step 5 (R@5 0.4213, R@10 0.4796, R@20 0.5785, R@100 0.7699)', '',
     '== A. Retrieval quality (all queries) ==',
     f'{"method":<20}' + ''.join(f'{m:>9}' for m in METRICS)]
for name, per_q in res.items():
    m = mean_of(per_q, qids)
    L.append(f'{name:<20}' + ''.join(f'{m[k]:>9.4f}' for k in METRICS))
L.append(f'(rrf out-of-fold: c chosen by {args.select_metric} on the other half: {chosen})')

miss100 = [q for q in qids if not hit(enc[q], qrels[q], 100)]
miss10 = [q for q in qids if not hit(enc[q], qrels[q], 10)]
L += ['', '== B. Does BM25 find what enc_a misses? (counts of queries with >=1 gold doc found) ==',
      f'enc_a misses in top 100: {len(miss100)} queries -> BM25 finds gold in top 10: '
      f'{sum(hit(bm[q], qrels[q], 10) for q in miss100)}, top 20: {sum(hit(bm[q], qrels[q], 20) for q in miss100)}, '
      f'top 100: {sum(hit(bm[q], qrels[q], 100) for q in miss100)}',
      f'enc_a misses in top 10:  {len(miss10)} queries -> BM25 finds gold in top 10: '
      f'{sum(hit(bm[q], qrels[q], 10) for q in miss10)}',
      '', 'top-10 hit overlap:   both  enc_a only  bm25 only  neither']
both = sum(hit(enc[q], qrels[q], 10) and hit(bm[q], qrels[q], 10) for q in qids)
eo = sum(hit(enc[q], qrels[q], 10) and not hit(bm[q], qrels[q], 10) for q in qids)
bo = sum(hit(bm[q], qrels[q], 10) and not hit(enc[q], qrels[q], 10) for q in qids)
L.append(f'{"":<21}{both:>5}{eo:>12}{bo:>11}{len(qids) - both - eo - bo:>9}')
union100 = sum(hit(list(dict.fromkeys(enc[q] + bm[q])), qrels[q], 200) for q in qids) / len(qids)
L.append(f'any gold in union of both top-100 lists: {union100:.3f} of queries '
         f'(enc_a top 100 alone: {sum(hit(enc[q], qrels[q], 100) for q in qids) / len(qids):.3f})')

summary = '\n'.join(L)
print(summary)
(args.out_dir / 'summary.txt').write_text(summary + '\n', encoding='utf-8')
with open(args.out_dir / 'rankings_bm25.jsonl', 'w', encoding='utf-8') as f:
    for q in qids:
        f.write(json.dumps({'query_id': q, 'ranked_ids': bm[q]}) + '\n')
with open(args.out_dir / 'per_query.csv', 'w', encoding='utf-8') as f:
    f.write('query_id,enc_hit10,bm25_hit10,enc_hit100,bm25_hit100,transcript\n')
    for q in qids:
        t = trans[q].replace('"', "'")
        f.write(f'{q},{int(hit(enc[q], qrels[q], 10))},{int(hit(bm[q], qrels[q], 10))},'
                f'{int(hit(enc[q], qrels[q], 100))},{int(hit(bm[q], qrels[q], 100))},"{t}"\n')
