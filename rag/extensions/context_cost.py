"""Evidence coverage and prompt size vs retrieval depth k (no ELM). Also saves enc_a top-N rankings for reuse."""
import argparse, csv, json, statistics, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]  # .../rag
sys.path.insert(0, str(ROOT))
from src.data import CourseData                       # supplied
from src.encoder import LocalEncoder                  # supplied
from src.context_builder import SimpleContextBuilder  # supplied: builds the exact baseline prompt
from src.metrics import recall_at_k                   # supplied

ap = argparse.ArgumentParser()
ap.add_argument('--split', default='practice')
ap.add_argument('--transcript-cache', type=Path, default=ROOT / '.cache/practice_transcripts.jsonl')
ap.add_argument('--ks', type=int, nargs='+', default=[5, 10, 20])
ap.add_argument('--save-top', type=int, default=100)
ap.add_argument('--device', default=None)
ap.add_argument('--out-dir', type=Path, required=True)
args = ap.parse_args()
args.out_dir.mkdir(parents=True, exist_ok=True)

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
top = np.argsort(-scores, axis=1)[:, :args.save_top]

with open(args.out_dir / 'rankings.jsonl', 'w', encoding='utf-8') as f:
    for i, q in enumerate(qids):
        f.write(json.dumps({'query_id': q, 'ranked_ids': [ids[j] for j in top[i]],
                            'scores': [round(float(scores[i, j]), 6) for j in top[i]]}) + '\n')
base = {q: [ids[j] for j in top[i]] for i, q in enumerate(qids)}

builder = SimpleContextBuilder()
rows = []
for k in args.ks:
    for q in qids:
        ranked = base[q][:k]
        gold_pos = [p for p, r in enumerate(ranked, start=1) if r in qrels[q]]
        prompt = builder.build(trans[q], ranked, data)['prompt']
        rows.append({'query_id': q, 'k': k, 'recall': recall_at_k(ranked, qrels[q], k),
                     'hit': int(bool(gold_pos)), 'first_gold_pos': gold_pos[0] if gold_pos else '',
                     'prompt_chars': len(prompt), 'prompt_words': len(prompt.split())})

with open(args.out_dir / 'per_query.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)

lines = [f'queries: {len(qids)}   sanity check: Recall@5/10/20 should be 0.4213 / 0.4796 / 0.5785 (Step 5)', '',
         f'{"k":>3}{"Recall@k":>10}{"hit@k":>8}{"1st gold pos (median)":>23}'
         f'{"chars mean":>12}{"chars median":>14}{"chars p90":>11}{"words mean":>12}']
for k in args.ks:
    r = [x for x in rows if x['k'] == k]
    chars = [x['prompt_chars'] for x in r]
    pos = [x['first_gold_pos'] for x in r if x['first_gold_pos'] != '']
    lines.append(f'{k:>3}{statistics.mean(x["recall"] for x in r):>10.4f}'
                 f'{statistics.mean(x["hit"] for x in r):>8.3f}'
                 f'{(statistics.median(pos) if pos else 0):>23}'
                 f'{statistics.mean(chars):>12.0f}{statistics.median(chars):>14.0f}'
                 f'{statistics.quantiles(chars, n=10)[-1]:>11.0f}'
                 f'{statistics.mean(x["prompt_words"] for x in r):>12.0f}')
lines.append('\nhit@k = share of queries with at least one gold doc in the context.')
lines.append('Token counts are not computed (the ELM tokenizer is not available); roughly, 1 token ≈ 4 characters of English.')
summary = '\n'.join(lines)
print(summary)
(args.out_dir / 'summary.txt').write_text(summary + '\n', encoding='utf-8')