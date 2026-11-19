# Supplementary Code — Speech Recognition & RAG Reranking Pipeline

This repository contains the supplementary code for the INFR11269 coursework project. The codebase implements an end-to-end audio Question-Answering system combining custom CUDA kernels for speech recognition with cross-encoder document reranking.

---

## 1. Distinction of Student Work vs. Supplied Baseline Code

The original coursework template provided baseline infrastructure for ASR token decoding and RAG retrieval. The table below explicitly distinguishes student-implemented contributions from supplied components:

| Directory / File | Status | Description of Contributions / Changes |
| :--- | :--- | :--- |
| `hw1-asr/csrc/task2_reduce.cu` | **Student Modified** | Implemented vectorized 128-bit memory access (`float4*` / `LDG.128`) for `rmsnorm_kernel`. Added a dynamic runtime 16-byte alignment guard (`uintptr_t % 16 == 0 && cols % 4 == 0`) with scalar fallback. |
| `hw1-asr/csrc/task1_rope.cu` | **Student Implemented** | Completed custom Rotary Position Embedding CUDA kernel. |
| `hw1-asr/csrc/task3_gemm.cu` | **Student Implemented** | Completed Tiled GEMM CUDA kernel for linear projection layers. |
| `hw1-asr/csrc/task4_attention.cu` | **Student Implemented** | Completed FlashAttention CUDA kernel with shared-memory staging. |
| `rag/src/reranker.py` | **Student Added** | Developed cross-encoder reranking algorithms: Reciprocal Rank Fusion (RRF), Pure Reranking, Score Fusion, Top-$m$ Protection, and Confidence Gating. |
| `rag/scripts/evaluate_reranking.py` | **Student Added** | Authored evaluation suite for Recall@k, MRR@10, rescued/broken query counting, and latency sweeps. |
| `hw1-asr/glm_asr_cuda/` | Supplied Baseline | Unmodified Python wrapper and token decoding pipeline for GLM-ASR-Nano (2.3B). |
| `rag/src/pipeline.py` & `enc_a` | Supplied Baseline | Unmodified dense retriever (`enc_a`) dual-encoder search and EuroLLM-22B API interface. |
| `cuda-tutorial/` | Supplied Baseline | Lecture CUDA reference examples and Slurm environment scripts. |

---

## 2. Directory & Relevant File Map

```
edin-mls-26-autumn/
├── hw1-asr/                       # Speech Recognition Module
│   ├── csrc/
│   │   ├── task1_rope.cu          # [Student] Rotary Position Embedding kernel
│   │   ├── task2_reduce.cu        # [Student] Vectorized float4 RMSNorm & alignment guard
│   │   ├── task3_gemm.cu          # [Student] Tiled GEMM linear layer kernel
│   │   └── task4_attention.cu     # [Student] FlashAttention kernel
│   ├── tests/                     # Baseline CPU reference tests
│   └── run.sh                     # Build and profiling script
├── rag/                           # Retrieval-Augmented Generation Module
│   ├── src/
│   │   ├── reranker.py            # [Student] RRF & Cross-Encoder ranking fusion
│   │   └── pipeline.py            # Pipeline integration (ASR -> enc_a -> RRF -> LLM)
│   ├── scripts/
│   │   ├── evaluate_reranking.py  # [Student] Retrieval metrics & latency evaluation
│   │   └── run_audio_query.py     # End-to-end audio query runner
│   └── data/rag_corpus/           # 24,000 corpus records & evaluation query splits
└── README.md                      # Supplementary code instructions (this file)
```

---

## 3. Dependencies & System Requirements

### Hardware Requirements
* **GPU**: NVIDIA GPU with Compute Capability $\ge \text{sm\_75}$ (Tested on RTX 3090 `sm_86`, RTX 2080 Ti `sm_75`, and H200 MIG `sm_90`).
* **CUDA Toolkit**: CUDA 11.6 or newer (CUDA 12.8 recommended).

### Environment Setup & Python Dependencies
The coursework uses two isolated Python virtual environments:

1. **ASR Environment (`hw1-asr`)**:
   * `python >= 3.10`
   * `torch >= 2.1.0`
   * `ninja` (for CUDA extension compilation)
   * `sentencepiece`

2. **RAG Environment (`rag`)**:
   * `python >= 3.10`
   * `sentence-transformers == 6.2.0`
   * `torch >= 2.15.0`
   * `numpy`, `scipy`

---

## 4. Commands to Build & Run

### A. CUDA Kernels & ASR Verification
1. **Allocate GPU Compute Node (Slurm)**:
   ```bash
   srun -p Teaching --gres=gpu:1 --cpus-per-task=4 --mem=16G --time=01:00:00 --pty bash
   export PATH=/opt/cuda-12.8.0/bin:$PATH
   ```

2. **Compile & Profile ASR CUDA Kernels**:
   ```bash
   cd hw1-asr
   ./run.sh --profile
   ```
   *Verifies kernel numerical accuracy against CPU reference and outputs execution timings.*

### B. RAG Reranking & End-to-End Pipeline Execution
1. **Configure API Key**:
   Create `rag/.env` with your University ELM API key:
   ```bash
   echo "ELM_API_KEY=your_elm_api_key_here" > rag/.env
   ```

2. **Run End-to-End Audio Question Answering**:
   ```bash
   cd rag
   python scripts/run_audio_query.py --audio data/rag_corpus/test_audio.wav --reranker rrf --k 5
   ```

3. **Execute Reranking Evaluation Sweeps (Practice Split)**:
   ```bash
   cd rag
   python scripts/evaluate_reranking.py --split practice --method rrf --reranker ms-marco-MiniLM-L-6-v2 --top_n 20
   ```

---

## 5. Anonymity & Clean Submission Notes
* All personal author metadata, UUNs, student names, and absolute file system paths have been removed.
* All Git commit logs and API credentials have been excluded.
* Model weights and full datasets are excluded per submission instructions; only source code, configuration files, and script launchers are included.
