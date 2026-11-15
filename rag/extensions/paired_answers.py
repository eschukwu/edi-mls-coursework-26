"""Per-query paired comparison of two answer_judge_per_query.jsonl files (e.g. baseline vs RRF),
split by whether retrieval (R@5) got better or worse. Reads only small JSON files: safe on the login node."""
import argparse, json, random, statistics
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--a', type=Path, required=True, help='answer_judge_per_query.jsonl (baseline)')
ap.add_argument('--b', type=Path, required=True, help='answer_judge_per_query.jsonl (new method)')
ap.add_argument('--qids', type=Path, required=True, help='qids file from r5_changed.py (R@5-up first, then down)')
ap.add_argument('--n-up', type=int, required=True, help='how many of the first qids had R@5 up')
ap.add_argument('--output', type=Path, default=None, help='optional per-query csv')
args = ap.parse_args()

def flat(d, pre=''):
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(flat(v, pre + k + '.'))
        else:
            out[pre + k] = v
    return out

def num(v):
    if isinstance(v, list):
        v = [x for x in v if isinstance(x, (int, float))]
        return statistics.mean(v) if v else None
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

def load(p):
    rows = {}
    for line in open(p, encoding='utf-8'):
        if not line.strip():
            continue
        r = flat(json.loads(line))
        rows.setdefault(r['query_id'], []).append(r)
    return rows

A, B = load(args.a), load(args.b)
keys = list(next(iter(A.values()))[0].keys())
def find(word):
    ks = [k for k in keys if word in k.lower() and num(next(iter(A.values()))[0][k]) is not None]
    return ks[0] if ks else None
cols = {'score': find('normalised') or find('normalized'), 'correct': find('correct'),
        'ground': find('ground'), 'complete': find('complete')}
if not cols['score']:
    raise SystemExit(f'could not find a normalised score field; fields are: {keys}')
print('fields used:', cols)

def val(rows, q, k):
    vs = [num(r[cols[k]]) for r in rows[q] if cols[k] and num(r.get(cols[k])) is not None]
    return statistics.mean(vs) if vs else None

qids = [l.strip() for l in open(args.qids, encoding='utf-8') if l.strip()]
groups = {'R@5 up': qids[:args.n_up], 'R@5 down': qids[args.n_up:], 'all': qids}

print(f'\n{"group":<10}{"n":>4}{"A score":>9}{"B score":>9}{"diff":>8}{"B better":>10}{"B worse":>9}{"same":>6}   diff in correct / ground / complete')
for name, qs in groups.items():
    qs = [q for q in qs if q in A and q in B]
    d = [val(B, q, 'score') - val(A, q, 'score') for q in qs]
    extra = []
    for k in ['correct', 'ground', 'complete']:
        if cols[k]:
            extra.append(f'{statistics.mean(val(B, q, k) - val(A, q, k) for q in qs):+.2f}')
    print(f'{name:<10}{len(qs):>4}{statistics.mean(val(A, q, "score") for q in qs):>9.3f}'
          f'{statistics.mean(val(B, q, "score") for q in qs):>9.3f}{statistics.mean(d):>+8.3f}'
          f'{sum(x > 0 for x in d):>10}{sum(x < 0 for x in d):>9}{sum(x == 0 for x in d):>6}   {" / ".join(extra)}')

qs = [q for q in qids if q in A and q in B]
d = [val(B, q, 'score') - val(A, q, 'score') for q in qs]
rng = random.Random(0)
bs = sorted(statistics.mean(rng.choice(d) for _ in d) for _ in range(10000))
p = min(1.0, 2 * min(sum(x <= 0 for x in bs), sum(x >= 0 for x in bs)) / len(bs))
print(f'\nall {len(qs)} queries: mean diff {statistics.mean(d):+.3f}, bootstrap 95% CI [{bs[249]:+.3f}, {bs[9749]:+.3f}], p = {p:.3f}')

if args.output:
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write('query_id,retrieval,score_a,score_b,diff\n')
        for i, q in enumerate(qs):
            f.write(f'{q},{"up" if q in groups["R@5 up"] else "down"},{val(A, q, "score"):.4f},{val(B, q, "score"):.4f},{d[i]:+.4f}\n')
    print('per-query table ->', args.output)
