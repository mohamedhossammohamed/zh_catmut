from __future__ import annotations

import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Iterable, Optional

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py
from setuptools.command.sdist import sdist as _sdist

try:
    from setuptools.command.develop import develop as _develop
except Exception:  # pragma: no cover - optional setuptools command
    _develop = None

try:
    from setuptools.command.editable_wheel import editable_wheel as _editable_wheel
except Exception:  # pragma: no cover - optional setuptools command
    _editable_wheel = None

try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel
except Exception:  # pragma: no cover - optional wheel command
    _bdist_wheel = None

ROOT = Path(__file__).resolve().parent
NATIVE_DIR = ROOT / "native"
SOURCE_PACKAGE = ROOT / "src" / "zh_catmut"
COMPILED_DIR = ROOT / "compiled"
NATIVE_LIBRARY_NAMES = {"libzh_catmut.so", "libzh_catmut.dylib", "zh_catmut.dll"}


def _library_name() -> str:
    system = platform.system()
    if system == "Windows":
        return "zh_catmut.dll"
    if system == "Darwin":
        return "libzh_catmut.dylib"
    return "libzh_catmut.so"


def _normalized_arch(arch: str) -> Optional[str]:
    return {
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }.get(arch.lower())


def _platform_tag() -> Optional[str]:
    explicit = os.environ.get("ZH_CATMUT_PREBUILT_TAG")
    if explicit:
        return explicit
    arch = _normalized_arch(platform.machine())
    if arch is None:
        return None
    return f"{platform.system().lower()}-{arch}"


def _macos_wheel_platform_name() -> Optional[str]:
    if platform.system() != "Darwin":
        return None

    cibw_arch = os.environ.get("CIBW_ARCHS") or os.environ.get("CIBW_ARCHS_MACOS")
    if cibw_arch and " " not in cibw_arch.strip():
        arch = cibw_arch.strip()
    else:
        arch = platform.machine().lower()

    normalized = _normalized_arch(arch)
    if normalized == "aarch64":
        return "macosx-11.0-arm64"
    if normalized == "x86_64":
        target = os.environ.get("MACOSX_DEPLOYMENT_TARGET", "10.9")
        parts = target.split(".")
        major = int(parts[0]) if parts and parts[0].isdigit() else 10
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 9
        return f"macosx-{major}.{minor}-x86_64"
    return None


def _prebuilt_library() -> Optional[Path]:
    explicit = os.environ.get("ZH_CATMUT_PREBUILT_LIBRARY")
    if explicit:
        path = Path(explicit)
        return path if path.exists() else None
    tag = _platform_tag()
    if tag is None:
        return None
    path = COMPILED_DIR / tag / _library_name()
    return path if path.exists() else None


def _target_from_env() -> Optional[str]:
    explicit = os.environ.get("ZH_CATMUT_ZIG_TARGET")
    if explicit:
        return explicit

    cibw_arch = os.environ.get("CIBW_ARCHS") or os.environ.get("CIBW_ARCHS_MACOS")
    if cibw_arch and " " not in cibw_arch.strip():
        arch = cibw_arch.strip()
    else:
        arch = platform.machine().lower()

    zig_arch = _normalized_arch(arch)
    if zig_arch is None:
        return None

    system = platform.system()
    if system == "Darwin":
        return f"{zig_arch}-macos"
    if system == "Windows":
        return f"{zig_arch}-windows"
    if system == "Linux":
        return f"{zig_arch}-linux-gnu"
    return None


def _copy_library(source: Path, destinations: Iterable[Path]) -> None:
    for destination_dir in destinations:
        destination_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination_dir / source.name)


def _build_native(build_temp: Path, destinations: Iterable[Path]) -> Path:
    prebuilt = _prebuilt_library()
    if prebuilt is not None and os.environ.get("ZH_CATMUT_FORCE_ZIG_BUILD") != "1":
        _copy_library(prebuilt, destinations)
        return prebuilt

    build_temp = build_temp.resolve()
    zig = os.environ.get("ZIG", "zig")
    optimize = os.environ.get("ZH_CATMUT_ZIG_OPTIMIZE", "fast").lower()
    prefix = build_temp / "zig-prefix"
    prefix.mkdir(parents=True, exist_ok=True)

    command = [
        zig,
        "build",
        f"--release={optimize}",
        "--prefix",
        str(prefix),
    ]
    target = _target_from_env()
    if target:
        command.append(f"-Dtarget={target}")

    try:
        subprocess.check_call(command, cwd=NATIVE_DIR)
    except FileNotFoundError as exc:
        prebuilt = _prebuilt_library()
        if prebuilt is not None:
            _copy_library(prebuilt, destinations)
            return prebuilt
        raise RuntimeError(
            "building zh_catmut from source requires Zig on PATH or ZIG=/path/to/zig"
        ) from exc
    except subprocess.CalledProcessError as exc:
        prebuilt = _prebuilt_library()
        if prebuilt is not None:
            _copy_library(prebuilt, destinations)
            return prebuilt
        raise RuntimeError(f"Zig native build failed with exit code {exc.returncode}") from exc

    library = prefix / "lib" / _library_name()
    if not library.exists():
        candidates = sorted(prefix.rglob(_library_name()))
        if not candidates:
            raise RuntimeError(f"Zig build did not produce {_library_name()}")
        library = candidates[0]

    _copy_library(library, destinations)
    return library


class build_py(_build_py):
    def run(self) -> None:
        super().run()
        build_temp = Path(self.get_finalized_command("build").build_temp) / "zh_catmut_native"
        destinations = [Path(self.build_lib) / "zh_catmut"]
        if os.environ.get("ZH_CATMUT_COPY_TO_SOURCE", "0") != "0":
            destinations.append(SOURCE_PACKAGE)
        _build_native(build_temp, destinations)


class sdist(_sdist):
    def _without_native_libraries(self, files: Iterable[str]) -> list[str]:
        excluded = {
            str((SOURCE_PACKAGE / name).relative_to(ROOT)).replace(os.sep, "/")
            for name in NATIVE_LIBRARY_NAMES
        }
        return [file for file in files if file.replace(os.sep, "/") not in excluded]

    def get_file_list(self) -> None:
        super().get_file_list()
        self.filelist.files = self._without_native_libraries(self.filelist.files)

    def make_release_tree(self, base_dir: str, files: list[str]) -> None:
        super().make_release_tree(base_dir, self._without_native_libraries(files))


cmdclass = {"build_py": build_py, "sdist": sdist}

if _develop is not None:

    class develop(_develop):  # type: ignore[misc, valid-type]
        def run(self) -> None:
            _build_native(ROOT / "build" / "zh_catmut_develop", [SOURCE_PACKAGE])
            super().run()

    cmdclass["develop"] = develop

if _editable_wheel is not None:

    class editable_wheel(_editable_wheel):  # type: ignore[misc, valid-type]
        def run(self) -> None:
            _build_native(ROOT / "build" / "zh_catmut_editable", [SOURCE_PACKAGE])
            super().run()

    cmdclass["editable_wheel"] = editable_wheel

if _bdist_wheel is not None:

    class bdist_wheel(_bdist_wheel):  # type: ignore[misc, valid-type]
        def finalize_options(self) -> None:
            super().finalize_options()
            self.root_is_pure = False
            macos_platform = _macos_wheel_platform_name()
            if macos_platform is not None:
                self.plat_name = macos_platform
                self.plat_name_supplied = True

    cmdclass["bdist_wheel"] = bdist_wheel


setup(cmdclass=cmdclass)
