# Our scripts (rag/extensions)

Code written by our group. Everything else under rag/ is supplied by the course.

| Script | Purpose | Inputs | Outputs | Status |
| --- | --- | --- | --- | --- |
| inspect_judge.py | Per-query judge scores vs. whether gold docs were retrieved | generate_answers output (.jsonl), evaluate_answers --out-dir | printed table | analysis, active |
| per_query_table.py | Join Step 5 per-query Recall@10 with transcripts and qrels; summary by #gold docs and transcript length | results/step5_practice_retrieval.txt, .cache transcripts, qrels | results/per_query_step5.csv + printed summary | analysis, done |
| gold_rank.py | Rank of every gold doc in the full exact enc_a ranking, per query | .cache transcripts, qrels, enc_a model + corpus embeddings | results/<run>/gold_ranks.csv, summary.txt | analysis, active |
| rerank_eval.py | Pilot: rerank enc_a top-N with a cross-encoder; retrieval metrics vs baseline, rescued failures, rerank latency | .cache transcripts, qrels, corpus, enc_a, cross-encoder | results/<run>/summary.txt, per_query.csv | experiment (pilot), active |
| compare_per_query.py | Win/loss analysis of per-query Recall@10 vs baseline (better/worse, rescued/broken, biggest changes) | per_query.csv from rerank_eval.py | printed summary | analysis, active |
| context_cost.py | Evidence coverage (Recall@k, hit@k, first gold position) and baseline prompt size vs k; saves enc_a top-100 rankings for reuse | .cache transcripts, qrels, corpus, enc_a | results/<run>/summary.txt, per_query.csv, rankings.jsonl | analysis, active |
| gen_from_rankings.py | Generate answers for a chosen k from saved rankings + cached transcripts (no ASR/encoder), same prompt and generator as baseline; output judgeable by evaluate_answers.py | results/<run>/rankings.jsonl, .cache transcripts, corpus, rag/.env | answers .jsonl | experiment, active |
| fusion_eval.py | Rerank vs score fusion / RRF / gating / top-m protection on enc_a top-N; 2-fold parameter choice; diagnosis of broken vs rescued queries | transcript cache, corpus, enc_a, cross-encoder | summary.txt, per_query.csv, ce_scores.jsonl | experiment, active |
| fusion_followup.py | Wider grids, multi-split stability, paired bootstrap vs baseline, rankings + changed-top-5 lists for answer checks; reuses ce_scores.jsonl | results/<fusion run>/ce_scores.jsonl, qrels | summary.txt, rankings_*.jsonl, changed_top5_*.txt | analysis, active |
| r5_changed.py | List queries whose Recall@k differs between two rankings files | two rankings_*.jsonl, qrels | query id list (.txt) | analysis, active |
| paired_answers.py | Per-query paired comparison of two judge outputs, split by R@5 up/down; bootstrap CI | two answer_judge_per_query.jsonl, qids file from r5_changed.py | printed table, optional csv | analysis, active |
| bm25_probe.py | Probe: BM25 alone and RRF(enc_a, BM25); does BM25 find gold docs enc_a misses; index build time/size, query latency | enc_a rankings.jsonl (top 100), transcripts, corpus, qrels | summary.txt, rankings_bm25.jsonl, per_query.csv | probe, active |
| common.py | Shared helpers: loading, metrics, RRF / fusion / protect orderings, 2-fold parameter choice | – | – | library |
| rerank_cost.py | Quality vs cost per reranker model × candidate depth N (rerank + out-of-fold RRF; latency, load time, GPU memory, params); run per device | enc_a rankings.jsonl, transcripts, corpus, qrels | summary.txt, results.csv, ce_scores_*.jsonl | experiment, active |
| enc_rankings.py | Encode a split's cached transcripts with enc_a and save top-K rankings (ids + scores); prints baseline metrics | transcript cache, corpus embeddings, enc_a | rankings .jsonl | data prep, active |
| heldout_eval.py | Held-out check: choose each method's parameter on practice, apply unchanged to dev; bootstrap CIs; rerank latency | rankings from enc_rankings.py for both splits, transcripts, qrels | summary.txt, rankings_dev_*.jsonl | experiment, active |
| failure_cases.py | Case file for manual failure analysis: rescued/broken queries under rerank and RRF with gold ranks and texts | fusion_eval ce_scores.jsonl, transcripts, corpus, qrels | markdown case file | analysis, active |
| e2e_timing.py | End-to-end timing on one machine, baseline vs RRF: mirrors supplied RAGPipeline stages + rerank stage; load times; transcript reproducibility | audio, corpus, enc_a, reranker, rag/.env | answers+timings .jsonl, .summary.txt | experiment, active |
| judge_noise.py | Judge reliability from judge_cache.jsonl with repeats: within-answer spread, agreement, repeat correlation, per-repeat system difference | two judge_cache.jsonl | printed table | analysis, active |
| compare_transcripts.py | Compare two transcript caches (e.g. PyTorch vs our kernels): identical count, WER, largest differences | two transcript caches | printed report, optional csv | analysis, active |
| rrf_vs_rerank.py | Direct test of combine vs replace: RRF minus pure rerank on practice (out-of-fold) and dev; paired bootstrap, per-query wins/losses with sign test | fusion_eval ce_scores.jsonl, heldout_eval rankings, enc_dev rankings, qrels | summary text | analysis, active |

