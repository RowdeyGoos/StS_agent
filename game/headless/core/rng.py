"""Deterministic, named game-randomness streams for headless fixtures.

This module intentionally models only project-authored structural randomness.
It does not claim parity with a target game's RNG domains, seeds, or draw order.
"""

from __future__ import annotations

from collections.abc import Mapping, MutableSequence, Sequence
from dataclasses import dataclass
from random import Random
from typing import Any, TypeVar

RANDOM_SERVICE_SCHEMA = "python_mt19937_v1"
RANDOM_SERVICE_SNAPSHOT_VERSION = 1

_MT19937_STATE_VERSION = 3
_MT19937_WORD_COUNT = 624
_MT19937_STATE_LENGTH = _MT19937_WORD_COUNT + 1
_MT19937_WORD_MAX = (1 << 32) - 1
_SNAPSHOT_KEYS = frozenset({"schema", "snapshot_version", "seed", "streams"})
_STREAM_SNAPSHOT_KEYS = frozenset({"request_count", "state"})
_STATE_SNAPSHOT_KEYS = frozenset({"version", "internal_state", "gauss_next"})

T = TypeVar("T")


@dataclass(slots=True)
class _NamedStream:
    rng: Random
    request_count: int = 0


class GameRandomService:
    """Own deterministic MT19937 streams for game rules, never policy sampling.

    Streams are initialized lazily from the service seed and their exact name.
    Therefore, draws from one stream cannot perturb the state or results of
    another. A request counter records successful public RNG operations, not
    the implementation-specific number of underlying MT19937 draws.
    """

    def __init__(self, seed: int) -> None:
        self._seed = self._validate_seed(seed)
        self._streams: dict[str, _NamedStream] = {}

    @property
    def seed(self) -> int:
        """Return the immutable root seed for the current service state."""
        return self._seed

    @property
    def stream_names(self) -> tuple[str, ...]:
        """Return initialized stream names in canonical order."""
        return tuple(sorted(self._streams))

    def request_count(self, stream_name: str) -> int:
        """Return successful-operation count for a named stream, or zero."""
        self._validate_stream_name(stream_name)
        stream = self._streams.get(stream_name)
        return 0 if stream is None else stream.request_count

    def randint(self, stream_name: str, lower: int, upper: int) -> int:
        """Return an inclusive integer draw from one named game stream."""
        self._validate_integer(lower, "lower")
        self._validate_integer(upper, "upper")
        if lower > upper:
            raise ValueError("lower must not exceed upper.")

        stream = self._get_stream(stream_name)
        result = stream.rng.randint(lower, upper)
        stream.request_count += 1
        return result

    def choice(self, stream_name: str, values: Sequence[T]) -> T:
        """Return one item from a non-empty sequence using one named stream."""
        if len(values) == 0:
            raise ValueError("values must not be empty.")

        stream = self._get_stream(stream_name)
        result = stream.rng.choice(values)
        stream.request_count += 1
        return result

    def random(self, stream_name: str) -> float:
        """Draw a uniform value in [0, 1) from an owned stream."""
        stream = self._get_stream(stream_name)
        result = stream.rng.random()
        stream.request_count += 1
        return result

    def shuffle(self, stream_name: str, values: MutableSequence[T]) -> None:
        """Shuffle a mutable sequence in place using one named stream."""
        if not isinstance(values, MutableSequence):
            raise TypeError("values must be a mutable sequence.")

        stream = self._get_stream(stream_name)
        stream.rng.shuffle(values)
        stream.request_count += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a strict, JSON-safe snapshot for exact continuation.

        The returned object contains only JSON-compatible primitives, lists,
        and dictionaries. It is private engine state, never a policy feature.
        """
        return {
            "schema": RANDOM_SERVICE_SCHEMA,
            "snapshot_version": RANDOM_SERVICE_SNAPSHOT_VERSION,
            "seed": self._seed,
            "streams": {
                stream_name: self._serialize_stream(stream)
                for stream_name, stream in sorted(self._streams.items())
            },
        }

    def restore(self, snapshot: Mapping[str, Any]) -> None:
        """Replace this service state from a strict versioned snapshot.

        Validation completes before any local state changes, so rejected input
        leaves the existing service untouched.
        """
        seed, streams = self._parse_snapshot(snapshot)
        self._seed = seed
        self._streams = streams

    def _get_stream(self, stream_name: str) -> _NamedStream:
        self._validate_stream_name(stream_name)
        stream = self._streams.get(stream_name)
        if stream is None:
            stream = _NamedStream(rng=Random(self._derive_stream_seed(stream_name)))
            self._streams[stream_name] = stream
        return stream

    def _derive_stream_seed(self, stream_name: str) -> int:
        """Return a stable non-cryptographic 64-bit seed for one stream name."""
        value = 0xCBF29CE484222325
        payload = f"{self._seed}:{len(stream_name)}:{stream_name}".encode("utf-8")
        for byte in payload:
            value ^= byte
            value = (value * 0x100000001B3) & ((1 << 64) - 1)
        return value

    @classmethod
    def _serialize_stream(cls, stream: _NamedStream) -> dict[str, Any]:
        version, internal_state, gauss_next = stream.rng.getstate()
        if version != _MT19937_STATE_VERSION or gauss_next is not None:
            raise RuntimeError("Unexpected Python MT19937 state shape.")
        return {
            "request_count": stream.request_count,
            "state": {
                "version": version,
                "internal_state": list(internal_state),
                "gauss_next": gauss_next,
            },
        }

    @classmethod
    def _parse_snapshot(
        cls,
        snapshot: Mapping[str, Any],
    ) -> tuple[int, dict[str, _NamedStream]]:
        if not isinstance(snapshot, Mapping):
            raise ValueError("RNG snapshot must be a mapping.")
        if set(snapshot) != _SNAPSHOT_KEYS:
            raise ValueError("RNG snapshot fields do not match the required schema.")
        if snapshot["schema"] != RANDOM_SERVICE_SCHEMA:
            raise ValueError("Unsupported RNG snapshot schema.")
        snapshot_version = snapshot["snapshot_version"]
        cls._validate_integer(snapshot_version, "snapshot_version")
        if snapshot_version != RANDOM_SERVICE_SNAPSHOT_VERSION:
            raise ValueError("Unsupported RNG snapshot version.")

        seed = cls._validate_seed(snapshot["seed"])
        serialized_streams = snapshot["streams"]
        if not isinstance(serialized_streams, Mapping):
            raise ValueError("RNG snapshot streams must be a mapping.")

        streams: dict[str, _NamedStream] = {}
        for stream_name, serialized_stream in serialized_streams.items():
            cls._validate_stream_name(stream_name)
            streams[stream_name] = cls._parse_stream(serialized_stream)
        return seed, streams

    @classmethod
    def _parse_stream(cls, serialized_stream: Any) -> _NamedStream:
        if not isinstance(serialized_stream, Mapping):
            raise ValueError("RNG stream snapshot must be a mapping.")
        if set(serialized_stream) != _STREAM_SNAPSHOT_KEYS:
            raise ValueError("RNG stream snapshot fields do not match the required schema.")

        request_count = serialized_stream["request_count"]
        cls._validate_integer(request_count, "request_count")
        if request_count < 0:
            raise ValueError("request_count must be non-negative.")

        state = serialized_stream["state"]
        if not isinstance(state, Mapping) or set(state) != _STATE_SNAPSHOT_KEYS:
            raise ValueError("RNG state fields do not match the required schema.")
        state_version = state["version"]
        cls._validate_integer(state_version, "RNG state version")
        if state_version != _MT19937_STATE_VERSION:
            raise ValueError("Unsupported Python MT19937 state version.")
        if state["gauss_next"] is not None:
            raise ValueError("RNG snapshots with gauss_next are not supported.")

        internal_state = state["internal_state"]
        if not isinstance(internal_state, list) or len(internal_state) != _MT19937_STATE_LENGTH:
            raise ValueError("RNG internal_state has an invalid length.")
        for word in internal_state[:_MT19937_WORD_COUNT]:
            cls._validate_integer(word, "RNG state word")
            if not 0 <= word <= _MT19937_WORD_MAX:
                raise ValueError("RNG state word is outside the MT19937 range.")
        index = internal_state[-1]
        cls._validate_integer(index, "RNG state index")
        if not 0 <= index <= _MT19937_WORD_COUNT:
            raise ValueError("RNG state index is outside the MT19937 range.")

        rng = Random()
        try:
            rng.setstate((_MT19937_STATE_VERSION, tuple(internal_state), None))
        except (TypeError, ValueError) as error:
            raise ValueError("RNG internal_state is invalid.") from error
        return _NamedStream(rng=rng, request_count=request_count)

    @staticmethod
    def _validate_seed(seed: Any) -> int:
        GameRandomService._validate_integer(seed, "seed")
        return seed

    @staticmethod
    def _validate_stream_name(stream_name: Any) -> None:
        if not isinstance(stream_name, str) or not stream_name:
            raise ValueError("stream_name must be a non-empty string.")

    @staticmethod
    def _validate_integer(value: Any, name: str) -> None:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{name} must be an integer.")


def from_snapshot(snapshot):
    """Restore either explicit fixture randomness or the pinned native profile."""
    from game.headless.core.native_service import NativeRandomService, SCHEMA
    rng = NativeRandomService(snapshot['seed']) if snapshot.get('schema') == SCHEMA else GameRandomService(snapshot['seed'])
    rng.restore(snapshot)
    return rng
