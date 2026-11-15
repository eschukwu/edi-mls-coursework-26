"""List queries whose Recall@5 differs between two rankings files (e.g. baseline vs RRF), for targeted answer checks."""
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # .../rag
sys.path.insert(0, str(ROOT))
from src.data import CourseData        # supplied
from src.metrics import recall_at_k    # supplied

ap = argparse.ArgumentParser()
ap.add_argument('--a', type=Path, required=True, help='rankings jsonl (e.g. baseline)')
ap.add_argument('--b', type=Path, required=True, help='rankings jsonl (e.g. rrf)')
ap.add_argument('--split', default='practice')
ap.add_argument('--k', type=int, default=5)
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()

qrels = CourseData(ROOT / 'data/rag_corpus').load_qrels(args.split)
load = lambda p: {r['query_id']: r['ranked_ids'] for r in map(json.loads, open(p, encoding='utf-8'))}
A, B = load(args.a), load(args.b)
up, down = [], []
for q in sorted(A):
    if q in B and q in qrels:
        ra, rb = recall_at_k(A[q], qrels[q], args.k), recall_at_k(B[q], qrels[q], args.k)
        (up if rb > ra else down if rb < ra else []).append(q)
args.output.write_text('\n'.join(up + down) + '\n', encoding='utf-8')
print(f'R@{args.k}: b better on {len(up)}, worse on {len(down)} -> {args.output}')
