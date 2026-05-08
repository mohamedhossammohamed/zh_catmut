from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from zh_catmut import MemoryGateError, NativeStatusError, remap_categorical, remap_codes_inplace
from zh_catmut._abi import ZHCM_ABI_VERSION, ZHCM_ERR_CODE_OUT_OF_RANGE, ZHCM_OK
from zh_catmut._loader import load_native


def test_native_library_exports_expected_abi() -> None:
    lib = load_native()

    assert int(lib.zhcm_abi_version()) == ZHCM_ABI_VERSION
    assert lib.zhcm_status_message(ZHCM_OK).decode("utf-8") == "ok"


@pytest.mark.parametrize("dtype", [np.int8, np.int16, np.int32, np.int64])
def test_remap_codes_inplace_all_supported_dtypes(dtype: type[np.signedinteger]) -> None:
    codes = np.array([0, 1, 2, -1, 1], dtype=dtype)
    lut = np.array([2, 0, 1], dtype=np.int64)

    report = remap_codes_inplace(codes, lut, target_category_count=3)

    assert codes.tolist() == [2, 0, 1, -1, 0]
    assert report.abi_version == ZHCM_ABI_VERSION
    assert report.status == ZHCM_OK
    assert report.item_count == 5
    assert report.changed_count == 4
    assert report.missing_count == 1


def test_native_validation_is_all_or_nothing() -> None:
    codes = np.array([0, 2, 1], dtype=np.int8)
    original = codes.copy()
    lut = np.array([0, 1], dtype=np.int64)

    with pytest.raises(NativeStatusError) as exc_info:
        remap_codes_inplace(codes, lut, target_category_count=2)

    assert codes.tolist() == original.tolist()
    assert exc_info.value.status == ZHCM_ERR_CODE_OUT_OF_RANGE
    assert exc_info.value.report.first_invalid_index == 1
    assert exc_info.value.report.first_invalid_code == 2


def test_threads_greater_than_one_are_reserved() -> None:
    codes = np.array([0, 1], dtype=np.int8)
    lut = np.array([1, 0], dtype=np.int64)

    with pytest.raises(MemoryGateError, match="reserved"):
        remap_codes_inplace(codes, lut, target_category_count=2, threads=2)


def test_remap_categorical_copy_fallback_preserves_source() -> None:
    series = pd.Series(
        pd.Categorical(
            ["pending", "disabled_old", "other", None],
            categories=["pending", "disabled_old", "other"],
        ),
        name="state",
    )

    out = remap_categorical(
        series,
        {"pending": "active", "disabled_old": "disabled"},
        copy_fallback=True,
    )

    assert series.tolist()[:3] == ["pending", "disabled_old", "other"]
    assert out.name == "state"
    assert out.tolist()[:3] == ["active", "disabled", "other"]
    assert pd.isna(out.iloc[3])
    assert list(out.cat.categories) == ["active", "disabled", "other"]
