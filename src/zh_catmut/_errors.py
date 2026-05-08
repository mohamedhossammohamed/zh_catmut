from __future__ import annotations

from typing import Any


class ZhCatmutError(Exception):
    """Base exception for zh_catmut failures."""


class NativeLibraryLoadError(ZhCatmutError):
    """Raised when the bundled native library cannot be loaded."""


class NativeStatusError(ZhCatmutError):
    """Raised when the native library returns a non-zero status."""

    def __init__(
        self, context: str, status: int, message: str, report: Any = None
    ) -> None:
        super().__init__(f"{context} failed: {message} ({status})")
        self.context = context
        self.status = status
        self.native_message = message
        self.report = report


class MemoryGateError(ZhCatmutError, ValueError):
    """Raised when Python-side shape, dtype, or memory gates reject an input."""


class CopyOnWriteSafetyError(MemoryGateError):
    """Raised when in-place mutation cannot be proven safe under Pandas CoW."""
