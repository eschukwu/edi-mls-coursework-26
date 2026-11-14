"""Encode a split's cached transcripts with enc_a and save the exact-search top-K rankings (ids + cosine scores),
so later experiments can reuse them without re-encoding. Prints the baseline retrieval metrics as a check."""
import argparse, json
from pathlib import Path

import numpy as np

import common as C
from src.encoder import LocalEncoder  # supplied

ap = argparse.ArgumentParser()
ap.add_argument('--split', required=True)
ap.add_argument('--transcript-cache', type=Path, required=True)
ap.add_argument('--device', default=None)
ap.add_argument('--depth', type=int, default=100)
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()
if args.output.exists():
    ap.error('output exists; choose a new filename')

data = C.CourseData(C.DATA_DIR)
qrels = data.load_qrels(args.split)
trans = C.load_transcripts(args.transcript_cache)
qids = [q for q in trans if q in qrels]
emb = np.load(C.DATA_DIR / 'embeddings/corpus_enc_a.npy').astype(np.float32)
ids = json.loads((C.DATA_DIR / 'embeddings/corpus_enc_a_ids.json').read_text(encoding='utf-8'))
enc = LocalEncoder(C.ROOT / 'models/enc_a', device=args.device)
Q = enc.encode_many([trans[q] for q in qids])
S = Q @ emb.T
top = np.argsort(-S, axis=1)[:, :args.depth]
args.output.parent.mkdir(parents=True, exist_ok=True)
ranked = {}
with open(args.output, 'w', encoding='utf-8') as f:
    for i, q in enumerate(qids):
        ranked[q] = [ids[j] for j in top[i]]
        f.write(json.dumps({'query_id': q, 'ranked_ids': ranked[q], 'scores': S[i, top[i]].round(6).tolist()}) + '\n')
m = C.mean_of({q: C.metrics(ranked[q], qrels[q]) for q in qids}, qids)
print(f'{args.split}: {len(qids)} queries  ' + '  '.join(f'{k} {v:.4f}' for k, v in m.items()) + f'  -> {args.output}')
