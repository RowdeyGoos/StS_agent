"""Lightweight semantic timing and resource reports for training runs."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from dataclasses import dataclass
import json
import os
from pathlib import Path
import platform
from time import perf_counter, process_time
from typing import Any, Iterator, Mapping

try:
    import resource
except ModuleNotFoundError:  # pragma: no cover - resource is Unix-only
    resource = None


@dataclass(frozen=True, slots=True)
class PhaseProfile:
    """Aggregated timing for one named training phase."""

    name: str
    total_seconds: float
    calls: int
    mean_seconds: float
    max_seconds: float
    wall_time_fraction: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "total_seconds": self.total_seconds,
            "calls": self.calls,
            "mean_seconds": self.mean_seconds,
            "max_seconds": self.max_seconds,
            "wall_time_fraction": self.wall_time_fraction,
        }


@dataclass(frozen=True, slots=True)
class TrainingProfile:
    """Completed timing and resource analysis for one training invocation."""

    algorithm: str
    wall_seconds: float
    process_cpu_seconds: float
    cpu_core_equivalents: float
    logical_cpu_count: int | None
    total_cpu_capacity_fraction: float | None
    peak_rss_bytes: int | None
    system_memory_bytes: int | None
    device: str | None
    torch_version: str | None
    accelerator: dict[str, Any]
    phases: tuple[PhaseProfile, ...]
    unattributed_seconds: float
    bottleneck_phase: str | None
    bottleneck_fraction: float | None
    notes: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "profile_format_version": 1,
            "algorithm": self.algorithm,
            "wall_seconds": self.wall_seconds,
            "process_cpu_seconds": self.process_cpu_seconds,
            "cpu_core_equivalents": self.cpu_core_equivalents,
            "logical_cpu_count": self.logical_cpu_count,
            "total_cpu_capacity_fraction": self.total_cpu_capacity_fraction,
            "peak_rss_bytes": self.peak_rss_bytes,
            "system_memory_bytes": self.system_memory_bytes,
            "device": self.device,
            "torch_version": self.torch_version,
            "accelerator": self.accelerator,
            "phases": [phase.as_dict() for phase in self.phases],
            "unattributed_seconds": self.unattributed_seconds,
            "bottleneck_phase": self.bottleneck_phase,
            "bottleneck_fraction": self.bottleneck_fraction,
            "notes": list(self.notes),
        }

    def summary_dict(self) -> dict[str, Any]:
        """Return checkpoint-sized headline profiling results."""
        return {
            "wall_seconds": self.wall_seconds,
            "cpu_core_equivalents": self.cpu_core_equivalents,
            "total_cpu_capacity_fraction": self.total_cpu_capacity_fraction,
            "peak_rss_bytes": self.peak_rss_bytes,
            "device": self.device,
            "bottleneck_phase": self.bottleneck_phase,
            "bottleneck_fraction": self.bottleneck_fraction,
        }

    def write_json(self, path: str | Path) -> Path:
        """Write the full report to a JSON file."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return output_path


class TrainingProfiler:
    """Collect synchronized timings for named, non-overlapping phases."""

    def __init__(self, algorithm: str) -> None:
        self.algorithm = algorithm
        self._started_wall = perf_counter()
        self._started_cpu = process_time()
        self._timings: dict[str, list[float]] = {}
        self._device: str | None = None
        self._torch_module: Any | None = None
        self._synchronize: Any | None = None
        self._external_process_cpu_seconds = 0.0
        self._finalized_profile: TrainingProfile | None = None

    def attach_torch(self, torch_module: Any, device: str) -> None:
        """Attach a Torch backend for accurate asynchronous accelerator timing."""
        self._torch_module = torch_module
        self._device = str(device)
        device_type = self._device.split(":", maxsplit=1)[0]
        if device_type == "cuda":
            self._synchronize = lambda: torch_module.cuda.synchronize(self._device)
            reset_peak = getattr(torch_module.cuda, "reset_peak_memory_stats", None)
            if reset_peak is not None:
                reset_peak(self._device)
        elif device_type == "mps":
            mps_module = getattr(torch_module, "mps", None)
            self._synchronize = getattr(mps_module, "synchronize", None)

    @contextmanager
    def measure(self, name: str, *, synchronize: bool = True) -> Iterator[None]:
        """Measure one semantic phase, synchronizing accelerators at its boundaries."""
        if self._finalized_profile is not None:
            raise RuntimeError("Cannot record phases after the profile is finalized.")
        if synchronize:
            self._sync()
        started_at = perf_counter()
        try:
            yield
        finally:
            if synchronize:
                self._sync()
            self._timings.setdefault(name, []).append(perf_counter() - started_at)

    def finalize(self) -> TrainingProfile:
        """Freeze and return the complete timing and resource report."""
        if self._finalized_profile is not None:
            return self._finalized_profile
        self._sync()
        wall_seconds = max(0.0, perf_counter() - self._started_wall)
        process_cpu_seconds = max(
            0.0,
            process_time()
            - self._started_cpu
            + self._external_process_cpu_seconds,
        )
        cpu_core_equivalents = (
            0.0 if wall_seconds == 0.0 else process_cpu_seconds / wall_seconds
        )
        logical_cpu_count = os.cpu_count()
        total_cpu_capacity_fraction = (
            None
            if not logical_cpu_count
            else cpu_core_equivalents / logical_cpu_count
        )

        phase_profiles = tuple(
            sorted(
                (
                    PhaseProfile(
                        name=name,
                        total_seconds=sum(durations),
                        calls=len(durations),
                        mean_seconds=sum(durations) / len(durations),
                        max_seconds=max(durations),
                        wall_time_fraction=(
                            0.0 if wall_seconds == 0.0 else sum(durations) / wall_seconds
                        ),
                    )
                    for name, durations in self._timings.items()
                    if durations
                ),
                key=lambda phase: phase.total_seconds,
                reverse=True,
            )
        )
        measured_seconds = sum(phase.total_seconds for phase in phase_profiles)
        bottleneck = phase_profiles[0] if phase_profiles else None
        accelerator = _accelerator_snapshot(self._torch_module, self._device)
        notes = _analysis_notes(
            bottleneck=bottleneck,
            cpu_core_equivalents=cpu_core_equivalents,
            logical_cpu_count=logical_cpu_count,
            device=self._device,
            accelerator=accelerator,
        )
        self._finalized_profile = TrainingProfile(
            algorithm=self.algorithm,
            wall_seconds=wall_seconds,
            process_cpu_seconds=process_cpu_seconds,
            cpu_core_equivalents=cpu_core_equivalents,
            logical_cpu_count=logical_cpu_count,
            total_cpu_capacity_fraction=total_cpu_capacity_fraction,
            peak_rss_bytes=_peak_rss_bytes(),
            system_memory_bytes=_system_memory_bytes(),
            device=self._device,
            torch_version=(
                None
                if self._torch_module is None
                else str(getattr(self._torch_module, "__version__", "unknown"))
            ),
            accelerator=accelerator,
            phases=phase_profiles,
            unattributed_seconds=max(0.0, wall_seconds - measured_seconds),
            bottleneck_phase=None if bottleneck is None else bottleneck.name,
            bottleneck_fraction=(
                None if bottleneck is None else bottleneck.wall_time_fraction
            ),
            notes=notes,
        )
        return self._finalized_profile

    def add_external_process_cpu_seconds(self, seconds: float) -> None:
        """Include CPU time consumed by persistent training worker processes."""
        if self._finalized_profile is not None:
            raise RuntimeError("Cannot add worker CPU time after finalization.")
        if seconds < 0.0:
            raise ValueError("External process CPU seconds cannot be negative.")
        self._external_process_cpu_seconds += seconds

    def _sync(self) -> None:
        if self._synchronize is not None:
            self._synchronize()


def profile_phase(
    profiler: TrainingProfiler | None,
    name: str,
    *,
    synchronize: bool = True,
) -> Any:
    """Return a profiling context manager without branching at each call site."""
    return (
        nullcontext()
        if profiler is None
        else profiler.measure(name, synchronize=synchronize)
    )


def print_training_profile(profile: TrainingProfile, max_phases: int = 12) -> None:
    """Print a compact human-readable bottleneck and resource report."""
    print(
        "Training profile: "
        f"wall={profile.wall_seconds:.3f}s "
        f"process_cpu={profile.process_cpu_seconds:.3f}s "
        f"cpu_cores={profile.cpu_core_equivalents:.2f} "
        f"device={profile.device or 'unknown'}"
    )
    capacity = (
        "n/a"
        if profile.total_cpu_capacity_fraction is None
        else f"{profile.total_cpu_capacity_fraction * 100.0:.1f}%"
    )
    print(
        "  Resources: "
        f"logical_cpus={profile.logical_cpu_count or 'unknown'} "
        f"total_cpu_capacity={capacity} "
        f"peak_rss={_format_bytes(profile.peak_rss_bytes)} "
        f"system_memory={_format_bytes(profile.system_memory_bytes)}"
    )
    print(f"  Accelerator: {_accelerator_summary(profile.accelerator)}")
    for phase in profile.phases[:max_phases]:
        print(
            f"  {phase.name}: {phase.total_seconds:.3f}s "
            f"({phase.wall_time_fraction * 100.0:.1f}%) "
            f"calls={phase.calls} mean={phase.mean_seconds * 1000.0:.3f}ms"
        )
    if profile.unattributed_seconds > 0.0:
        fraction = profile.unattributed_seconds / max(profile.wall_seconds, 1e-12)
        print(
            f"  unattributed: {profile.unattributed_seconds:.3f}s "
            f"({fraction * 100.0:.1f}%)"
        )
    for note in profile.notes:
        print(f"  Note: {note}")


def load_training_profile(path: str | Path) -> dict[str, Any]:
    """Load a profile JSON directly or from a standard training run directory."""
    candidate = Path(path)
    profile_path = candidate / "profile.json" if candidate.is_dir() else candidate
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("profile_format_version") != 1:
        raise ValueError(f"Unsupported training profile payload: {profile_path}")
    return payload


def print_training_profile_payload(payload: Mapping[str, Any], max_phases: int = 12) -> None:
    """Print a previously saved profile without reconstructing dataclasses."""
    print(
        "Training profile: "
        f"wall={float(payload['wall_seconds']):.3f}s "
        f"process_cpu={float(payload['process_cpu_seconds']):.3f}s "
        f"cpu_cores={float(payload['cpu_core_equivalents']):.2f} "
        f"device={payload.get('device') or 'unknown'}"
    )
    capacity_value = payload.get("total_cpu_capacity_fraction")
    capacity = (
        "n/a"
        if capacity_value is None
        else f"{float(capacity_value) * 100.0:.1f}%"
    )
    print(
        "  Resources: "
        f"logical_cpus={payload.get('logical_cpu_count') or 'unknown'} "
        f"total_cpu_capacity={capacity} "
        f"peak_rss={_format_bytes(payload.get('peak_rss_bytes'))} "
        f"system_memory={_format_bytes(payload.get('system_memory_bytes'))}"
    )
    accelerator = payload.get("accelerator", {})
    print(
        "  Accelerator: "
        f"{_accelerator_summary(accelerator if isinstance(accelerator, Mapping) else {})}"
    )
    phases = payload.get("phases", [])
    if not isinstance(phases, list):
        raise ValueError("Training profile 'phases' must be a list.")
    for phase in phases[:max_phases]:
        if not isinstance(phase, Mapping):
            continue
        print(
            f"  {phase['name']}: {float(phase['total_seconds']):.3f}s "
            f"({float(phase['wall_time_fraction']) * 100.0:.1f}%) "
            f"calls={int(phase['calls'])} "
            f"mean={float(phase['mean_seconds']) * 1000.0:.3f}ms"
        )
    unattributed_seconds = float(payload.get("unattributed_seconds", 0.0))
    wall_seconds = max(float(payload["wall_seconds"]), 1e-12)
    if unattributed_seconds > 0.0:
        print(
            f"  unattributed: {unattributed_seconds:.3f}s "
            f"({unattributed_seconds / wall_seconds * 100.0:.1f}%)"
        )
    for note in payload.get("notes", []):
        print(f"  Note: {note}")


def _analysis_notes(
    *,
    bottleneck: PhaseProfile | None,
    cpu_core_equivalents: float,
    logical_cpu_count: int | None,
    device: str | None,
    accelerator: Mapping[str, Any],
) -> tuple[str, ...]:
    notes: list[str] = []
    if bottleneck is not None:
        notes.append(
            f"Largest measured phase is {bottleneck.name} at "
            f"{bottleneck.wall_time_fraction * 100.0:.1f}% of wall time."
        )
        if bottleneck.name == "ppo.gradient_updates":
            notes.append(
                "Optimization is the measured bottleneck; increase PPO minibatch size "
                "or reduce PPO epochs before increasing environment count."
            )
        elif bottleneck.name.startswith("ppo.rollout"):
            notes.append(
                "Rollout collection is the measured bottleneck; more environment slots "
                "or simulator optimization may improve throughput."
            )
        elif bottleneck.name == "ppo.evaluation":
            notes.append(
                "Evaluation is the measured bottleneck; reduce eval episodes or disable "
                "periodic evaluation when measuring training throughput."
            )
        elif bottleneck.name == "ppo.setup.environment_workers":
            notes.append(
                "Worker startup is the measured bottleneck; process-parallel collection "
                "is most useful when this fixed cost can amortize over a longer run."
            )
    if logical_cpu_count:
        notes.append(
            f"Training averaged {cpu_core_equivalents:.2f} logical CPU cores out "
            f"of {logical_cpu_count}; this includes CPU time reported by PPO workers."
        )
    device_type = None if device is None else device.split(":", maxsplit=1)[0]
    if device_type in {"cuda", "mps"}:
        notes.append(
            "Portable PyTorch APIs do not provide reliable average accelerator compute "
            "utilization here; use Activity Monitor GPU History for MPS or nvidia-smi "
            "for CUDA alongside this phase report."
        )
    memory_fraction = accelerator.get("memory_fraction")
    if isinstance(memory_fraction, (int, float)):
        notes.append(
            f"Peak/current reported accelerator memory is approximately "
            f"{float(memory_fraction) * 100.0:.1f}% of device capacity."
        )
    return tuple(notes)


def _accelerator_snapshot(torch_module: Any | None, device: str | None) -> dict[str, Any]:
    if torch_module is None or device is None:
        return {"backend": None, "utilization_available": False}
    device_type = device.split(":", maxsplit=1)[0]
    if device_type == "cuda":
        cuda = torch_module.cuda
        properties = cuda.get_device_properties(device)
        peak_allocated = int(cuda.max_memory_allocated(device))
        peak_reserved = int(cuda.max_memory_reserved(device))
        total_memory = int(properties.total_memory)
        return {
            "backend": "cuda",
            "device_name": str(properties.name),
            "peak_memory_allocated_bytes": peak_allocated,
            "peak_memory_reserved_bytes": peak_reserved,
            "total_memory_bytes": total_memory,
            "memory_fraction": (
                None if total_memory <= 0 else peak_reserved / total_memory
            ),
            "utilization_available": False,
        }
    if device_type == "mps":
        mps = getattr(torch_module, "mps", None)
        current_allocated = _optional_int_call(mps, "current_allocated_memory")
        driver_allocated = _optional_int_call(mps, "driver_allocated_memory")
        recommended_max = _optional_int_call(mps, "recommended_max_memory")
        return {
            "backend": "mps",
            "current_allocated_memory_bytes": current_allocated,
            "driver_allocated_memory_bytes": driver_allocated,
            "recommended_max_memory_bytes": recommended_max,
            "memory_fraction": (
                None
                if not recommended_max or driver_allocated is None
                else driver_allocated / recommended_max
            ),
            "utilization_available": False,
        }
    return {"backend": device_type, "utilization_available": False}


def _optional_int_call(owner: Any, name: str) -> int | None:
    function = getattr(owner, name, None)
    if function is None:
        return None
    try:
        return int(function())
    except (RuntimeError, TypeError):
        return None


def _peak_rss_bytes() -> int | None:
    if resource is None:
        return None
    peak_rss = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak_rss if platform.system() == "Darwin" else peak_rss * 1024


def _system_memory_bytes() -> int | None:
    try:
        return int(os.sysconf("SC_PAGE_SIZE")) * int(os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, OSError, TypeError, ValueError):
        return None


def _format_bytes(value: Any) -> str:
    if not isinstance(value, (int, float)) or value < 0:
        return "n/a"
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024.0 or unit == "TiB":
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TiB"


def _accelerator_summary(accelerator: Mapping[str, Any]) -> str:
    backend = accelerator.get("backend") or "none"
    fragments = [f"backend={backend}"]
    if accelerator.get("device_name"):
        fragments.append(f"device={accelerator['device_name']}")
    if backend == "cuda":
        fragments.append(
            "peak_reserved="
            f"{_format_bytes(accelerator.get('peak_memory_reserved_bytes'))}"
        )
        fragments.append(
            f"total_memory={_format_bytes(accelerator.get('total_memory_bytes'))}"
        )
    elif backend == "mps":
        fragments.append(
            "driver_allocated="
            f"{_format_bytes(accelerator.get('driver_allocated_memory_bytes'))}"
        )
        fragments.append(
            "recommended_max="
            f"{_format_bytes(accelerator.get('recommended_max_memory_bytes'))}"
        )
    fragments.append(
        f"compute_utilization_available={bool(accelerator.get('utilization_available'))}"
    )
    return " ".join(fragments)
