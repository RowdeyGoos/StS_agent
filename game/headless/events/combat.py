"""Plain event combat requests and owned run history, without callbacks."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EventCombatRequest:
    encounter_id: str


@dataclass
class EventCombatRecord:
    event_instance_id: int
    definition_id: str
    node_id: str | None
    encounter_id: str
    combat_number: int
    outcome: str | None = None
    rewards_left: bool = False
    continuation: dict | None = None
    timed_out: bool = False
    resumed: bool = False
