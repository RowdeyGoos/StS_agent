"""Actual native attack-command vectors and bounded automatic death-hook regressions."""

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS, CardCatalog
from game.headless.cards.effects import RandomEnemyAttack
from game.headless.cards.operations import Attack
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import NativeRandomService, COMBAT_STREAMS
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.monsters.base import Enemy
from game.headless.monsters.vantom import Vantom
from game.headless.monsters.phrog_parasite import PhrogParasite
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.inventory import add_relic
from game.headless.powers.ironclad import apply_power

VECTORS = json.loads(
    (Path(__file__).parents[1] / "fixtures/headless_native_interaction_vectors.json").read_text()
)


def saved(engine):
    return json.loads(json.dumps(engine.snapshot()))


def slot(enemy, enemies, initial_count):
    index = enemies.index(enemy)
    return f"initial{index}" if index < initial_count else f"wriggler{index - initial_count + 1}"


@pytest.mark.parametrize("row", VECTORS["rows"], ids=lambda r: f"{r['seed']}-{r['mode']}")
def test_native_multihit_damage_death_spawn_targets_and_rng_suffixes(row, monkeypatch):
    targeted = row["mode"] == "targeted_spawn"
    area = row["mode"] == "area_spawn"
    original = DEFAULT_CARDS.definition("sword_boomerang")
    definition = replace(
        original,
        levels=(replace(original.levels[0], base_damage=row["damage"], uses_target=targeted),),
        effects=(
            (
                Attack(hits=row["hits"], all_enemies=area)
                if targeted or area
                else RandomEnemyAttack(row["hits"], row["hits"])
            ),
        ),
    )
    catalog = CardCatalog([definition])
    service = NativeRandomService(int(row["seed"]))
    streams = {n: service.stream(n) for n in COMBAT_STREAMS}

    def encounter(_):
        rng = MonsterConstruction(streams["monster_ai"], streams["niche"])
        return [(PhrogParasite if c["type"] == "PhrogParasite" else Vantom)(rng) for c in row["before"]]

    combat = CombatEngine(
        deck_factory=lambda: [catalog.create("sword_boomerang")], encounter_factory=encounter, cards=catalog
    )
    combat.native_streams = streams
    combat.reset()
    for enemy, native in zip(combat.enemies, row["before"]):
        assert enemy.max_hp == native["maxHp"]
        enemy.hp, enemy.block = native["hp"], native["block"]
        enemy.statuses._counts = {p["id"].removesuffix("_power"): p["amount"] for p in native["powers"]}
    other = CombatEngine(cards=catalog)
    other.restore(saved(combat))
    trace = []
    original_damage = Enemy.take_damage

    def damage(enemy, amount, **kwargs):
        before_hp, before_block = enemy.hp, enemy.block
        result = original_damage(enemy, amount, **kwargs)
        if enemy.combat_player is combat.player:
            trace.append(
                {
                    "slot": slot(enemy, combat.enemies, len(row["before"])),
                    "damage": before_hp - enemy.hp,
                    "blocked": before_block - enemy.block,
                }
            )
        return result

    monkeypatch.setattr(Enemy, "take_damage", damage)
    action = PlayCard(combat.player.hand[0].instance_id, 0 if targeted else None)
    combat.apply(action)
    other.apply(action)
    assert saved(combat) == saved(other)
    assert trace == [
        {k: v for k, v in hit.items() if k != "overkill"} for group in row["results"] for hit in group
    ]
    alive = [e for e in combat.enemies if e.is_alive]
    assert [(slot(e, combat.enemies, len(row["before"])), e.hp, e.max_hp, e.block) for e in alive] == [
        (e["slot"], e["hp"], e["maxHp"], e["block"]) for e in row["after"]
    ]
    for enemy, native in zip(alive, row["after"]):
        assert enemy.statuses.get("slippery") == next(
            (p["amount"] for p in native["powers"] if p["id"] == "slippery_power"), 0
        )
    for name, prefix in (("combat_targets", "target"), ("niche", "hp"), ("monster_ai", "ai")):
        assert streams[name].counter == row[prefix + "Counter"]
        assert deepcopy(streams[name]).next_double() == row[prefix + "Suffix"]
    final = CombatEngine(cards=catalog)
    final.restore(saved(combat))
    assert saved(final) == saved(combat)


def phrog_run(*, choices=False):
    run = RunEngine(
        seed=2, rng_profile="native", config=RunConfig(), card_ids=["strike", "strike", "defend", "bash"]
    )
    add_relic(run.state, "gremlin_horn", cards=run.cards)
    run.start_combat(encounter_id="overgrowth_phrog_parasite", cards_per_turn=0)
    p = run.combat.player
    strikes = [c for c in p.deck.draw_pile if c.definition.definition_id == "strike"]
    p.deck.draw_pile.remove(strikes[0])
    p.hand.append(strikes[0])
    p.deck.draw_pile.remove(strikes[1])
    p.deck.draw_pile.append(strikes[1])
    if choices:
        p.deck.discard_pile = p.deck.draw_pile
        p.deck.draw_pile = []
        apply_power(p, "stratagem", 1)
    else:
        apply_power(p, "hellraiser", 1)
    run.combat.enemies[0].hp = 1
    return run, strikes


def test_horn_hellraiser_strike_runs_before_infested_and_cannot_target_future_children():
    run, strikes = phrog_run()
    before_rng = run.combat.player.deck.target_rng.getstate()
    other = RunEngine()
    other.restore(saved(run))
    action = PlayCard(strikes[0].instance_id, 0)
    run.apply(action)
    other.apply(action)
    assert saved(run) == saved(other)
    p = run.combat.player
    assert len(run.combat.enemies) == 5 and not run.combat.done
    assert all(e.hp == e.max_hp for e in run.combat.enemies[1:])
    assert p.rules.attacks_finished == 1  # Drawn Strike has no target and is not played.
    assert {c.instance_id for c in p.deck.discard_pile} == {c.instance_id for c in strikes}
    assert p.deck.target_rng.getstate() == before_rng
    assert p.energy == 3


def test_paused_death_hook_exposes_choice_after_infested_and_parent_play_finish():
    run, strikes = phrog_run(choices=True)
    run.apply(PlayCard(strikes[0].instance_id, 0))
    p = run.combat.player
    assert not run.combat.done and p.rules.selection
    assert len(run.combat.enemies) == 5 and run.combat.enemies[0].spawned
    assert p.rules.attacks_finished == 1 and not p.deck.in_play
    assert p.rules.active_hook == 1 and not p.rules.deferred_hooks
    before = saved(run)
    other = RunEngine()
    other.restore(before)
    for mutation in ("foreign_context", "duplicate_spawn", "living"):
        bad = deepcopy(before)
        rules = bad["combat"]["player"]["rules"]
        if mutation == "foreign_context":
            rules["active_hook"] = 2
        elif mutation == "duplicate_spawn":
            rules["tasks"].append(["spawn_wrigglers", 0])
        else:
            bad["combat"]["enemies"][0]["state"]["hp"] = 1
        with pytest.raises(ValueError):
            other.restore(bad)
        assert saved(other) == before
    choice = p.rules.selection["candidates"][0]
    for action in (ChooseCombatCard(choice), ConfirmCombatSelection()):
        run.apply(action)
        other.apply(action)
        assert saved(run) == saved(other)
    assert len(run.combat.enemies) == 5 and not run.combat.done
    assert p.rules.active_hook == 0 and not p.rules.tasks


@pytest.mark.parametrize("lethal", [False, True])
def test_direct_damage_drains_only_its_lethal_callback_boundary(lethal):
    run, _ = phrog_run()
    p, phrog = run.combat.player, run.combat.enemies[0]
    phrog.hp = 1 if lethal else 10
    p.rules.tasks.append(["energy", 3])
    phrog.take_damage(1, is_attack=False)
    if lethal:
        assert phrog.spawned and len(run.combat.enemies) == 5
        assert p.rules.tasks == [] and p.energy == 7  # Base3 + Horn1 + queued3.
    else:
        assert not phrog.spawned and len(run.combat.enemies) == 1
        assert p.rules.tasks == [["energy", 3]] and p.energy == 3
