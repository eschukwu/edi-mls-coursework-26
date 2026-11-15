"""Per-query view of judge scores vs. whether gold docs were retrieved."""
import argparse, csv, json
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--answers', required=True, help='generate_answers.py output (.jsonl)')
ap.add_argument('--judge-dir', required=True, help='evaluate_answers.py --out-dir')
ap.add_argument('--split', default='practice')
args = ap.parse_args()

root = Path(__file__).resolve().parents[1]  # .../rag
ans = {r['query_id']: r for r in map(json.loads, open(args.answers))}
gold = {}
for row in csv.DictReader(open(root / f'data/rag_corpus/qrels_{args.split}.tsv'), delimiter='\t'):
    if float(row.get('score', 1)) > 0:
        gold.setdefault(row['query_id'], set()).add(row['record_id'])

for r in map(json.loads, open(Path(args.judge_dir) / 'answer_judge_per_query.jsonl')):
    q = r['query_id']
    hit = len(set(ans[q]['retrieved_record_ids']) & gold[q])
    print(q, '| C/G/Comp =', r['correctness'], r['grounding'], r['completeness'],
          f'| gold in top-k: {hit}/{len(gold[q])}')
    print('  transcript:', ans[q]['transcript'])
    print('  judge:', r['judge_explanations'][0][:300])
    print()