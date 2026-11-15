"""Generate answers from saved enc_a rankings and cached transcripts (no ASR, no encoder) for a chosen k.
Output rows match generate_answers.py, so the supplied evaluate_answers.py can judge them."""
import argparse, json, random, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # .../rag
sys.path.insert(0, str(ROOT))
from src.data import CourseData                       # supplied
from src.context_builder import SimpleContextBuilder  # supplied
from src.generator import ELMGenerator                # supplied (reads rag/.env)

ap = argparse.ArgumentParser()
ap.add_argument('--rankings', type=Path, required=True, help='rankings.jsonl from context_cost.py')
ap.add_argument('--transcript-cache', type=Path, default=ROOT / '.cache/practice_transcripts.jsonl')
ap.add_argument('--split', default='practice')
ap.add_argument('--k', type=int, required=True)
ap.add_argument('--n', type=int, default=20, help='number of queries (random sample, fixed seed)')
ap.add_argument('--seed', type=int, default=0)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--qids', type=Path, default=None, help='file with one query_id per line; sample only from these')
args = ap.parse_args()
if args.output.exists():
    ap.error('Output exists; choose a new filename to preserve prior results')

rankings = {}
for line in open(args.rankings, encoding='utf-8'):
    row = json.loads(line)
    rankings[row['query_id']] = row['ranked_ids']
trans = {}
for line in open(args.transcript_cache, encoding='utf-8'):
    if line.strip():
        row = json.loads(line)
        trans[row['query_id']] = row['transcript']

if args.qids:
    wanted = {l.strip() for l in open(args.qids, encoding='utf-8') if l.strip()}
    qids = sorted(q for q in rankings if q in trans and q in wanted)
else:
    qids = sorted(q for q in rankings if q in trans)
random.Random(args.seed).shuffle(qids)
qids = qids[:args.n]

data = CourseData(ROOT / 'data/rag_corpus')
builder = SimpleContextBuilder()
gen = ELMGenerator()

times = []
args.output.parent.mkdir(parents=True, exist_ok=True)
with args.output.open('x', encoding='utf-8') as f:
    for i, q in enumerate(qids, start=1):
        ranked = rankings[q][:args.k]
        prompt = builder.build(trans[q], ranked, data)['prompt']
        result = gen.generate(prompt)
        times.append(result['latency_ms'])
        f.write(json.dumps({'query_id': q, 'split': args.split, 'transcript': trans[q],
                            'answer': result['answer'], 'retrieved_record_ids': ranked, 'k': args.k,
                            'prompt_chars': len(prompt), 'timing': {'generation_ms': result['latency_ms']}},
                           ensure_ascii=False) + '\n')
        f.flush()
        print(f'[{i:>3}/{len(qids)}] {q}  k={args.k}  prompt={len(prompt)} chars  gen={result["latency_ms"]:.0f} ms')

print(f'\nk={args.k}: {len(times)} answers, generation ms mean {statistics.mean(times):.0f}, median {statistics.median(times):.0f}')