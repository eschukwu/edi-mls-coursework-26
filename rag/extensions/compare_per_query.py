"""Win/loss analysis: compare each config's per-query Recall@10 with the baseline column of a per_query.csv."""
import argparse, csv, statistics

ap = argparse.ArgumentParser()
ap.add_argument('--csv', required=True, help='per_query.csv written by rerank_eval.py')
ap.add_argument('--baseline', default='baseline_R@10')
ap.add_argument('--show', type=int, default=5, help='how many biggest losses/wins to print')
args = ap.parse_args()

rows = list(csv.DictReader(open(args.csv, encoding='utf-8')))
configs = [c for c in rows[0] if c.endswith('_R@10') and c != args.baseline]

for c in configs:
    d = [(float(r[c]) - float(r[args.baseline]), r) for r in rows]
    wins = [x for x in d if x[0] > 0]
    losses = [x for x in d if x[0] < 0]
    rescued = sum(float(r[args.baseline]) == 0 and float(r[c]) > 0 for _, r in d)
    broken = sum(float(r[args.baseline]) > 0 and float(r[c]) == 0 for _, r in d)
    print(f'\n=== {c} vs {args.baseline}')
    print(f'  better: {len(wins)}   worse: {len(losses)}   unchanged: {len(d) - len(wins) - len(losses)}')
    print(f'  rescued (0 -> >0): {rescued}   broken (>0 -> 0): {broken}')
    print(f'  mean change in Recall@10: {statistics.mean(x[0] for x in d):+.4f}')
    print(f'  biggest losses:')
    for delta, r in sorted(losses, key=lambda x: x[0])[:args.show]:
        print(f'    {delta:+.2f}  {r["query_id"]}  {r["transcript"]}')
    print(f'  biggest wins:')
    for delta, r in sorted(wins, key=lambda x: -x[0])[:args.show]:
        print(f'    {delta:+.2f}  {r["query_id"]}  {r["transcript"]}')