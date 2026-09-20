"""Owned Neow offers and acquisition history, before entering the map."""

from dataclasses import dataclass, field
from copy import deepcopy
from game.headless.run.actions import ChooseAncientRelic

PROFILE = "neow_solo_all_unlocked_v2"
RESTRICTED_PROFILE = "neow_pickups_restricted_v1"
OFFERS = ("golden_pearl", "nutritious_oyster")
POSITIVES = (
    "arcane_scroll", "booming_conch", "fishing_rod", "golden_pearl", "kaleidoscope",
    "lead_paperweight", "lost_coffer", "neows_torment", "new_leaf", "phial_holster",
    "precise_scissors", "scroll_boxes", "winged_boots",
)
CURSES = ("cursed_pearl", "hefty_tablet", "large_capsule", "leafy_poultice", "neows_bones",
          "precarious_shears", "silken_tress", "silver_crucible")
EXCLUSIONS = {"cursed_pearl": "golden_pearl", "hefty_tablet": "arcane_scroll",
              "leafy_poultice": "new_leaf", "precarious_shears": "precise_scissors"}


def generate(rng, unavailable=()):
    curse = rng.choice("ancient.neow", [n for n in CURSES if n not in unavailable])
    positives = [n for n in POSITIVES if n != EXCLUSIONS.get(curse)]
    if curse != "large_capsule":
        positives.append(rng.choice("ancient.neow", ("lava_rock", "small_capsule")))
    positives.append(rng.choice("ancient.neow", ("nutritious_oyster", "stone_humidifier")))
    positives.append(rng.choice("ancient.neow", ("neows_talisman", "pomander")))
    positives = [n for n in positives if n not in unavailable]
    rng.shuffle("ancient.neow", positives)
    return positives[:2] + [curse]


@dataclass
class AncientStart:
    profile: str = PROFILE
    selected: str | None = None
    relic_instance_id: str | None = None
    offers: list[str] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)

    def validate(self, state, graph, cards=None):
        from game.headless.run.state import RunPhase
        from game.headless.core.rng import GameRandomService
        if self.profile not in (PROFILE, RESTRICTED_PROFILE) or graph is None or graph.generation is None:
            raise ValueError("Ancient start requires its generated route.")
        if (not isinstance(self.unavailable, list) or len(self.unavailable) != len(set(self.unavailable))
                or any(n not in ("kaleidoscope", "scroll_boxes") for n in self.unavailable)):
            raise ValueError("Invalid Neow content exclusions.")
        from game.headless.cards.catalog import DEFAULT_CARDS
        from game.headless.relics.neow import available
        expected_unavailable = [n for n in ("kaleidoscope", "scroll_boxes") if not available(n, cards or DEFAULT_CARDS)]
        if self.unavailable != expected_unavailable:
            raise ValueError("Neow exclusions differ from the configured card catalog.")
        expected = list(OFFERS) if self.profile == RESTRICTED_PROFILE else generate(type(state.rng)(state.seed), self.unavailable)
        if self.offers != expected:
            raise ValueError("Neow offers differ from their seeded construction.")
        pending = state.pending is not None and state.pending.get("kind") == "ancient"
        if self.selected is None:
            if (not pending or state.pending != {"kind": "ancient", "profile": self.profile}
                    or state.phase is not RunPhase.ROOM or state.visited_nodes
                    or state.current_node_id is not None or state.combats_completed
                    or self.relic_instance_id is not None):
                raise ValueError("Invalid unresolved Ancient start.")
        else:
            if pending or self.selected not in self.offers or not isinstance(self.relic_instance_id, str):
                raise ValueError("Invalid Ancient selection.")
            suffix = self.relic_instance_id.removeprefix("run.item.")
            if (not self.relic_instance_id.startswith("run.item.") or not suffix.isdecimal()
                    or str(int(suffix)) != suffix or int(suffix) >= state.next_item_id):
                raise ValueError("Invalid Ancient relic identity.")
            if any(p is not None and p.instance_id == self.relic_instance_id for p in state.potions):
                raise ValueError("Ancient relic identity belongs to an owned potion.")
            owned = next((r for r in state.relics if r.instance_id == self.relic_instance_id), None)
            if owned is not None and owned.definition_id != self.selected:
                raise ValueError("Ancient relic identity differs from its acquisition.")


def begin(state, *, profile, cards=None):
    from game.headless.run.state import RunPhase
    from game.headless.cards.catalog import DEFAULT_CARDS
    from game.headless.relics.neow import available
    cards = cards or DEFAULT_CARDS
    state.require_between_rooms()
    if (profile not in (PROFILE, RESTRICTED_PROFILE) or state.ancient_start is not None or state.visited_nodes
            or state.combats_completed or any(r.definition_id in (*POSITIVES, *CURSES, *OFFERS) for r in state.relics)):
        raise ValueError("Unsupported or already started Ancient choice.")
    unavailable = [n for n in ("kaleidoscope", "scroll_boxes") if not available(n, cards)]
    offers = list(OFFERS) if profile == RESTRICTED_PROFILE else generate(state.rng, unavailable)
    from game.headless.events.progression import NATIVE_PROFILES
    if state.event_progression is not None and state.event_progression.profile in NATIVE_PROFILES:
        # Native Neow is an EventRoom and consumes one room-set event position.
        state.event_progression.cursor += 1
    state.ancient_start = AncientStart(profile, offers=offers, unavailable=unavailable)
    state.pending = {"kind": "ancient", "profile": profile}
    state.phase = RunPhase.ROOM


def legal_actions(state):
    from game.headless.run.state import RunPhase
    start = state.ancient_start
    if (state.phase is not RunPhase.ROOM or start is None or start.selected is not None
            or state.pending != {"kind": "ancient", "profile": start.profile}):
        return ()
    return tuple(ChooseAncientRelic(r) for r in start.offers)


def choose(state, action, *, cards=None):
    from game.headless.run.inventory import add_relic
    from game.headless.run.state import RunPhase
    if action not in legal_actions(state):
        raise ValueError("Ancient reward is not available.")
    before = deepcopy(state)
    try:
        # Nested acquisition uses the same relic work queue as every other source.
        relic = add_relic(state, action.definition_id, cards=cards)
        state.ancient_start.selected = relic.definition_id
        state.ancient_start.relic_instance_id = relic.instance_id
        state.pending = None
        if state.hp:
            state.phase = RunPhase.ROUTE
        return relic
    except Exception:
        state.__dict__.clear()
        state.__dict__.update(before.__dict__)
        raise
