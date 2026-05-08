# Build Systems and Distribution

`zh_catmut` ships a Python package plus a small Zig shared library. The Python layer owns Pandas/NumPy validation and dynamic loading; the Zig layer exposes a stable C ABI declared in `include/zh_catmut_abi.h`.

## Local source builds

```bash
python -m pip install -e ".[test]"
python -m pytest -q
(cd native && zig build test)
```

The custom `setup.py` build commands call `zig build`, copy the platform shared library into the `zh_catmut` package, and mark wheels as platform-specific. Source distributions intentionally exclude generated native libraries so they can be rebuilt by the installer.

## ABI ownership

The C ABI accepts only borrowed pointers, primitive sizes, flags, and caller-allocated report structs. Native code never retains, reallocates, or frees Python-owned memory. Python validates shape, dtype, contiguity, alignment, writeability, and Pandas Copy-on-Write risk before exporting pointers.

The ABI version is bumped when exported function signatures or report layouts change. Python verifies the loaded shared library version at import-time through `zhcm_abi_version()`.

## Wheel matrix

The release workflow builds CPython 3.9 through 3.13 wheels for:

- Linux x86_64 (`manylinux`, glibc)
- macOS x86_64
- macOS arm64
- Windows AMD64

Linux builds use `tool.cibuildwheel.linux.before-build` to install Zig inside the manylinux container before each wheel build. macOS and Windows runners install Zig before invoking `cibuildwheel`.

## Verification before publishing

Before publishing a release, verify:

```bash
python -m build
python -m twine check dist/*
python -m pytest -q
python -m zh_catmut doctor
```

For release candidates, run the publish workflow against TestPyPI and install each produced wheel in a clean environment with:

```bash
python -m pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ zh-catmut
python -m zh_catmut doctor
python -m pytest -q tests
```
