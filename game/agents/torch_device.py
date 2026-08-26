"""Shared Torch device selection for optional neural training backends."""

from __future__ import annotations

from typing import Any


def resolve_torch_device(
    requested_device: str | None,
    torch_module: Any,
) -> str:
    """Resolve an explicit device or choose CUDA, Apple MPS, then CPU."""
    if requested_device is not None:
        return requested_device
    if torch_module.cuda.is_available():
        return "cuda"

    backends = getattr(torch_module, "backends", None)
    mps_backend = getattr(backends, "mps", None)
    if mps_backend is not None and mps_backend.is_available():
        return "mps"
    return "cpu"
