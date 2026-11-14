# Results summary (RAG investigation) — frozen numbers for writing

All numbers: practice split (350 queries) unless marked **dev** (125 queries). Transcripts: cached, PyTorch ASR (`ASR_CUDA=none`). Reranker default: ms-marco-MiniLM-L-6-v2, enc_a top-20. Parameters out-of-fold (2-fold, seed 0) unless stated. Sources = folders under `rag/results/`.

## Storyline (one line per step)

1. Retrieval is the weak link, and its failures are mostly **ordering**, not absence.
2. Giving the LLM **more** documents does not help → fix **which** 5 documents.
3. **Replacing** enc_a's order with a reranker fixes some queries but breaks as many.
4. **Combining** the two rankings (RRF) keeps most fixes and almost no breaks.
5. The gain is stable on practice, but **smaller and not significant on held-out dev**.
6. Answers **follow retrieval**: better where retrieval improves; net end-to-end gain small.
7. Cost is small on GPU (~1–2% of end-to-end), larger on CPU; bigger models / deeper lists cost more for no RRF gain.
8. Alternatives that do not help: BM25 first stage, confidence gating.

---

## E0 Baseline and failure diagnosis → §4.1 (motivation)
- Practice: R@5 .4213, R@10 .4796, R@20 .5785, R@100 .7699, MRR@10 .4887, NDCG@10 .4205 (= official Step 5)
- **Dev**: R@5 .3795, R@10 .4746, R@20 .5795, R@100 .7244, MRR@10 .4597, NDCG@10 .3983 (= official evaluate_rag.py)
- All-or-nothing: 122/350 (35%) R@10 = 0; 111 (32%) R@10 = 1
- Gold rank of the 122 failures: 11–20 25% · 21–50 24% · 51–100 17% · 101–1000 23% · >1000 11% → **49% within top 50** (reorderable), 34% beyond 100
- 6 failures checked by listening: audio = transcript → **not ASR errors**; wording mismatch (payments vs checks; valuing options vs binomial pricing; fund composition vs annual report positions), vague/generic queries, near-empty gold doc
- Ceiling: perfect reordering of top-20 caps R@5 at ≈ R@20 = .58 (we reach .44)
- Sources: step5 output, `2026-11-14_gold_rank/`, `per_query_step5.csv`

## E1 Retrieval depth k → §4.1 (motivation for k = 5)
- Same 20 queries (seed 0), 1 judge repeat
- k = 5 / 10 / 20: hit@k .59 / .65 / .74; prompt 5.3k / 10.5k / 20.9k chars; answer score **.50 / .49 / .41**; generation 4.9 / 4.6 / 5.4 s
- Claim: more documents raise coverage but **no answer gain**; generation time ~flat
- ⚠ Difference .09 is borderline vs judge noise (see E11) → say "no gain", not "worse"
- Source: `2026-11-15_k_sweep/`

## E2 Reranker alone (pilot) → §4.2
- Top-20 / 50 / 100: R@5 .411 / .399 / .388; R@10 .495 / .484 / .474; rescued/broken 21/13, 27/20, 28/26; 87 / 215 / 312 ms (GPU)
- Claim: averages flat because of churn; deeper lists add more breaks than rescues
- Wins: wording mismatch (q_9cd7, q_0c24); losses: names/acronyms ("B A A V O", SWIFT, U.S.), vague queries (to confirm in E12)
- Source: `2026-11-14_rerank_pilot/`

## E3 Replace vs combine (main table) → §4.2, Table "methods"
| Method | Param (fold1, fold2) | R@5 | R@10 | MRR@10 | NDCG@10 | Rescued | Broken |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | – | .4213 | .4796 | .4887 | .4205 | – | – |
| Rerank | – | .4111 | .4947 | .4706 | .4141 | 21 | 13 |
| Score fusion | α .2, .3 | .4332 | .5054 | .4907 | .4299 | 19 | 9 |
| **RRF** | c 5, 0 | **.4397** | **.5144** | **.5038** | **.4402** | 16 | **3** |
| Protect top m | m 3, 4 | .4364 | .5130 | .4945 | .4339 | 20 | 8 |
| Gating | ≈ no rerank | .4154 | .4789 | .4839 | .4170 | 2 | 1 |
- Gating fails: enc_a top1–top2 margin is the same for broken (.0061) and rescued (.0052) queries (all .0067) → confidence cannot predict when reranking helps
- Broken-by-rerank queries: median gold rank 5, only 8% at rank 1 (gold was "barely in top 10")
- Why RRF: uses ranks only → a doc must rank well in both lists; no score-scale tuning
- Sources: `2026-11-15_fusion/` (gate, diagnosis), `2026-11-15_fusion_followup/` (others)

## E4 Robustness on practice → §4.3
- 20 random 2-fold splits (R@5 / R@10 mean ± sd): RRF .4386±.0020 / .5150±.0012 (most stable); protect .4320±.0053 / .5121±.0018; fusion .4248±.0065 / .5083±.0036 (α jumps .1–.8)
- Paired bootstrap vs baseline (10k): **RRF R@10 +.035 [+.015, +.056], p < .001**; R@5 +.018 [−.001, +.038], p = .06; MRR +.015, p = .09
- Protect R@10 +.033 [+.010, +.058], p = .007; fusion R@10 +.026 [+.002, +.051], p = .035; rerank n.s.
- 12 comparisons → RRF R@10 survives Bonferroni
- Source: `2026-11-15_fusion_followup/`

## E5 Held-out dev (params fixed on all practice) → §4.3, add dev columns to main table
| Method | Param | dev R@5 | dev R@10 | MRR | Resc/Brok | ΔR@5 [95% CI] | ΔR@10 [95% CI] |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Baseline | – | .3795 | .4746 | .4597 | – | – | – |
| Rerank | – | .3743 | .4742 | .4281 | 9/6 | −.005 | −.000 |
| Fusion | α .2 | .3832 | .4688 | .4405 | 7/5 | +.004 | −.006 |
| **RRF** | c 0 | **.3929** | **.4885** | .4581 | 6/**2** | +.013 [−.020, +.047] p .43 | +.014 [−.023, +.052] p .44 |
| Protect | m 3 | .3871 | .4828 | .4650 | 8/4 | +.008 | +.008 |
- Replicates: method ordering, rerank-alone no gain, RRF fewest breaks
- Does not replicate: size/significance (R@10 +.035 → +.014). Reasons: n = 125 (CI ~2× wider); selecting the best of several methods on practice → optimistic estimate
- Source: `2026-11-15_heldout/`

## E6 Answer quality (39 practice queries whose R@5 changes under RRF: 24 up, 15 down) → §4.5
- 3 judge repeats (mean): baseline .347 → RRF .400
| Group | n | Base | RRF | Diff | better/worse/same |
| --- | --- | --- | --- | --- | --- |
| R@5 up | 24 | .310 | .454 | **+.144** | 14/4/6 (sign test p≈.03) |
| R@5 down | 15 | .406 | .313 | −.093 | 2/8/5 |
| All | 39 | .347 | .400 | +.053 [−.028, +.135], p .20 | 16/12/11 |
- Claim: answers follow retrieval; net gain not significant; ≈ +.006 over all 350 queries (only 11% change)
- 1-repeat run gave the same direction (+.032, ties 18)
- ⚠ Judge sees gold docs → retrieving gold may raise scores partly by construction
- Source: `2026-11-15_rrf_answers/` (paired3.txt)

## E7 Judge noise → §3 or §4.5 (measurement reliability)
- Identical across 3 repeats: 21/39 (base), 25/39 (RRF); repeat correlation .70 / .81
- Single-judgement sd .136 (heavy-tailed: most stable, a few vary widely); 3-repeat mean sd .078
- Single-repeat estimates of RRF − base: +.049, +.077, +.032 → magnitude unreliable with 1 repeat; direction consistent
- Source: `2026-11-15_rrf_answers/judge_noise.txt`

## E8 Quality vs cost (model × N × device) → §4.4, Figure "R@5 vs latency"
GPU = H200 MIG 1g.18gb; CPU = Xeon Gold 6542Y, 4 cores. Median ms/query.
| Model | N | RRF R@5 | RRF R@10 | Rerank-only R@5 | GPU ms | CPU ms | Peak GPU MB |
| --- | --- | --- | --- | --- | --- | --- | --- |
| L-6 (22.7M) | 10 | .4281 | .4796 | .4050 | 44 | 486 | 271 |
| L-6 | **20** | **.4397** | .5144 | .4111 | **88** | 1001 | 360 |
| L-6 | 30 | .4336 | .5229 | .4106 | 130 | 1515 | 449 |
| L-6 | 50 | .4293 | .5117 | .3990 | 215 | 2902 | 628 |
| L-12 (33.4M) | 10 | .4231 | .4796 | .4079 | 79 | 954 | 538 |
| L-12 | 20 | .4393 | .5172 | .4350 | 163 | 2001 | 627 |
| L-12 | 30 | .4328 | .5191 | .4291 | 242 | – | 716 |
| L-12 | 50 | .4364 | .5065 | .4199 | 401 | – | 895 |
- Latency linear in N (L-6 ≈ 4.3 ms/doc GPU, ≈ 50 ms/doc CPU); CPU ≈ 11–13× slower; load ≈ 1 s (cached)
- RRF R@5 peaks at N = 20; deeper lists add distractors
- L-12 alone beats baseline (.435) unlike L-6 (.411), but **RRF equal** → bigger model costs 1.85× for no RRF gain
- Quality identical on CPU and GPU (device affects cost only)
- N = 10: R@10 unchanged by construction
- CPU L-12 N = 30/50 not measured (job time limit)
- Best trade-off: **L-6, N = 20, RRF**
- Sources: `2026-11-15_cost_gpu/`, `2026-11-15_cost_cpu.log`

## E9 End-to-end timing (RTX 2080 Ti, 20 practice queries, after 1 warm-up) → §4.4
- Median: ASR 1521 ms, encoding 33 ms, retrieval 2.5 ms, **rerank 84 ms**, generation 4.8 s; end-to-end 6.4 s (base) / 6.2 s (RRF)
- Shares (mean): generation ~74%, ASR ~25%, rerank 2.3%
- RRF − base end-to-end +262 ms mean (mostly generation noise; generation 2.5–12 s per query)
- One-off: ASR load 188 s, encoder 51 s, reranker 5.3 s, warm-up query 50 s
- Fresh transcripts = cache: **20/20** (ASR deterministic → reusing cache valid)
- Rerank 84 ms on 2080 Ti ≈ 88 ms on H200 MIG
- ⚠ Rerank mean 153 ms inflated by first query (1481 ms) → report medians
- Source: `2026-11-15_e2e/`

## E10 BM25 as alternative first stage → §4.6 (short) / §5
- BM25 (k1 1.2, b .75, no stemming): R@5 .2468, R@10 .2988, R@100 .5112; build 1.7 s, 11 MB, 0.3 ms/query
- RRF(enc_a, BM25) out-of-fold: R@5 .4058, R@10 .4796, R@100 .7332 → no gain, R@5 worse
- Of 42 queries enc_a misses in top 100, BM25 finds 1 (top 10), 5 (top 100); union of top-100 lists .894 vs .880
- Top-10 hits: both 138, enc_a only 90, BM25 only 13
- Claim: failures are semantic/vague, not missing keywords
- Source: `2026-11-15_bm25_probe/`

## E11 Failure analysis (manual) → §5 — **TODO**
- Case file: `2026-11-15_failure_cases/cases.md` (rerank broken 13, rescued 21; RRF broken 3, rescued 17)
- To fill: category + why per case; count categories; pick 2–3 examples (incl. ASR letter-spelled acronyms if confirmed)

---

## Limitations to state
- Practice used for all development; dev confirms direction only (n = 125, not significant)
- Judge: same LLM as generator, sees gold docs, single judgement noisy (sd .14)
- k sweep: 20 queries, 1 repeat
- One reranker family (MiniLM, MS MARCO); no fine-tuning
- Reordering cannot fix the 34% of failures with gold beyond rank 100
- Timing: H200 MIG slice and 2080 Ti; generation time includes ELM network latency

## Video candidates
- Q1 design choice: combine (RRF, ranks only) instead of replace; why
- Q2 checking: baseline reproduced exactly; dev held-out (and that the gain shrank); transcripts 20/20 identical; CPU = GPU quality; listened to failed queries
