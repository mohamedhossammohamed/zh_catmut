# zh_catmut

`zh_catmut` is a native Python package for remapping large Pandas categorical code buffers through a narrow C ABI. It keeps category-label reconciliation in Python, where the metadata is small, and moves the full-column integer remap into a bundled Zig shared library.

## Problem

Pandas categoricals are dictionary encoded:

- `categories`: a small label dictionary.
- `codes`: a dense signed integer NumPy array with one element per row.

When category dictionaries are relabeled, merged, or realigned through high-level APIs, Pandas may allocate replacement code arrays, temporary masks, or object-mode intermediates. On large columns, those allocations dominate runtime and memory pressure.

`zh_catmut` targets the core operation:

```text
new_code = lut[old_code]
```

The Python layer builds the dense LUT from category metadata. The native layer remaps the contiguous integer payload in one batch.

## Installation

```bash
pip install zh-catmut
```

## Public API

```python
from zh_catmut import remap_categorical, remap_codes_inplace
```

### `remap_codes_inplace`

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

Low-level API for callers that already have a NumPy categorical codes buffer and a dense lookup table.

Parameters:

- `codes`: one-dimensional, C-contiguous NumPy ndarray with dtype `int8`, `int16`, `int32`, or `int64`.
- `lut`: one-dimensional, C-contiguous `np.int64` ndarray. Each non-missing source code indexes this array.
- `target_category_count`: number of categories in the target dictionary. Every non-missing mapped code must be in `[0, target_category_count)`.
- `missing_code`: missing sentinel. Defaults to `-1`, matching Pandas categorical codes.
- `allow_missing`: when `True`, missing input codes and LUT outputs equal to `missing_code` are accepted. When `False`, either case is rejected before mutation.
- `threads`: native thread request. The current implementation accepts the parameter and executes the scalar native remap path.

Return value:

- `NativeExecutionReport`, containing ABI version, status, flags, item count, changed count, missing count, invalid counts, and first invalid element information.

Safety behavior:

- Python validates shape, dtype, contiguity, integer bounds, and LUT dtype before pointer export.
- Native prediction runs before mutation.
- Read-only NumPy buffers are temporarily made writeable only for the native call and restored afterward.
- Invalid native statuses raise `NativeStatusError`.
- Python-side memory gate failures raise `MemoryGateError`.

### `remap_categorical`

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

High-level API for category label remapping.

Parameters:

- `obj`: a Pandas `Series` with categorical dtype or a `pd.Categorical`.
- `mapping`: label mapping. Categories not present in the mapping are preserved. Multiple old labels may map to the same new label.
- `assume_unique`: bypasses the high-level Copy-on-Write uniqueness check and allows controlled in-place mutation after all other gates pass.
- `copy_fallback`: when `True`, allocate a Python-owned destination codes buffer and use the native copy remap path. The original codes buffer is preserved.
- `threads`: forwarded to the low-level native call.

Return value:

- If the input is a `pd.Categorical`, returns a new `pd.Categorical`.
- If the input is a `pd.Series`, returns a new `pd.Series` preserving `index` and `name`.

Categorical semantics:

- The target category list is built from old categories after applying `mapping`.
- Target categories preserve first-seen order after deduplication.
- Missing values remain missing.
- The returned categorical is reattached with `pd.Categorical.from_codes(..., validate=False)` after native validation has proven code ranges.

## Exceptions

- `ZhCatmutError`: base exception.
- `NativeLibraryLoadError`: native library could not be loaded or ABI version mismatched.
- `NativeStatusError`: native function returned a non-zero status.
- `MemoryGateError`: Python-side dtype, shape, contiguity, or bounds gate failed.
- `CopyOnWriteSafetyError`: in-place high-level mutation was unsafe under Pandas Copy-on-Write checks.

## Native ABI

The bundled shared library exposes:

- `zhcm_abi_version`
- `zhcm_status_message`
- `zhcm_predict_remap_lut`
- `zhcm_remap_lut_inplace`
- `zhcm_remap_lut_copy`

See [`architecture.md`](architecture.md) for the boundary design.
