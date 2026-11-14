"""Join per-query Recall@10 (Step 5 output) with transcripts and qrels."""
import csv, json, re, statistics
from collections import defaultdict
from pathlib import Path

root = Path(__file__).resolve().parents[1]  # .../rag

r10 = {}
for line in open(root / 'results/step5_practice_retrieval.txt', encoding='utf-8'):
    m = re.search(r'\]\s+(q_\w+)\s+R@10=([0-9.]+)', line)
    if m:
        r10[m.group(1)] = float(m.group(2))

trans = {}
for line in open(root / '.cache/practice_transcripts.jsonl', encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        trans[row['query_id']] = row['transcript']

ngold = defaultdict(int)
for row in csv.DictReader(open(root / 'data/rag_corpus/qrels_practice.tsv', encoding='utf-8-sig'), delimiter='\t'):
    if float(row.get('score', 1)) > 0:
        ngold[row['query_id']] += 1

rows = []
for q, v in r10.items():
    t = trans.get(q, '')
    rows.append({'query_id': q, 'recall_at_10': v, 'n_gold': ngold[q],
                 'n_words': len(t.split()), 'transcript': t})

out = root / 'results/per_query_step5.csv'
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
print(f'{len(rows)} queries -> {out}')

print('\nRecall@10 distribution:')
for v in sorted({r['recall_at_10'] for r in rows}):
    print(f'  {v:.3f}: {sum(r["recall_at_10"] == v for r in rows)} queries')

print('\nMean Recall@10 by number of gold docs:')
for n in sorted({r['n_gold'] for r in rows}):
    g = [r['recall_at_10'] for r in rows if r['n_gold'] == n]
    print(f'  {n} gold doc(s): {len(g)} queries, mean {statistics.mean(g):.3f}')

print('\nMean Recall@10 by transcript length (words):')
for lo, hi, label in [(0, 8, '1-7'), (8, 12, '8-11'), (12, 16, '12-15'), (16, 10**6, '16+')]:
    g = [r['recall_at_10'] for r in rows if lo <= r['n_words'] < hi]
    if g:
        print(f'  {label} words: {len(g)} queries, mean {statistics.mean(g):.3f}')

print('\nFirst 10 queries with Recall@10 = 0:')
for r in [r for r in rows if r['recall_at_10'] == 0][:10]:
    print(f"  {r['query_id']}  gold={r['n_gold']}  {r['transcript']}")