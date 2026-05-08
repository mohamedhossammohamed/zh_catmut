# Project Documentation

License: [Apache-2.0](../LICENSE) · GitHub: [mohamedhossammohamed](https://github.com/mohamedhossammohamed) · X: [@MohamedHz72007](https://x.com/MohamedHz72007)

This directory contains the organized technical documentation for the high-performance
Pandas categorical mutation native extension project. The architecture bridges Python
with modern systems languages (Zig and C# NativeAOT) to enable zero-copy, SIMD-accelerated
in-place mutation of massive categorical DataFrames.

## Documentation Index

| # | Document | Focus Area |
|---|----------|------------|
| 1 | [01-categorical-internals-and-memory.md](01-categorical-internals-and-memory.md) | Pandas categorical internals, memory layout, and the object-mode fallback bottleneck |
| 2 | [02-ffi-zero-copy-architecture.md](02-ffi-zero-copy-architecture.md) | FFI boundary design, C-ABI safety, buffer protocol, and zero-copy mutation mechanics |
| 3 | [03-performance-algorithms.md](03-performance-algorithms.md) | SIMD optimization, CPU cache locality, multi-threading, and lookup table strategies |
| 4 | [04-build-systems-and-distribution.md](04-build-systems-and-distribution.md) | Build systems, CI/CD pipelines, cross-platform wheel distribution, and Arrow PyCapsules |

## Architecture Overview

The system is designed to solve the critical bottleneck of merging or relabeling
categorical columns in Pandas DataFrames exceeding 100 million rows. The standard
Python/NumPy execution path triggers catastrophic memory inflation (object-mode fallback)
that can increase memory usage from ~100 MB to 5-10 GB.

### Core Architectural Layers

1. **Data Layer** — Pandas Categorical internals, BlockManager, and Arrow C Data Interface
2. **Boundary Layer** — Foreign Function Interface (FFI) via C-ABI with zero-copy pointer handoff
3. **Compute Layer** — Native algorithms in Zig / C# NativeAOT utilizing SIMD (AVX-512/NEON) and multi-threading
4. **Packaging Layer** — PEP 517 build backends, cibuildwheel CI matrices, and manylinux-compatible wheels
5. **Runtime Layer** — Dynamic library loading, PyCapsule memory safety, and CoW-compliant reintegration

### Key Design Principles

- **Zero-Copy Mutation:** Pass raw memory pointers across the FFI boundary without serialization or duplication
- **GIL Bypass:** Release the Python Global Interpreter Lock during native execution to maximize throughput
- **Memory Safety:** Use Apache Arrow PyCapsules with bound destructors to prevent unmanaged memory leaks
- **CoW Compliance:** Respect Pandas 3.0 Copy-on-Write semantics via `pd.Categorical.from_codes()` reintegration
- **Frictionless Distribution:** Pre-compile wheels for Linux, macOS, and Windows via GitHub Actions + cibuildwheel

## Reading Order

For engineers new to the codebase, the recommended reading order is:

1. **01-categorical-internals-and-memory.md** — Understand *why* the problem exists
2. **02-ffi-zero-copy-architecture.md** — Understand *how* we cross the language boundary safely
3. **03-performance-algorithms.md** — Understand *how* we maximize CPU throughput
4. **04-build-systems-and-distribution.md** — Understand *how* we package and ship the native binaries
