"""Native Sword Boomerang/death/choice composition and private continuation."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.combat import CombatEngine
from game.headless.core.native_service import NativeRandomService, COMBAT_STREAMS
from game.headless.encounters.randomness import MonsterConstruction
from game.headless.monsters.base import Enemy
from game.headless.monsters.phrog_parasite import PhrogParasite
from game.headless.powers.ironclad import apply_power
from game.headless.relics.base import RelicInstance

RECORD = json.loads((Path(__file__).parents[2] / "docs/evidence/native_attack_hooks_2026_09_19.json").read_text())


MULTIPLE = json.loads((Path(__file__).parents[2] / "docs/evidence/native_multiple_deaths_2026_09_19.json").read_text())


def saved(combat):
    return json.loads(json.dumps(combat.snapshot()))


@pytest.mark.parametrize("row", RECORD["result"]["rows"] + MULTIPLE["result"]["rows"], ids=lambda r: f'{r["seed"]}-{r["fillers"]}-{r["upgraded"]}-{r.get("terminal", "single")}')
def test_native_card_death_spawn_and_paused_horn(row, monkeypatch):
    multiple = "terminal" in row
    terminal = row.get("terminal", False)
    service = NativeRandomService(int(row["seed"]))
    streams = {name: service.stream(name) for name in COMBAT_STREAMS}
    initial_shuffle = streams["shuffle"].getstate()
    combat = CombatEngine(
        cards=DEFAULT_CARDS, cards_per_turn=0,
        deck_factory=lambda: [DEFAULT_CARDS.create("defend") for _ in range(row["fillers"])] + [DEFAULT_CARDS.create("sword_boomerang")],
        encounter_factory=lambda _: [PhrogParasite(MonsterConstruction(streams["monster_ai"], streams["niche"]))],
    )
    combat.native_streams = streams
    combat.rng = streams["monster_ai"]
    combat.reset(relics=[RelicInstance("the_abacus", "relic.0"), RelicInstance("gremlin_horn", "relic.1")])
    p = combat.player
    cards = sorted(p.deck.all_cards(), key=lambda c: c.instance_id)
    attack = next(c for c in cards if c.definition.definition_id == "sword_boomerang")
    fillers = [c for c in cards if c is not attack]
    identities = {c.instance_id: f"card.{i}" for i, c in enumerate([*fillers, attack])}
    p.deck.draw_pile, p.deck.discard_pile = [], fillers
    p.hand[:] = [attack]
    p.deck.rng.setstate(initial_shuffle)  # Native explicit fixture has no opening shuffle.
    p.energy = 1
    apply_power(p, "stratagem", 1)
    if multiple:
        p.strength = 100
    if terminal:
        apply_power(p, "duplication", 1)
    if row["upgraded"]:
        attack.upgrade()
    combat.enemies[0].hp = 1
    combat.enemies[0].statuses._counts = {"infested": 1}

    def state(engine):
        player = engine.player
        return dict(**({"play": [identities[c.instance_id] for c in player.deck.in_play]} if multiple else {}), hand=[identities[c.instance_id] for c in player.hand],
                    draw=[identities[c.instance_id] for c in reversed(player.deck.draw_pile)],
                    discard=[identities[c.instance_id] for c in player.deck.discard_pile],
                    energy=player.energy, block=player.block)

    def slot(enemy):
        index = combat.enemies.index(enemy)
        return "enemy" if index == 0 else f"wriggler{index}"

    def enemies(engine):
        return [dict(type=type(e).__name__, slot="enemy" if i == 0 else f"wriggler{i}",
                     hp=e.hp, maxHp=e.max_hp, block=e.block,
                     powers=[dict(id=k + "_power", amount=v) for k, v in e.statuses._counts.items()])
                for i, e in enumerate(engine.enemies) if e.is_alive]

    assert state(combat) == row["before"]
    assert enemies(combat) == row["enemiesBefore"]
    hits = []
    original = Enemy.take_damage

    def damage(enemy, amount, **kwargs):
        hp, block = enemy.hp, enemy.block
        result = original(enemy, amount, **kwargs)
        if enemy.combat_player is p:
            hits.append(dict(slot=slot(enemy), damage=hp - enemy.hp, blocked=block - enemy.block))
        return result

    monkeypatch.setattr(Enemy, "take_damage", damage)
    combat.apply(PlayCard(attack.instance_id))
    if multiple:
        # Native damage history omits the terminal hit; target RNG and all-dead
        # state independently verify that the fifth hit really executed.
        assert (hits[:-1] if terminal else hits) == row["hits"]
        assert len(hits) == row["deaths"]
        assert enemies(combat) == row["enemiesCheckpoint"]
        explicit_choice = bool(row["answers"] and row["answers"][0]["options"])
        assert bool(p.rules.selection) == explicit_choice
        if explicit_choice:
            assert state(combat) == row["checkpoint"]
            assert [identities[i] for i in p.rules.selection["candidates"]] == row["answers"][0]["options"]
        assert row["pendingStates"] == (["Canceled"] if terminal else ["Finished"])
        assert p.rules.hook_sequence == (4 if terminal else row["deaths"])
        assert combat.done == terminal
    else:
        assert hits == row["hits"]
        assert state(combat) == row["paused"]
        assert enemies(combat) == row["enemiesPaused"]
        assert bool(p.rules.selection) == row["detached"] == (row["fillers"] == 3)
    assert p.rules.attacks_finished == (2 if terminal else 1)
    assert attack in p.deck.discard_pile
    assert len(combat.enemies) == 5 and not combat.enemies[0].is_alive
    other = CombatEngine(cards=DEFAULT_CARDS)
    other.restore(saved(combat))
    assert saved(other) == saved(combat)
    if p.rules.selection:
        native_selected = row["answers"][0]["selected"][0] if multiple else row["selected"]
        selected = next(i for i, label in identities.items() if label == native_selected)
        assert selected in p.rules.selection["candidates"]
        for action in (ChooseCombatCard(selected), ConfirmCombatSelection()):
            combat.apply(action)
            other.apply(action)
            assert saved(combat) == saved(other)
    assert state(combat) == state(other)
    if terminal:
        # Native result-pile Add is suppressed once IsEnding. Headless disposes
        # the completed outer play into discard. Keep this representation
        # difference explicit rather than claiming terminal pile equality.
        native = row["after"]
        assert native == row["checkpoint"]  # Cancellation changed nothing.
        assert native["play"] == [identities[attack.instance_id]]
        assert native["discard"] == []
        actual = state(combat)
        assert actual["play"] == []
        assert actual["discard"] == [identities[attack.instance_id]]
        assert {k: actual[k] for k in ("hand", "draw", "energy", "block")} == {k: native[k] for k in ("hand", "draw", "energy", "block")}
        assert combat.legal_actions() == other.legal_actions() == ()
        checkpoint = saved(combat)
        with pytest.raises(RuntimeError):
            combat.apply(ConfirmCombatSelection())
        assert saved(combat) == checkpoint
    else:
        assert state(combat) == row["after"]
    assert enemies(combat) == enemies(other) == row["enemiesAfter"]
    assert not p.rules.selection and not p.rules.tasks and not p.rules.deferred_hooks
    for engine in (combat, other):
        deck = engine.player.deck
        for rng, key in ((deck.rng, "shuffle"), (deck.target_rng, "targets"), (deck.niche_rng, "niche"), (engine.rng, "ai")):
            assert rng.counter == row[key]["counter"]
            assert deepcopy(rng).next_double() == row[key]["suffix"]
