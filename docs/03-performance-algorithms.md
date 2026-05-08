# Performance Algorithms

`zh_catmut` accelerates categorical remapping by reducing the full-column operation to a dense integer lookup table (LUT) over Pandas categorical codes.

## Work split

The Python layer handles the small metadata problem:

1. Read category labels through public Pandas APIs.
2. Apply the user mapping once per category, not once per row.
3. Deduplicate target labels in first-seen order.
4. Build a dense `np.int64` LUT where `lut[old_code] = new_code`.

The Zig layer handles the large row-count problem:

```text
for code in codes:
    if code == missing_code:
        preserve missing_code
    else:
        code = lut[code]
```

This keeps labels, Python objects, dictionaries, and Pandas internals out of the native hot path.

## Complexity

Let `n` be the number of rows and `k` be the number of categories.

- LUT construction: `O(k)` Python work.
- Native validation: `O(n)` contiguous integer scan.
- Native remap: `O(n)` contiguous integer scan.
- High-level default output allocation: one Python-owned destination codes buffer.

The algorithm avoids per-row Python callbacks, object-array expansion, and boolean-mask fanout.

## Validation before mutation

Native execution is intentionally two-phase:

1. `zhcm_predict_remap_lut` checks source codes, LUT outputs, target category bounds, missing-code policy, pointer nullness, and pointer alignment without writing.
2. `zhcm_remap_lut_inplace` or `zhcm_remap_lut_copy` performs the remap only after validation succeeds.

For in-place mutation, validation failure is all-or-nothing: no element is written before invalid input is reported.

## Supported code widths

Pandas categorical codes are signed because `-1` is the missing sentinel. The native ABI supports the signed physical widths Pandas uses:

- `int8`
- `int16`
- `int32`
- `int64`

Unsigned, floating, object, strided, non-1D, unaligned, and read-only low-level buffers are rejected by Python gates before pointer export.

## Copy versus in-place

`remap_categorical` defaults to explicit copy semantics. It reads codes through public Pandas APIs, writes into a Python-owned destination buffer, and constructs the returned object with `pd.Categorical.from_codes(..., validate=True)`.

`remap_codes_inplace` remains available for callers that already own a writable, aligned, C-contiguous NumPy codes buffer and want direct mutation.

`remap_categorical(..., copy_fallback=False, assume_unique=True)` is an expert-only escape hatch for controlled in-place Pandas mutation after the same dtype, shape, alignment, range, and native validation gates pass.

## Cache behavior

The scalar native loop is memory-bandwidth oriented. It benefits from:

- sequential reads over the codes buffer;
- a dense LUT that is typically small enough to remain cache-resident;
- no Python object allocation inside the row loop;
- no per-row hash table lookup;
- no temporary boolean masks.

SIMD and threaded kernels can be added behind the same ABI only after benchmarks show they improve end-to-end runtime across realistic category counts and memory bandwidth constraints.
