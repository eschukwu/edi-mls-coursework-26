"""Compare two transcript caches of the same split (e.g. PyTorch ASR vs our CUDA kernels): exact matches,
matches after normalising case/punctuation, word error rate (WER) of B against A, and the differing examples.
Reads JSON only: safe on the login node."""
import argparse, json, re
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--a', type=Path, required=True, help='reference cache (e.g. practice_transcripts.jsonl, PyTorch)')
ap.add_argument('--b', type=Path, required=True, help='cache to compare (e.g. practice_transcripts_ours.jsonl)')
ap.add_argument('--show', type=int, default=15, help='how many differing examples to print')
ap.add_argument('--output', type=Path, default=None, help='optional csv of all differing queries')
args = ap.parse_args()

def load(p):
    return {r['query_id']: r['transcript'] for r in map(json.loads, open(p, encoding='utf-8')) if r}

def norm(t):
    return re.sub(r'[^a-z0-9 ]', ' ', t.lower()).split()

def edits(a, b):
    """word-level Levenshtein distance"""
    prev = list(range(len(b) + 1))
    for i, wa in enumerate(a, 1):
        cur = [i]
        for j, wb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (wa != wb)))
        prev = cur
    return prev[-1]

A, B = load(args.a), load(args.b)
qids = sorted(set(A) & set(B))
exact = [q for q in qids if A[q] == B[q]]
normd = [q for q in qids if norm(A[q]) == norm(B[q])]
diff = [q for q in qids if norm(A[q]) != norm(B[q])]
errs = sum(edits(norm(A[q]), norm(B[q])) for q in qids)
words = sum(len(norm(A[q])) for q in qids)
print(f'queries in both: {len(qids)} (A only {len(set(A) - set(B))}, B only {len(set(B) - set(A))})')
print(f'identical: {len(exact)}/{len(qids)}   identical after normalising case/punctuation: {len(normd)}/{len(qids)}')
print(f'WER of B vs A: {errs / max(words, 1):.4f}  ({errs} word edits over {words} words)')
if diff:
    per = sorted(((edits(norm(A[q]), norm(B[q])) / max(len(norm(A[q])), 1), q) for q in diff), reverse=True)
    print(f'\nlargest differences (showing {min(args.show, len(per))} of {len(per)}):')
    for w, q in per[:args.show]:
        print(f'- {q}  WER {w:.2f}\n    A: {A[q]}\n    B: {B[q]}')
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write('query_id,wer,a,b\n')
            for w, q in per:
                f.write(f'{q},{w:.4f},"{A[q].replace(chr(34), chr(39))}","{B[q].replace(chr(34), chr(39))}"\n')
        print(f'\nall differing queries -> {args.output}')
