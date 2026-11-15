"""For each query, find the rank of every gold document in the full exact enc_a ranking."""
import argparse, csv, json, statistics, sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # .../rag
sys.path.insert(0, str(ROOT))
from src.encoder import LocalEncoder  # supplied by the course

ap = argparse.ArgumentParser()
ap.add_argument('--split', default='practice')
ap.add_argument('--transcript-cache', type=Path, default=ROOT / '.cache/practice_transcripts.jsonl')
ap.add_argument('--device', default=None)
ap.add_argument('--out-dir', type=Path, required=True)
args = ap.parse_args()
args.out_dir.mkdir(parents=True, exist_ok=True)

data_dir = ROOT / 'data/rag_corpus'
emb = np.load(data_dir / 'embeddings/corpus_enc_a.npy').astype(np.float32)
ids = json.loads((data_dir / 'embeddings/corpus_enc_a_ids.json').read_text(encoding='utf-8'))
pos = {rid: i for i, rid in enumerate(ids)}

trans = {}
for line in open(args.transcript_cache, encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        trans[row['query_id']] = row['transcript']

gold = defaultdict(set)
for row in csv.DictReader(open(data_dir / f'qrels_{args.split}.tsv', encoding='utf-8-sig'), delimiter='\t'):
    if float(row.get('score', 1)) > 0:
        gold[row['query_id']].add(row['record_id'])

qids = [q for q in trans if q in gold]
enc = LocalEncoder(ROOT / 'models/enc_a', device=args.device)
Q = enc.encode_many([trans[q] for q in qids])   # normalised, as in the baseline
scores = Q @ emb.T                              # cosine similarity, queries x corpus

rows = []
for i, q in enumerate(qids):
    s = scores[i]
    ranks = sorted(int((s > s[pos[r]]).sum()) + 1 for r in gold[q])
    rows.append({'query_id': q, 'n_gold': len(ranks), 'best_rank': ranks[0], 'worst_rank': ranks[-1],
                 'ranks': ';'.join(map(str, ranks)),
                 'recall_at_10': sum(r <= 10 for r in ranks) / len(ranks),
                 'transcript': trans[q]})

with open(args.out_dir / 'gold_ranks.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

lines = [f'queries: {len(rows)}',
         f'sanity check, mean Recall@10 (Step 5 official: 0.4796): {statistics.mean(r["recall_at_10"] for r in rows):.4f}']
fails = [r for r in rows if r['recall_at_10'] == 0]
lines.append(f'\nQueries with Recall@10 = 0: {len(fails)}. Where is their BEST-ranked gold doc?')
for lo, hi in [(11, 20), (21, 50), (51, 100), (101, 1000), (1001, 10**9)]:
    n = sum(lo <= r['best_rank'] <= hi for r in fails)
    label = f'{lo}-{hi}' if hi < 10**9 else f'>{lo - 1}'
    lines.append(f'  rank {label:>9}: {n:3d} queries ({n / len(fails):.0%})')
summary = '\n'.join(lines)
print(summary)
(args.out_dir / 'summary.txt').write_text(summary + '\n', encoding='utf-8')