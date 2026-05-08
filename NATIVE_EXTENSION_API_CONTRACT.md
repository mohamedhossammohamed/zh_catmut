# Native Extension API Contract

This document is the exact production C-ABI contract for the first implementation
draft of `zh_catmut`, a zero-config Python package with a bundled native core for
large Pandas categorical code remapping.

The native boundary is intentionally narrow:

- Python owns every input and output buffer.
- The native library receives only raw pointers, integer lengths, primitive
  configuration values, and POD report structs.
- The native library never receives Python objects, Pandas objects, NumPy object
  arrays, JSON, strings, dictionaries, or serialized payloads.
- The native library never stores borrowed pointers after a function returns.
- The native library never frees memory allocated by Python.
- The native library never calls back into Python during the hot path.
- No unit tests, integration tests, benchmarks, or test scaffolding are part of
  this contract.

## Exact C Header

The implementation agent must create this header as `include/zh_catmut_abi.h`
and keep the native exports and Python `ctypes` declarations synchronized with
it exactly.

```c
#ifndef ZH_CATMUT_ABI_H
#define ZH_CATMUT_ABI_H

#include <stdint.h>
#include <stddef.h>

#if defined(_WIN32)
  #define ZHCM_API __declspec(dllexport)
#else
  #define ZHCM_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define ZHCM_ABI_VERSION 1u

/*
 * Physical signed integer dtype of the Pandas/NumPy categorical codes buffer.
 * These values are ABI-stable and must not be reordered.
 */
typedef enum zhcm_dtype_t {
    ZHCM_DTYPE_I8  = 1,
    ZHCM_DTYPE_I16 = 2,
    ZHCM_DTYPE_I32 = 3,
    ZHCM_DTYPE_I64 = 4
} zhcm_dtype_t;

/*
 * Stable status codes returned by every native operation.
 */
typedef enum zhcm_status_t {
    ZHCM_OK = 0,
    ZHCM_ERR_NULL_POINTER = 1,
    ZHCM_ERR_UNSUPPORTED_DTYPE = 2,
    ZHCM_ERR_INVALID_LENGTH = 3,
    ZHCM_ERR_INVALID_LUT = 4,
    ZHCM_ERR_CODE_OUT_OF_RANGE = 5,
    ZHCM_ERR_TARGET_OUT_OF_RANGE = 6,
    ZHCM_ERR_INTEGER_OVERFLOW = 7,
    ZHCM_ERR_THREAD_FAILURE = 8,
    ZHCM_ERR_PYTHON_GATE_REJECTED = 50,
    ZHCM_ERR_INTERNAL = 255
} zhcm_status_t;

/*
 * Bitflags accepted by prediction and execution functions.
 */
#define ZHCM_FLAG_ALLOW_MISSING   0x0000000000000001ull
#define ZHCM_FLAG_VALIDATE_INPUT  0x0000000000000002ull
#define ZHCM_FLAG_COLLECT_COUNTS  0x0000000000000004ull
#define ZHCM_FLAG_PARALLEL        0x0000000000000008ull

/*
 * Report populated by zhcm_predict_remap_lut before any mutation occurs.
 *
 * If no invalid input is found:
 * - status is ZHCM_OK.
 * - invalid_input_count and invalid_output_count are 0.
 * - first_invalid_index is UINT64_MAX.
 *
 * If invalid input is found:
 * - status identifies the first failure class.
 * - first_invalid_index points to the first offending logical element.
 * - first_invalid_code is the original code at that index.
 * - first_invalid_mapped_code is the LUT result when applicable.
 */
typedef struct zhcm_gate_report_t {
    uint32_t abi_version;
    int32_t status;
    uint64_t flags;
    uint64_t item_count;
    uint64_t lut_len;
    uint64_t target_category_count;
    uint64_t invalid_input_count;
    uint64_t invalid_output_count;
    uint64_t missing_count;
    uint64_t first_invalid_index;
    int64_t first_invalid_code;
    int64_t first_invalid_mapped_code;
} zhcm_gate_report_t;

/*
 * Report populated by mutation functions.
 *
 * If ZHCM_FLAG_COLLECT_COUNTS is not set, changed_count and missing_count may
 * be set to UINT64_MAX to avoid extra accounting overhead.
 */
typedef struct zhcm_exec_report_t {
    uint32_t abi_version;
    int32_t status;
    uint64_t flags;
    uint64_t item_count;
    uint64_t changed_count;
    uint64_t missing_count;
    uint64_t invalid_input_count;
    uint64_t invalid_output_count;
    uint64_t first_invalid_index;
    int64_t first_invalid_code;
    int64_t first_invalid_mapped_code;
} zhcm_exec_report_t;

/*
 * Return the native ABI version implemented by the loaded shared library.
 */
ZHCM_API uint32_t zhcm_abi_version(void);

/*
 * Return a static, null-terminated status message for a zhcm_status_t value.
 *
 * Ownership:
 * - Returned pointer is owned by the native library.
 * - Python must not free it.
 * - Pointer remains valid for the process lifetime.
 */
ZHCM_API const char *zhcm_status_message(int32_t status);

/*
 * Predictive safety gate for LUT remapping.
 *
 * This function scans the codes buffer and LUT without writing to any buffer.
 * Python must call it before zhcm_remap_lut_inplace unless it intentionally
 * opts out of validation for an expert-only fast path.
 *
 * Arguments:
 * - codes_ptr: borrowed pointer to a contiguous signed integer codes buffer.
 * - item_count: logical number of elements in codes_ptr.
 * - dtype: one of ZHCM_DTYPE_I8/I16/I32/I64.
 * - lut_ptr: borrowed pointer to int64 LUT values.
 * - lut_len: number of entries in lut_ptr.
 * - target_category_count: number of categories in the post-remap dictionary.
 * - missing_code: missing sentinel, normally -1 for Pandas categoricals.
 * - flags: ZHCM_FLAG_* bitmask.
 * - out_report: optional pointer to a caller-allocated report struct.
 *
 * Semantics:
 * - A non-missing old code must satisfy 0 <= old_code < lut_len.
 * - lut_ptr[old_code] is the target code.
 * - A non-missing target code must satisfy
 *   0 <= target_code < target_category_count.
 * - If ZHCM_FLAG_ALLOW_MISSING is set, missing_code is preserved and LUT
 *   entries may also map to missing_code.
 * - If ZHCM_FLAG_ALLOW_MISSING is not set, missing_code in either input or
 *   output is rejected.
 *
 * Ownership:
 * - codes_ptr and lut_ptr are borrowed for the duration of the call only.
 * - Native code must not retain, free, resize, or reallocate either pointer.
 */
ZHCM_API int32_t zhcm_predict_remap_lut(
    const void *codes_ptr,
    uintptr_t item_count,
    uint32_t dtype,
    const int64_t *lut_ptr,
    uintptr_t lut_len,
    uintptr_t target_category_count,
    int64_t missing_code,
    uint64_t flags,
    zhcm_gate_report_t *out_report
);

/*
 * In-place LUT remapping.
 *
 * This function mutates codes_ptr directly. If ZHCM_FLAG_VALIDATE_INPUT is set,
 * it must perform the same predictive validation as zhcm_predict_remap_lut
 * before writing the first element. If validation fails, no writes may occur.
 *
 * Arguments are identical to zhcm_predict_remap_lut, plus:
 * - thread_count: 0 means native auto-selection; 1 means scalar single-thread;
 *   values >1 request explicit parallel execution when ZHCM_FLAG_PARALLEL is set.
 * - out_report: optional pointer to a caller-allocated execution report.
 *
 * Ownership:
 * - codes_ptr remains owned by Python.
 * - lut_ptr remains owned by Python.
 * - Native code mutates only the item_count logical elements of codes_ptr.
 * - Native code must not write outside the buffer.
 * - Native code must not retain any pointer after return.
 */
ZHCM_API int32_t zhcm_remap_lut_inplace(
    void *codes_ptr,
    uintptr_t item_count,
    uint32_t dtype,
    const int64_t *lut_ptr,
    uintptr_t lut_len,
    uintptr_t target_category_count,
    int64_t missing_code,
    uint32_t thread_count,
    uint64_t flags,
    zhcm_exec_report_t *out_report
);

/*
 * Copying LUT remapping for CoW fallback.
 *
 * This function reads src_codes_ptr and writes dst_codes_ptr. Python allocates
 * both buffers and owns both buffers. The native library never allocates or
 * frees them.
 *
 * Use this only when Python cannot prove that in-place mutation is safe under
 * Pandas Copy-on-Write semantics. It preserves the same C-ABI boundary and
 * primitive-only crossing, but it is not the preferred zero-copy path.
 */
ZHCM_API int32_t zhcm_remap_lut_copy(
    const void *src_codes_ptr,
    void *dst_codes_ptr,
    uintptr_t item_count,
    uint32_t dtype,
    const int64_t *lut_ptr,
    uintptr_t lut_len,
    uintptr_t target_category_count,
    int64_t missing_code,
    uint32_t thread_count,
    uint64_t flags,
    zhcm_exec_report_t *out_report
);

#ifdef __cplusplus
}
#endif

#endif /* ZH_CATMUT_ABI_H */
```

## Python `ctypes` Contract

The Python wrapper must load the native library with `ctypes.CDLL`, not
`ctypes.PyDLL`, so the GIL is released while the native function executes.

The wrapper must declare exact `argtypes` and `restype` for every symbol:

```python
lib.zhcm_abi_version.argtypes = []
lib.zhcm_abi_version.restype = ctypes.c_uint32

lib.zhcm_status_message.argtypes = [ctypes.c_int32]
lib.zhcm_status_message.restype = ctypes.c_char_p

lib.zhcm_predict_remap_lut.argtypes = [
    ctypes.c_void_p,      # const void *codes_ptr
    ctypes.c_size_t,      # uintptr_t item_count
    ctypes.c_uint32,      # uint32_t dtype
    ctypes.POINTER(ctypes.c_int64),
    ctypes.c_size_t,      # uintptr_t lut_len
    ctypes.c_size_t,      # uintptr_t target_category_count
    ctypes.c_int64,       # int64_t missing_code
    ctypes.c_uint64,      # uint64_t flags
    ctypes.POINTER(ZhcmGateReport),
]
lib.zhcm_predict_remap_lut.restype = ctypes.c_int32

lib.zhcm_remap_lut_inplace.argtypes = [
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_int64),
    ctypes.c_size_t,
    ctypes.c_size_t,
    ctypes.c_int64,
    ctypes.c_uint32,
    ctypes.c_uint64,
    ctypes.POINTER(ZhcmExecReport),
]
lib.zhcm_remap_lut_inplace.restype = ctypes.c_int32

lib.zhcm_remap_lut_copy.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_size_t,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_int64),
    ctypes.c_size_t,
    ctypes.c_size_t,
    ctypes.c_int64,
    ctypes.c_uint32,
    ctypes.c_uint64,
    ctypes.POINTER(ZhcmExecReport),
]
lib.zhcm_remap_lut_copy.restype = ctypes.c_int32
```

## Boundary Ownership Rules

### Borrowed Python Buffers

`codes_ptr`, `src_codes_ptr`, `dst_codes_ptr`, and `lut_ptr` are borrowed memory
addresses. The Python wrapper is responsible for keeping the backing NumPy
arrays alive for the entire native call.

Native code must not:

- call `free` on these pointers;
- call any Python C-API function with these pointers;
- store them in global state;
- spawn detached work that outlives the call;
- assume any lifetime beyond the current function invocation.

### Native Mutation Rules

`zhcm_remap_lut_inplace` may write only to `codes_ptr[0:item_count]`.
`zhcm_remap_lut_copy` may write only to `dst_codes_ptr[0:item_count]`.
All other inputs are read-only.

### Missing Values

Pandas categoricals use `-1` as the missing sentinel. The wrapper must pass
`missing_code = -1` unless a future API explicitly supports another encoding.

### Mapping Semantics

The LUT is dense and zero-based:

```text
new_code = lut_ptr[old_code]
```

The Python wrapper must construct the LUT from category labels because labels
are small metadata. The native core must never receive Python strings or Pandas
objects.

### Predictive Gating

The full gate sequence is:

1. Python validates shape, dtype, contiguity, writeability, and Pandas ownership.
2. Python builds a contiguous `int64` LUT.
3. Python calls `zhcm_predict_remap_lut`.
4. If prediction returns non-zero, Python raises before any mutation.
5. Python calls `zhcm_remap_lut_inplace` with `ZHCM_FLAG_VALIDATE_INPUT`.
6. Python resets any temporarily modified NumPy writeability flag.
7. Python reattaches mutated codes via `pd.Categorical.from_codes(..., validate=False)`.

The native predictive gate can validate only what is visible at the C-ABI layer:
null pointers, supported dtype, length arithmetic, input code range, LUT range,
target category range, and missing-sentinel policy. Python-specific safety such
as Pandas Copy-on-Write sharing must be handled in Python before pointer export.
