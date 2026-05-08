# Project Documentation

License: [Apache-2.0](../LICENSE) · GitHub: [mohamedhossammohamed](https://github.com/mohamedhossammohamed) · X: [@MohamedHz72007](https://x.com/MohamedHz72007)

This directory contains the organized technical documentation for the high-performance
Pandas categorical mutation native extension project. The current implementation bridges
Python with a Zig shared library through a strict C ABI to remap contiguous categorical
code buffers without expanding labels into object arrays.

## Documentation Index

| # | Document | Focus Area |
|---|----------|------------|
| 1 | [01-categorical-internals-and-memory.md](01-categorical-internals-and-memory.md) | Pandas categorical internals, memory layout, and the object-mode fallback bottleneck |
| 2 | [02-ffi-zero-copy-architecture.md](02-ffi-zero-copy-architecture.md) | FFI boundary design, C-ABI safety, buffer protocol, and zero-copy mutation mechanics |
| 3 | [03-performance-algorithms.md](03-performance-algorithms.md) | Performance strategies, CPU cache locality, SIMD options, and lookup table tradeoffs |
| 4 | [04-build-systems-and-distribution.md](04-build-systems-and-distribution.md) | Build systems, CI/CD pipelines, cross-platform wheel distribution, and dynamic loading |
| 5 | [publishing.md](publishing.md) | PyPI release workflow, trusted publishing setup, and install verification |
| 6 | [../CHANGELOG.md](../CHANGELOG.md) | Version history, API changes, and native ABI changes |

## Architecture Overview

The system is designed for relabeling categorical columns where the category metadata is
small but the integer codes buffer is large. The goal is to avoid expanding a full column
into object arrays or building large temporary masks.

### Core Architectural Layers

1. **Data Layer** — Pandas Categorical internals and NumPy-backed integer codes
2. **Boundary Layer** — Foreign Function Interface (FFI) via C-ABI with borrowed pointer handoff
3. **Compute Layer** — Native scalar LUT remapping in Zig with explicit validation reports
4. **Packaging Layer** — PEP 517 build hooks, cibuildwheel CI matrices, and platform wheels
5. **Runtime Layer** — Dynamic library loading, Python-owned buffer safety, and validated Pandas reintegration

### Key Design Principles

- **Zero-Copy In-Place Path:** Pass raw memory pointers across the FFI boundary without serialization
- **GIL Bypass:** Release the Python Global Interpreter Lock during native execution to maximize throughput
- **Memory Safety:** Keep Python as the owner of all buffers and expire native borrowed pointers on return
- **CoW Compliance:** Prefer public Pandas APIs and explicit copy semantics for high-level remaps
- **Frictionless Distribution:** Pre-compile wheels for Linux, macOS, and Windows via GitHub Actions + cibuildwheel

## Reading Order

For engineers new to the codebase, the recommended reading order is:

1. **01-categorical-internals-and-memory.md** — Understand *why* the problem exists
2. **02-ffi-zero-copy-architecture.md** — Understand *how* we cross the language boundary safely
3. **03-performance-algorithms.md** — Understand *how* we maximize CPU throughput
4. **04-build-systems-and-distribution.md** — Understand *how* we package and ship the native binaries
5. **publishing.md** — Understand *how* to publish and verify the package
6. **CHANGELOG.md** — Understand *what changed* between releases
