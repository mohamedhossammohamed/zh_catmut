# Native/Python Systems Implementation Plan

This file is the implementation prompt and production coding plan for the agent
that will draft the native/Python package. It includes the compiled Phase 2
research and strict implementation constraints.

The exact C-ABI contract is defined separately in:

- `NATIVE_EXTENSION_API_CONTRACT.md`

The implementation agent must read that API contract first and implement it
exactly.

## Non-Negotiable Constraints

1. **Production implementation only.**
   - Do not create unit tests.
   - Do not create integration tests.
   - Do not create benchmarks.
   - Do not create `tests/`, `benchmarks/`, `test_*.py`, `*_test.py`, or
     benchmark scripts.
2. **Strict C-ABI boundary.**
   - Python may pass raw pointers, lengths, primitive integers, flags, and POD
     report structs only.
   - Do not pass Python objects, Pandas objects, NumPy object arrays, strings,
     dictionaries, JSON, or serialized payloads into the native core.
3. **Predictive gating before mutation.**
   - Python must validate Python/Pandas/NumPy invariants before pointer export.
   - Native code must validate dtype, length arithmetic, code ranges, LUT
     ranges, target category ranges, and missing-sentinel policy before writing.
4. **Zero-config installation target.**
   - End users must install through normal `pip install`.
   - End users must not need a local Zig compiler, C compiler, or .NET SDK when
     installing prebuilt wheels.
5. **No hidden memory ownership transfers.**
   - V1 native functions borrow Python-owned buffers only.
   - V1 native functions do not allocate output buffers and do not return raw
     heap pointers.
   - Arrow PyCapsules are a future extension point only if native-owned memory
     is introduced later.

## Compiled Phase 2 Research Notes

### Problem Mechanics

- Pandas categoricals are dictionary encoded: a small `categories` array plus a
  dense integer `codes` array.
- The dense `codes` array is the payload that reaches hundreds of millions of
  rows. Depending on category cardinality, Pandas stores it as signed `int8`,
  `int16`, `int32`, or `int64`.
- The missing sentinel is normally `-1`.
- When two categorical dictionaries are misaligned, Pandas cannot compare codes
  safely. It may fall back to object mode, expanding a compact integer array into
  a massive array of Python object/string references.
- At 100M rows, object fallback can inflate memory from roughly 100-800 MB to
  multiple GB and destroy CPU locality through pointer chasing.
- High-level NumPy/Pandas workarounds such as `np.where`, `np.select`,
  `Series.map`, `replace`, `set_categories`, and `inplace=True` commonly create
  temporary masks, copied arrays, boxed Python integers, or CoW-triggered
  defensive copies.

### FFI Boundary Research

- The boundary must be crossed once per dataset, not once per row.
- `ctypes` is acceptable for batch execution because its microsecond-level call
  overhead is amortized across millions of elements.
- `ctypes.CDLL` should be used rather than `ctypes.PyDLL` so CPython releases
  the GIL during native execution.
- The native library must expose standard C symbols only.
- Zig exports must use `export fn`.
- C# NativeAOT exports would use `[UnmanagedCallersOnly]`, but V1 should use
  Zig as the primary implementation because it is lighter to cross-compile and
  easier to ship as a self-contained shared library.

### Memory Safety Research

- CPython is non-moving: a NumPy buffer will not be relocated while it is alive.
- Lifetime safety is still required: Python must keep the backing arrays alive
  during the native call.
- The native function must receive the base pointer and logical length together.
- NumPy arrays can be sliced or strided; V1 must reject non-contiguous arrays in
  Python before pointer export.
- Pandas categorical codes are intentionally read-only and Pandas 3.0 Copy-on-
  Write semantics make blind mutation dangerous.
- The Python layer must own the Pandas safety gate:
  - signed integer dtype only;
  - 1D only;
  - C-contiguous only;
  - writable or temporarily made writable under a controlled context;
  - ownership/CoW status must be proven or the call must fail/fallback;
  - after mutation, reattach with `pd.Categorical.from_codes(..., validate=False)`
    to refresh Pandas metadata safely.
- Directly mutating an existing Pandas object without reattachment risks stale
  caches and CoW violations.

### Algorithm Research

- The V1 operation should be dense LUT remapping:

  ```text
  new_code = lut[old_code]
  ```

- Python constructs the LUT from the small category metadata. The native core
  only sees integer codes and the integer LUT.
- Missing values use the sentinel `-1`; when allowed, they are preserved or
  produced by the LUT.
- The native loop should be sequential and contiguous for cache locality.
- Parallel execution is useful for huge arrays but must chunk on cache-line or
  page-aligned boundaries to reduce false sharing.
- SIMD gather over large random LUTs is usually poor. V1 should prioritize a
  simple, predictable scalar loop that LLVM can autovectorize where possible.
  Specialized shuffle/SIMD kernels can be added later for very small LUTs.
- Native validation must occur before in-place writes if the caller sets
  `ZHCM_FLAG_VALIDATE_INPUT`, which Python must do by default.

### Packaging and Runtime Loading Research

- Use prebuilt wheels via `cibuildwheel`.
- Use manylinux containers on Linux; inject Zig in `CIBW_BEFORE_ALL_LINUX`.
- Zig can target glibc/musl variants more easily than NativeAOT and avoids the
  manylinux_2_28 NativeAOT constraint for V1.
- Runtime loading should use `importlib.resources.files(...)` and
  `importlib.resources.as_file(...)`, not `ctypes.util.find_library`.
- On Windows, call `os.add_dll_directory(package_dir)` before loading if needed.
- The native shared library should live inside the Python package directory as
  package data:
  - Linux: `libzh_catmut.so`
  - macOS: `libzh_catmut.dylib`
  - Windows: `zh_catmut.dll`

## Chosen V1 Architecture

Implement a Zig shared library loaded from Python through `ctypes`.

V1 is intentionally narrower than the full Arrow PyCapsule architecture:

- It solves the immediate bottleneck by remapping the dense categorical codes
  buffer in place.
- It does not pass category strings across the C-ABI.
- It does not allocate native-owned Arrow buffers.
- It leaves category-label reconciliation and LUT construction in Python because
  categories are small relative to the codes array.
- It preserves an Arrow/PyCapsule migration path for future native-owned output.

## Public Python API Shape

Implement a minimal public API in `src/zh_catmut/__init__.py`:

```python
from ._categorical import remap_categorical, remap_codes_inplace

__all__ = ["remap_categorical", "remap_codes_inplace"]
```

### `remap_codes_inplace`

Low-level API for callers that already have a writable, uniquely owned NumPy
codes array and a dense LUT.

```python
def remap_codes_inplace(
    codes: np.ndarray,
    lut: np.ndarray,
    *,
    target_category_count: int,
    missing_code: int = -1,
    allow_missing: bool = True,
    threads: int = 0,
) -> NativeExecutionReport:
    ...
```

Rules:

- `codes` must be 1D, C-contiguous, signed integer dtype in int8/int16/int32/int64.
- `lut` must be 1D, C-contiguous, int64.
- Python calls `zhcm_predict_remap_lut`.
- Python calls `zhcm_remap_lut_inplace` with `ZHCM_FLAG_VALIDATE_INPUT`.
- Python raises a typed exception on any non-zero status.

### `remap_categorical`

High-level Pandas API for category label remapping.

```python
def remap_categorical(
    obj: pd.Series | pd.Categorical,
    mapping: Mapping[object, object],
    *,
    assume_unique: bool = False,
    copy_fallback: bool = False,
    threads: int = 0,
) -> pd.Series | pd.Categorical:
    ...
```

Rules:

- Build `new_categories` and dense `int64` LUT in Python from category metadata.
- Extract the internal codes array without copying.
- If unique ownership cannot be proven:
  - if `copy_fallback` is `False`, raise a safety error before mutation;
  - if `copy_fallback` is `True`, allocate Python-owned destination codes and
    call `zhcm_remap_lut_copy`.
- If `assume_unique` is `True`, allow the controlled in-place path after all
  dtype/shape/range gates pass.
- Reattach with `pd.Categorical.from_codes(mutated_codes, categories=new_categories, validate=False)`.
- If input is a `Series`, return a `Series` preserving name and index.
- Do not mutate category labels through undocumented Pandas cache internals.

## File-by-File Coding Plan

### `include/zh_catmut_abi.h`

Create the exact C header from `NATIVE_EXTENSION_API_CONTRACT.md`.

This header is the single source of truth for:

- ABI version;
- dtype enum values;
- status enum values;
- flag bitmasks;
- gate report layout;
- execution report layout;
- exported C function signatures.

### `native/build.zig`

Create a Zig build graph that:

- builds a shared library named `zh_catmut`;
- compiles `native/src/root.zig`;
- uses `ReleaseFast` by default for wheel builds;
- accepts target and optimize options from setuptools/cibuildwheel;
- emits:
  - `libzh_catmut.so` on Linux;
  - `libzh_catmut.dylib` on macOS;
  - `zh_catmut.dll` on Windows.

Initial draft structure:

```zig
const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{ .preferred_optimize_mode = .ReleaseFast });

    const lib = b.addSharedLibrary(.{
        .name = "zh_catmut",
        .root_source_file = b.path("src/root.zig"),
        .target = target,
        .optimize = optimize,
    });

    lib.linkLibC();
    b.installArtifact(lib);
}
```

### `native/src/root.zig`

Implement the C-ABI exports:

- `zhcm_abi_version`
- `zhcm_status_message`
- `zhcm_predict_remap_lut`
- `zhcm_remap_lut_inplace`
- `zhcm_remap_lut_copy`

Implementation guidance:

- Use `export fn` for every ABI function.
- Use `callconv(.C)` where appropriate for explicit ABI clarity.
- Convert raw pointers to typed slices only after null, dtype, and length gates.
- Dispatch by dtype to a generic function:

```zig
fn remapInplaceTyped(comptime T: type, codes: []T, lut: []const i64, target_category_count: usize, missing_code: i64) Status {
    for (codes) |*code| {
        const old: i64 = @intCast(code.*);
        if (old == missing_code) continue;
        const mapped = lut[@intCast(old)];
        code.* = @intCast(mapped);
    }
    return .ok;
}
```

Required safety behavior:

- `zhcm_predict_remap_lut` must never write.
- If `ZHCM_FLAG_VALIDATE_INPUT` is set, mutation functions must validate first
  and return before writing on failure.
- `item_count * sizeof(dtype)` must be checked for integer overflow.
- Reject null `codes_ptr` when `item_count > 0`.
- Reject null `lut_ptr` when `lut_len > 0`.
- Reject non-missing codes outside `[0, lut_len)`.
- Reject non-missing mapped codes outside `[0, target_category_count)`.
- Preserve or reject missing values according to `ZHCM_FLAG_ALLOW_MISSING`.
- Do not allocate in the in-place hot path.
- Do not call Python C-API.

Parallel execution:

- Implement scalar first.
- Add parallel path only behind `ZHCM_FLAG_PARALLEL`.
- Split work into non-overlapping contiguous chunks.
- Align chunk starts to at least 64-byte boundaries when practical.
- Do not spawn detached work; all threads must join before return.

### `src/zh_catmut/_abi.py`

Define Python constants and ctypes structs matching `include/zh_catmut_abi.h`.

Initial draft:

```python
import ctypes

ZHCM_ABI_VERSION = 1

ZHCM_DTYPE_I8 = 1
ZHCM_DTYPE_I16 = 2
ZHCM_DTYPE_I32 = 3
ZHCM_DTYPE_I64 = 4

ZHCM_OK = 0
ZHCM_FLAG_ALLOW_MISSING = 0x1
ZHCM_FLAG_VALIDATE_INPUT = 0x2
ZHCM_FLAG_COLLECT_COUNTS = 0x4
ZHCM_FLAG_PARALLEL = 0x8


class ZhcmGateReport(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("status", ctypes.c_int32),
        ("flags", ctypes.c_uint64),
        ("item_count", ctypes.c_uint64),
        ("lut_len", ctypes.c_uint64),
        ("target_category_count", ctypes.c_uint64),
        ("invalid_input_count", ctypes.c_uint64),
        ("invalid_output_count", ctypes.c_uint64),
        ("missing_count", ctypes.c_uint64),
        ("first_invalid_index", ctypes.c_uint64),
        ("first_invalid_code", ctypes.c_int64),
        ("first_invalid_mapped_code", ctypes.c_int64),
    ]


class ZhcmExecReport(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("status", ctypes.c_int32),
        ("flags", ctypes.c_uint64),
        ("item_count", ctypes.c_uint64),
        ("changed_count", ctypes.c_uint64),
        ("missing_count", ctypes.c_uint64),
        ("invalid_input_count", ctypes.c_uint64),
        ("invalid_output_count", ctypes.c_uint64),
        ("first_invalid_index", ctypes.c_uint64),
        ("first_invalid_code", ctypes.c_int64),
        ("first_invalid_mapped_code", ctypes.c_int64),
    ]
```

### `src/zh_catmut/_loader.py`

Implement platform-aware dynamic loading.

Requirements:

- Use `importlib.resources.files("zh_catmut")`.
- Use `as_file(...)` so zipped or non-filesystem installs can still resolve a
  physical path.
- Resolve library filename by platform.
- On Windows, wrap loading with `os.add_dll_directory(package_dir)`.
- Use `ctypes.CDLL`.
- Declare exact `argtypes` and `restype`.
- Verify `zhcm_abi_version() == ZHCM_ABI_VERSION` at import/load time.

Initial draft:

```python
import ctypes
import os
import platform
from contextlib import ExitStack
from importlib.resources import as_file, files

from ._abi import *


def _library_name() -> str:
    system = platform.system()
    if system == "Windows":
        return "zh_catmut.dll"
    if system == "Darwin":
        return "libzh_catmut.dylib"
    return "libzh_catmut.so"


def load_native():
    resource = files("zh_catmut").joinpath(_library_name())
    stack = ExitStack()
    path = stack.enter_context(as_file(resource))
    if os.name == "nt":
        stack.enter_context(os.add_dll_directory(str(path.parent)))

    lib = ctypes.CDLL(str(path))
    _declare_signatures(lib)
    if lib.zhcm_abi_version() != ZHCM_ABI_VERSION:
        raise RuntimeError("zh_catmut native ABI version mismatch")
    return lib, stack
```

Keep the `ExitStack` alive for the lifetime of the loaded library by storing it
in a module-level variable.

### `src/zh_catmut/_errors.py`

Define production exceptions:

- `ZhCatmutError`
- `NativeLibraryLoadError`
- `NativeStatusError`
- `MemoryGateError`
- `CopyOnWriteSafetyError`

No test helpers.

### `src/zh_catmut/_types.py`

Implement dtype mapping and small report wrappers.

Requirements:

- Map `np.int8` to `ZHCM_DTYPE_I8`.
- Map `np.int16` to `ZHCM_DTYPE_I16`.
- Map `np.int32` to `ZHCM_DTYPE_I32`.
- Map `np.int64` to `ZHCM_DTYPE_I64`.
- Reject unsigned, floating, boolean, object, nullable extension, and non-NumPy
  dtypes before native invocation.

### `src/zh_catmut/_gates.py`

Implement Python-side predictive gates.

Required checks:

- `codes` is a NumPy ndarray.
- `codes.ndim == 1`.
- `codes.flags.c_contiguous` is true.
- `codes.dtype` is supported signed integer.
- `lut` is a NumPy ndarray.
- `lut.dtype == np.int64`.
- `lut.ndim == 1`.
- `lut.flags.c_contiguous` is true.
- `target_category_count >= 0`.
- `len(lut)` fits in `ctypes.c_size_t`.
- `codes.size` fits in `ctypes.c_size_t`.
- For high-level Pandas API, reject mutation if CoW/ownership safety cannot be
  established and `copy_fallback` is false.

Writeability handling:

- Use a context manager that stores the original NumPy `writeable` flag.
- Set `writeable=True` only immediately before native mutation.
- Restore the original flag in `finally`.

### `src/zh_catmut/_categorical.py`

Implement public operations.

#### Low-level `remap_codes_inplace`

Flow:

1. Run `_gates.validate_codes_array`.
2. Run `_gates.validate_lut_array`.
3. Convert pointers:

   ```python
   codes_ptr = codes.ctypes.data_as(ctypes.c_void_p)
   lut_ptr = lut.ctypes.data_as(ctypes.POINTER(ctypes.c_int64))
   ```

4. Call `zhcm_predict_remap_lut`.
5. Raise on non-zero status.
6. Temporarily ensure writeability.
7. Call `zhcm_remap_lut_inplace` with:
   - `ZHCM_FLAG_ALLOW_MISSING` when requested;
   - `ZHCM_FLAG_VALIDATE_INPUT`;
   - `ZHCM_FLAG_PARALLEL` when `threads != 1`.
8. Raise on non-zero status.
9. Return a production report object.

#### High-level `remap_categorical`

Flow:

1. Accept `pd.Series` or `pd.Categorical`.
2. Extract `cat = obj.array` for Series or `cat = obj` for Categorical.
3. Read `old_categories = list(cat.categories)`.
4. Build `new_categories` by applying `mapping` to category labels while
   preserving stable order and deduplicating.
5. Build dense `lut: np.ndarray[np.int64]` where each old category index maps to
   the new category index.
6. Extract `codes` through a single helper that avoids copies and verifies memory
   sharing.
7. If ownership is safe or `assume_unique=True`, call `remap_codes_inplace`.
8. Otherwise, if `copy_fallback=True`, allocate destination codes in Python and
   call `zhcm_remap_lut_copy`.
9. Reattach:

   ```python
   new_cat = pd.Categorical.from_codes(
       codes,
       categories=new_categories,
       ordered=cat.ordered,
       validate=False,
   )
   ```

10. Return a Series preserving index/name when the input was a Series.

Do not mutate Pandas private category metadata in place.

### `src/zh_catmut/__init__.py`

Expose only production public API:

```python
from ._categorical import remap_categorical, remap_codes_inplace

__all__ = ["remap_categorical", "remap_codes_inplace"]
```

### `src/zh_catmut/py.typed`

Include an empty marker file so type checkers recognize inline types.

### `pyproject.toml`

Use setuptools as the build backend.

Required sections:

- `[build-system]` with `setuptools` and `wheel`.
- `[project]` metadata.
- Runtime dependencies: `numpy` and `pandas`.
- Package discovery under `src`.
- Include native library package data.

Do not add test dependencies.

### `setup.py`

Implement custom native build orchestration.

Requirements:

- Invoke `zig build` as a subprocess.
- Pass target/optimization values derived from platform and cibuildwheel env.
- Copy the produced shared library into `build_lib/zh_catmut/`.
- Ensure the native binary is included in wheels.
- Do not require Zig at runtime.

The build command may fail with a clear message if building from source without
Zig installed. That is acceptable for source builds; prebuilt wheels remain
zero-config for users.

### `MANIFEST.in`

Include:

- `include/zh_catmut_abi.h`
- `native/build.zig`
- `native/src/root.zig`

Do not include test assets.

### `.github/workflows/wheels.yml`

Add wheel-building workflow only if the implementation scope includes CI.

Requirements:

- Use `pypa/cibuildwheel`.
- Build Linux/macOS/Windows wheels.
- Inject Zig in Linux manylinux containers with `CIBW_BEFORE_ALL_LINUX`.
- Use native macOS runners for x86_64 and arm64 when needed.
- Upload built wheels as artifacts.

Do not add test execution jobs.

## Initial Native Implementation Draft

The native code should start with a scalar, safe implementation and only then add
parallel execution behind a flag.

Pseudo-structure:

```zig
const std = @import("std");

const Status = enum(i32) {
    ok = 0,
    null_pointer = 1,
    unsupported_dtype = 2,
    invalid_length = 3,
    invalid_lut = 4,
    code_out_of_range = 5,
    target_out_of_range = 6,
    integer_overflow = 7,
    thread_failure = 8,
    python_gate_rejected = 50,
    internal = 255,
};

export fn zhcm_abi_version() callconv(.C) u32 {
    return 1;
}
```

Validation and mutation should be separate functions so `predict` and `remap`
share identical range logic.

## Initial Python Implementation Draft

The Python implementation should centralize all native status handling:

```python
def _raise_for_status(lib, status: int, context: str) -> None:
    if status == ZHCM_OK:
        return
    message = lib.zhcm_status_message(status).decode("utf-8", "replace")
    raise NativeStatusError(f"{context} failed: {message} ({status})")
```

The low-level call must keep `codes` and `lut` strongly referenced until the
native function returns:

```python
report = ZhcmExecReport()
status = lib.zhcm_remap_lut_inplace(
    ctypes.c_void_p(codes.ctypes.data),
    codes.size,
    dtype_code,
    lut.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)),
    lut.size,
    target_category_count,
    missing_code,
    threads,
    flags,
    ctypes.byref(report),
)
_raise_for_status(lib, status, "zhcm_remap_lut_inplace")
```

## Completion Criteria for the Coding Agent

The coding agent is complete when:

- all production files listed above are created;
- the native library exposes the exact C symbols in `NATIVE_EXTENSION_API_CONTRACT.md`;
- Python loads the bundled native binary via `importlib.resources` and `ctypes.CDLL`;
- the low-level and high-level production APIs exist;
- Python gates run before pointer export;
- native predictive validation runs before in-place mutation;
- no test files, benchmark files, or test dependencies are created.
