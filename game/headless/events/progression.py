"""Owned event queue for the explicitly all-unlocked, supported Act 1 pool."""

from dataclasses import dataclass, field


PROFILE = "supported_events_all_unlocked_v1"


@dataclass
class EventProgression:
    queue: list[str]
    profile: str = PROFILE
    cursor: int = 0
    assignments: dict[str, str] = field(default_factory=dict)

    @classmethod
    def generate(cls, rng, pool):
        queue = list(pool)
        rng.shuffle("act1.events", queue)
        return cls(queue)

    def pull(self, node_id):
        if node_id in self.assignments:
            raise ValueError("Event point is already assigned.")
        # Both supported event definitions inherit native IsAllowed == true.
        # RoomSet skips visited events, then permits repetition after a full pass.
        seen = set(self.assignments.values())
        for _ in self.queue:
            if self.queue[self.cursor % len(self.queue)] not in seen:
                break
            self.cursor += 1
        result = self.queue[self.cursor % len(self.queue)]
        self.cursor += 1
        self.assignments[node_id] = result
        return result

    def validate(self, state, graph):
        from game.headless.run.unknown_rooms import room_node
        if (self.profile != PROFILE or not isinstance(self.queue, list)
                or any(not isinstance(e, str) for e in self.queue)
                or len(self.queue) != len(state.config.event_pool)
                or set(self.queue) != set(state.config.event_pool)
                or type(self.cursor) is not int or self.cursor < 0
                or not isinstance(self.assignments, dict)):
            raise ValueError("Invalid restricted event progression.")
        expected = EventProgression(list(self.queue))
        for node_id in state.visited_nodes:
            node = room_node(state, graph, node_id)
            if node.kind == "event" and expected.pull(node_id) != node.event_id:
                raise ValueError("Event outcome differs from its owned queue.")
        if self.cursor != expected.cursor or self.assignments != expected.assignments:
            raise ValueError("Event progression differs from visited rooms.")
