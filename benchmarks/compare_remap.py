"""Benchmark: zh_catmut remap_categorical vs pandas equivalent.

Shows the core value proposition: merging categories (many-to-one mapping)
where pandas has no native fast path.

Run from the repo root:
    python benchmarks/compare_remap.py
"""
from __future__ import annotations

import gc
import time
from typing import Callable

import numpy as np
import pandas as pd

from zh_catmut import remap_categorical


def _make_series(n: int) -> pd.Series:
    rng = np.random.default_rng(42)
    codes = rng.integers(0, 4, size=n)
    cat = pd.Categorical.from_codes(
        codes,
        categories=["pending", "active", "disabled", "archived"],
    )
    return pd.Series(cat)


def _timed(label: str, fn: Callable[[], object]) -> float:
    gc.collect()
    t0 = time.perf_counter()
    fn()
    return time.perf_counter() - t0


def _run(n: int) -> None:
    series = _make_series(n)
    mapping = {"pending": "merged", "disabled": "merged"}

    def pandas_way() -> None:
        # Pandas approach for merging categories: reconstruct from scratch
        cat = series.cat
        new_codes = cat.codes.copy()
        old_categories = list(cat.categories)
        new_categories = []
        cat_map = {}
        for i, c in enumerate(old_categories):
            mapped = mapping.get(c, c)
            if mapped not in cat_map:
                cat_map[mapped] = len(new_categories)
                new_categories.append(mapped)
            new_codes[new_codes == i] = cat_map[mapped]
        pd.Categorical.from_codes(new_codes, categories=new_categories)

    def zh_way() -> None:
        remap_categorical(series, mapping)

    t_pandas = _timed("pandas", pandas_way)
    t_zh = _timed("zh_catmut", zh_way)
    ratio = t_pandas / t_zh if t_zh > 0 else float("inf")

    print(f"  n={n:>12,}  pandas={t_pandas:.4f}s  zh_catmut={t_zh:.4f}s  speedup={ratio:.2f}x")


def main() -> int:
    print("Comparing zh_catmut remap_categorical vs pandas manual merge")
    print("(many-to-one category merge)")
    print()
    for n in (1_000_000, 10_000_000, 100_000_000):
        _run(n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
