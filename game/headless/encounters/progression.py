"""Run-owned Act 1 encounter queues, separate from map geometry and combat."""

from dataclasses import dataclass, field
from types import MappingProxyType

from game.headless.encounters.catalog import ENCOUNTERS, NATIVE_OVERGROWTH_ENCOUNTERS

WEAK = tuple(NATIVE_OVERGROWTH_ENCOUNTERS[n] for n in (
    "FuzzyWurmCrawlerWeak", "NibbitsWeak", "ShrinkerBeetleWeak", "SlimesWeak"))
NORMAL = tuple(name for native, name in NATIVE_OVERGROWTH_ENCOUNTERS.items()
               if ENCOUNTERS[name].room_kind == "combat" and name not in WEAK)
ELITES = tuple(name for name, definition in ENCOUNTERS.items()
               if name in NATIVE_OVERGROWTH_ENCOUNTERS.values() and definition.room_kind == "elite")
BOSSES = ("overgrowth_vantom", "overgrowth_ceremonial_beast", "overgrowth_the_kin")
TAGS = MappingProxyType({
    "overgrowth_nibbit": frozenset({3}), "overgrowth_shrinker": frozenset({4}),
    "overgrowth_slimes": frozenset({5}), "overgrowth_slimes_normal": frozenset({5}),
    "overgrowth_fuzzy": frozenset({8}), "overgrowth_crawlers": frozenset({4, 8}),
    "overgrowth_flyconid": frozenset({5, 9}), "overgrowth_jaxfruit": frozenset({9}),
})


def native_ids(act):
    from game.headless.encounters.catalog import NATIVE_UNDERDOCKS_ENCOUNTERS
    if act == 'overgrowth':
        return NATIVE_OVERGROWTH_ENCOUNTERS
    if act == 'underdocks':
        return NATIVE_UNDERDOCKS_ENCOUNTERS
    raise ValueError('Unsupported Act 1 location.')


def pools_for(act):
    if act == 'overgrowth':
        # Retain the original fixture order; native initialization uses its own order.
        return WEAK, NORMAL, ELITES, BOSSES
    from game.headless.generation.room_pools import ACT1_POOLS
    ids = native_ids(act)
    return tuple(tuple(ids[n] for n in pool) for pool in ACT1_POOLS[act][5])


def _compatible(previous, candidate):
    from game.headless.generation.room_pools import ENCOUNTER_TAGS
    def tags(name):
        if name in TAGS:
            return TAGS[name]
        ids = native_ids('underdocks')
        native = next((n for n, identity in ids.items() if identity == name), None)
        return frozenset(ENCOUNTER_TAGS.get(native, ()))
    return candidate != previous and not tags(previous) & tags(candidate)


def _extend_queue(rng, queue, pool, count, stream):
    bag = []
    for _ in range(count):
        if not bag:
            bag = list(pool)
        previous = queue[-1] if queue else None
        eligible = [name for name in bag if _compatible(previous, name)]
        chosen = rng.choice(stream, eligible or bag)
        bag.remove(chosen)
        queue.append(chosen)


def _validate_queue(queue, segments):
    if not isinstance(queue, list) or len(queue) != sum(count for _, count in segments):
        raise ValueError("Invalid encounter queue length.")
    offset = 0
    for pool, count in segments:
        bag = []
        for index in range(offset, offset + count):
            if not bag:
                bag = list(pool)
            previous = queue[index - 1] if index else None
            eligible = [name for name in bag if _compatible(previous, name)]
            if queue[index] not in (eligible or bag):
                raise ValueError("Encounter queue violates its bag or tag exclusions.")
            bag.remove(queue[index])
        offset += count


@dataclass
class EncounterProgression:
    normal_queue: list[str]
    elite_queue: list[str]
    boss: str
    discovery: str = "all_seen"
    assignments: dict[str, str] = field(default_factory=dict)
    act: str = "overgrowth"

    @classmethod
    def generate(cls, rng, *, discovery="all_seen", act="overgrowth"):
        weak, normal_pool, elites_pool, bosses = pools_for(act)
        # Explicitly skips native first-run/discovery overrides; never reads a profile.
        if discovery != "all_seen":
            raise ValueError("Only declared all-seen Act 1 discovery is supported.")
        normal = []
        _extend_queue(rng, normal, weak, 3, "act1.encounters")
        _extend_queue(rng, normal, normal_pool, 12, "act1.encounters")
        elites = []
        _extend_queue(rng, elites, elites_pool, 15, "act1.encounters")
        return cls(normal, elites, rng.choice("act1.encounters", bosses), discovery, act=act)

    def next_encounter(self, kind):
        if kind == "boss":
            return self.boss
        queue = self.normal_queue if kind == "combat" else self.elite_queue if kind == "elite" else None
        if queue is None:
            raise ValueError("No encounter queue for this room kind.")
        index = sum(ENCOUNTERS[name].room_kind == kind for name in self.assignments.values())
        return queue[index % len(queue)]

    def validate(self, graph, visited_nodes, *, pending_node=False, room_kinds=None):
        weak, normal, elites, bosses = pools_for(self.act)
        if self.discovery != "all_seen" or self.boss not in bosses:
            raise ValueError("Unsupported encounter discovery or boss.")
        _validate_queue(self.normal_queue, ((weak, 3), (normal, 12)))
        _validate_queue(self.elite_queue, ((elites, 15),))
        if not isinstance(self.assignments, dict):
            raise ValueError("Invalid encounter assignments.")
        kinds = room_kinds if room_kinds is not None else {n.node_id: n.kind for n in graph.nodes}
        expected_nodes = [node_id for node_id in visited_nodes
                          if kinds[node_id] in ("combat", "elite", "boss")]
        if pending_node and expected_nodes and expected_nodes[-1] == visited_nodes[-1]:
            expected_nodes.pop()
        if set(self.assignments) != set(expected_nodes):
            raise ValueError("Encounter assignments differ from visited combat rooms.")
        counts = {"combat": 0, "elite": 0, "boss": 0}
        for node_id in expected_nodes:
            kind = kinds[node_id]
            queue = self.normal_queue if kind == "combat" else self.elite_queue if kind == "elite" else [self.boss]
            if self.assignments[node_id] != queue[counts[kind] % len(queue)]:
                raise ValueError("Encounter assignment differs from its queue position.")
            counts[kind] += 1


def encounter_at(state, node):
    """Return the assigned identity, or peek at the next queue without drawing."""
    if state.encounter_progression is None:
        return node.encounter_id
    progression = state.encounter_progression
    return progression.assignments.get(node.node_id) or progression.next_encounter(node.kind)
