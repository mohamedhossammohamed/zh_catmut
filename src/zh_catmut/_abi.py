from __future__ import annotations

import ctypes

ZHCM_ABI_VERSION = 2

ZHCM_DTYPE_I8 = 1
ZHCM_DTYPE_I16 = 2
ZHCM_DTYPE_I32 = 3
ZHCM_DTYPE_I64 = 4

ZHCM_OK = 0
ZHCM_ERR_NULL_POINTER = 1
ZHCM_ERR_UNSUPPORTED_DTYPE = 2
ZHCM_ERR_INVALID_LENGTH = 3
ZHCM_ERR_INVALID_LUT = 4
ZHCM_ERR_CODE_OUT_OF_RANGE = 5
ZHCM_ERR_TARGET_OUT_OF_RANGE = 6
ZHCM_ERR_INTEGER_OVERFLOW = 7
ZHCM_ERR_THREAD_FAILURE = 8
ZHCM_ERR_MISALIGNED_POINTER = 9
ZHCM_ERR_PYTHON_GATE_REJECTED = 50
ZHCM_ERR_INTERNAL = 255

ZHCM_FLAG_ALLOW_MISSING = 0x1
ZHCM_FLAG_VALIDATE_INPUT = 0x2
ZHCM_FLAG_COLLECT_COUNTS = 0x4

UINT64_MAX = (1 << 64) - 1


class ZhcmGateReport(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("status", ctypes.c_int32),
        ("flags", ctypes.c_uint64),
        ("item_count", ctypes.c_uint64),
        ("lut_len", ctypes.c_uint64),
        ("target_category_count", ctypes.c_uint64),
        ("invalid_input_count", ctypes.c_uint64),
        ("invalid_output_count", ctypes.c_uint64),
        ("missing_count", ctypes.c_uint64),
        ("first_invalid_index", ctypes.c_uint64),
        ("first_invalid_code", ctypes.c_int64),
        ("first_invalid_mapped_code", ctypes.c_int64),
    ]


class ZhcmExecReport(ctypes.Structure):
    _fields_ = [
        ("abi_version", ctypes.c_uint32),
        ("status", ctypes.c_int32),
        ("flags", ctypes.c_uint64),
        ("item_count", ctypes.c_uint64),
        ("changed_count", ctypes.c_uint64),
        ("missing_count", ctypes.c_uint64),
        ("invalid_input_count", ctypes.c_uint64),
        ("invalid_output_count", ctypes.c_uint64),
        ("first_invalid_index", ctypes.c_uint64),
        ("first_invalid_code", ctypes.c_int64),
        ("first_invalid_mapped_code", ctypes.c_int64),
    ]


__all__ = [
    "UINT64_MAX",
    "ZHCM_ABI_VERSION",
    "ZHCM_DTYPE_I8",
    "ZHCM_DTYPE_I16",
    "ZHCM_DTYPE_I32",
    "ZHCM_DTYPE_I64",
    "ZHCM_ERR_CODE_OUT_OF_RANGE",
    "ZHCM_ERR_INTEGER_OVERFLOW",
    "ZHCM_ERR_INTERNAL",
    "ZHCM_ERR_INVALID_LENGTH",
    "ZHCM_ERR_INVALID_LUT",
    "ZHCM_ERR_MISALIGNED_POINTER",
    "ZHCM_ERR_NULL_POINTER",
    "ZHCM_ERR_PYTHON_GATE_REJECTED",
    "ZHCM_ERR_TARGET_OUT_OF_RANGE",
    "ZHCM_ERR_THREAD_FAILURE",
    "ZHCM_ERR_UNSUPPORTED_DTYPE",
    "ZHCM_FLAG_ALLOW_MISSING",
    "ZHCM_FLAG_COLLECT_COUNTS",
    "ZHCM_FLAG_VALIDATE_INPUT",
    "ZHCM_OK",
    "ZhcmExecReport",
    "ZhcmGateReport",
]
