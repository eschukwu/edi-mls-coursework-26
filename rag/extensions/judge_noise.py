"""How noisy is the LLM judge? Reads judge_cache.jsonl files written by evaluate_answers.py --repeats R
(one row per judgement) and reports, per system: within-answer spread across repeats, how often repeats agree,
and repeat-to-repeat correlation; then compares the between-system difference with judge noise, including
the difference each single repeat would have reported on its own. Reads JSON only: safe on the login node."""
import argparse, json, statistics
from collections import defaultdict
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument('--a', type=Path, required=True, help='judge_cache.jsonl of system A (baseline)')
ap.add_argument('--b', type=Path, required=True, help='judge_cache.jsonl of system B (e.g. RRF)')
ap.add_argument('--repeats', type=int, default=3)
args = ap.parse_args()
DIMS = ['correctness', 'grounding', 'completeness']

def load(path):
    per_q = defaultdict(list)
    for line in open(path, encoding='utf-8'):
        if line.strip():
            r = json.loads(line)
            res = r['result']
            per_q[r['query_id']].append(sum(res[d] for d in DIMS) / (4 * len(DIMS)))
    odd = {q: len(v) for q, v in per_q.items() if len(v) != args.repeats}
    if odd:
        print(f'note: {path.parent.name}: {len(odd)} queries without exactly {args.repeats} judgements: {odd} (using first {args.repeats})')
    return {q: v[:args.repeats] for q, v in per_q.items() if len(v) >= args.repeats}

A, B = load(args.a), load(args.b)
qids = sorted(set(A) & set(B))
print(f'queries with {args.repeats} judgements in both: {len(qids)}\n')
print(f'{"system":<10}{"mean sd":>9}{"mean range":>12}{"all equal":>11}{"r(rep1,rep2)":>14}')
for name, S in [('A', A), ('B', B)]:
    sds = [statistics.pstdev(S[q]) for q in qids]
    rng = [max(S[q]) - min(S[q]) for q in qids]
    eq = sum(len(set(S[q])) == 1 for q in qids)
    r12 = np.corrcoef([S[q][0] for q in qids], [S[q][1] for q in qids])[0, 1]
    print(f'{name:<10}{statistics.mean(sds):>9.3f}{statistics.mean(rng):>12.3f}{f"{eq}/{len(qids)}":>11}{r12:>14.2f}')

pooled = statistics.mean(statistics.variance(S[q]) for S in (A, B) for q in qids) ** 0.5
diff = [statistics.mean(B[q]) - statistics.mean(A[q]) for q in qids]
print(f'\nsingle-judgement noise (pooled sd): {pooled:.3f}; sd of a {args.repeats}-repeat mean: {pooled / args.repeats ** 0.5:.3f}')
print(f'per-query |B - A| (repeat means): mean {statistics.mean(abs(d) for d in diff):.3f}; mean B - A {statistics.mean(diff):+.3f}')
print('mean B - A if only one repeat had been run: ' +
      ', '.join(f'repeat {i + 1} {statistics.mean(B[q][i] - A[q][i] for q in qids):+.3f}' for i in range(args.repeats)))
