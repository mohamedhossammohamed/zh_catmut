from __future__ import annotations

import argparse
import os
import platform
import shutil
import tarfile
import tempfile
import urllib.request
from pathlib import Path


ZIG_VERSION = "0.16.0"


def _zig_platform() -> str:
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch = {
        "amd64": "x86_64",
        "x64": "x86_64",
        "x86_64": "x86_64",
        "arm64": "aarch64",
        "aarch64": "aarch64",
    }.get(machine)
    if system == "linux" and arch in {"x86_64", "aarch64"}:
        return f"{arch}-linux"
    if system == "darwin" and arch in {"x86_64", "aarch64"}:
        return f"{arch}-macos"
    raise RuntimeError(
        f"unsupported Zig bootstrap platform: {platform.system()} {platform.machine()}. "
        f"Use a system package manager (e.g. brew install zig) or download manually on Windows/macOS."
    )


def install_zig(install_dir: Path, version: str = ZIG_VERSION) -> Path:
    install_dir.mkdir(parents=True, exist_ok=True)
    binary = install_dir / "zig"
    if binary.exists():
        return binary

    tag = _zig_platform()
    archive_name = f"zig-{tag}-{version}.tar.xz"
    url = f"https://ziglang.org/download/{version}/{archive_name}"

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir).resolve()
        archive_path = Path(temp_dir) / archive_name
        urllib.request.urlretrieve(url, archive_path)
        with tarfile.open(archive_path) as archive:
            for member in archive.getmembers():
                target = (temp_root / member.name).resolve()
                try:
                    target.relative_to(temp_root)
                except ValueError:
                    raise RuntimeError(f"unsafe archive path: {member.name}")
            archive.extractall(temp_dir)
        extracted = Path(temp_dir) / f"zig-{tag}-{version}"
        shutil.copy2(extracted / "zig", binary)
        os.chmod(binary, 0o755)

    return binary


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Zig into a local directory for cibuildwheel.")
    parser.add_argument("--install-dir", type=Path, required=True)
    parser.add_argument("--version", default=ZIG_VERSION)
    args = parser.parse_args()
    binary = install_zig(args.install_dir, args.version)
    print(binary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
