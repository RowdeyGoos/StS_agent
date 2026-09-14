"""Pinned native construction/shuffle vectors and owned combat continuations."""

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import EndTurn, PlayCard
from game.headless.core.deck import Deck
from game.headless.core.native_rng import NativeRng
from game.headless.core.native_service import NativeRandomService
from game.headless.core.native_shuffle import stable_shuffle
from game.headless.encounters.catalog import ENCOUNTERS, NATIVE_OVERGROWTH_ENCOUNTERS
from game.headless.encounters.randomness import EncounterRandom, MonsterConstruction
from game.headless.monsters.overgrowth import Mawler, LeafSlimeSmall, TwigSlimeMedium
from game.headless.run.actions import ChooseNode
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine

VECTORS = json.loads((Path(__file__).parents[1] / "fixtures/headless_native_combat_vectors.json").read_text())


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def restored(run):
    copy = RunEngine()
    copy.restore(saved(run))
    assert saved(copy) == saved(run)
    return copy


def normalized_move(value):
    aliases = {
        "FIRST_ACID_GOOP": "Acid Goop",
        "SLICE_MOVE": "Hesitant Slice",
        "POWER_DANCE_MOVE": "Dance",
        "NASTY_BITE_MOVE": "Bite",
    }
    return re.sub("[^a-z]", "", aliases.get(value, value.replace("_MOVE", "")).lower())


@pytest.mark.parametrize("row", VECTORS["rows"], ids=lambda r: f"{r['seed']}-{r['floor']}-{r['encounter']}")
def test_native_construction_hp_opening_moves_and_all_rng_suffixes(row):
    rng = NativeRandomService(row["seed"])
    context = EncounterRandom(
        rng.root_seed, row["floor"], row["id"].upper(), rng.stream("monster_ai"), rng.stream("niche")
    )
    enemies = ENCOUNTERS[NATIVE_OVERGROWTH_ENCOUNTERS.get(row["encounter"], "dense_vegetation_event")](
        context
    )
    names = {
        "LeafSlimeSmall": "LeafSlimeS",
        "LeafSlimeMedium": "LeafSlimeM",
        "TwigSlimeSmall": "TwigSlimeS",
        "TwigSlimeMedium": "TwigSlimeM",
    }
    assert [names.get(type(e).__name__, type(e).__name__) for e in enemies] == [
        e["type"] for e in row["monsters"]
    ]
    assert [e.max_hp for e in enemies] == [e["hp"] for e in row["monsters"]]
    assert [normalized_move(e.intent.move_name) for e in enemies] == [
        normalized_move(e["move"]) for e in row["monsters"]
    ]
    for prefix, stream in [
        ("composition", context.composition),
        ("hp", rng.stream("niche")),
        ("ai", rng.stream("monster_ai")),
    ]:
        assert stream.counter == row[prefix + "Counter"]
        assert stream.next_double() == row[prefix + "Suffix"]
    assert all(e.rng is rng.stream("monster_ai") for e in enemies)


def cards_for(row):
    aliases = {"StrikeIronclad": "strike", "DefendIronclad": "defend"}
    return [
        DEFAULT_CARDS.create(
            aliases.get(c["type"], re.sub(r"(?<!^)(?=[A-Z])", "_", c["type"]).lower()),
            upgrade_level=int(c["upgraded"]),
            instance_id=str(i),
        )
        for i, c in enumerate(row["inputs"])
    ]


@pytest.mark.parametrize("row", VECTORS["shuffles"], ids=lambda r: f"{r['seed']}-{r['size']}-{r['stable']}")
def test_native_shuffle_copy_identity_and_actual_draw_order(row):
    cards, rng = cards_for(row), NativeRng(row["seed"])
    if row["stable"]:
        deck = Deck([], rng)
        deck.discard_pile = cards
        deck._refill_draw_pile()
    else:
        deck = Deck(cards, rng)
    assert [int(c.instance_id) for c in reversed(deck.draw_pile)] == row["order"]
    assert rng.counter == row["counter"]
    assert rng.next_double() == row["suffix"]
    drawn = []
    while deck.draw_pile:
        drawn.extend(int(c.instance_id) for c in deck.draw(10))
        deck.hand.clear()
    assert drawn == row["order"]
    # Catastrophe's candidate shuffle shares the same stable permutation.
    if row["stable"]:
        cards, rng = cards_for(row), NativeRng(row["seed"])
        stable_shuffle(cards, rng)
        assert [int(c.instance_id) for c in cards] == row["order"]


@pytest.mark.parametrize("seed", [0, 1, 2, 42])
def test_generated_first_combat_counts_the_completed_ancient_root(seed):
    run = RunEngine.ironclad_act1(seed=seed)
    node = run.graph.entry_node_ids[0]
    rng = deepcopy(run.state.rng)
    run.apply(ChooseNode(node))
    native_type = next(
        k for k, v in NATIVE_OVERGROWTH_ENCOUNTERS.items() if v == run.state.active_encounter_id
    )
    context = EncounterRandom(
        rng.root_seed,
        2,
        re.sub(r"(?<!^)(?=[A-Z])", "_", native_type).upper(),
        rng.stream("monster_ai"),
        rng.stream("niche"),
    )
    enemies = ENCOUNTERS[run.state.active_encounter_id](context)
    assert [(type(e), e.max_hp) for e in enemies] == [(type(e), e.max_hp) for e in run.combat.enemies]
    restored(run)


@pytest.mark.parametrize("encounter", ["overgrowth_phrog_parasite", "overgrowth_fogmog"])
def test_summons_use_niche_preserve_ai_and_restore_owned_streams(encounter):
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(), max_hp=10000)
    run.start_combat(encounter_id=encounter, cards_per_turn=0)
    other = restored(run)
    before_hp = run.state.rng.request_count("niche")
    for current in [run, other]:
        if encounter == "overgrowth_phrog_parasite":
            current.combat.enemies[0].take_damage(10000, is_attack=False)
            current.combat.resolve_external_effect()
        else:
            current.apply(EndTurn())
    assert saved(run) == saved(other)
    assert len(run.combat.enemies) > 1
    assert run.state.rng.request_count("niche") - before_hp == len(run.combat.enemies) - 1
    copy = restored(run)
    assert copy.combat.player.deck.niche_rng is copy.state.rng.stream("niche")
    assert all(e.rng is copy.combat.rng for e in copy.combat.enemies)


def test_foreign_enemy_rng_and_missing_hp_domain_reject_atomically():
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig())
    run.start_combat(encounter_id="overgrowth_flyconid")
    before = saved(run)
    bad = deepcopy(before)
    bad["combat"]["enemies"][-1]["rng"] = bad["combat"]["deck"]["niche_rng"]
    with pytest.raises(ValueError, match="Enemy AI"):
        run.restore(bad)
    assert saved(run) == before
    bad = deepcopy(before)
    del bad["combat"]["deck"]["niche_rng"]
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before


class EndpointRng(NativeRng):
    def __init__(self, value):
        super().__init__(0)
        self.value = value

    def next_float(self, low=0, high=1):
        return self.value * (high - low) + low

    def random(self):
        return self.value


@pytest.mark.parametrize("value,move", [(0.5, "Rip and Tear"), (1.0, "Roar")])
def test_native_mawler_inclusive_branch_boundaries(value, move):
    enemy = Mawler(EndpointRng(value))
    enemy.advance_intent()
    assert enemy.intent.move_name == move


def test_slime_half_boundary_and_fixed_hp_consumption():
    ai, hp = EndpointRng(0.5), NativeRng(42)
    context = MonsterConstruction(ai, hp)
    enemy = LeafSlimeSmall(context)
    assert enemy.intent.move_name == "Tackle"
    twig = TwigSlimeMedium(context)
    twig.advance_intent()
    twig.advance_intent()
    assert twig.intent.move_name == "Chomp"
    Mawler(context)
    assert hp.counter == 3


def test_native_random_multihits_reselect_after_death_and_restore():
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(), card_ids=["sword_boomerang"])
    run.start_combat(encounter_id="overgrowth_nibbits")
    for enemy in run.combat.enemies:
        enemy.hp = 1
    other = restored(run)
    before = saved(run)
    card_id = run.combat.player.hand[0].instance_id
    with pytest.raises(ValueError):
        run.apply(PlayCard(card_id, 0))
    assert saved(run) == before
    expected = deepcopy(run.combat.player.deck.target_rng)
    expected.choice([0, 1])
    expected.choice([0])
    for current in [run, other]:
        current.apply(PlayCard(card_id))
    assert saved(run) == saved(other)
    assert run.state.rng.stream("combat_targets").getstate() == expected.getstate()


def test_fogmog_weighted_binary32_boundary():
    from game.headless.monsters.fogmog import Fogmog
    from game.headless.core.native_rng import single

    enemy = Fogmog(EndpointRng(single(0.4)))
    enemy.advance_intent()
    enemy.advance_intent()
    assert enemy._intent_index == 2


def test_native_catastrophe_uses_stable_candidate_order_for_each_autoplay():
    run = RunEngine(seed=42, rng_profile="native", config=RunConfig(), card_ids=["catastrophe"])
    run.start_combat(encounter_id="overgrowth_cubex")
    deck = run.combat.player.deck
    deck.draw_pile = [DEFAULT_CARDS.create("bash", upgrade_level=i % 2) for i in range(19)]
    for card in deck.draw_pile:
        deck._ensure_identity(card)
    expected_rng = deepcopy(deck.rng)
    candidates = list(reversed(deck.draw_pile))
    selected = []
    for _ in range(2):
        pool = list(candidates)
        stable_shuffle(pool, expected_rng)
        selected.append(pool[0].instance_id)
        candidates.remove(pool[0])
    clone = restored(run)
    for current in (run, clone):
        current.apply(PlayCard(current.combat.player.hand[0].instance_id))
    assert saved(run) == saved(clone)
    assert [c.instance_id for c in deck.discard_pile if c.definition.definition_id == "bash"] == selected
    assert deck.rng.getstate() == expected_rng.getstate()
