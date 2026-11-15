"""Follow-up to fusion_eval.py, reusing its saved cross-encoder scores (no encoder, no reranker, no ELM):
(1) wider parameter grids, (2) out-of-fold results over several random splits,
(3) paired bootstrap significance vs the baseline, (4) top-5 rankings for answer-quality checks."""
import argparse, json, random, statistics, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # .../rag
sys.path.insert(0, str(ROOT))
from src.data import CourseData                           # supplied
from src.metrics import recall_at_k, mrr_at_k, ndcg_at_k  # supplied

ap = argparse.ArgumentParser()
ap.add_argument('--ce-scores', type=Path, required=True, help='ce_scores.jsonl written by fusion_eval.py')
ap.add_argument('--split', default='practice')
ap.add_argument('--select-metric', default='R@5')
ap.add_argument('--seeds', type=int, default=20, help='number of random 2-fold splits')
ap.add_argument('--boot', type=int, default=10000, help='bootstrap resamples')
ap.add_argument('--out-dir', type=Path, required=True)
args = ap.parse_args()
if (args.out_dir / 'summary.txt').exists():
    ap.error('out-dir already has results; choose a new folder')
args.out_dir.mkdir(parents=True, exist_ok=True)
METRICS = ['R@5', 'R@10', 'MRR@10', 'NDCG@10']

qrels = CourseData(ROOT / 'data/rag_corpus').load_qrels(args.split)
cand, enc_s, ce_s = {}, {}, {}
for line in open(args.ce_scores, encoding='utf-8'):
    row = json.loads(line)
    q = row['query_id']
    cand[q], enc_s[q], ce_s[q] = row['cand_ids'], np.asarray(row['enc_scores']), np.asarray(row['ce_scores'])
qids = [q for q in cand if q in qrels]
N = len(cand[qids[0]])

# ---- same methods as fusion_eval.py (reorder enc_a top-N; metrics only look at the top 10) ----
def minmax(x):
    r = x.max() - x.min()
    return (x - x.min()) / r if r > 0 else np.zeros_like(x)

def by_score(q, s):
    return [cand[q][i] for i in np.argsort(-s, kind='stable')]

def fusion(q, a):
    return by_score(q, a * minmax(enc_s[q]) + (1 - a) * minmax(ce_s[q]))

def rrf(q, c):
    ce_rank = np.empty(N); ce_rank[np.argsort(-ce_s[q], kind='stable')] = np.arange(N)
    return by_score(q, 1 / (c + 1 + np.arange(N)) + 1 / (c + 1 + ce_rank))

def protect(q, m):
    rest = sorted(range(m, N), key=lambda i: -ce_s[q][i])
    return [cand[q][i] for i in list(range(m)) + rest]

FAMILIES = {
    'rerank': (lambda q, p: fusion(q, 0.0), [None]),
    'fusion': (fusion, [round(a, 1) for a in np.arange(0, 1.01, 0.1)]),
    'rrf': (rrf, [0, 1, 2, 3, 5, 10, 20, 30, 60, 100]),
    'protect': (protect, [1, 2, 3, 4, 5, 6, 8, 10]),
}

def metrics(ranked, rel):
    return {'R@5': recall_at_k(ranked, rel, 5), 'R@10': recall_at_k(ranked, rel, 10),
            'MRR@10': mrr_at_k(ranked, rel, 10), 'NDCG@10': ndcg_at_k(ranked, rel, 10)}

def mean_of(per_q, qs):
    return {m: statistics.mean(per_q[q][m] for q in qs) for m in METRICS}

base_rank = {q: cand[q] for q in qids}
res_base = {q: metrics(base_rank[q], qrels[q]) for q in qids}
rank = {(f, p): {q: fn(q, p) for q in qids} for f, (fn, ps) in FAMILIES.items() for p in ps}
res = {key: {q: metrics(r[q], qrels[q]) for q in qids} for key, r in rank.items()}

def oof_split(fam, seed):
    order = sorted(qids); random.Random(seed).shuffle(order)
    h = len(order) // 2
    per_q, chosen = {}, []
    for train, test in [(order[:h], order[h:]), (order[h:], order[:h])]:
        _, ps = FAMILIES[fam]
        best = max(ps, key=lambda p: mean_of(res[(fam, p)], train)[args.select_metric])
        chosen.append(best)
        for q in test:
            per_q[q] = (best, res[(fam, best)][q])
    return per_q, chosen

def churn(per_q):
    r = sum(res_base[q]['R@10'] == 0 and per_q[q]['R@10'] > 0 for q in qids)
    b = sum(res_base[q]['R@10'] > 0 and per_q[q]['R@10'] == 0 for q in qids)
    return r, b

rng = np.random.default_rng(0)
boot_idx = rng.integers(0, len(qids), size=(args.boot, len(qids)))

def paired(per_q, metric):
    d = np.array([per_q[q][metric] - res_base[q][metric] for q in qids])
    bs = d[boot_idx].mean(axis=1)
    lo, hi = np.percentile(bs, [2.5, 97.5])
    p = 2 * min((bs <= 0).mean(), (bs >= 0).mean())  # two-sided bootstrap p
    return d.mean(), lo, hi, min(p, 1.0), int((d > 0).sum()), int((d < 0).sum())

def w(x, n=8):
    return f'{x:>{n}.4f}'

L = [f'queries: {len(qids)}   candidates per query: {N}   parameters chosen by {args.select_metric} on one half, '
     f'tested on the other', 'sanity: baseline should equal Step 5 (R@5 0.4213, R@10 0.4796, MRR@10 0.4887, NDCG@10 0.4205)', '']

L += ['== A. Out-of-fold, seed 0 (same split as fusion_eval.py) ==',
      f'{"method":<10}{"R@5":>8}{"R@10":>8}{"MRR@10":>8}{"NDCG@10":>9}{"rescued":>9}{"broken":>8}  chosen']
m = mean_of(res_base, qids)
L.append(f'{"baseline":<10}' + ''.join(w(m[k], 9 if k == 'NDCG@10' else 8) for k in METRICS))
oof0 = {}
for fam in FAMILIES:
    pq, ch = oof_split(fam, 0)
    oof0[fam] = pq
    flat = {q: pq[q][1] for q in qids}
    m = mean_of(flat, qids); r, b = churn(flat)
    L.append(f'{fam:<10}' + ''.join(w(m[k], 9 if k == 'NDCG@10' else 8) for k in METRICS) + f'{r:>9}{b:>8}  {ch}')

L += ['', f'== B. Stability over {args.seeds} random 2-fold splits (mean ± sd of out-of-fold score; how often each param was chosen) ==']
for fam in FAMILIES:
    vals = {k: [] for k in METRICS}; picks = {}
    for s in range(args.seeds):
        pq, ch = oof_split(fam, s)
        mm = mean_of({q: pq[q][1] for q in qids}, qids)
        for k in METRICS:
            vals[k].append(mm[k])
        for p in ch:
            picks[p] = picks.get(p, 0) + 1
    sd = lambda v: statistics.stdev(v) if len(v) > 1 else 0.0
    L.append(f'{fam:<10}' + '  '.join(f'{k} {statistics.mean(vals[k]):.4f}±{sd(vals[k]):.4f}' for k in METRICS[:2])
             + '   picks: ' + ', '.join(f'{p}×{n}' for p, n in sorted(picks.items(), key=lambda t: -t[1])))

L += ['', f'== C. Paired bootstrap vs baseline (seed-0 out-of-fold, {args.boot} resamples over queries) ==',
      f'{"method":<10}{"metric":<8}{"diff":>9}{"95% CI":>22}{"p":>8}{"better":>8}{"worse":>7}']
for fam in FAMILIES:
    flat = {q: oof0[fam][q][1] for q in qids}
    for k in ['R@5', 'R@10', 'MRR@10']:
        d, lo, hi, p, nb, nw = paired(flat, k)
        L.append(f'{fam:<10}{k:<8}{d:>+9.4f}{f"[{lo:+.4f}, {hi:+.4f}]":>22}{p:>8.3f}{nb:>8}{nw:>7}')

L += ['', '== D. All parameters on all queries (in-sample, for illustration only) ==',
      f'{"method":<10}{"param":>7}{"R@5":>8}{"R@10":>8}{"MRR@10":>8}{"NDCG@10":>9}{"rescued":>9}{"broken":>8}']
for (fam, p), per_q in res.items():
    m = mean_of(per_q, qids); r, b = churn(per_q)
    L.append(f'{fam:<10}{"-" if p is None else str(p):>7}' + ''.join(w(m[k], 9 if k == 'NDCG@10' else 8) for k in METRICS)
             + f'{r:>9}{b:>8}')

# ---- rankings for answer-quality checks (gen_from_rankings.py reads query_id + ranked_ids) ----
def dump(name, ranked):
    with open(args.out_dir / f'rankings_{name}.jsonl', 'w', encoding='utf-8') as f:
        for q in qids:
            f.write(json.dumps({'query_id': q, 'ranked_ids': ranked[q]}) + '\n')

dump('baseline', base_rank)
L += ['', '== E. Rankings written (out-of-fold params, seed 0) and queries whose top-5 SET changed ==']
for fam in ['rrf', 'protect', 'fusion']:
    ranked = {q: rank[(fam, oof0[fam][q][0])][q] for q in qids}
    dump(fam, ranked)
    changed = sorted(q for q in qids if set(ranked[q][:5]) != set(base_rank[q][:5]))
    (args.out_dir / f'changed_top5_{fam}.txt').write_text('\n'.join(changed) + '\n', encoding='utf-8')
    gain = sum(res[(fam, oof0[fam][q][0])][q]['R@5'] > res_base[q]['R@5'] for q in changed)
    loss = sum(res[(fam, oof0[fam][q][0])][q]['R@5'] < res_base[q]['R@5'] for q in changed)
    L.append(f'{fam:<10} changed {len(changed):>4} queries  (R@5 up {gain}, down {loss}, same {len(changed) - gain - loss})'
             f'  -> rankings_{fam}.jsonl, changed_top5_{fam}.txt')

summary = '\n'.join(L)
print(summary)
(args.out_dir / 'summary.txt').write_text(summary + '\n', encoding='utf-8')
