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

## X Thread

### Tweet 1

Pandas categoricals are memory-efficient until relabeling or category alignment forces large temporary arrays or object-mode fallbacks.

`zh_catmut` remaps the dense integer code buffer directly through a native C ABI.

### Tweet 2

Python builds the category LUT and validates Pandas/NumPy safety; a bundled Zig shared library receives only raw pointers, lengths, flags, and POD reports, then remaps the contiguous codes in one batch.

### Tweet 3

Install:

```bash
pip install zh-catmut
```

GitHub: `<your GitHub repository URL>`
