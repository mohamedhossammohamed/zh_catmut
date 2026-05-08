from __future__ import annotations

from ._categorical import remap_categorical, remap_codes_inplace
from ._errors import (
    CopyOnWriteSafetyError,
    MemoryGateError,
    NativeLibraryLoadError,
    NativeStatusError,
    ZhCatmutError,
)
from ._types import NativeExecutionReport, NativeGateReport

try:
    from importlib.metadata import version

    __version__ = version("zh-catmut")
except Exception:
    __version__ = "0.1.0"

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
