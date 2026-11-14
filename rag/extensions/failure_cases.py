"""Write a readable case file for manual failure analysis: queries rescued or broken by pure reranking and by RRF,
with the transcript, where the gold record ranks under each ordering, the gold text, and the record that took the
top slot. Reads saved reranker scores (fusion_eval.py output); no encoder, no reranker, no ELM."""
import argparse
from pathlib import Path

import common as C

ap = argparse.ArgumentParser()
ap.add_argument('--ce-scores', type=Path, required=True, help='ce_scores.jsonl from fusion_eval.py (enc_a top-N + scores)')
ap.add_argument('--split', default='practice')
ap.add_argument('--transcript-cache', type=Path, default=C.TRANSCRIPTS)
ap.add_argument('--rrf-c', type=int, default=0, help='RRF parameter (0 = value chosen on all of practice)')
ap.add_argument('--chars', type=int, default=300, help='characters of record text to show')
ap.add_argument('--output', type=Path, required=True, help='markdown file to write')
args = ap.parse_args()
if args.output.exists():
    ap.error('output exists; choose a new filename')

data = C.CourseData(C.DATA_DIR)
qrels = data.load_qrels(args.split)
trans = C.load_transcripts(args.transcript_cache)
rows = {r['query_id']: r for r in C.load_jsonl(args.ce_scores)}
qids = [q for q in rows if q in qrels and q in trans]

order = {}
for q in qids:
    cand, ce = rows[q]['cand_ids'], rows[q]['ce_scores']
    order[q] = {'enc_a': cand,
                'rerank': C.apply_order(cand, C.order_rerank(ce)),
                'rrf': C.apply_order(cand, C.order_rrf(ce, args.rrf_c))}

def gold_rank(ranked, rel):
    return next((i + 1 for i, d in enumerate(ranked) if d in set(rel)), None)

def hit10(ranked, rel):
    return gold_rank(ranked[:10], rel) is not None

def snippet(rid):
    t = ' '.join(data.record_text(rid).split())
    return t[:args.chars] + ('…' if len(t) > args.chars else '')

groups = {}
for m in ['rerank', 'rrf']:
    groups[f'{m}: broken (enc_a hit@10 -> miss)'] = [q for q in qids if hit10(order[q]['enc_a'], qrels[q]) and not hit10(order[q][m], qrels[q])]
    groups[f'{m}: rescued (enc_a miss@10 -> hit)'] = [q for q in qids if not hit10(order[q]['enc_a'], qrels[q]) and hit10(order[q][m], qrels[q])]

N = len(rows[qids[0]]['cand_ids'])
out = [f'# Failure cases ({args.split}, enc_a top-{N}, RRF c={args.rrf_c})', '',
       'For each case fill in **category** (e.g. wording mismatch / name or acronym / ASR form / vague query / '
       'near-duplicate docs / bad gold) and a one-line **why**.', '',
       '| group | n |', '| --- | --- |'] + [f'| {g} | {len(qs)} |' for g, qs in groups.items()] + ['']
for g, qs in groups.items():
    out += [f'## {g}', '']
    for q in qs:
        rel = qrels[q]
        ranks = {m: gold_rank(order[q][m], rel) for m in ['enc_a', 'rerank', 'rrf']}
        gold = next((d for d in order[q]['enc_a'] if d in set(rel)), None) or next(iter(rel))
        m = g.split(':')[0]
        top = order[q][m][0]
        out += [f'### {q}', f'- transcript: "{trans[q]}"',
                f'- gold rank (top-{N}): enc_a {ranks["enc_a"] or ">N"} | rerank {ranks["rerank"] or ">N"} | rrf {ranks["rrf"] or ">N"}',
                f'- gold `{gold}`: {snippet(gold)}',
                f'- {m} top-1 `{top}`{" (gold)" if top in set(rel) else ""}: {snippet(top)}',
                '- category: ', '- why: ', '']
args.output.parent.mkdir(parents=True, exist_ok=True)
args.output.write_text('\n'.join(out), encoding='utf-8')
print('\n'.join(f'{g}: {len(qs)}' for g, qs in groups.items()), f'\n-> {args.output}')
