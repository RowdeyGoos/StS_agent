"""Neow's first supported pickup choices, before entering the map.

The fixed two-positive offer profile is deliberately restricted. It does not
claim native Neow's randomized two-positive/one-curse offer generation.
"""

from dataclasses import dataclass

from game.headless.run.actions import ChooseAncientRelic


PROFILE = "neow_pickups_restricted_v1"
OFFERS = ("golden_pearl", "nutritious_oyster")


@dataclass
class AncientStart:
    profile: str = PROFILE
    selected: str | None = None
    relic_instance_id: str | None = None

    def validate(self, state, graph):
        from game.headless.run.state import RunPhase
        if self.profile != PROFILE or graph is None or graph.generation is None:
            raise ValueError("Ancient start requires its supported generated route.")
        pending = state.pending is not None and state.pending.get("kind") == "ancient"
        if self.selected is None:
            if (not pending or state.pending != {"kind": "ancient", "profile": self.profile}
                    or state.phase is not RunPhase.ROOM or state.visited_nodes
                    or state.current_node_id is not None or state.combats_completed
                    or self.relic_instance_id is not None
                    or any(r.definition_id in OFFERS for r in state.relics)):
                raise ValueError("Invalid unresolved Ancient start.")
        else:
            if pending or self.selected not in OFFERS or not isinstance(self.relic_instance_id, str):
                raise ValueError("Invalid Ancient selection.")
            # This is acquisition history, not a requirement to retain the relic
            # forever. Removal does not reverse a native upon-pickup effect.
            suffix = self.relic_instance_id.removeprefix("run.item.")
            if (not self.relic_instance_id.startswith("run.item.") or not suffix.isdecimal()
                    or str(int(suffix)) != suffix or int(suffix) >= state.next_item_id):
                raise ValueError("Invalid Ancient relic identity.")
            if any(p is not None and p.instance_id == self.relic_instance_id for p in state.potions):
                raise ValueError("Ancient relic identity belongs to an owned potion.")
            owned = next((r for r in state.relics if r.instance_id == self.relic_instance_id), None)
            if owned is not None and owned.definition_id != self.selected:
                raise ValueError("Ancient relic identity differs from its acquisition.")


def begin(state, *, profile):
    from game.headless.run.state import RunPhase
    state.require_between_rooms()
    if (profile != PROFILE or state.ancient_start is not None or state.visited_nodes
            or state.combats_completed or any(r.definition_id in OFFERS for r in state.relics)):
        raise ValueError("Unsupported or already started Ancient choice.")
    state.ancient_start = AncientStart(profile)
    state.pending = {"kind": "ancient", "profile": profile}
    state.phase = RunPhase.ROOM


def legal_actions(state):
    from game.headless.run.state import RunPhase
    if (state.phase is not RunPhase.ROOM or state.ancient_start is None
            or state.ancient_start.selected is not None
            or state.pending != {"kind": "ancient", "profile": PROFILE}):
        return ()
    return tuple(ChooseAncientRelic(r) for r in OFFERS)


def choose(state, action):
    from game.headless.run.inventory import add_relic
    from game.headless.run.state import RunPhase
    if action not in legal_actions(state):
        raise ValueError("Ancient reward is not available.")
    relic = add_relic(state, action.definition_id)
    state.ancient_start.selected = relic.definition_id
    state.ancient_start.relic_instance_id = relic.instance_id
    state.pending = None
    state.phase = RunPhase.ROUTE
    return relic
