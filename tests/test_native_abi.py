from __future__ import annotations

import ctypes

import numpy as np
import pandas as pd
import pytest

from zh_catmut import (
    CopyOnWriteSafetyError,
    MemoryGateError,
    NativeStatusError,
    remap_categorical,
    remap_codes_inplace,
)
from zh_catmut._abi import (
    ZHCM_ABI_VERSION,
    ZHCM_DTYPE_I16,
    ZHCM_ERR_CODE_OUT_OF_RANGE,
    ZHCM_ERR_MISALIGNED_POINTER,
    ZHCM_FLAG_ALLOW_MISSING,
    ZHCM_FLAG_COLLECT_COUNTS,
    ZHCM_OK,
    ZhcmGateReport,
)
from zh_catmut._categorical import _labels_equal, _mapped_label
from zh_catmut._loader import load_native


def test_native_library_exports_expected_abi() -> None:
    lib = load_native()

    assert int(lib.zhcm_abi_version()) == ZHCM_ABI_VERSION
    assert lib.zhcm_status_message(ZHCM_OK).decode("utf-8") == "ok"
    assert lib.zhcm_status_message(ZHCM_ERR_MISALIGNED_POINTER).decode("utf-8") == "misaligned pointer"


@pytest.mark.parametrize("dtype", [np.int8, np.int16, np.int32, np.int64])
def test_remap_codes_inplace_all_supported_signed_dtypes(dtype: type[np.signedinteger]) -> None:
    codes = np.array([0, 1, 2, -1, 1], dtype=dtype)
    lut = np.array([2, 0, 1], dtype=np.int64)

    report = remap_codes_inplace(codes, lut, target_category_count=3)

    assert codes.tolist() == [2, 0, 1, -1, 0]
    assert report.abi_version == ZHCM_ABI_VERSION
    assert report.status == ZHCM_OK
    assert report.item_count == 5
    assert report.changed_count == 4
    assert report.missing_count == 1


def test_remap_codes_inplace_accepts_empty_arrays() -> None:
    codes = np.array([], dtype=np.int8)
    lut = np.array([], dtype=np.int64)

    report = remap_codes_inplace(codes, lut, target_category_count=0)

    assert codes.tolist() == []
    assert report.status == ZHCM_OK
    assert report.item_count == 0
    assert report.changed_count == 0
    assert report.missing_count == 0


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


def test_remap_codes_inplace_rejects_missing_when_disallowed() -> None:
    codes = np.array([0, -1, 1], dtype=np.int8)
    original = codes.copy()
    lut = np.array([0, 1], dtype=np.int64)

    with pytest.raises(NativeStatusError) as exc_info:
        remap_codes_inplace(codes, lut, target_category_count=2, allow_missing=False)

    assert codes.tolist() == original.tolist()
    assert exc_info.value.status == ZHCM_ERR_CODE_OUT_OF_RANGE
    assert exc_info.value.report.first_invalid_index == 1


def test_remap_codes_inplace_rejects_invalid_target_code() -> None:
    codes = np.array([0, 1], dtype=np.int8)
    original = codes.copy()
    lut = np.array([0, 2], dtype=np.int64)

    with pytest.raises(NativeStatusError) as exc_info:
        remap_codes_inplace(codes, lut, target_category_count=2)

    assert codes.tolist() == original.tolist()
    assert exc_info.value.report.first_invalid_index == 1
    assert exc_info.value.report.first_invalid_mapped_code == 2


def test_threads_keyword_was_removed_from_low_level_api() -> None:
    codes = np.array([0, 1], dtype=np.int8)
    lut = np.array([1, 0], dtype=np.int64)

    with pytest.raises(TypeError, match="threads"):
        remap_codes_inplace(codes, lut, target_category_count=2, threads=1)  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "codes",
    [
        np.array([0, 1, 0], dtype=np.uint8),
        np.array([0, 1, 0], dtype=np.float32),
        np.array([0, 1, 0], dtype=object),
    ],
)
def test_remap_codes_inplace_rejects_unsupported_dtypes(codes: np.ndarray) -> None:
    lut = np.array([0, 1], dtype=np.int64)

    with pytest.raises(MemoryGateError, match="unsupported codes dtype"):
        remap_codes_inplace(codes, lut, target_category_count=2)


def test_remap_codes_inplace_rejects_non_contiguous_codes() -> None:
    codes = np.array([0, 1, 0, 1], dtype=np.int8)[::2]
    lut = np.array([1, 0], dtype=np.int64)

    with pytest.raises(MemoryGateError, match="C-contiguous"):
        remap_codes_inplace(codes, lut, target_category_count=2)


def test_remap_codes_inplace_rejects_non_1d_codes() -> None:
    codes = np.array([[0, 1]], dtype=np.int8)
    lut = np.array([1, 0], dtype=np.int64)

    with pytest.raises(MemoryGateError, match="one-dimensional"):
        remap_codes_inplace(codes, lut, target_category_count=2)


def test_remap_codes_inplace_rejects_unwriteable_codes() -> None:
    codes = np.array([0, 1], dtype=np.int8)
    codes.setflags(write=False)
    lut = np.array([1, 0], dtype=np.int64)

    with pytest.raises(MemoryGateError, match="writeable"):
        remap_codes_inplace(codes, lut, target_category_count=2)


def test_remap_codes_inplace_rejects_unaligned_codes() -> None:
    raw = np.zeros(5, dtype=np.uint8)
    codes = np.ndarray(shape=(2,), dtype=np.int16, buffer=raw, offset=1)
    lut = np.array([1, 0], dtype=np.int64)

    assert not codes.flags.aligned
    with pytest.raises(MemoryGateError, match="aligned"):
        remap_codes_inplace(codes, lut, target_category_count=2)


def test_remap_codes_inplace_rejects_bad_lut_shape_dtype_and_alignment() -> None:
    codes = np.array([0, 1], dtype=np.int8)

    with pytest.raises(MemoryGateError, match="one-dimensional"):
        remap_codes_inplace(codes, np.array([[1, 0]], dtype=np.int64), target_category_count=2)
    with pytest.raises(MemoryGateError, match="dtype int64"):
        remap_codes_inplace(codes, np.array([1, 0], dtype=np.int32), target_category_count=2)

    raw = np.zeros(17, dtype=np.uint8)
    lut = np.ndarray(shape=(2,), dtype=np.int64, buffer=raw, offset=1)
    assert not lut.flags.aligned
    with pytest.raises(MemoryGateError, match="aligned"):
        remap_codes_inplace(codes, lut, target_category_count=2)


def test_native_preflight_rejects_misaligned_ctypes_pointer() -> None:
    lib = load_native()
    raw = np.zeros(5, dtype=np.uint8)
    codes = np.ndarray(shape=(2,), dtype=np.int16, buffer=raw, offset=1)
    lut = np.array([0, 1], dtype=np.int64)
    report = ZhcmGateReport()

    status = lib.zhcm_predict_remap_lut(
        ctypes.c_void_p(int(codes.ctypes.data)),
        codes.size,
        ZHCM_DTYPE_I16,
        lut.ctypes.data_as(ctypes.POINTER(ctypes.c_int64)),
        lut.size,
        2,
        -1,
        ZHCM_FLAG_ALLOW_MISSING | ZHCM_FLAG_COLLECT_COUNTS,
        ctypes.byref(report),
    )

    assert int(status) == ZHCM_ERR_MISALIGNED_POINTER
    assert int(report.status) == ZHCM_ERR_MISALIGNED_POINTER


def test_remap_categorical_default_copy_preserves_source() -> None:
    series = pd.Series(
        pd.Categorical(
            ["pending", "disabled_old", "other", None],
            categories=["pending", "disabled_old", "other"],
        ),
        name="state",
    )

    out = remap_categorical(series, {"pending": "active", "disabled_old": "disabled"})

    assert series.tolist()[:3] == ["pending", "disabled_old", "other"]
    assert out.name == "state"
    assert out.tolist()[:3] == ["active", "disabled", "other"]
    assert pd.isna(out.iloc[3])
    assert list(out.cat.categories) == ["active", "disabled", "other"]


def test_remap_categorical_accepts_categorical_input() -> None:
    cat = pd.Categorical(["old", "same", None], categories=["old", "same"], ordered=True)

    out = remap_categorical(cat, {"old": "new"})

    assert isinstance(out, pd.Categorical)
    assert out.ordered
    assert out.tolist()[:2] == ["new", "same"]
    assert pd.isna(out[2])
    assert list(out.categories) == ["new", "same"]


def test_remap_categorical_accepts_categorical_index() -> None:
    index = pd.CategoricalIndex(["old", "same", None], categories=["old", "same"], name="state")

    out = remap_categorical(index, {"old": "new"})

    assert isinstance(out, pd.CategoricalIndex)
    assert out.name == "state"
    assert out.tolist()[:2] == ["new", "same"]
    assert pd.isna(out[2])
    assert list(out.categories) == ["new", "same"]


def test_remap_categorical_preserves_ordered_on_categorical_index() -> None:
    index = pd.CategoricalIndex(
        ["old", "same", None],
        categories=["old", "same"],
        ordered=True,
        name="state",
    )

    out = remap_categorical(index, {"old": "new"})

    assert isinstance(out, pd.CategoricalIndex)
    assert out.ordered is True
    assert out.name == "state"


def test_remap_categorical_accepts_dataframe_column_series() -> None:
    df = pd.DataFrame({"state": pd.Categorical(["old", "same"], categories=["old", "same"])})

    out = remap_categorical(df["state"], {"old": "new"})

    assert isinstance(out, pd.Series)
    assert df["state"].tolist() == ["old", "same"]
    assert out.tolist() == ["new", "same"]
    assert list(out.cat.categories) == ["new", "same"]


def test_remap_categorical_handles_empty_categorical() -> None:
    cat = pd.Categorical([], categories=[])

    out = remap_categorical(cat, {})

    assert isinstance(out, pd.Categorical)
    assert out.tolist() == []
    assert list(out.categories) == []


def test_remap_categorical_requires_categorical_series() -> None:
    series = pd.Series(["old", "same"])

    with pytest.raises(TypeError, match="categorical dtype"):
        remap_categorical(series, {"old": "new"})


def test_remap_categorical_requires_mapping() -> None:
    cat = pd.Categorical(["old"], categories=["old"])

    with pytest.raises(TypeError, match="mapping"):
        remap_categorical(cat, [("old", "new")])  # type: ignore[arg-type]


def test_threads_keyword_was_removed_from_high_level_api() -> None:
    cat = pd.Categorical(["old"], categories=["old"])

    with pytest.raises(TypeError, match="threads"):
        remap_categorical(cat, {"old": "new"}, threads=1)  # type: ignore[call-arg]


def test_remap_categorical_copy_fallback_false_requires_expert_override() -> None:
    cat = pd.Categorical(["old", "same"], categories=["old", "same"])

    with pytest.raises(CopyOnWriteSafetyError, match="uniquely owned"):
        remap_categorical(cat, {"same": "old"}, copy_fallback=False)

    out = remap_categorical(cat, {"same": "old"}, copy_fallback=False, assume_unique=True)

    assert out.tolist() == ["old", "old"]
    assert list(out.categories) == ["old"]


def test_mapped_label_preserves_unhashable_labels() -> None:
    label = ["a"]

    assert _mapped_label(label, {}) is label


def test_labels_equal_treats_scalar_missing_values_as_equal() -> None:
    assert _labels_equal(pd.NA, pd.NA)
    assert _labels_equal(np.nan, np.nan)
