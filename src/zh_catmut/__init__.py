from __future__ import annotations

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("zh-catmut")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.2.0"

from ._categorical import remap_categorical, remap_codes_inplace
from ._errors import (
    CopyOnWriteSafetyError,
    MemoryGateError,
    NativeLibraryLoadError,
    NativeStatusError,
    ZhCatmutError,
)
from ._types import NativeExecutionReport, NativeGateReport

__all__ = [
    "CopyOnWriteSafetyError",
    "MemoryGateError",
    "NativeExecutionReport",
    "NativeGateReport",
    "NativeLibraryLoadError",
    "NativeStatusError",
    "ZhCatmutError",
    "__version__",
    "remap_categorical",
    "remap_codes_inplace",
]
