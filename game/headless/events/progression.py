"""Owned event queue for the explicitly all-unlocked, supported Act 1 pool."""

from copy import deepcopy
from dataclasses import dataclass, field

from game.headless.events.eligibility import is_allowed, validate_conditions

PROFILE = "supported_events_all_unlocked_v7"
NATIVE_PROFILE = "native_act1_events_all_unlocked_v1"


@dataclass
class EventProgression:
    queue: list[str]
    profile: str = PROFILE
    cursor: int = 0
    assignments: dict[str, str] = field(default_factory=dict)
    entry_conditions: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def generate(cls, rng, pool):
        queue = list(pool)
        rng.shuffle("act1.events", queue)
        return cls(queue)

    def pull(self, node_id, *, conditions=None):
        from game.headless.events.catalog import EVENTS

        conditions = {"gold": 0, "transformable_cards": 0} if conditions is None else conditions
        validate_conditions(conditions)
        if node_id in self.assignments:
            raise ValueError("Event point is already assigned.")
        # RoomSet skips visited/ineligible events, then permits repetition after
        # one full pass even if the fallback itself is ineligible.
        seen = set(self.assignments.values())
        from game.headless.generation.room_pools import ACT1_INELIGIBLE_EVENTS

        cursor = self.cursor
        for _ in self.queue:
            candidate = self.queue[cursor % len(self.queue)]
            excluded = self.profile == NATIVE_PROFILE and candidate in ACT1_INELIGIBLE_EVENTS
            if not excluded and candidate not in EVENTS:
                raise ValueError("Event queue contains unsupported eligible content.")
            if not excluded and candidate not in seen and is_allowed(EVENTS[candidate], conditions):
                break
            cursor += 1
        result = self.queue[cursor % len(self.queue)]
        if result not in EVENTS:
            raise ValueError("Exhausted event queue selected unsupported later-act content.")
        self.cursor = cursor + 1
        self.assignments[node_id] = result
        self.entry_conditions[node_id] = deepcopy(conditions)
        return result

    def validate(self, state, graph):
        from game.headless.run.unknown_rooms import room_node
        from game.headless.generation.room_pools import ACT_POOLS, SHARED_EVENTS

        native = self.profile == NATIVE_PROFILE
        pool = (*ACT_POOLS[0][3], *SHARED_EVENTS) if native else state.config.event_pool
        if (
            self.profile not in (PROFILE, NATIVE_PROFILE)
            or native
            and state.initialization is None
            or not isinstance(self.queue, list)
            or any(not isinstance(e, str) for e in self.queue)
            or len(self.queue) != len(pool)
            or set(self.queue) != set(pool)
            or type(self.cursor) is not int
            or self.cursor < 0
            or not isinstance(self.assignments, dict)
            or not isinstance(self.entry_conditions, dict)
            or set(self.entry_conditions) != set(self.assignments)
        ):
            raise ValueError("Invalid restricted event progression.")
        expected = EventProgression(list(self.queue), profile=self.profile)
        for node_id in state.visited_nodes:
            node = room_node(state, graph, node_id)
            if node.kind == "event":
                conditions = self.entry_conditions.get(node_id)
                validate_conditions(conditions)
                if expected.pull(node_id, conditions=conditions) != node.event_id:
                    raise ValueError("Event outcome differs from its owned queue.")
        if self.cursor != expected.cursor or self.assignments != expected.assignments:
            raise ValueError("Event progression differs from visited rooms.")
