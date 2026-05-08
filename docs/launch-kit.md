# zh_catmut Launch Kit

This launch copy documents the actual V1 implementation: Python plus a bundled Zig native core through a C ABI.

## Hacker News

### Title

Show HN: zh_catmut - Native remapping for Pandas categorical code buffers

### First Comment

I built `zh_catmut` to target a specific Pandas bottleneck: relabeling or merging large categorical columns without expanding the data into object arrays or allocating large temporary masks.

Pandas categoricals are dictionary encoded. The full column is a dense integer `codes` buffer; the category labels are small metadata. `zh_catmut` keeps label reconciliation in Python, builds a dense `int64` lookup table, and sends only raw code-buffer pointers, lengths, dtype IDs, flags, and POD report structs across a strict C ABI.

The native core is Zig. It exposes stable C symbols loaded with `ctypes.CDLL`, so the GIL is released during the batch remap. Before mutation, Python checks dtype, contiguity, size bounds, writeability, and Pandas Copy-on-Write safety. Native code then runs a predictive validation pass over the codes and LUT. If any code or target is invalid, the in-place path does not write a single element.

V1 deliberately does not pass Python objects, Pandas objects, strings, dicts, JSON, or object arrays to native code. Python owns every buffer. For unsafe CoW cases, `copy_fallback=True` allocates a Python-owned destination array and uses the native copy path.

I am interested in critique on the ABI design, Pandas CoW gate, and whether the scalar LUT loop is the right V1 baseline before adding specialized SIMD/parallel kernels.

## Reddit

### r/Python

Title: Native LUT remapping for huge Pandas categorical columns

We all know the painful version of this: a categorical column is compact until you need to relabel, merge, or realign categories at scale, then high-level Pandas operations can allocate replacement arrays, temporary masks, or object-mode intermediates.

`zh_catmut` targets the integer payload directly. Pandas categoricals store labels as metadata and the full column as dense signed integer codes. The package builds a dense `int64` LUT from the category metadata, validates all Python/Pandas/NumPy invariants, then calls a bundled Zig shared library through a strict C ABI.

Usage:

```python
import pandas as pd
from zh_catmut import remap_categorical

s = pd.Series(pd.Categorical(["pending", "active", "old", None]))
out = remap_categorical(s, {"pending": "active", "old": "disabled"}, copy_fallback=True)
```

The native layer receives only raw pointers, lengths, dtype IDs, flags, and report structs. It does not see Python strings or Pandas objects. Native validation is all-or-nothing before mutation, and unsafe Pandas Copy-on-Write cases can use the copy fallback path.

Install:

```bash
pip install zh-catmut
```

### r/Zig

Title: Zig native core for remapping Pandas categorical code buffers through a C ABI

I used Zig for the native core of `zh_catmut`, a Python package that remaps Pandas categorical code buffers without passing Python objects into native code.

The Python side builds a dense `int64` LUT from category metadata, then calls exported Zig functions through `ctypes.CDLL`. The ABI accepts only pointers, lengths, dtype IDs, flags, and POD reports. Python owns all buffers; Zig borrows pointers only for the duration of each call.

The main exported functions:

- `zhcm_predict_remap_lut`
- `zhcm_remap_lut_inplace`
- `zhcm_remap_lut_copy`

The implementation starts with a scalar contiguous LUT remap for `int8`, `int16`, `int32`, and `int64` code buffers. The design leaves room for specialized SIMD/parallel kernels once the ABI and safety behavior are stable.

I would welcome feedback on the C ABI shape and Zig implementation strategy.

### r/dotnet

No `r/dotnet` launch copy is included because V1 is implemented in Zig, not C# NativeAOT. Publishing a .NET-focused post would misrepresent the code.

## X Short Launch Post

Published `zh_catmut`: a Python + Zig package for remapping huge Pandas categorical columns by touching the dense integer codes buffer directly, without expanding labels into object arrays.

Apache-2.0.

GitHub: https://github.com/mohamedhossammohamed/zh_catmut

## X Deep Architecture Thread

### Tweet 1

Deep dive on `zh_catmut`: a native remapping engine for Pandas categoricals.

The design goal is simple: keep label semantics in Python, move only the repetitive full-column integer loop to native code.

Repo: https://github.com/mohamedhossammohamed/zh_catmut

### Tweet 2

Decision map:

1. Treat Pandas categories as metadata.
2. Treat categorical `codes` as the real large payload.
3. Build a dense LUT in Python.
4. Send only primitive memory to native code.
5. Validate everything before mutation.

### Tweet 3

Why this exists:

Pandas categoricals are compact because the column stores integer codes, not repeated Python strings.

The pain starts when relabeling, merging, or aligning categories forces full-column work, replacement buffers, masks, or object-mode intermediates.

### Tweet 4

Core execution model:

```text
old_code -> lut[old_code] -> new_code
```

The category labels stay in Python. The native side only sees a contiguous signed integer code buffer and an `int64` lookup table.

### Tweet 5

Architecture split:

Python:

- reads old labels
- applies the mapping
- deduplicates target categories
- builds the LUT
- checks Pandas/NumPy safety

Zig:

- validates code and target ranges
- remaps the contiguous integer buffer
- returns a POD execution report

### Tweet 6

The C ABI is intentionally narrow.

Native functions receive only:

- raw pointers
- lengths
- dtype IDs
- flags
- caller-owned report structs

No Python objects, Pandas objects, strings, dicts, JSON, or object arrays cross the boundary.

### Tweet 7

Safety decision:

Mutation is all-or-nothing.

Before writing, native code runs a prediction pass that rejects invalid source codes, invalid mapped targets, missing-policy violations, null pointers, and oversized lengths.

If validation fails, the in-place path writes nothing.

### Tweet 8

CoW decision:

High-level in-place mutation is strict because Pandas storage may be shared.

When ownership is unclear:

```python
remap_categorical(series, mapping, copy_fallback=True)
```

This uses a Python-owned destination codes buffer.

### Tweet 9

Why Zig for V1:

The native primitive is small and explicit: a C ABI, integer dtype dispatch, validation, and a contiguous LUT loop.

Zig keeps the shared library compact, exports stable C symbols, and makes the memory contract easy to audit.

### Tweet 10

How it executes:

1. User calls `remap_categorical`.
2. Python builds target categories.
3. Python builds dense `np.int64` LUT.
4. Python gates dtype/shape/contiguity/bounds.
5. `ctypes.CDLL` calls Zig.
6. Zig validates.
7. Zig remaps.
8. Python reattaches a categorical.

### Tweet 11

The public API is intentionally small:

```python
from zh_catmut import remap_categorical, remap_codes_inplace
```

Use `remap_categorical` for Pandas objects.

Use `remap_codes_inplace` only when you own a writable, contiguous NumPy codes buffer and a dense LUT.

### Tweet 12

V1 baseline:

The first native kernel is a scalar contiguous LUT remap for `int8`, `int16`, `int32`, and `int64` code buffers.

The ABI leaves room for future SIMD and threaded kernels without changing the Python-facing model.

### Tweet 13

What I tried to avoid:

- native ownership of Python buffers
- passing objects across FFI
- hidden allocation in native code
- partial mutation after validation failure
- relying on Pandas internals without safety gates

The narrow boundary is the product.

### Tweet 14

`zh_catmut` is Apache-2.0.

I would love feedback on:

- the C ABI shape
- the Pandas CoW gate
- whether scalar LUT remap is the right V1 baseline
- where SIMD/threading should enter later

Repo: https://github.com/mohamedhossammohamed/zh_catmut
