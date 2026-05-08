# Categorical Internals and Memory

Pandas categoricals store repeated labels as dictionary-encoded integer codes:

- `categories`: the small ordered dictionary of unique labels.
- `codes`: the dense signed integer array that points into `categories`.
- `-1`: the missing-value sentinel used by Pandas categorical codes.

For large columns, almost all data lives in `codes`. A 100M-row `int8` categorical code buffer is roughly 100 MB; an `int32` buffer is roughly 400 MB. Remapping labels should therefore avoid expanding the column into Python objects or building large boolean masks.

## Why category remapping gets expensive

High-level relabeling or merging can allocate temporary arrays, re-factorize categories, or fall back to object-oriented paths when category dictionaries do not align. Those allocations dominate runtime and memory for large columns.

`zh_catmut` avoids that by doing only `O(k)` Python metadata work for `k` categories, then applying an `O(n)` native integer LUT over `n` rows.

## Public Pandas boundary

The high-level API reads categorical codes through public Pandas APIs and uses explicit-copy semantics by default. It does not depend on private Pandas attributes or block-manager reference internals.

The returned object is reconstructed with `pd.Categorical.from_codes(..., validate=True)`, preserving Pandas' final validation step even after native validation has passed.

## Supported physical dtypes

Pandas categorical codes are signed integer arrays because missing values use `-1`. The native ABI supports:

- `int8`
- `int16`
- `int32`
- `int64`

Unsupported unsigned, floating, object, non-contiguous, non-1D, unaligned, or read-only low-level buffers are rejected before pointer export.
