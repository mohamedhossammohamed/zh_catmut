from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
TARGET_URLS = {
    "testpypi": "https://test.pypi.org/legacy/",
    "pypi": "https://upload.pypi.org/legacy/",
}
TOKEN_KEYS = {
    "testpypi": "TEST_PYPI_API_TOKEN",
    "pypi": "PYPI_API_TOKEN",
}


def _load_env(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"{path} does not exist; copy .env.example to .env and add your token")

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            raise SystemExit(f"{path}:{line_number}: expected KEY=VALUE")
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            os.environ.setdefault(key, value)


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+ " + " ".join(command))
    subprocess.check_call(command, cwd=ROOT, env=env)


def _distribution_files(directory: Path) -> list[str]:
    files = sorted(str(path) for path in directory.glob("*") if path.suffix in {".whl", ".gz"})
    if not files:
        raise SystemExit(f"no distributions found in {directory}")
    return files


def _twine_env(target: str) -> dict[str, str]:
    env = os.environ.copy()
    env["TWINE_USERNAME"] = env.get("TWINE_USERNAME") or "__token__"
    if not env.get("TWINE_PASSWORD"):
        token_key = TOKEN_KEYS[target]
        token = env.get(token_key)
        if not token:
            raise SystemExit(f"missing {token_key} in .env")
        env["TWINE_PASSWORD"] = token
    return env


def _check_and_upload(files: Iterable[str], target: str, *, yes: bool) -> None:
    file_list = list(files)
    _run([sys.executable, "-m", "twine", "check", *file_list])
    if not yes:
        raise SystemExit("checked distributions; refusing to upload without --yes")
    _run(
        [sys.executable, "-m", "twine", "upload", "--repository-url", TARGET_URLS[target], *file_list],
        env=_twine_env(target),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and publish zh-catmut using a local ignored .env token.")
    parser.add_argument("--target", choices=sorted(TARGET_URLS), default="testpypi")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--no-build", action="store_true", help="upload existing files from dist instead of building")
    parser.add_argument("--yes", action="store_true", help="actually upload distributions")
    args = parser.parse_args(argv)

    _load_env(args.env_file)

    if args.no_build:
        _check_and_upload(_distribution_files(ROOT / "dist"), args.target, yes=args.yes)
    else:
        with tempfile.TemporaryDirectory(prefix="zh-catmut-dist-") as temp_dir:
            dist_dir = Path(temp_dir)
            _run([sys.executable, "-m", "build", "--outdir", str(dist_dir)])
            _check_and_upload(_distribution_files(dist_dir), args.target, yes=args.yes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
