# Experiment log

## 2026-11-12 RAG Step 3: check_setup
- commit: 6bbdfbc
- node / GPU: damnii07, RTX 2080 Ti
- result: all 6 checks PASS (24000 records, 475 audio, embeddings 24000x384)

## 2026-11-12 RAG Step 4: first single query
- command: ASR_CUDA=none python rag/scripts/run_audio_query.py --device cpu
- query: q_7e9a0f2716c017d2 (practice, first in manifest)
- settings: k=5, enc_a on CPU, exact cosine retrieval, ELM EuroLLM-22B-Instruct, temperature 0.1
- transcript: correct ("Understanding sales tax implications when purchasing items in a retail store.")
- retrieval scores: 0.870–0.877 (top-5 very close)
- answer: text supported by evidence, but mixes in seller-side content (LLC, gross sales) not relevant to a buyer's question
- timing (ms): asr 124298, embedding 36104, retrieval 2102, generation 7025, end-to-end 169972
- notes: ASR 124 s vs ~0.8 s steady state in run.sh -> likely first-query cold start; enc_a loaded as float16 on CPU (warning). Single-query timing NOT representative; verify in Step 5.

## 2026-11-12 RAG Step 5: practice retrieval evaluation
- command: python rag/scripts/evaluate_rag.py --device cpu --split practice --transcript-cache rag/.cache/practice_transcripts.jsonl
- output: rag/results/step5_practice_retrieval.txt
- startup: evaluate_rag spent ~9.5 min loading enc_a + corpus embeddings before starting the ASR worker; ASR worker load is I/O-bound (low CPU, slow RSS growth) on the shared home filesystem.
- result: Recall@5 0.4213, Recall@10 0.4796, Recall@20 0.5785, Recall@100 0.7699, MRR@10 0.4887, NDCG@10 0.4205
- queries: 350 (practice), ASR_CUDA=none, k_max=100
- notes: ~9.5 min startup before ASR worker launched; large gap between R@5 and R@20


## 2026-11-11 RAG Step 6: answer generation + judging (5-query trial)
- commands: generate_answers.py --limit 5; evaluate_answers.py --allow-subset (dry-run, then judge)
- judge: same model as ELM_MODEL (EuroLLM-22B-Instruct), repeats=1
- scores: 0.000, 0.417, 0.000, 0.417, 0.333 (mean ~0.23, n=5, NOT representative)
- note: judge compares answer to GOLD docs from qrels, not retrieved docs → answer score coupled to retrieval recall
- inspect_judge (rag/extensions/inspect_judge.py) findings, n=5:
  - q_7e9a: gold 1/2 in top-5 but score 0 → generator ignored gold doc among 4 distractors
  - q_9cd7: gold 0/1 → score 0 (retrieval miss)
  - q_e3f1: ASR error "GICO" (should be GEICO)
  - q_ea0b: judge text says "mostly grounded" but grounding=1 → judge noise; consider --repeats
  - queries read as topics, gold docs are specific → ambiguity limits scores

  ## 2026-11-11 RAG Step 6 timing (from sample_answers.jsonl timing fields)
- node / GPU: damnii07, RTX 2080 Ti   (confirm from file time vs sacct job 3712728)
- 5 queries: first (cold) query 207 s (ASR 150 s, encoding 45 s)
- warm (4 queries) mean ~6.1 s: generation 3.7 s (61%), ASR 1.5 s (24%), encoding 0.9 s (15%), retrieval 5 ms (0.1%)

## 2026-11-11 HW1 Task 1: run.sh --cuda task1
- node / GPU: damnii07, RTX 2080 Ti
- result: PASS, 790.0 ms ± 1.9 ms per transcription

## 2026-11-12 HW1 Task 2: make test2
- node / GPU: damnii09, RTX 2080 Ti
- result: ALL PASS (output saved: hw1-asr/task2_test_output.txt)
- notable: softmax vocabulary row (59264) only 3.5 GB/s (1% of peak), one block per row -> 1 of 68 SMs busy
- notable: layernorm audio encoder 380 GB/s (62%), softmax 64x4096 217 GB/s (35%)

## 2026-11-12 HW1 Task 1+2: run.sh --cuda task1,task2
- node / GPU: damnii12, RTX 2080 Ti
- srun with --propagate=NONE (hastings limits ulimit -v 512000 / -u 100 otherwise break PyTorch)
- result: PASS, 702.3 ms ± 1.2 ms per transcription, 54.0 ms per token, model load 221.6 s
- note: faster than task1-only (790 ms), but different node; needs same-node comparison

## 2026-11-14 Gold-doc rank analysis
- purpose: for the 122 practice queries with Recall@10 = 0, are gold docs ranked 11–100 (retrieved but too low) or beyond 100 (not matched)? Decides between depth/reranking vs representation directions.
- script: rag/extensions/gold_rank.py (ours; uses supplied src/encoder.py)
- command: python -u rag/extensions/gold_rank.py --out-dir rag/results/2026-11-14_gold_rank
- input: practice transcript cache (ASR_CUDA=none), qrels_practice.tsv, enc_a + corpus_enc_a embeddings
- output: rag/results/2026-11-14_gold_rank/ (gold_ranks.csv, summary.txt, run.log)
- sanity check: mean Recall@10 = 0.4796 (matches Step 5 official 0.4796)
- result: 122 zero-recall queries, best gold rank: 11–20: 30 (25%), 21–50: 29 (24%), 51–100: 21 (17%), 101–1000: 28 (23%), >1000: 14 (11%)
- conclusion: 66% of failures have a gold doc in the top 100 (49% in top 50) → reranking a deeper candidate list could recover part of them; 34% are beyond rank 100 → not fixable by reordering (representation / query / qrels issues).
- side note: encoding 350 queries took 2 min 21 s (enc_a float16 on CPU) → encoder cost may matter.

## 2026-11-15 BM25 probe (alternative first stage)
- Script: `rag/extensions/bm25_probe.py` (own BM25, k1 1.2, b 0.75, lowercase + stopwords, no stemming); enc_a top-100 from context_cost; CPU node. Sanity: enc_a = Step 5.
- Cost: index build 1.7 s, 11 MB postings, 0.3 ms/query.
- BM25 R@5 .2468 R@10 .2988 R@100 .5112; RRF(enc_a, BM25) out-of-fold (c 0/5) R@5 .4058 R@10 .4796 R@100 .7332 → no gain, R@5 worse.
- enc_a misses in top 100: 42 queries; BM25 recovers 1 (top 10), 5 (top 100). Union of top-100 lists covers .894 vs .880.
- Top-10 hits: both 138, enc_a only 90, BM25 only 13, neither 109.
- Conclusion: failures are semantic/vague, not missing keywords; lexical first stage does not help → keep reranking. Negative result for the report's "alternatives" paragraph.


## 2026-11-14 Reranking pilot
- purpose: does cross-encoder reranking of enc_a top-N improve retrieval, and at what latency? (pilot for option B; no ELM)
- script: rag/extensions/rerank_eval.py (uses supplied src/data.py, encoder.py, metrics.py)
- command: python -u rag/extensions/rerank_eval.py --device cuda --out-dir rag/results/2026-11-14_rerank_pilot
- settings: practice 350, cached transcripts (ASR_CUDA=none), enc_a on GPU, ms-marco-MiniLM-L-6-v2, N = 20/50/100
- sanity check: baseline = Step 5 exactly
- result: rerank_top20 R@5 0.4111 R@10 0.4947 MRR 0.4706 NDCG 0.4141, rescued 21/122, 87 ms/q; top50 0.3990/0.4841/0.4538/0.3993, 27/122, 215 ms/q; top100 0.3877/0.4739/0.4535/0.3952, 28/122, 312 ms/q; model load + warm-up 5.0 s
- conclusion: generic cross-encoder rescues some failures but hurts others; net metrics slightly worse, worse with larger N; cost small. Hypotheses: domain mismatch, enc_a tuned to corpus, topic-like queries, truncation, incomplete qrels. Next: win/loss analysis, score fusion, stronger reranker.
- win/loss (rag/results/2026-11-14_rerank_pilot/win_loss.txt): N=20: 40 better / 34 worse, rescued 21 / broken 13; N=50: rescued 27 / broken 20; N=100: rescued 28 / broken 26.
- larger N adds few rescues but many breaks → distractors.
- wins include manually identified wording-mismatch queries (q_9cd7, q_0c24); losses include acronyms / names / ASR-split names (B A A V O, SWIFT, U.S.) and vague queries (tentative, 5 examples).
- next: score fusion (α·enc_a + (1−α)·cross-encoder).

## 2026-11-14 Evidence coverage and context size vs k
- purpose: how much more gold evidence and how much longer the prompt do we get with k = 5/10/20? (no ELM; groundwork for comparing "more documents" vs "reranking")
- script: rag/extensions/context_cost.py (uses supplied SimpleContextBuilder to build the exact baseline prompt)
- command: python -u rag/extensions/context_cost.py --device cuda --out-dir rag/results/2026-11-14_context_cost
- sanity check: Recall@5/10/20 = 0.4213 / 0.4796 / 0.5785 (matches Step 5)
- result: hit@k 0.591 / 0.651 / 0.737; prompt chars mean 5322 / 10533 / 20927 (≈1.3k / 2.6k / 5.2k tokens, approx.); median first gold position = 1
- conclusion: prompt size grows linearly with k, coverage gains diminish; new hits from larger k sit at positions 6–20. Answer quality vs k still unknown (needs ELM pilot).
- also saved: rankings.jsonl (enc_a top 100 + scores, for later fusion / k experiments)

## 2026-11-15 k sweep (answer quality vs number of documents)

- Question: does giving the LLM more documents (k = 5, 10, 20) improve answers, and at what cost?
- Script: `rag/extensions/gen_from_rankings.py` (supplied SimpleContextBuilder + ELMGenerator, same prompt as baseline); judge: supplied `rag/scripts/evaluate_answers.py --allow-subset`
- Inputs: cached practice transcripts; enc_a rankings from `results/2026-11-14_context_cost/rankings.jsonl`
- Fixed: same 20 practice queries (random, seed 0), transcripts, enc_a ranking, LLM (EuroLLM-22B-Instruct, temp 0.1), judge (same model, 1 repeat). Only k changes.
- Hardware: CPU-only Slurm node (generation runs on the ELM API)
- Output: `results/2026-11-15_k_sweep/` (answers_k*.jsonl, gen_k*.log, judge_k*/)

| k | Hit@k (350 q) | Prompt chars (mean) | Correctness | Grounding | Completeness | Normalised score | Gen ms mean / median |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 0.591 | 5,322 | 2.10 | 2.10 | 1.80 | 0.500 | 4861 / 5183 |
| 10 | 0.651 | 10,533 | 2.00 | 2.15 | 1.75 | 0.492 | 4609 / 5186 |
| 20 | 0.737 | 20,927 | 1.65 | 1.80 | 1.45 | 0.408 | 5373 / 5336 |

(Hit@k and prompt chars from the 2026-11-14 context_cost run on all 350 queries.)

Notes:
- More docs → higher hit rate but no better answers; k = 20 lowest. Possible cause: distractor documents. Not significant (20 queries, 1 judge repeat; 0.09 ≈ 1 point out of 12 per query).
- Generation time nearly flat despite 4× longer prompts → cost of larger k is quality, not latency.
- Decision: keep k = 5; focus on ordering (reranking / fusion).
- Possible follow-up: paired per-query comparison k5 vs k20; repeat judge to estimate noise.

## 2026-11-15 fusion_eval (keep rescues, avoid breaks)
- Script: `rag/extensions/fusion_eval.py`; enc_a top-20 + ms-marco-MiniLM-L-6-v2 (CPU node); 350 practice queries; params chosen on one half by R@5, evaluated on the other (2-fold, seed 0). Sanity: baseline = Step 5.
- Out-of-fold: baseline R@5 .4213 R@10 .4796 | rerank .4111/.4947 (21 rescued/13 broken) | fusion α .2–.3 .4332/.5054 (19/9) | RRF c=10 .4388/.5136/MRR .4958/NDCG .4352 (15/3) | protect top-3 .4387/.5125 (20/9) | gate .4154/.4789 (2/1)
- Diagnosis: broken vs rescued have similar enc_a margins (0.0061 vs 0.0052; all 0.0067) → confidence gating cannot separate them. Broken: median gold rank 5, 8% at rank 1.
- To do: widen grids (c, m at edge), paired significance test, answer-quality check on changed queries.

## 2026-11-15 RRF vs baseline answers (R@5-changed queries)
- Queries: 39 practice queries whose R@5 differs between baseline and RRF (out-of-fold c, seed 0): 24 up, 15 down (`r5_changed.py`)
- Generation: `gen_from_rankings.py`, k=5, same transcripts/prompt/LLM; judge: supplied evaluate_answers.py, 1 repeat
- Output: `results/2026-11-15_rrf_answers/` (answers_*, judge_*, paired.csv, paired.txt)

| | Score | Correct | Ground | Complete | Gen ms mean |
| --- | --- | --- | --- | --- | --- |
| baseline | 0.346 | 1.41 | 1.62 | 1.13 | 4369 |
| RRF | 0.378 | 1.59 | 1.64 | 1.31 | 4366 |

Paired (`paired_answers.py`): R@5 up (24) +0.118, better/worse/same 11/3/10; R@5 down (15) −0.106, 2/5/8; all 39 +0.032, 95% CI [−0.075, +0.135], p = 0.55.
- Answers track retrieval direction; net effect not significant. Scaled to 350 queries ≈ +0.004.
- Caveat: judge sees gold docs, so retrieving them may favour scores partly by construction.

## 2026-11-15 rerank_cost (GPU)
- Script: `rag/extensions/rerank_cost.py` (+ `common.py`); 350 practice queries; enc_a top-100 from context_cost; RRF c out-of-fold (seed 0); batch 64
- Hardware: NVIDIA H200 MIG 1g.18gb (NOT the 2080 Ti used for earlier timing); timing = predict() only, after warm-up
- Cross-check: L-6 N=20 RRF = fusion_followup (R@5 .4397, R@10 .5144, 16/3) ✓
- Latency linear in N: L-6 ≈ 4.3 ms/doc (44/88/130/215 ms), L-12 ≈ 8 ms/doc (79/163/242/401 ms); load ≈ 1 s (cached); peak GPU 271–895 MB
- RRF R@5 peaks at N=20 for both models (.4397 L-6, .4393 L-12); larger N adds distractors
- L-12 pure rerank beats baseline (R@5 .4350 vs .4213) unlike L-6 (.4111), but RRF results equal → bigger model costs 1.85× latency for no RRF gain
- Best trade-off: L-6, N=20, RRF

## 2026-11-15 rerank_cost (CPU: Intel Xeon Gold 6542Y, 4 cores allocated, node saxa)
- Same command as GPU run with --device cpu; job hit the 1 h limit during L-12 N=30 → summary.txt not written; medians taken from log
- Quality identical to GPU run (all RRF R@5 match) → device affects cost only
- Median ms/query: L-6 486 / 1001 / 1515 / 2902 (N=10/20/30/50); L-12 954 / 2001 (N=10/20); ≈11–13× slower than H200 MIG
- vs ~6.1 s warm end-to-end (2080 Ti, different hardware): L-6 N=20 adds ~1.4% on GPU, ~16% on CPU; L-12 N=20 on CPU ~2 s
- Conclusion: GPU → reranking nearly free; CPU → keep small model, N ≤ 20

## 2026-11-15 Held-out check on dev (125 queries)
- Dev transcripts: `evaluate_rag.py --split dev` with ASR_CUDA=none (same ASR as practice) → `.cache/dev_transcripts.jsonl`
- Dev baseline (official script): R@5 .3795 R@10 .4746 R@20 .5795 R@100 .7244 MRR@10 .4597 NDCG@10 .3983; `enc_rankings.py` matches exactly; practice matches Step 5
- `heldout_eval.py`: L-6, N=20, params chosen on all of practice by R@5, applied unchanged to dev; latency on dev median 89 ms, p90 92 ms (H200 MIG)
- Dev: rerank R@5 .3743 (9/6) | fusion α .2 .3832 (7/5) | RRF c 0 .3929 R@10 .4885 (6/2), ΔR@5 +.0134 [−.020, +.047] p .43, ΔR@10 +.0139 [−.023, +.052] p .44 | protect m 3 .3871 (8/4)
- Ordering and low breakage replicate; gain smaller than practice (R@10 +.035 → +.014) and not significant at n=125 (small sample; selection on practice → optimistic estimate)

## 2026-11-15 End-to-end timing (RTX 2080 Ti, ASR_CUDA=none)
- Script: `rag/extensions/e2e_timing.py`; 20 practice queries (seed 0) after 1 untimed warm-up; baseline top-5 vs RRF(L-6, top-20, c=0); 2 ELM calls/query
- Transcripts identical to cache: 20/20 (ASR deterministic → reusing the cache is valid)
- Median per query: ASR 1521 ms, encoding 33 ms, retrieval 2.5 ms, rerank 84 ms (mean 153, first query 1481 outlier), generation 4.8 s; end-to-end 6.4 s (base) / 6.2 s (RRF)
- Shares (mean): ASR ~25%, generation ~74%, rerank 2.3%
- RRF − baseline end-to-end mean +262 ms, median +276 ms (mostly generation noise; deterministic extra = rerank)
- One-off: ASR load 188 s, encoder 51 s, reranker 5.3 s, warm-up query 50 s
- Rerank median on 2080 Ti (84 ms) ≈ H200 MIG (88 ms)

## 2026-11-15 Judge repeats (3×) on the 39 R@5-changed queries
- Same answers as 2026-11-15_rrf_answers; `evaluate_answers.py --repeats 3 --api-retries 8` (first attempt crashed on malformed judge JSON after 3 retries; rerun into same out-dir)
- Means: baseline .347 (C 1.44, G 1.58, Co 1.14) | RRF .400 (C 1.64, G 1.78, Co 1.38)
- Paired (`paired_answers.py`, 3-repeat means): R@5 up (24) +.144, 14/4/6 (sign test p≈.03); R@5 down (15) −.093, 2/8/5; all 39 +.053, CI [−.028, +.135], p .20
- vs 1 repeat: same direction, ties 18 → 11, CI lower bound −.075 → −.028
- Scaled to 350 queries ≈ +.006

## 2026-11-16 Our kernels: verification + end-to-end timing (damnii07 RTX 2080 Ti, CUDA 12.8.0, ASR_CUDA=all)
- asr_worker.py enables kernels via ops.set_cuda_groups(args.cuda) and errors if the built library is missing (no silent PyTorch fallback)
- e2e_timing.py --n 5: ASR median 3610 ms (vs 1521 ms PyTorch, 20 q) → kernels in use; transcripts = cache 5/5
- Median: rerank 86 ms (1.6%), generation 6.4 s (ELM noise), end-to-end 10.0 s (vs 6.4 s PyTorch)
- ASR share ~41% (vs ~25%); one-off ASR load 117 s
- TODO (optional): --n 20 for a matched comparison

## 2026-11-16 End-to-end timing with our kernels, 20 queries (damnii RTX 2080 Ti, CUDA 12.8.0, ASR_CUDA=all)
- Same 20 practice queries (seed 0) as the PyTorch run; transcripts = cache 20/20
- Median: ASR 4559 ms (vs 1521 PyTorch, ~3.0×), encoding 34, retrieval 2.6, rerank 84 (1.3%), generation 5.0 s, end-to-end 9.8 s (vs 6.4 s)
- ASR share ~50% (vs ~25%) → co-bottleneck with generation
- One-off ASR load 88 s (file-system dependent)
- Supersedes the 5-query run (ASR median 3.6 s)

## 2026-11-16 HW1 run.sh on one node (damnii, RTX 2080 Ti sm_75, CUDA 12.8.0)
- --cuda none (PyTorch): PASS, 1107.9 ± 7.5 ms/transcription, 85.2 ms/token, peak 8.88 GiB
- --cuda all --profile: PASS, 3337.7 ± 5.0 ms, 256.7 ms/token, peak 8.56 GiB → 3.0× slower (matches 3.0× ASR slowdown in the pipeline)
- Profile (3504 ms in kernels): linear/GEMM 2860.7 ms 81.6% (2757 calls), attention 466.1 ms 13.3%, rmsnorm 164.9 ms 4.7%, rope 3.1 ms, softmax 1.6 ms
- → slowdown is the Task 3 GEMM vs cuBLAS
- Note: earlier Task 1+2 only = 702 ms (damnii12, other day) < 1108 ms PyTorch → check task1,task2 and all-but-gemm on the same node
- Outputs: hw1-asr/run_none_output.txt, profile_all_output.txt

## 2026-11-16 HW1 per-config and per-op timing, one node (damnii RTX 2080 Ti, CUDA 12.8.0)
- none 1108 ms | provided 1096 ms | task1,task2 790 ms | all 3338 ms (profile run of none: 1084 ms)
- Profile none vs all (ms per transcription): linear 600.5 vs 2860.7; attention 317.0 vs 466.1; rope 265.9 vs 3.1; rmsnorm 87.3 vs 164.9; softmax 0.3 vs 1.6
- Task 1+2 speed-up is RoPE (fused single kernel vs several PyTorch ops); our RMSNorm is ~2× slower (one block per row → low parallelism when decoding one token)
- All-kernel slowdown: GEMM +2260 ms ≫ attention +149 ms ≫ RMSNorm +78 ms
- Correction: earlier guess that RMSNorm fusion caused the speed-up was wrong

## 2026-11-16 Failure analysis completed (manual, one annotator)
- File: results/2026-11-15_failure_cases/cases.md (category legend at top; examples tagged [EXAMPLE: ...])
- Broken by pure rerank (13): not reranker errors 6 (plausible alternative 4, ambiguous 1, vague 1); reranker errors 7 (wording mismatch/jargon 3, same-topic distractor 2, keyword distractor 1, ASR form 1); ASR form present in 4/13
- Rescued (6 inspected + 2 earlier): links different wording, matches a key condition in a long query, finds the specific question among similar docs, matches a key phrase
- RRF keeps all 17 rescues where rerank ranks gold 1–6, loses all 4 where it ranks gold 7–10 (outside rerank's own top 5 → no loss at k = 5)
- Judged on 300-char snippets with spot checks of full text (e.g. Walmart gold doc has no "Walmart" anywhere)

## 2026-11-16 RRF vs pure rerank, direct test (`rrf_vs_rerank.py`)
- Inputs: fusion_eval ce_scores (practice, RRF c out-of-fold [5, 0], seed 0); heldout_eval rankings (dev); CPU node
- Cross-check: practice and dev tables equal earlier runs exactly
- Practice RRF − rerank: R@5 +.0287 [+.004, +.054] p .023; R@10 +.0197 p .030; MRR +.0333 p .002; NDCG +.0261 p < .001; hit@5 RRF only 21 vs rerank only 9 (sign p .043)
- Dev: R@5 +.0186 p .37; R@10 +.0143 p .52; MRR +.0300 p .11; NDCG +.0240 p .076; hit@5 8 vs 4
- Output: results/2026-11-16_rrf_vs_rerank/summary.txt

## 2026-11-16 k sweep, 3 judge repeats
- Same answers as 2026-11-15_k_sweep; evaluate_answers.py --repeats 3 --api-retries 15 → judge3_k5/10/20
- k = 10 crashed twice on the same query (judge returned malformed JSON: "Invalid control character") → q_cde8053b3855199a excluded from k = 10 and 20 (answers_k*_excl.jsonl); analysis on the 19 queries judged for all three k
- Means: k5 .525 | k10 .469 | k20 .392 (all three dimensions fall)
- Paired bootstrap: k20 − k5 −.133 [−.238, −.029] p .011; k10 − k5 −.056 p .44; k20 − k10 −.077 p .24; k20 vs k5 per query 5 better / 12 worse / 2 same
- judge_noise (k5 vs k20): single-judgement sd .150; single-repeat differences −.079, −.145, −.175 (all negative)
- Outputs: results/2026-11-15_k_sweep/judge3_k*/, paired_k5_k20.txt