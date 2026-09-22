"""Native assembly vectors and adversarial acquisition/continuation regressions."""

import json
from copy import deepcopy
from pathlib import Path
import pytest
from game.headless.core.native_rng import NativeRng, single, deterministic_hash
from game.headless.core.native_service import NativeRandomService
from game.headless.run.engine import RunEngine
from game.headless.run import rewards, events, shop
from game.headless.generation import odds, relics
from game.headless.run.actions import ChooseAncientRelic, ChooseEventOption, BuyShopItem
from game.headless.run.inventory import add_relic

VECTORS = json.loads((Path(__file__).parents[1] / "fixtures/headless_native_rng_vectors.json").read_text())


@pytest.mark.parametrize("vector", VECTORS["results"], ids=lambda v: str(v["seed"]))
def test_pinned_assembly_vectors(vector):
    rng = NativeRng(vector["seed"])
    for row in vector["rows"]:
        actual = (
            rng.randrange(row["max"])
            if row["op"] == "int"
            else rng.next_float() if row["op"] == "float" else rng.next_double()
        )
        assert actual == (single(row["value"]) if row["op"] == "float" else row["value"])
        copy = NativeRng()
        copy.setstate(json.loads(json.dumps(rng.getstate())))
        assert copy.next_double() == deepcopy(rng).next_double()
    values = list(range(12))
    rng.shuffle(values)
    assert values == vector["shuffle"] and rng.counter == vector["counter"]


@pytest.mark.parametrize("row", VECTORS["hashes"])
def test_native_utf16_seed_hash(row):
    assert deterministic_hash(row["input"]) == (row["value"] & 0xFFFFFFFF)


def clone(run):
    snapshot = json.loads(json.dumps(run.snapshot()))
    other = RunEngine()
    other.restore(snapshot)
    assert json.loads(json.dumps(other.snapshot())) == snapshot
    assert other.legal_actions() == run.legal_actions()
    return other


def native(seed=2):
    return RunEngine(seed=seed, rng_profile="native")


def test_reward_stream_aliases_and_failed_restore_are_atomic():
    rng = NativeRandomService("ABC123")
    assert rng.stream("reward_offer") is rng.stream("potion_drop") is rng.stream("reward_relic")
    assert rng.stream("shops") is not rng.stream("rewards")
    rng.random("rewards")
    before = rng.snapshot()
    bad = deepcopy(before)
    bad["streams"]["rewards"]["seed"] ^= 1
    with pytest.raises(ValueError):
        rng.restore(bad)
    assert rng.snapshot() == before
    bad = deepcopy(before)
    bad["streams"]["reward_offer"] = bad["streams"].pop("rewards")
    with pytest.raises(ValueError):
        rng.restore(bad)
    assert rng.snapshot() == before


@pytest.mark.parametrize(
    "field,value",
    [("words", [0] * 4), ("words", [1, 2, 3, True]), ("counter", -1), ("draws", -1), ("schema", "wrong")],
)
def test_rng_rejects_corrupt_state(field, value):
    rng = NativeRng(7)
    rng.random()
    before = rng.getstate()
    bad = deepcopy(before)
    bad[field] = value
    with pytest.raises(ValueError):
        rng.setstate(bad)
    assert rng.getstate() == before


def test_native_event_seed_restarts_and_owner_cannot_change():
    run = native()
    events.begin(run.state, "aroma_of_chaos", cards=run.cards)
    bad = run.snapshot()
    bad["state"]["rng"]["active_event"] = "different_event"
    with pytest.raises(ValueError):
        RunEngine().restore(bad)
    rng = NativeRandomService(2)
    rng.begin_event("luminous_choir")
    a = rng.randint("event.luminous_choir", 0, 49)
    rng.begin_event("luminous_choir")
    assert rng.randint("event.luminous_choir", 0, 49) == a


def test_failed_reward_generation_preserves_rng_and_pity():
    run = native()
    before = run.snapshot()
    with pytest.raises(ValueError):
        rewards.begin_reward(run.state, run.cards, gold=1, card_ids=["strike"])
    assert run.snapshot() == before


def test_pity_base_boss_and_elite_boundaries(monkeypatch):
    run = native()
    state = run.state
    monkeypatch.setattr(state.rng, "random", lambda name: single(0.015))
    assert odds.rarity(state) == "uncommon"
    assert state.generation_odds["card_offset"] == single(single(-0.05) + single(0.01))
    old = state.generation_odds["card_offset"]
    assert odds.rarity(state, mode="base") == "rare"
    assert old == state.generation_odds["card_offset"]
    assert odds.rarity(state, "boss") == "rare"
    assert state.generation_odds["card_offset"] == single(-0.05)
    monkeypatch.setattr(state.rng, "random", lambda name: single(0.50))
    assert odds.potion_drop(state, "elite")
    assert state.generation_odds["potion_chance"] == single(single(0.4) - single(0.1))
    for _ in range(8):
        assert odds.potion_drop(state, "combat", forced=True)
    assert state.generation_odds["potion_chance"] < 0
    odds.validate(state.generation_odds)


def test_uniform_flags_upgrade_draw_and_rarity_wrapping(monkeypatch):
    from game.headless.cards.pools import COMMON_CARDS

    run = native()
    state = run.state
    pool = list(COMMON_CARDS[:5])
    before = state.rng.request_count("rewards")
    offers, upgrades = odds.card_offers(state, run.cards, pool, 3, uniform=True, upgrade_roll=False)
    assert len(set(offers)) == 3 and state.rng.request_count("rewards") - before == 3
    before = state.rng.request_count("rewards")
    odds.card_offers(state, run.cards, pool, 3, uniform=True, upgrade_roll=True)
    assert state.rng.request_count("rewards") - before == 6
    monkeypatch.setattr(state.rng, "random", lambda name: 0.0)
    state.generation_odds["card_offset"] = single(0.1)
    offers, upgrades = odds.card_offers(state, run.cards, pool, 1, upgrade_roll=True)
    assert offers[0] in pool and upgrades == offers
    assert state.generation_odds["card_offset"] == single(-0.05)  # rolledRare resets before wrapping


def test_potion_rarity_float32_threshold():
    from game.headless.potions.pools import generate, ORDINARY_POTIONS
    from game.headless.potions.base import POTIONS

    class Fixed:
        def random(self):
            return single(0.1)

        def choice(self, values):
            return values[0]

    assert POTIONS[generate(ORDINARY_POTIONS, Fixed())].rarity == "rare"


def test_relic_bags_deplete_at_offer_and_do_not_wrap_rare():
    run = native()
    state = run.state
    before = state.rng.request_count("rewards")
    name = state.relic_bags["player"]["common"][0]
    assert relics.pull(state, rarity="common") == name
    assert state.rng.request_count("rewards") == before
    assert all(name not in bag for groups in state.relic_bags.values() for bag in groups.values())
    state.relic_bags["player"]["rare"] = []
    assert relics.pull(state, rarity="rare") == "circlet"
    assert state.relic_bags["player"]["common"]
    clone(run)


@pytest.mark.parametrize("seed", range(8))
def test_neow_and_combat_keep_owned_native_streams(seed):
    from game.headless.run.ancient import PROFILE
    from game.headless.core.actions import EndTurn

    run = RunEngine.ironclad_act1(seed=seed, ancient_profile=PROFILE)
    clone(run)
    # First combat can also be exercised as a direct native scenario.
    run = native(seed)
    run.start_combat()
    other = clone(run)
    run.apply(EndTurn())
    other.apply(EndTurn())
    assert run.snapshot() == other.snapshot()
    bad = run.snapshot()
    bad["state"]["rng"]["streams"]["shuffle"]["words"][0] ^= 1
    with pytest.raises(ValueError):
        RunEngine().restore(bad)


@pytest.mark.parametrize("seed", range(8))
def test_native_shop_composition_restore_and_courier_refill(seed):
    from game.headless.run.config import RunConfig
    from game.headless.potions.pools import ORDINARY_POTIONS
    from game.headless.relics.pools import ORDINARY_RELICS, SHOP_RELICS

    run = RunEngine(
        seed=seed,
        rng_profile="native",
        gold=10000,
        config=RunConfig(
            reward_relics=ORDINARY_RELICS, shop_relics=SHOP_RELICS, reward_potions=ORDINARY_POTIONS
        ),
    )
    add_relic(run.state, "the_courier")
    shop.begin(run.state, run.cards)
    offers = run.state.pending["offers"]
    assert len(offers) == 13
    assert [o["kind"] for o in offers] == ["card"] * 7 + ["relic"] * 3 + ["potion"] * 3
    assert len({o["definition_id"] for o in offers}) == 13
    assert sum(o["on_sale"] for o in offers) == 1
    for index in (0, 7, 10):
        other = clone(run)
        action = BuyShopItem(run.state.pending["offers"][index]["offer_id"])
        run.apply(action)
        other.apply(action)
        assert run.snapshot() == other.snapshot()
        assert run.state.pending["offers"][index]["generation"] == 1
        # Some purchases own mandatory relic work; choose a simple native relic instead below.
        if run.state.relic_work:
            break


@pytest.mark.parametrize("row", VECTORS["neow"])
def test_neow_matches_pinned_rng_and_source_composition(row):
    from game.headless.run.ancient import generate

    rng = NativeRandomService(row["seed"])
    assert generate(rng, ["kaleidoscope"]) == row["offers"]
    assert rng.request_count("ancient.neow") == row["counter"]


def test_depleted_merchant_circlets_remain_individually_buyable():
    from game.headless.run.config import RunConfig
    from game.headless.potions.pools import ORDINARY_POTIONS
    from game.headless.relics.pools import ORDINARY_RELICS, SHOP_RELICS

    run = RunEngine(
        rng_profile="native",
        gold=10000,
        config=RunConfig(
            reward_relics=ORDINARY_RELICS, shop_relics=SHOP_RELICS, reward_potions=ORDINARY_POTIONS
        ),
    )
    for bag in run.state.relic_bags["player"].values():
        bag.clear()
    shop.begin(run.state, run.cards)
    for offer in run.state.pending["offers"][7:10]:
        assert offer["definition_id"] == "circlet"
        run.apply(BuyShopItem(offer["offer_id"]))
        clone(run)
    assert sum(r.definition_id == "circlet" for r in run.state.relics) == 3


def test_dingy_rug_does_not_modify_native_merchant_pool():
    from game.headless.run.config import RunConfig
    from game.headless.potions.pools import ORDINARY_POTIONS
    from game.headless.relics.pools import ORDINARY_RELICS, SHOP_RELICS

    config = RunConfig(
        reward_relics=ORDINARY_RELICS, shop_relics=SHOP_RELICS, reward_potions=ORDINARY_POTIONS
    )
    run = RunEngine(rng_profile="native", config=config)
    add_relic(run.state, "dingy_rug")
    shop.begin(run.state, run.cards)
    assert all(
        run.cards.definition(o["definition_id"]).pool == "ironclad" for o in run.state.pending["offers"][:5]
    )


def test_named_relic_pickup_depletes_both_bags_even_after_removal():
    from game.headless.run.inventory import remove_relic

    run = native()
    obtained = add_relic(run.state, "strawberry")
    remove_relic(run.state, obtained.instance_id)
    assert all("strawberry" not in bag for groups in run.state.relic_bags.values() for bag in groups.values())
    clone(run)


def test_new_leaf_transform_uses_niche_without_advancing_transformations():
    from game.headless.run.actions import ChooseRelicCard, ConfirmRelicSelection

    run = native()
    add_relic(run.state, "new_leaf")
    run.apply(ChooseRelicCard(run.state.relic_work[0]["candidates"][0]))
    other = clone(run)
    run.apply(ConfirmRelicSelection())
    other.apply(ConfirmRelicSelection())
    assert run.snapshot() == other.snapshot()
    assert run.state.rng.request_count("niche") == 1
    assert run.state.rng.request_count("transformations") == 0


@pytest.mark.parametrize("row", VECTORS["gaussian"])
def test_native_gaussian_rejection_counter_and_restored_suffix(row):
    rng = NativeRng(row["seed"])
    assert [rng.gaussian_int(5, 2, 3, 7) for _ in range(10)] == row["values"]
    assert rng.counter == row["counter"]
    assert rng.draws >= 20
    restored = NativeRng()
    restored.setstate(json.loads(json.dumps(rng.getstate())))
    assert rng.next_double() == restored.next_double() == row["suffix"]
