"""Strict private snapshot codec for ``reduced_world_state_v0``.

Snapshots are complete engine continuation records.  They intentionally have a
different type, schema, and API from ``headless_v0.PublicObservation``.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from game.contracts.headless_v0 import CONTRACT_FINGERPRINT
from game.engine.headless_state import (
    WORLD_SEMANTIC_KEY_VERSION,
    WORLD_STATE_FINGERPRINT,
    WORLD_STATE_SCHEMA,
    WORLD_STATE_VERSION,
    StateValidationError,
    WorldState,
    _freeze_private_json,
    _load_private_object,
    _require_fields,
    _thaw_private_json,
    _validate_fingerprint,
    canonical_private_json,
)


PRIVATE_SNAPSHOT_SCHEMA = "reduced_world_state_v0.private_snapshot.v1"
PRIVATE_SNAPSHOT_VERSION = 1


class SnapshotValidationError(ValueError):
    """Raised when a private snapshot is malformed or incompatible."""


@dataclass(frozen=True, slots=True)
class PrivateWorldSnapshot:
    """JSON-safe, immutable envelope for complete private world state."""

    contract_fingerprint: str
    content_fingerprint: str
    rules_fingerprint: str
    state_fingerprint: str
    semantic_key: str
    payload: Mapping[str, Any]
    snapshot_schema: str = PRIVATE_SNAPSHOT_SCHEMA
    snapshot_version: int = PRIVATE_SNAPSHOT_VERSION
    state_schema: str = WORLD_STATE_SCHEMA
    state_version: int = WORLD_STATE_VERSION
    semantic_key_version: str = WORLD_SEMANTIC_KEY_VERSION

    def __post_init__(self) -> None:
        if self.snapshot_schema != PRIVATE_SNAPSHOT_SCHEMA:
            raise SnapshotValidationError("Unsupported private snapshot schema.")
        if (
            not isinstance(self.snapshot_version, int)
            or isinstance(self.snapshot_version, bool)
            or self.snapshot_version != PRIVATE_SNAPSHOT_VERSION
        ):
            raise SnapshotValidationError("Unsupported private snapshot version.")
        if self.state_schema != WORLD_STATE_SCHEMA:
            raise SnapshotValidationError("Unsupported world-state schema identity.")
        if (
            not isinstance(self.state_version, int)
            or isinstance(self.state_version, bool)
            or self.state_version != WORLD_STATE_VERSION
        ):
            raise SnapshotValidationError("Unsupported world-state schema identity.")
        if self.semantic_key_version != WORLD_SEMANTIC_KEY_VERSION:
            raise SnapshotValidationError("Unsupported semantic-key version.")
        for name in (
            "contract_fingerprint",
            "content_fingerprint",
            "rules_fingerprint",
            "state_fingerprint",
            "semantic_key",
        ):
            try:
                _validate_fingerprint(getattr(self, name), f"snapshot.{name}")
            except StateValidationError as error:
                raise SnapshotValidationError(str(error)) from error
        if not isinstance(self.payload, Mapping):
            raise SnapshotValidationError("snapshot.payload must be an object.")
        try:
            frozen = _freeze_private_json(self.payload, "snapshot.payload")
        except StateValidationError as error:
            raise SnapshotValidationError(str(error)) from error
        object.__setattr__(self, "payload", frozen)

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_fingerprint": self.content_fingerprint,
            "contract_fingerprint": self.contract_fingerprint,
            "payload": _thaw_private_json(self.payload),
            "rules_fingerprint": self.rules_fingerprint,
            "semantic_key": self.semantic_key,
            "semantic_key_version": self.semantic_key_version,
            "snapshot_schema": self.snapshot_schema,
            "snapshot_version": self.snapshot_version,
            "state_fingerprint": self.state_fingerprint,
            "state_schema": self.state_schema,
            "state_version": self.state_version,
        }

    def to_json(self) -> str:
        return canonical_private_json(self.to_dict())

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PrivateWorldSnapshot":
        fields = {
            "content_fingerprint",
            "contract_fingerprint",
            "payload",
            "rules_fingerprint",
            "semantic_key",
            "semantic_key_version",
            "snapshot_schema",
            "snapshot_version",
            "state_fingerprint",
            "state_schema",
            "state_version",
        }
        try:
            _require_fields(value, fields, "snapshot")
        except StateValidationError as error:
            raise SnapshotValidationError(str(error)) from error
        payload = value["payload"]
        if not isinstance(payload, Mapping):
            raise SnapshotValidationError("snapshot.payload must be an object.")
        return cls(
            contract_fingerprint=value["contract_fingerprint"],
            content_fingerprint=value["content_fingerprint"],
            rules_fingerprint=value["rules_fingerprint"],
            state_fingerprint=value["state_fingerprint"],
            semantic_key=value["semantic_key"],
            payload=payload,
            snapshot_schema=value["snapshot_schema"],
            snapshot_version=value["snapshot_version"],
            state_schema=value["state_schema"],
            state_version=value["state_version"],
            semantic_key_version=value["semantic_key_version"],
        )

    @classmethod
    def from_json(cls, text: str | bytes | bytearray) -> "PrivateWorldSnapshot":
        try:
            value = _load_private_object(text)
        except StateValidationError as error:
            raise SnapshotValidationError(str(error)) from error
        return cls.from_dict(value)


@dataclass(frozen=True, slots=True)
class WorldSnapshotCodec:
    """Capture and restore exact worlds for one fingerprint compatibility set."""

    content_fingerprint: str
    rules_fingerprint: str
    contract_fingerprint: str = CONTRACT_FINGERPRINT
    state_fingerprint: str = WORLD_STATE_FINGERPRINT

    def __post_init__(self) -> None:
        for name in (
            "content_fingerprint",
            "rules_fingerprint",
            "contract_fingerprint",
            "state_fingerprint",
        ):
            try:
                _validate_fingerprint(getattr(self, name), f"codec.{name}")
            except StateValidationError as error:
                raise SnapshotValidationError(str(error)) from error
        if self.contract_fingerprint != CONTRACT_FINGERPRINT:
            raise SnapshotValidationError("Codec contract fingerprint is incompatible.")
        if self.state_fingerprint != WORLD_STATE_FINGERPRINT:
            raise SnapshotValidationError("Codec state fingerprint is incompatible.")

    def capture(self, state: WorldState) -> PrivateWorldSnapshot:
        if not isinstance(state, WorldState):
            raise SnapshotValidationError("state has the wrong type.")
        try:
            state.validate()
        except StateValidationError as error:
            raise SnapshotValidationError("Cannot snapshot invalid world state.") from error
        if state.contract_fingerprint != self.contract_fingerprint:
            raise SnapshotValidationError("World contract fingerprint is incompatible.")
        if state.content_fingerprint != self.content_fingerprint:
            raise SnapshotValidationError("World content fingerprint is incompatible.")
        if state.rules_fingerprint != self.rules_fingerprint:
            raise SnapshotValidationError("World rules fingerprint is incompatible.")
        return PrivateWorldSnapshot(
            contract_fingerprint=self.contract_fingerprint,
            content_fingerprint=self.content_fingerprint,
            rules_fingerprint=self.rules_fingerprint,
            state_fingerprint=self.state_fingerprint,
            semantic_key=state.semantic_key(),
            payload=state.to_private_dict(),
        )

    def restore(self, snapshot: PrivateWorldSnapshot) -> WorldState:
        if not isinstance(snapshot, PrivateWorldSnapshot):
            raise SnapshotValidationError("snapshot has the wrong private type.")
        expected = {
            "contract_fingerprint": self.contract_fingerprint,
            "content_fingerprint": self.content_fingerprint,
            "rules_fingerprint": self.rules_fingerprint,
            "state_fingerprint": self.state_fingerprint,
        }
        for name, expected_value in expected.items():
            if getattr(snapshot, name) != expected_value:
                raise SnapshotValidationError(f"Snapshot {name} is incompatible.")
        try:
            state = WorldState.from_private_dict(_thaw_private_json(snapshot.payload))
        except StateValidationError as error:
            raise SnapshotValidationError("Snapshot payload is not valid world state.") from error
        if state.semantic_key() != snapshot.semantic_key:
            raise SnapshotValidationError("Snapshot semantic key does not match its payload.")
        return state

    def dumps(self, state: WorldState) -> str:
        return self.capture(state).to_json()

    def loads(self, text: str | bytes | bytearray) -> WorldState:
        return self.restore(PrivateWorldSnapshot.from_json(text))
