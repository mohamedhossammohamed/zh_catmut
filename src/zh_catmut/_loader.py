from __future__ import annotations

import ctypes
import os
import platform
from contextlib import ExitStack
from importlib.resources import as_file, files
from typing import Optional, Tuple

from ._abi import ZHCM_ABI_VERSION, ZhcmExecReport, ZhcmGateReport
from ._errors import NativeLibraryLoadError

_LoadedNative = Tuple[ctypes.CDLL, ExitStack]
_LOADED: Optional[_LoadedNative] = None


def _library_name() -> str:
    system = platform.system()
    if system == "Windows":
        return "zh_catmut.dll"
    if system == "Darwin":
        return "libzh_catmut.dylib"
    return "libzh_catmut.so"


def _declare_signatures(lib: ctypes.CDLL) -> None:
    lib.zhcm_abi_version.argtypes = []
    lib.zhcm_abi_version.restype = ctypes.c_uint32

    lib.zhcm_status_message.argtypes = [ctypes.c_int32]
    lib.zhcm_status_message.restype = ctypes.c_char_p

    lib.zhcm_predict_remap_lut.argtypes = [
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_int64,
        ctypes.c_uint64,
        ctypes.POINTER(ZhcmGateReport),
    ]
    lib.zhcm_predict_remap_lut.restype = ctypes.c_int32

    lib.zhcm_remap_lut_inplace.argtypes = [
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_int64,
        ctypes.c_uint64,
        ctypes.POINTER(ZhcmExecReport),
    ]
    lib.zhcm_remap_lut_inplace.restype = ctypes.c_int32

    lib.zhcm_remap_lut_copy.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_size_t,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_size_t,
        ctypes.c_size_t,
        ctypes.c_int64,
        ctypes.c_uint64,
        ctypes.POINTER(ZhcmExecReport),
    ]
    lib.zhcm_remap_lut_copy.restype = ctypes.c_int32


def load_native() -> ctypes.CDLL:
    global _LOADED
    if _LOADED is not None:
        return _LOADED[0]

    library_name = _library_name()
    stack = ExitStack()
    try:
        resource = files("zh_catmut").joinpath(library_name)
        path = stack.enter_context(as_file(resource))
        if os.name == "nt":
            stack.enter_context(os.add_dll_directory(str(path.parent)))

        lib = ctypes.CDLL(str(path))
        _declare_signatures(lib)
        actual_version = int(lib.zhcm_abi_version())
        if actual_version != ZHCM_ABI_VERSION:
            raise NativeLibraryLoadError(
                f"zh_catmut native ABI version mismatch: expected "
                f"{ZHCM_ABI_VERSION}, got {actual_version}"
            )
    except Exception as exc:
        stack.close()
        if isinstance(exc, NativeLibraryLoadError):
            raise
        raise NativeLibraryLoadError(f"failed to load {library_name}: {exc}") from exc

    _LOADED = (lib, stack)
    return lib


__all__ = ["load_native"]
