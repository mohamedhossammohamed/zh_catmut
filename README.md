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

Verify the installed wheel and bundled native library:

```bash
zh-catmut doctor
```

The import package name uses an underscore:

```python
import zh_catmut
```

## Quickstart

```python
import pandas as pd
from zh_catmut import remap_categorical

s = pd.Series(pd.Categorical(["new", "old", "old", None]))
out = remap_categorical(s, {"old": "new"}, copy_fallback=True)
```

`copy_fallback=True` is the safest default for application code because it allocates a Python-owned destination codes buffer and keeps the original object unchanged.

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

### `remap_categorical`

```python
remap_categorical(
    obj,
    mapping,
    *,
    assume_unique=False,
    copy_fallback=False,
    threads=0,
)
```

- `obj`: a Pandas `Series` with categorical dtype or a `pd.Categorical`.
- `mapping`: mapping from old labels to new labels. Labels not present in the mapping are preserved.
- `copy_fallback`: when `True`, allocate a destination codes buffer and avoid in-place ownership risk.
- `assume_unique`: expert-only escape hatch for controlled in-place mutation after all other gates pass.
- `threads`: accepted by the native ABI. The current V1 kernel uses the scalar remap path.

### `remap_codes_inplace`

```python
remap_codes_inplace(
    codes,
    lut,
    *,
    target_category_count,
    missing_code=-1,
    allow_missing=True,
    threads=0,
)
```

- `codes`: one-dimensional, C-contiguous NumPy array with dtype `int8`, `int16`, `int32`, or `int64`.
- `lut`: one-dimensional, C-contiguous `np.int64` lookup table.
- `target_category_count`: every mapped non-missing code must be in `[0, target_category_count)`.
- `missing_code`: default `-1`, matching Pandas categorical codes.
- `allow_missing`: when `False`, missing input or missing LUT output is rejected before mutation.

## Command-line help for installed users

`zh-catmut` installs a small diagnostic CLI:

```bash
zh-catmut --help
zh-catmut info
zh-catmut example
zh-catmut doctor
python -m zh_catmut doctor
```

- `info` prints the project purpose, install command, API summary, and support links.
- `example` prints a minimal `copy_fallback=True` Pandas example.
- `doctor` verifies NumPy/Pandas imports, native library loading, ABI version, and low/high-level remap smoke tests.
- If your Python user scripts directory is not on `PATH`, use `python -m zh_catmut ...` instead of `zh-catmut ...`.

## Troubleshooting

### `NativeLibraryLoadError`

Run:

```bash
zh-catmut doctor
```

If the package was installed from a wheel, reinstall:

```bash
python -m pip install --force-reinstall zh-catmut
```

If pip built from source, Zig must be installed and visible as `zig` on `PATH`, or set:

```bash
ZIG=/path/to/zig python -m pip install zh-catmut
```

### Copy-on-Write safety errors

For ordinary Pandas application code, prefer:

```python
out = remap_categorical(series, mapping, copy_fallback=True)
```

Use `assume_unique=True` only when you control the object lifetime and know the underlying categorical codes buffer is not shared.

### Supported runtime inputs

- Python 3.9+
- CPython
- NumPy + Pandas
- Pandas categorical codes backed by contiguous signed integer arrays
- Code dtypes: `int8`, `int16`, `int32`, `int64`

## Links

- GitHub profile: [mohamedhossammohamed](https://github.com/mohamedhossammohamed)
- X profile: [@MohamedHz72007](https://x.com/MohamedHz72007)
- License: [Apache-2.0](LICENSE)
