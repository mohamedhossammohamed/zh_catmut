# zh_catmut

![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![Native Core](https://img.shields.io/badge/native-Zig-orange)
![DataFrame](https://img.shields.io/badge/pandas-categorical-green)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)

**Remap huge Pandas categorical columns without expanding them into object arrays or allocating boolean masks.**

## Before / After

```python
# Before: high-level remapping can allocate temporary arrays or trigger
# categorical re-encoding work on the full column.
series = series.cat.rename_categories({"pending": "active"})
series = series.cat.set_categories(["active", "disabled"])

# After: build a dense metadata LUT, mutate integer categorical codes natively,
# and return a refreshed categorical object.
from zh_catmut import remap_categorical

series = remap_categorical(
    series,
    {"pending": "active", "disabled_old": "disabled"},
    copy_fallback=True,
)
```

## Installation

```bash
pip install zh-catmut
```

## Quickstart

```python
import pandas as pd
from zh_catmut import remap_categorical

s = pd.Series(pd.Categorical(["new", "old", "old", None]))
out = remap_categorical(s, {"old": "new"}, copy_fallback=True)
```

## Why it's fast

- Pandas categoricals store the full column as dense integer `codes`; category labels are only metadata.
- `zh_catmut` builds a small dense `int64` lookup table from category labels in Python.
- A bundled Zig shared library receives only raw pointers, lengths, primitive flags, and POD reports through a C ABI.
- The native loop remaps contiguous `int8`, `int16`, `int32`, or `int64` code buffers in one batch.
- `ctypes.CDLL` is used so the GIL is released while the native remap executes.
- Python runs shape, dtype, contiguity, writeability, and Copy-on-Write safety gates before exporting pointers.
- Native validation is all-or-nothing: invalid source codes, invalid target codes, null pointers, and oversized lengths are rejected before mutation.
- If in-place mutation is unsafe, `copy_fallback=True` uses a Python-owned destination buffer and keeps the source buffer unchanged.

## Public API

```python
from zh_catmut import remap_categorical, remap_codes_inplace
```

Use `remap_categorical` for Pandas objects and `remap_codes_inplace` only when you already own a writable, contiguous NumPy codes buffer and a dense `int64` LUT.

## Links

- GitHub profile: [mohamedhossammohamed](https://github.com/mohamedhossammohamed)
- X profile: [@MohamedHz72007](https://x.com/MohamedHz72007)
- License: [Apache-2.0](LICENSE)
