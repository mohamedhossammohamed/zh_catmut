from __future__ import annotations

import ctypes
from collections.abc import Mapping
from typing import Any, Literal, Tuple, cast

import numpy as np
import pandas as pd

from ._abi import (
    ZHCM_FLAG_ALLOW_MISSING,
    ZHCM_FLAG_COLLECT_COUNTS,
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


_CategoricalKind = Literal["series", "categorical", "categorical_index"]


def _execution_flags(allow_missing: bool) -> int:
    flags = ZHCM_FLAG_VALIDATE_INPUT | ZHCM_FLAG_COLLECT_COUNTS
    if allow_missing:
        flags |= ZHCM_FLAG_ALLOW_MISSING
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
) -> NativeExecutionReport:
    return _remap_codes_inplace(
        codes,
        lut,
        target_category_count=target_category_count,
        missing_code=missing_code,
        allow_missing=allow_missing,
        require_writeable=True,
    )


def _remap_codes_inplace(
    codes: np.ndarray,
    lut: np.ndarray,
    *,
    target_category_count: int,
    missing_code: int = -1,
    allow_missing: bool = True,
    require_writeable: bool = True,
) -> NativeExecutionReport:
    dtype_code = validate_codes_array(codes, require_writeable=require_writeable)
    validate_lut_array(lut)
    target_count = validate_size(target_category_count, "target_category_count")
    missing = validate_int64(missing_code, "missing_code")

    lib = load_native()
    _predict(lib, codes, dtype_code, lut, target_count, missing, allow_missing)

    report = ZhcmExecReport()
    flags = _execution_flags(allow_missing)
    with temporarily_writeable(codes):
        status = lib.zhcm_remap_lut_inplace(
            ctypes.c_void_p(int(codes.ctypes.data)),
            codes.size,
            dtype_code,
            _lut_pointer(lut),
            lut.size,
            target_count,
            missing,
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
) -> Tuple[np.ndarray, NativeExecutionReport]:
    dtype_code = validate_codes_array(codes)
    validate_lut_array(lut)
    target_count = validate_size(target_category_count, "target_category_count")
    missing = validate_int64(missing_code, "missing_code")

    destination = np.empty_like(codes)
    lib = load_native()
    _predict(lib, codes, dtype_code, lut, target_count, missing, allow_missing)

    report = ZhcmExecReport()
    flags = _execution_flags(allow_missing)
    status = lib.zhcm_remap_lut_copy(
        ctypes.c_void_p(int(codes.ctypes.data)),
        ctypes.c_void_p(int(destination.ctypes.data)),
        codes.size,
        dtype_code,
        _lut_pointer(lut),
        lut.size,
        target_count,
        missing,
        flags,
        ctypes.byref(report),
    )
    wrapped = NativeExecutionReport.from_ctype(report)
    _raise_for_status(lib, status, "zhcm_remap_lut_copy", wrapped)
    return destination, wrapped


def _mapped_label(label: Any, mapping: Mapping[object, object]) -> Any:
    try:
        return mapping.get(label, label)
    except TypeError:
        return label


def _is_scalar_na(value: Any) -> bool:
    try:
        result = pd.isna(value)
    except Exception:
        return False
    return isinstance(result, (bool, np.bool_)) and bool(result)


def _labels_equal(left: Any, right: Any) -> bool:
    if left is right:
        return True
    try:
        equal = left == right
        if equal is pd.NA:
            return _is_scalar_na(left) and _is_scalar_na(right)
        return bool(equal)
    except Exception:
        return _is_scalar_na(left) and _is_scalar_na(right)


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
    codes = np.asarray(cat.codes)
    if isinstance(codes, np.ndarray):
        return codes
    raise MemoryGateError("could not extract NumPy categorical codes")


def _codes_are_owned(codes: np.ndarray) -> bool:
    return bool(codes.flags.owndata) and codes.base is None


def _as_categorical(obj: pd.Series | pd.Categorical | pd.CategoricalIndex) -> Tuple[pd.Categorical, _CategoricalKind]:
    if isinstance(obj, pd.Series):
        if not isinstance(obj.dtype, pd.CategoricalDtype):
            raise TypeError("Series input must have categorical dtype")
        return obj.array, "series"
    if isinstance(obj, pd.CategoricalIndex):
        return obj.array, "categorical_index"
    if isinstance(obj, pd.Categorical):
        return obj, "categorical"
    raise TypeError("obj must be a pandas Series, pandas Categorical, or pandas CategoricalIndex")


def _check_inplace_safety(
    codes: np.ndarray,
    assume_unique: bool,
) -> None:
    if assume_unique:
        return
    if not _codes_are_owned(codes):
        raise CopyOnWriteSafetyError("categorical codes are not uniquely owned")


def _wrap_categorical(
    obj: pd.Series | pd.Categorical | pd.CategoricalIndex,
    kind: _CategoricalKind,
    cat: pd.Categorical,
) -> pd.Series | pd.Categorical | pd.CategoricalIndex:
    if kind == "series":
        series = cast(pd.Series, obj)
        return pd.Series(cat, index=series.index, name=series.name, copy=False)
    if kind == "categorical_index":
        index = cast(pd.CategoricalIndex, obj)
        return pd.CategoricalIndex(cat, name=index.name)
    return cat


def remap_categorical(
    obj: pd.Series | pd.Categorical | pd.CategoricalIndex,
    mapping: Mapping[object, object],
    *,
    assume_unique: bool = False,
    copy_fallback: bool = True,
) -> pd.Series | pd.Categorical | pd.CategoricalIndex:
    if not isinstance(mapping, Mapping):
        raise TypeError("mapping must be a Mapping")

    cat, kind = _as_categorical(obj)
    new_categories, lut = _build_lut(cat, mapping)
    codes = _extract_codes(cat)
    validate_codes_array(codes)

    if copy_fallback:
        remapped_codes, _ = _remap_codes_copy(
            codes,
            lut,
            target_category_count=len(new_categories),
            allow_missing=True,
        )
    else:
        _check_inplace_safety(codes, assume_unique)
        _remap_codes_inplace(
            codes,
            lut,
            target_category_count=len(new_categories),
            allow_missing=True,
            require_writeable=False,
        )
        remapped_codes = codes

    new_cat = pd.Categorical.from_codes(
        remapped_codes,
        categories=new_categories,
        ordered=cat.ordered,
        validate=True,
    )
    return _wrap_categorical(obj, kind, new_cat)


__all__ = ["remap_categorical", "remap_codes_inplace"]
