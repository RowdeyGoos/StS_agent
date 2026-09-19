"""Acquisition predicates and pool changes compared with pinned native execution."""

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.cards.pools import REWARD_CARDS, COLORLESS_CARDS
from game.headless.core.content_order import IRONCLADCARDPOOL, COLORLESSCARDPOOL, ordered
from game.headless.core.native_rng import NativeRng
from game.headless.generation import relics
from game.headless.potions.pools import ORDINARY_POTIONS, generate_many
from game.headless.relics.base import RELICS
from game.headless.relics.eligibility import is_allowed, SHOP_EXCLUDED
from game.headless.relics.pools import ORDINARY_RELICS, SHOP_RELICS
from game.headless.relics.rewards import extend_pool
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from game.headless.run import shop

VECTORS = json.loads(
    (Path(__file__).parents[1] / "fixtures/headless_runtime_eligibility_vectors.json").read_text()
)


def restored(run):
    snapshot = json.loads(json.dumps(run.snapshot()))
    other = RunEngine()
    other.restore(snapshot)
    assert json.loads(json.dumps(other.snapshot())) == snapshot
    return other


@pytest.mark.parametrize(
    "row", VECTORS["predicates"], ids=lambda row: f"floor{row['floor']}-runs{row['runs']}"
)
def test_all_161_relic_predicates_against_native(row):
    assert {m["id"] for m in VECTORS["metadata"]} <= set(RELICS)
    assert {
        m["id"] for m in VECTORS["metadata"] if is_allowed(m["id"], total_floor=row["floor"], prior_runs=row["runs"])
    } == set(row["allowed"])


def test_native_shop_exclusions_and_all_unlocked_scope():
    assert {m["id"] for m in VECTORS["metadata"] if not m["shop"]} == SHOP_EXCLUDED
    assert set(SHOP_RELICS) == {
        m["id"]
        for m in VECTORS["metadata"]
        if m["rarity"] in ("Common", "Uncommon", "Rare", "Shop") and m["shop"]
    }
    for name in SHOP_EXCLUDED:
        with pytest.raises(ValueError):
            RunConfig(shop_relics=(name,))
    # Unlock restrictions are recorded separately from runtime IsAllowed rules.
    assert all(p["epochRules"] for p in VECTORS["pools"])


@pytest.mark.parametrize("row", VECTORS["bagRows"], ids=lambda row: f"seed{row['seed']}-floor{row['floor']}")
def test_native_bag_depletion_filtering_fallback_and_rng_suffix(row):
    raw = NativeRng(row["seed"])
    adapter = SimpleNamespace(shuffle=lambda stream, values: raw.shuffle(values))
    bags = relics.populate(adapter)
    assert bags["player"] == row["initial"]
    state = SimpleNamespace(relic_bags=bags, relics=[], visited_nodes=[None] * row["floor"], rng=adapter)
    for step in row["steps"]:
        allowed = SHOP_RELICS if step["back"] else RELICS
        if step["only"] is not None:
            allowed = set(allowed) & {step["only"]}
        result = relics.pull(state, rarity=step["rarity"], back=step["back"], allowed=allowed)
        assert result == step["selected"]
        assert bags["player"] == step["player"]
        assert bags["shared"] == step["shared"]
        assert raw.counter == step["counter"]
        # Serialized bags preserve skipped candidates and depletion exactly.
        bags = json.loads(json.dumps(bags))
        relics.validate(bags)
        state.relic_bags = bags
    assert raw.next_double() == row["suffix"]


@pytest.mark.parametrize("row", VECTORS["cardRows"], ids=lambda row: row["mode"])
def test_dingy_rug_pool_context_matches_native_hook(row):
    run = RunEngine(seed=7, rng_profile="native")
    add_relic(run.state, "dingy_rug")
    mode = row["mode"]
    pool = list(COLORLESS_CARDS if mode == "colorless" else REWARD_CARDS)
    if mode == "rare_reward":
        pool = [n for n in pool if DEFAULT_CARDS.definition(n).rarity == "rare"]
    before = run.state.rng.snapshot()
    actual = extend_pool(
        run.state,
        run.cards,
        pool,
        card_reward=mode != "direct",
        custom_pool=mode == "custom",
        no_pool_changes=mode == "blocked",
    )
    expected = [n for n in row["ids"] if n in set(REWARD_CARDS) | set(COLORLESS_CARDS)]
    assert ordered(actual, (*IRONCLADCARDPOOL, *COLORLESSCARDPOOL)) == expected
    assert run.state.rng.snapshot() == before


@pytest.mark.parametrize(
    "row", VECTORS["potionRows"], ids=lambda row: f"seed{row['seed']}-combat{row['combat']}"
)
def test_potion_factory_blacklists_combat_eligibility_and_unique_batch(row):
    rng = NativeRng(row["seed"])
    actual = generate_many(ORDINARY_POTIONS, rng, 3, in_combat=row["combat"], blacklist=row["blacklist"])
    assert actual == row["selected"]
    assert rng.counter == row["counter"]
    assert rng.next_double() == row["suffix"]


@pytest.mark.parametrize("seed", [0, 1, 2, 42])
def test_shop_filter_survives_restore_and_preserves_excluded_relics(seed):
    run = RunEngine(
        seed=seed,
        rng_profile="native",
        gold=5000,
        config=RunConfig(
            reward_relics=ORDINARY_RELICS, shop_relics=SHOP_RELICS, reward_potions=ORDINARY_POTIONS
        ),
    )
    before = deepcopy(run.state.relic_bags["player"])
    shop.begin(run.state, run.cards)
    assert not {o["definition_id"] for o in run.state.pending["offers"]} & SHOP_EXCLUDED
    for name in SHOP_EXCLUDED:
        rarity = RELICS[name].rarity
        assert name in before[rarity] and name in run.state.relic_bags["player"][rarity]
    restored(run)


def test_rejected_shop_purchase_preserves_bags_rng_and_pending_offers():
    from game.headless.run.actions import BuyShopItem

    run = RunEngine(
        seed=2,
        rng_profile="native",
        config=RunConfig(
            reward_relics=ORDINARY_RELICS, shop_relics=SHOP_RELICS, reward_potions=ORDINARY_POTIONS
        ),
    )
    shop.begin(run.state, run.cards)
    snapshot = run.snapshot()
    with pytest.raises(ValueError):
        run.apply(BuyShopItem("not-an-offer"))
    assert run.snapshot() == snapshot


@pytest.mark.parametrize("kind", ["combat", "elite", "boss"])
def test_lasting_candy_uses_base_odds_and_three_native_draws(kind):
    from game.headless.relics.rewards import add_power_option

    run = RunEngine(seed=2, rng_profile="native")
    add_relic(run.state, "lasting_candy")
    offers = ["anger", "armaments", "bash"]
    offset = run.state.generation_odds["card_offset"]
    stream = run.state.rng.stream("rewards")
    before = stream.counter
    add_power_option(run.state, run.cards, offers, REWARD_CARDS, kind=kind)
    assert len(offers) == 4 and run.cards.definition(offers[-1]).levels[0].kind == "power"
    assert stream.counter == before + 3  # rarity, card pick, upgrade check
    assert run.state.generation_odds["card_offset"] == offset
    if kind == "boss":
        assert run.cards.definition(offers[-1]).rarity == "rare"
    restored(run)


def test_white_star_and_lasting_candy_extra_reward_survives_restore():
    from game.headless.encounters.catalog import ENCOUNTERS
    from game.headless.relics.rewards import extra_rewards, validate_extra

    run = RunEngine(seed=2, rng_profile="native", config=RunConfig())
    add_relic(run.state, "white_star")
    add_relic(run.state, "lasting_candy")
    encounter = next(e for e in ENCOUNTERS.values() if e.room_kind == "elite")
    before = run.state.rng.stream("rewards").counter
    extra = extra_rewards(run.state, run.cards, encounter)
    assert len(extra) == 1 and len(extra[0]["offers"]) == 4
    assert all(run.cards.definition(n).rarity == "rare" for n in extra[0]["offers"])
    assert run.state.rng.stream("rewards").counter == before + 12
    validate_extra(run.state, run.cards, json.loads(json.dumps(extra)))
    assert restored(run).state.rng.snapshot() == run.state.rng.snapshot()


def test_dingy_rug_applies_to_orrery_but_not_hefty_tablet_or_direct_event_grants():
    from game.headless.run import events
    from game.headless.run.actions import ChooseEventOption

    run = RunEngine(seed=2, rng_profile="native", config=RunConfig())
    add_relic(run.state, "dingy_rug")
    add_relic(run.state, "orrery")
    offers = [o["definition_id"] for w in run.state.relic_work for o in w.get("offers", [])]
    assert any(run.cards.definition(n).pool == "colorless" for n in offers)
    restored(run)
    direct = RunEngine(seed=2, rng_profile="native", config=RunConfig())
    add_relic(direct.state, "dingy_rug")
    add_relic(direct.state, "hefty_tablet")
    offers = [
        o["definition_id"] for w in direct.state.relic_work if w["kind"] == "card_reward" for o in w["offers"]
    ]
    assert all(direct.cards.definition(n).pool == "ironclad" for n in offers)
    restored(direct)
    event = RunEngine(seed=2, rng_profile="native", config=RunConfig())
    add_relic(event.state, "dingy_rug")
    events.begin(event.state, "brain_leech")
    choice = next(
        a
        for a in event.legal_actions()
        if isinstance(a, ChooseEventOption) and a.option_id == "share_knowledge"
    )
    event.apply(choice)
    offers = event.state.pending["data"]["active"]["offers"]
    assert all(event.cards.definition(n).pool == "ironclad" for n in offers)
    restored(event)


def test_restricted_lasting_candy_duplicate_fallback_rejects_atomically():
    from game.headless.run import rewards
    run = RunEngine(seed=2, rng_profile="native", config=RunConfig(
        reward_cards=("inflame", "barricade", "demon_form")))
    add_relic(run.state, "lasting_candy")
    before = run.snapshot()
    with pytest.raises(ValueError, match="duplicate-power fallback"):
        rewards.begin_combat_rewards(run.state, run.cards)
    assert run.snapshot() == before
    restored(run)


def test_previous_run_schema_rejects_without_mutation():
    run = RunEngine(seed=2, rng_profile="native")
    before = run.snapshot()
    old = deepcopy(before)
    old["schema"] = "headless_run_state_v24"
    with pytest.raises(ValueError):
        run.restore(old)
    assert run.snapshot() == before
