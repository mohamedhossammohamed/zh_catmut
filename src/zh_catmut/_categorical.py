from __future__ import annotations

import ctypes
from collections.abc import Mapping
from typing import Any, Tuple

import numpy as np
import pandas as pd

from ._abi import (
    ZHCM_FLAG_ALLOW_MISSING,
    ZHCM_FLAG_COLLECT_COUNTS,
    ZHCM_FLAG_PARALLEL,
    ZHCM_FLAG_VALIDATE_INPUT,
    ZHCM_OK,
    ZhcmExecReport,
    ZhcmGateReport,
)
from ._errors import CopyOnWriteSafetyError, MemoryGateError, NativeStatusError
from ._gates import (
    temporarily_writeable,
    validate_codes_array,
    validate_int64,
    validate_lut_array,
    validate_size,
    validate_threads,
)
from ._loader import load_native
from ._types import NativeExecutionReport, NativeGateReport


def _status_message(lib: ctypes.CDLL, status: int) -> str:
    raw = lib.zhcm_status_message(int(status))
    if raw is None:
        return "unknown status"
    return raw.decode("utf-8", "replace")


def _raise_for_status(
    lib: ctypes.CDLL,
    status: int,
    context: str,
    report: NativeGateReport | NativeExecutionReport | None = None,
) -> None:
    if int(status) == ZHCM_OK:
        return
    raise NativeStatusError(context, int(status), _status_message(lib, int(status)), report)


def _execution_flags(allow_missing: bool, threads: int) -> int:
    flags = ZHCM_FLAG_VALIDATE_INPUT | ZHCM_FLAG_COLLECT_COUNTS
    if allow_missing:
        flags |= ZHCM_FLAG_ALLOW_MISSING
    if threads != 1:
        flags |= ZHCM_FLAG_PARALLEL
    return flags


def _prediction_flags(allow_missing: bool) -> int:
    flags = ZHCM_FLAG_COLLECT_COUNTS
    if allow_missing:
        flags |= ZHCM_FLAG_ALLOW_MISSING
    return flags


def _lut_pointer(lut: np.ndarray) -> ctypes.POINTER(ctypes.c_int64):
    return lut.ctypes.data_as(ctypes.POINTER(ctypes.c_int64))


def _predict(
    lib: ctypes.CDLL,
    codes: np.ndarray,
    dtype_code: int,
    lut: np.ndarray,
    target_category_count: int,
    missing_code: int,
    allow_missing: bool,
) -> NativeGateReport:
    report = ZhcmGateReport()
    status = lib.zhcm_predict_remap_lut(
        ctypes.c_void_p(int(codes.ctypes.data)),
        codes.size,
        dtype_code,
        _lut_pointer(lut),
        lut.size,
        target_category_count,
        missing_code,
        _prediction_flags(allow_missing),
        ctypes.byref(report),
    )
    wrapped = NativeGateReport.from_ctype(report)
    _raise_for_status(lib, status, "zhcm_predict_remap_lut", wrapped)
    return wrapped


def remap_codes_inplace(
    codes: np.ndarray,
    lut: np.ndarray,
    *,
    target_category_count: int,
    missing_code: int = -1,
    allow_missing: bool = True,
    threads: int = 0,
) -> NativeExecutionReport:
    dtype_code = validate_codes_array(codes)
    validate_lut_array(lut)
    target_count = validate_size(target_category_count, "target_category_count")
    missing = validate_int64(missing_code, "missing_code")
    thread_count = validate_threads(threads)

    lib = load_native()
    _predict(lib, codes, dtype_code, lut, target_count, missing, allow_missing)

    report = ZhcmExecReport()
    flags = _execution_flags(allow_missing, thread_count)
    with temporarily_writeable(codes):
        status = lib.zhcm_remap_lut_inplace(
            ctypes.c_void_p(int(codes.ctypes.data)),
            codes.size,
            dtype_code,
            _lut_pointer(lut),
            lut.size,
            target_count,
            missing,
            thread_count,
            flags,
            ctypes.byref(report),
        )
    wrapped = NativeExecutionReport.from_ctype(report)
    _raise_for_status(lib, status, "zhcm_remap_lut_inplace", wrapped)
    return wrapped


def _remap_codes_copy(
    codes: np.ndarray,
    lut: np.ndarray,
    *,
    target_category_count: int,
    missing_code: int = -1,
    allow_missing: bool = True,
    threads: int = 0,
) -> Tuple[np.ndarray, NativeExecutionReport]:
    dtype_code = validate_codes_array(codes)
    validate_lut_array(lut)
    target_count = validate_size(target_category_count, "target_category_count")
    missing = validate_int64(missing_code, "missing_code")
    thread_count = validate_threads(threads)

    destination = np.empty_like(codes)
    lib = load_native()
    _predict(lib, codes, dtype_code, lut, target_count, missing, allow_missing)

    report = ZhcmExecReport()
    flags = _execution_flags(allow_missing, thread_count)
    status = lib.zhcm_remap_lut_copy(
        ctypes.c_void_p(int(codes.ctypes.data)),
        ctypes.c_void_p(int(destination.ctypes.data)),
        codes.size,
        dtype_code,
        _lut_pointer(lut),
        lut.size,
        target_count,
        missing,
        thread_count,
        flags,
        ctypes.byref(report),
    )
    wrapped = NativeExecutionReport.from_ctype(report)
    _raise_for_status(lib, status, "zhcm_remap_lut_copy", wrapped)
    return destination, wrapped


def _mapped_label(label: Any, mapping: Mapping[object, object]) -> Any:
    sentinel = object()
    try:
        mapped = mapping.get(label, sentinel)
    except TypeError:
        mapped = sentinel
    if mapped is not sentinel:
        return mapped
    try:
        return mapping[label]
    except (KeyError, TypeError):
        return label


def _labels_equal(left: Any, right: Any) -> bool:
    if left is right:
        return True
    try:
        return bool(left == right)
    except Exception:
        return False


def _category_index(label: Any, categories: list[Any], index: dict[Any, int]) -> int:
    try:
        return index[label]
    except KeyError:
        next_index = len(categories)
        categories.append(label)
        index[label] = next_index
        return next_index
    except TypeError:
        for position, existing in enumerate(categories):
            if _labels_equal(existing, label):
                return position
        categories.append(label)
        return len(categories) - 1


def _build_lut(cat: pd.Categorical, mapping: Mapping[object, object]) -> Tuple[list[Any], np.ndarray]:
    new_categories: list[Any] = []
    category_index: dict[Any, int] = {}
    old_categories = list(cat.categories)
    lut = np.empty(len(old_categories), dtype=np.int64)

    for old_index, old_label in enumerate(old_categories):
        new_label = _mapped_label(old_label, mapping)
        lut[old_index] = _category_index(new_label, new_categories, category_index)

    return new_categories, lut


def _extract_codes(cat: pd.Categorical) -> np.ndarray:
    codes = getattr(cat, "_codes", None)
    if isinstance(codes, np.ndarray):
        return codes
    codes = cat.codes
    if not isinstance(codes, np.ndarray):
        raise MemoryGateError("could not extract NumPy categorical codes")
    return codes


def _series_has_cow_references(series: pd.Series) -> bool:
    try:
        blocks = series._mgr.blocks
        return any(block.refs.has_reference() for block in blocks if hasattr(block, "refs"))
    except Exception:
        return True


def _codes_are_owned(codes: np.ndarray) -> bool:
    return bool(codes.flags.owndata) and codes.base is None


def _as_categorical(obj: pd.Series | pd.Categorical) -> Tuple[pd.Categorical, bool]:
    if isinstance(obj, pd.Series):
        if not isinstance(obj.dtype, pd.CategoricalDtype):
            raise TypeError("Series input must have categorical dtype")
        return obj.array, True
    if isinstance(obj, pd.Categorical):
        return obj, False
    raise TypeError("obj must be a pandas Series or pandas Categorical")


def _check_inplace_safety(
    obj: pd.Series | pd.Categorical,
    is_series: bool,
    codes: np.ndarray,
    assume_unique: bool,
) -> None:
    if assume_unique:
        return
    if not _codes_are_owned(codes):
        raise CopyOnWriteSafetyError("categorical codes are not uniquely owned")
    if is_series and _series_has_cow_references(obj):  # type: ignore[arg-type]
        raise CopyOnWriteSafetyError("Series shares categorical storage under Pandas Copy-on-Write")


def remap_categorical(
    obj: pd.Series | pd.Categorical,
    mapping: Mapping[object, object],
    *,
    assume_unique: bool = False,
    copy_fallback: bool = False,
    threads: int = 0,
) -> pd.Series | pd.Categorical:
    if not isinstance(mapping, Mapping):
        raise TypeError("mapping must be a Mapping")

    cat, is_series = _as_categorical(obj)
    new_categories, lut = _build_lut(cat, mapping)
    codes = _extract_codes(cat)
    validate_codes_array(codes)

    if copy_fallback:
        remapped_codes, _ = _remap_codes_copy(
            codes,
            lut,
            target_category_count=len(new_categories),
            allow_missing=True,
            threads=threads,
        )
    else:
        _check_inplace_safety(obj, is_series, codes, assume_unique)
        remap_codes_inplace(
            codes,
            lut,
            target_category_count=len(new_categories),
            allow_missing=True,
            threads=threads,
        )
        remapped_codes = codes

    new_cat = pd.Categorical.from_codes(
        remapped_codes,
        categories=new_categories,
        ordered=cat.ordered,
        validate=False,
    )
    if is_series:
        series = obj  # type: ignore[assignment]
        return pd.Series(new_cat, index=series.index, name=series.name, copy=False)
    return new_cat


__all__ = ["remap_categorical", "remap_codes_inplace"]
