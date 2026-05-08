# Changelog

## 0.2.0

- Removed reserved `threads` parameters from the Python and C ABI surfaces.
- Bumped native ABI to version 2 and added explicit pointer-alignment preflight checks.
- Switched high-level Pandas remapping to public-code extraction and explicit-copy defaults.
- Re-enabled Pandas `from_codes` validation for the returned categorical.
- Added `pd.CategoricalIndex` support and broader edge-case tests.
- Added NumPy and Pandas dependency lower bounds.

## 0.1.0

- Initial public release.
- Bundled Zig C ABI for dense categorical code LUT remapping.
- Python integration for Pandas `Series` and `Categorical` inputs.
- Native and Python validation for dtype, shape, contiguity, missing codes, and target code ranges.
