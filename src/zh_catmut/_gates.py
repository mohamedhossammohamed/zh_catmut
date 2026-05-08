from __future__ import annotations

import ctypes
import operator
import sys
from contextlib import contextmanager
from typing import Iterator

import numpy as np

from ._errors import MemoryGateError
from ._types import dtype_to_zhcm

_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1
_SIZE_T_MAX = ctypes.c_size_t(-1).value


def _index(value: object, name: str) -> int:
    try:
        return operator.index(value)
    except TypeError as exc:
        raise MemoryGateError(f"{name} must be an integer") from exc


def validate_size(value: object, name: str) -> int:
    size = _index(value, name)
    if size < 0:
        raise MemoryGateError(f"{name} must be non-negative")
    if size > _SIZE_T_MAX or size > sys.maxsize:
        raise MemoryGateError(f"{name} does not fit in native size_t")
    return size


def validate_int64(value: object, name: str) -> int:
    resolved = _index(value, name)
    if resolved < _INT64_MIN or resolved > _INT64_MAX:
        raise MemoryGateError(f"{name} does not fit in int64")
    return resolved


def validate_codes_array(codes: object, *, require_writeable: bool = False) -> int:
    if not isinstance(codes, np.ndarray):
        raise MemoryGateError("codes must be a NumPy ndarray")
    if codes.ndim != 1:
        raise MemoryGateError("codes must be one-dimensional")
    if not codes.flags.c_contiguous:
        raise MemoryGateError("codes must be C-contiguous")
    if not codes.flags.aligned:
        raise MemoryGateError("codes must be aligned")
    if require_writeable and not codes.flags.writeable:
        raise MemoryGateError("codes must be writeable")
    dtype_code = dtype_to_zhcm(codes.dtype)
    validate_size(codes.size, "codes.size")
    return dtype_code


def validate_lut_array(lut: object) -> None:
    if not isinstance(lut, np.ndarray):
        raise MemoryGateError("lut must be a NumPy ndarray")
    if lut.ndim != 1:
        raise MemoryGateError("lut must be one-dimensional")
    if lut.dtype != np.dtype(np.int64):
        raise MemoryGateError("lut must have dtype int64")
    if not lut.flags.c_contiguous:
        raise MemoryGateError("lut must be C-contiguous")
    if not lut.flags.aligned:
        raise MemoryGateError("lut must be aligned")
    validate_size(lut.size, "lut.size")


@contextmanager
def temporarily_writeable(array: np.ndarray) -> Iterator[None]:
    original = bool(array.flags.writeable)
    try:
        if not original:
            array.setflags(write=True)
        yield
    except ValueError as exc:
        raise MemoryGateError("codes buffer cannot be made writeable") from exc
    finally:
        if bool(array.flags.writeable) != original:
            array.setflags(write=original)


__all__ = [
    "temporarily_writeable",
    "validate_codes_array",
    "validate_int64",
    "validate_lut_array",
    "validate_size",
]
