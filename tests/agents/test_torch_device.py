"""Tests for CUDA, Apple MPS, and CPU device selection."""

from __future__ import annotations

from game.agents.torch_device import resolve_torch_device


class _Availability:
    def __init__(self, available: bool) -> None:
        self.available = available

    def is_available(self) -> bool:
        return self.available


class _Backends:
    def __init__(self, mps_available: bool) -> None:
        self.mps = _Availability(mps_available)


class _FakeTorch:
    def __init__(self, cuda_available: bool, mps_available: bool) -> None:
        self.cuda = _Availability(cuda_available)
        self.backends = _Backends(mps_available)


def test_explicit_torch_device_is_preserved() -> None:
    fake_torch = _FakeTorch(cuda_available=True, mps_available=True)

    assert resolve_torch_device("cpu", fake_torch) == "cpu"
    assert resolve_torch_device("mps", fake_torch) == "mps"


def test_cuda_is_preferred_when_available() -> None:
    fake_torch = _FakeTorch(cuda_available=True, mps_available=True)

    assert resolve_torch_device(None, fake_torch) == "cuda"


def test_mps_is_used_when_cuda_is_unavailable() -> None:
    fake_torch = _FakeTorch(cuda_available=False, mps_available=True)

    assert resolve_torch_device(None, fake_torch) == "mps"


def test_cpu_is_used_when_no_accelerator_is_available() -> None:
    fake_torch = _FakeTorch(cuda_available=False, mps_available=False)

    assert resolve_torch_device(None, fake_torch) == "cpu"


def test_old_torch_without_mps_backend_falls_back_to_cpu() -> None:
    fake_torch = _FakeTorch(cuda_available=False, mps_available=False)
    del fake_torch.backends.mps

    assert resolve_torch_device(None, fake_torch) == "cpu"
