"""End-to-end timing of the full spoken-query pipeline on one machine, baseline vs RRF reranking.
Mirrors the supplied RAGPipeline.answer_audio() stage by stage (same components and timers) and inserts the
reranking stage between retrieval and context building. Per query: ASR, encoding and retrieval run once;
then the baseline top-k and the RRF top-k each go through context building and generation (2 ELM calls/query).
Also reports one-off load times and whether fresh transcripts match the cached ones."""
import argparse, json, random, statistics, time
from pathlib import Path

import common as C
from src.asr_adapter import ASRAdapter                    # supplied
from src.context_builder import SimpleContextBuilder      # supplied
from src.encoder import LocalEncoder                      # supplied
from src.generator import ELMGenerator                    # supplied
from src.retriever import ExactDenseRetriever             # supplied

ap = argparse.ArgumentParser()
ap.add_argument('--split', default='practice', choices=['practice', 'dev'])
ap.add_argument('--n', type=int, default=20, help='timed queries (random sample, fixed seed)')
ap.add_argument('--seed', type=int, default=0)
ap.add_argument('--k', type=int, default=5)
ap.add_argument('--n-cand', type=int, default=20)
ap.add_argument('--rrf-c', type=int, default=0)
ap.add_argument('--model', default='cross-encoder/ms-marco-MiniLM-L-6-v2')
ap.add_argument('--device', default=None)
ap.add_argument('--transcript-cache', type=Path, default=None, help='compare fresh transcripts with this cache')
ap.add_argument('--output', type=Path, required=True)
args = ap.parse_args()
if args.output.exists():
    ap.error('output exists; choose a new filename')

ms = lambda t0: (time.perf_counter() - t0) * 1000.0
load = {}
data = C.CourseData(C.DATA_DIR)
items = sorted(data.audio_items(args.split), key=lambda it: it['query_id'])
random.Random(args.seed).shuffle(items)
warm_item, items = items[0], items[1:args.n + 1]

t0 = time.perf_counter(); asr = ASRAdapter(); asr.prepare(); load['asr_load_ms'] = ms(t0)
t0 = time.perf_counter(); encoder = LocalEncoder(C.ROOT / 'models/enc_a', device=args.device); load['encoder_load_ms'] = ms(t0)
t0 = time.perf_counter()
retriever = ExactDenseRetriever(C.DATA_DIR / 'embeddings/corpus_enc_a.npy', C.DATA_DIR / 'embeddings/corpus_enc_a_ids.json')
load['index_load_ms'] = ms(t0)
from sentence_transformers import CrossEncoder
t0 = time.perf_counter(); ce = CrossEncoder(args.model, device=args.device); load['reranker_load_ms'] = ms(t0)
builder, gen = SimpleContextBuilder(), ELMGenerator()
cache = C.load_transcripts(args.transcript_cache) if args.transcript_cache else {}

# one untimed warm-up query: first ASR / encoder / reranker calls include one-off CUDA set-up
t0 = time.perf_counter()
wt = asr.transcribe(C.DATA_DIR / warm_item['audio_file'])
encoder.encode(wt)
ce.predict([(wt, 'warm up')])
load['warmup_query_ms'] = ms(t0)

rows = []
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open('x', encoding='utf-8') as f:
    for i, it in enumerate(items, start=1):
        q, audio = it['query_id'], C.DATA_DIR / it['audio_file']
        t0 = time.perf_counter(); transcript = asr.transcribe(audio); asr_ms = ms(t0)
        t0 = time.perf_counter(); qv = encoder.encode(transcript); emb_ms = ms(t0)
        base = retriever.retrieve(qv, k=args.k)                    # exactly what the baseline does
        deep = retriever.retrieve(qv, k=args.n_cand)                # candidates for reranking
        cand = deep['record_ids']
        t0 = time.perf_counter()
        scores = ce.predict([(transcript, data.record_text(r)) for r in cand], batch_size=64)
        reranked = C.apply_order(cand, C.order_rrf(list(scores), args.rrf_c))
        rerank_ms = ms(t0)
        row = {'query_id': q, 'transcript': transcript,
               'matches_cache': (cache.get(q) == transcript) if cache else None}
        for mode, ids, extra in [('baseline', base['record_ids'], {'retrieval_ms': base['latency_ms']}),
                                 ('rrf', reranked[:args.k], {'retrieval_ms': deep['latency_ms'], 'rerank_ms': rerank_ms})]:
            t0 = time.perf_counter(); built = builder.build(transcript, ids, data); build_ms = ms(t0)
            g = gen.generate(built['prompt'])
            timing = {'asr_ms': asr_ms, 'embedding_ms': emb_ms, **extra, 'context_ms': build_ms,
                      'generation_ms': g['latency_ms']}
            timing['end_to_end_ms'] = sum(timing.values())
            row[mode] = {'record_ids': ids, 'answer': g['answer'], 'timing': timing}
        rows.append(row)
        f.write(json.dumps(row, ensure_ascii=False) + '\n'); f.flush()
        print(f'[{i:>2}/{len(items)}] {q}  asr {asr_ms:.0f}  rerank {rerank_ms:.0f}  '
              f'e2e base {row["baseline"]["timing"]["end_to_end_ms"]:.0f} / rrf {row["rrf"]["timing"]["end_to_end_ms"]:.0f} ms', flush=True)

stages = ['asr_ms', 'embedding_ms', 'retrieval_ms', 'rerank_ms', 'context_ms', 'generation_ms', 'end_to_end_ms']
L = [f'{args.split}: {len(rows)} timed queries (seed {args.seed}) after 1 untimed warm-up; k={args.k}, '
     f'RRF over enc_a top-{args.n_cand} with {args.model.split("/")[-1]}, c={args.rrf_c}; device {ce.device}',
     'one-off costs (ms): ' + ', '.join(f'{k} {v:.0f}' for k, v in load.items())]
if cache:
    L.append(f'fresh transcripts identical to cache: {sum(r["matches_cache"] for r in rows)}/{len(rows)}')
L += ['', f'{"stage":<15}{"baseline mean":>14}{"median":>9}{"share":>7}{"rrf mean":>11}{"median":>9}{"share":>7}']
for s in stages:
    vals = {m: [r[m]['timing'].get(s, 0.0) for r in rows] for m in ['baseline', 'rrf']}
    tot = {m: statistics.mean(r[m]['timing']['end_to_end_ms'] for r in rows) for m in vals}
    cells = ''.join(f'{statistics.mean(v):>{14 if m == "baseline" else 11}.1f}{statistics.median(v):>9.1f}'
                    f'{statistics.mean(v) / tot[m]:>7.1%}' for m, v in vals.items())
    L.append(f'{s:<15}{cells}')
d = [r['rrf']['timing']['end_to_end_ms'] - r['baseline']['timing']['end_to_end_ms'] for r in rows]
L.append(f'\nrrf minus baseline end-to-end: mean {statistics.mean(d):+.0f} ms, median {statistics.median(d):+.0f} ms '
         f'(includes generation-time noise; the deterministic extra cost is rerank_ms)')
summary = '\n'.join(L)
print('\n' + summary)
args.output.with_suffix('.summary.txt').write_text(summary + '\n', encoding='utf-8')
