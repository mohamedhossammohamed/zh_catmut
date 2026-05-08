# FFI and C ABI Architecture

`zh_catmut` uses a narrow C ABI between Python and Zig. Python owns all memory. Zig receives borrowed pointers, lengths, dtype IDs, flags, and caller-allocated report structs.

## Boundary rules

Native code must not:

- retain pointers after return;
- free Python-owned buffers;
- resize or reallocate inputs;
- call back into Python;
- inspect Pandas objects, labels, strings, dictionaries, or object arrays;
- write outside the logical element count.

Category labels stay in Python. Only integer code buffers and dense `int64` LUTs cross the ABI.

## Python gates

Before pointer export, Python checks:

- input is a NumPy ndarray;
- one-dimensional shape;
- C-contiguity;
- alignment;
- supported signed integer dtype;
- writeability for low-level in-place mutation;
- `np.int64` LUT dtype;
- `size_t` and `int64` bounds.

High-level Pandas remapping uses explicit-copy semantics by default to avoid relying on private Pandas ownership or Copy-on-Write internals.

## Native gates

The native ABI performs its own preflight:

- null pointer checks;
- length overflow checks;
- pointer alignment checks;
- source code range validation;
- LUT output range validation;
- missing-code policy validation.

`zhcm_predict_remap_lut` scans without writing. Mutating functions perform the same validation when `ZHCM_FLAG_VALIDATE_INPUT` is set, so validation failure is all-or-nothing.

## ABI functions

- `zhcm_abi_version`
- `zhcm_status_message`
- `zhcm_predict_remap_lut`
- `zhcm_remap_lut_inplace`
- `zhcm_remap_lut_copy`

The ABI version is bumped when exported signatures or report layouts change. Python verifies the loaded native library before use.

## Ownership model

- `zhcm_remap_lut_inplace` mutates a caller-owned, writable codes buffer.
- `zhcm_remap_lut_copy` reads a source codes buffer and writes a Python-allocated destination buffer.
- Reports are caller-allocated POD structs and are populated by native code.
