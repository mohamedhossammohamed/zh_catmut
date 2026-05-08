from __future__ import annotations

import argparse
import platform
import sys
import textwrap
from importlib.metadata import PackageNotFoundError, version
from typing import Sequence

import numpy as np
import pandas as pd

from ._abi import ZHCM_ABI_VERSION
from ._categorical import remap_categorical, remap_codes_inplace
from ._loader import load_native

DOCS_URL = "https://mohamedhossammohamed.github.io/zh_catmut/"
REPO_URL = "https://github.com/mohamedhossammohamed/zh_catmut"


def _package_version() -> str:
    try:
        return version("zh-catmut")
    except PackageNotFoundError:
        return "0.1.0"


def _print_block(text: str) -> None:
    print(textwrap.dedent(text).strip())


def _cmd_example(_: argparse.Namespace) -> int:
    _print_block(
        """
        import pandas as pd
        from zh_catmut import remap_categorical

        series = pd.Series(pd.Categorical(["new", "old", "old", None]))

        out = remap_categorical(
            series,
            {"old": "new"},
            copy_fallback=True,
        )

        print(out.tolist())
        """
    )
    return 0


def _cmd_doctor(_: argparse.Namespace) -> int:
    print(f"zh-catmut {_package_version()}")
    print(f"Python {platform.python_version()} on {platform.platform()}")
    print(f"NumPy {np.__version__}")
    print(f"Pandas {pd.__version__}")
    print(f"Expected native ABI {ZHCM_ABI_VERSION}")
    try:
        lib = load_native()
        actual_abi = int(lib.zhcm_abi_version())
        print(f"Loaded native ABI {actual_abi}")

        codes = np.array([0, 1, 1, -1], dtype=np.int8)
        lut = np.array([0, 0], dtype=np.int64)
        report = remap_codes_inplace(codes, lut, target_category_count=1)
        if codes.tolist() != [0, 0, 0, -1]:
            raise RuntimeError(f"low-level remap produced {codes.tolist()!r}")

        series = pd.Series(pd.Categorical(["new", "old", "old", None]))
        out = remap_categorical(series, {"old": "new"}, copy_fallback=True)
        if out.iloc[:3].tolist() != ["new", "new", "new"] or not pd.isna(out.iloc[3]):
            raise RuntimeError(f"high-level remap produced {out.tolist()!r}")

        print(f"Native smoke test passed: {report.item_count} codes checked")
        return 0
    except Exception as exc:
        print(f"zh-catmut doctor failed: {exc}", file=sys.stderr)
        _print_block(
            f"""

            Troubleshooting:
            - If this was installed from a wheel, reinstall with: python -m pip install --force-reinstall zh-catmut
            - If pip built from source, Zig must be available on PATH or through ZIG=/path/to/zig.
            - Confirm the platform wheel includes libzh_catmut.so, libzh_catmut.dylib, or zh_catmut.dll.
            - Open an issue with the doctor output: {REPO_URL}/issues
            """
        )
        return 1


def _cmd_info(_: argparse.Namespace) -> int:
    _print_block(
        f"""
        zh-catmut {_package_version()}

        Purpose:
          Remap large Pandas categorical columns by applying a dense integer LUT
          to the underlying categorical codes buffer through a bundled Zig
          shared library.

        Install:
          python -m pip install zh-catmut

        Verify:
          zh-catmut doctor
          python -m zh_catmut doctor

        Public Python API:
          from zh_catmut import remap_categorical, remap_codes_inplace

        Safe default for Pandas callers:
          remap_categorical(series, mapping, copy_fallback=True)

        Docs:
          {DOCS_URL}

        Source:
          {REPO_URL}
        """
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="zh-catmut",
        description="Help and diagnostics for zh_catmut.",
    )
    parser.add_argument("--version", action="version", version=f"zh-catmut {_package_version()}")
    subparsers = parser.add_subparsers(dest="command")

    info = subparsers.add_parser("info", help="print package purpose, install, API, and links")
    info.set_defaults(func=_cmd_info)

    doctor = subparsers.add_parser("doctor", help="verify imports, native library loading, and remap smoke tests")
    doctor.set_defaults(func=_cmd_doctor)

    example = subparsers.add_parser("example", help="print a minimal copy_fallback=True usage example")
    example.set_defaults(func=_cmd_example)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        return _cmd_info(args)
    return int(args.func(args))


__all__ = ["build_parser", "main"]
