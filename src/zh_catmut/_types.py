from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from ._abi import (
    UINT64_MAX,
    ZHCM_DTYPE_I16,
    ZHCM_DTYPE_I32,
    ZHCM_DTYPE_I64,
    ZHCM_DTYPE_I8,
    ZhcmExecReport,
    ZhcmGateReport,
)
from ._errors import MemoryGateError

_DTYPE_TO_ZHCM = {
    np.dtype(np.int8): ZHCM_DTYPE_I8,
    np.dtype(np.int16): ZHCM_DTYPE_I16,
    np.dtype(np.int32): ZHCM_DTYPE_I32,
    np.dtype(np.int64): ZHCM_DTYPE_I64,
}


def dtype_to_zhcm(dtype: np.dtype) -> int:
    resolved = np.dtype(dtype)
    try:
        return _DTYPE_TO_ZHCM[resolved]
    except KeyError as exc:
        raise MemoryGateError(f"unsupported codes dtype: {resolved}") from exc


def _none_if_uint64_max(value: int) -> Optional[int]:
    return None if value == UINT64_MAX else int(value)


@dataclass(frozen=True)
class NativeGateReport:
    abi_version: int
    status: int
    flags: int
    item_count: int
    lut_len: int
    target_category_count: int
    invalid_input_count: int
    invalid_output_count: int
    missing_count: int
    first_invalid_index: Optional[int]
    first_invalid_code: int
    first_invalid_mapped_code: int

    @classmethod
    def from_ctype(cls, report: ZhcmGateReport) -> "NativeGateReport":
        return cls(
            abi_version=int(report.abi_version),
            status=int(report.status),
            flags=int(report.flags),
            item_count=int(report.item_count),
            lut_len=int(report.lut_len),
            target_category_count=int(report.target_category_count),
            invalid_input_count=int(report.invalid_input_count),
            invalid_output_count=int(report.invalid_output_count),
            missing_count=int(report.missing_count),
            first_invalid_index=_none_if_uint64_max(int(report.first_invalid_index)),
            first_invalid_code=int(report.first_invalid_code),
            first_invalid_mapped_code=int(report.first_invalid_mapped_code),
        )


@dataclass(frozen=True)
class NativeExecutionReport:
    abi_version: int
    status: int
    flags: int
    item_count: int
    changed_count: Optional[int]
    missing_count: Optional[int]
    invalid_input_count: int
    invalid_output_count: int
    first_invalid_index: Optional[int]
    first_invalid_code: int
    first_invalid_mapped_code: int

    @classmethod
    def from_ctype(cls, report: ZhcmExecReport) -> "NativeExecutionReport":
        return cls(
            abi_version=int(report.abi_version),
            status=int(report.status),
            flags=int(report.flags),
            item_count=int(report.item_count),
            changed_count=_none_if_uint64_max(int(report.changed_count)),
            missing_count=_none_if_uint64_max(int(report.missing_count)),
            invalid_input_count=int(report.invalid_input_count),
            invalid_output_count=int(report.invalid_output_count),
            first_invalid_index=_none_if_uint64_max(int(report.first_invalid_index)),
            first_invalid_code=int(report.first_invalid_code),
            first_invalid_mapped_code=int(report.first_invalid_mapped_code),
        )


__all__ = [
    "NativeExecutionReport",
    "NativeGateReport",
    "dtype_to_zhcm",
]
