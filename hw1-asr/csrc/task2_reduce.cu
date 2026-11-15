// Task 2, part B: row-wise kernels built on the helpers in task2_reduce.cuh.
// Read docs/task2-reduce.md first.
//
// All three kernels work on a [rows, cols] matrix and use one block per row.
// The threads of a block walk along the row with a block-stride loop:
//
//     for (int c = threadIdx.x; c < cols; c += blockDim.x) ...
//
// so thread 0 handles columns 0, 256, 512, ..., thread 1 handles 1, 257, ...
// Neighbouring threads read neighbouring addresses, and any cols works.
#include "asr_kernels.h"
#include "task2_reduce.cuh"

#include "../../../../usr/include/math.h"

constexpr int REDUCE_THREADS = 256;  // threads per block: a multiple of 32, at most 1024

// Worked example. LayerNorm: y = (x - mean) / sqrt(var + eps) * weight + bias
__global__ void layernorm_kernel(const float* x, const float* weight, const float* bias,
                                 float* y, int cols, float eps) {
  const float* xr = x + static_cast<size_t>(blockIdx.x) * cols;  // this block's row
  float* yr = y + static_cast<size_t>(blockIdx.x) * cols;

  float sum = 0.0f;  // 1. mean
  for (int c = threadIdx.x; c < cols; c += blockDim.x) sum += xr[c];
  const float mean = block_reduce_sum(sum) / cols;

  float sq = 0.0f;   // 2. variance
  for (int c = threadIdx.x; c < cols; c += blockDim.x) {
    float d = xr[c] - mean;
    sq += d * d;
  }
  const float rstd = rsqrtf(block_reduce_sum(sq) / cols + eps);  // 1 / sqrt(var + eps)

  for (int c = threadIdx.x; c < cols; c += blockDim.x)  // 3. normalise and write
    yr[c] = (xr[c] - mean) * rstd * weight[c] + bias[c];
}

// // RMSNorm (text decoder): y = x / sqrt(mean(x^2) + eps) * weight
// __global__ void rmsnorm_kernel(const float* x, const float* weight, float* y, int cols,
//                                float eps) {
//   const float* xr = x + static_cast<size_t>(blockIdx.x) * cols;
//   float* yr = y + static_cast<size_t>(blockIdx.x) * cols;
//
//   // ======================== BLANK 2.5 =========================
//   // RMSNorm of this row: y = x / sqrt(mean(x^2) + eps) * weight.
//   // 1. Each thread calculates local sum of squares across frid stride
//   float sum_sq = 0.0f;
//   for (int i = threadIdx.x; i < cols; i += blockDim.x) {
//     float val = xr[i];
//     sum_sq += val * val;
//   }
//
//    // 2. Reduce total sum of squares across the block
//    float total_sum_sq = block_reduce_sum(sum_sq);
//
//   // 3. Compute scale facto: 1 / sqrt(mean(x^2) + eps)
//   float mean_sq = total_sum_sq / static_cast<float>(cols);
//   float rrms = rsqrtf(mean_sq + eps);
//
//   // 4. Normalize and apply weight
//   for (int i = threadIdx.x; i < cols; i += blockDim.x) {
//     yr[i] = xr[i] * rrms * weight[i];
//   }
//   // ============================================================
// }

// Vectorized RMSNorm: processes 4 floats (128 bits) per iteration
__global__ void rmsnorm_kernel(const float* x, const float* weight, float* y, int cols, float eps) {
  const float* xr = x + static_cast<size_t>(blockIdx.x) * cols;
  float* yr = y + static_cast<size_t>(blockIdx.x) * cols;

  // Check if all pointers are 16-byte (128-bit) aligned
  bool is_aligned = (reinterpret_cast<uintptr_t>(xr) % 16 == 0) &&
    (reinterpret_cast<uintptr_t>(weight) % 16 == 0) &&
      (reinterpret_cast<uintptr_t>(y) % 16 == 0) &&
        (cols % 4 == 0);

  float sum_sq = 0.0f;

  if (is_aligned) {
    // 1. Vectorized loop (4 floats per thread per stride)
    const int num_vecs = cols / 4;
    const float4* xr_vec = reinterpret_cast<const float4*>(xr);

    for (int i = threadIdx.x; i < num_vecs; i += blockDim.x) {
      float4 v = xr_vec[i];
      sum_sq += v.x * v.x + v.y * v.y + v.z * v.z + v.w * v.w;
    }
  } else {
    // Scalar fallback path
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
      float val = xr[i];
      sum_sq += val * val;
    }
  }

  // Reduce sum across block and compute reciprocal RMS scale factor
  float total_sum_sq = block_reduce_sum(sum_sq);
  float mean_sq = total_sum_sq / static_cast<float>(cols);
  float rrms = rsqrtf(mean_sq + eps);

  // Pass 2: Normalize & Store
  if (is_aligned) {
    const int num_vecs = cols / 4;
    const float4* xr_vec = reinterpret_cast<const float4*>(xr);
    const float4* weight_vec = reinterpret_cast<const float4*>(weight);
    float4* yr_vec = reinterpret_cast<float4*>(yr);

    for (int i = threadIdx.x; i < num_vecs; i += blockDim.x) {
      float4 vx = xr_vec[i];
      float4 vw = weight_vec[i];
      float4 vy;

      vy.x = vx.x * rrms * vw.x;
      vy.y = vx.y * rrms * vw.y;
      vy.z = vx.z * rrms * vw.z;
      vy.w = vx.w * rrms * vw.w;
      yr_vec[i] = vy;
    }
  } else {
    // 2. Scalar cleanup store for remaining elements
    for (int i = threadIdx.x; i < cols; i += blockDim.x) {
      yr[i] = xr[i] * rrms * weight[i];
    }
  }
}

// Softmax over each row: y = exp(x - max) / sum(exp(x - max)).
// The textbook version reads the row three times (max, sum, write). With the
// online-softmax MaxSum from part A, the first two passes become one.
__global__ void softmax_kernel(const float* x, float* y, int cols) {
  const float* xr = x + static_cast<size_t>(blockIdx.x) * cols;
  float* yr = y + static_cast<size_t>(blockIdx.x) * cols;

  float row_max = 0.0f;  // max of the whole row
  float row_sum = 1.0f;  // sum of exp(x - row_max) over the whole row
  // ======================== BLANK 2.6 =========================
  // Pass 1: set row_max and row_sum (the sum of exp(x - row_max) over the row),
  // reading x only once, with MaxSum.

  //1. Local accumulation per thread using MaxSum
  MaxSum ms = {-INFINITY, 0.0f};
  for (int i = threadIdx.x; i < cols; i += blockDim.x) {
    ms = maxsum_merge(ms, MaxSum{xr[i], 1.0f});
  }

  // 2. Intra-warp reduction of MaxSum structs
   for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
     MaxSum other;
     other.m = __shfl_xor_sync(0xffffffff, ms.m, offset);
     other.l = __shfl_xor_sync(0xffffffff, ms.l, offset);
     ms = maxsum_merge(ms, other);
   }

  // 3. Store warp results in shared memory
  __shared__ MaxSum partial[WARP_SIZE];
  const int lane = threadIdx.x % WARP_SIZE;
  const int warp = threadIdx.x / WARP_SIZE;
  const int num_warps = blockDim.x / WARP_SIZE;

  if (lane == 0) partial[warp] = ms;
  __syncthreads();

  // 4. Every warp loads partial[lane] and reduces again
  ms = (lane < num_warps) ? partial[lane] : MaxSum{-INFINITY, 0.0f};
  for (int offset = WARP_SIZE / 2; offset > 0; offset /= 2) {
    MaxSum other;
    other.m = __shfl_xor_sync(0xffffffff, ms.m, offset);
    other.l = __shfl_xor_sync(0xffffffff, ms.l, offset);
    ms = maxsum_merge(ms, other);
  }
  __syncthreads();

  row_max = ms.m;
  row_sum = ms.l;


  // ============================================================

  // ======================== BLANK 2.7 =========================
  // Pass 2: y = exp(x - row_max) / row_sum.
  float inv_row_sum = 1.0f / row_sum;
  for (int i = threadIdx.x; i < cols; i += blockDim.x) {
    yr[i] = expf(xr[i] - row_max) * inv_row_sum;
  }
  // ============================================================
}

ASR_API int launch_rmsnorm(const float* x, const float* weight, float* y, int rows,
                           int cols, float eps, cudaStream_t stream) {
  rmsnorm_kernel<<<rows, REDUCE_THREADS, 0, stream>>>(x, weight, y, cols, eps);
  RETURN_LAUNCH_ERROR();
}

ASR_API int launch_layernorm(const float* x, const float* weight, const float* bias,
                             float* y, int rows, int cols, float eps, cudaStream_t stream) {
  layernorm_kernel<<<rows, REDUCE_THREADS, 0, stream>>>(x, weight, bias, y, cols, eps);
  RETURN_LAUNCH_ERROR();
}

ASR_API int launch_softmax(const float* x, float* y, int rows, int cols,
                           cudaStream_t stream) {
  softmax_kernel<<<rows, REDUCE_THREADS, 0, stream>>>(x, y, cols);
  RETURN_LAUNCH_ERROR();
}
