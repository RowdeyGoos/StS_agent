"""Actual native callback/draw vectors; explicit fixture, not an enclosing attack."""

import json
from pathlib import Path

import pytest

from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection
from game.headless.core.resolution import drain, push
from game.headless.powers.ironclad import apply_power
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic


RECORD = json.loads((Path(__file__).parents[2] / "docs/evidence/native_death_draw_2026_09_19.json").read_text())


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


@pytest.mark.parametrize("row", RECORD["result"]["rows"], ids=lambda row: f'{row["seed"]}-{row["fillers"]}')
def test_native_horn_shuffle_choice_and_restoration(row):
    run = RunEngine(seed=int(row["seed"]), rng_profile="native", card_ids=["defend"] * row["fillers"])
    for relic in ("gremlin_horn", "the_abacus"):
        add_relic(run.state, relic)
    initial_shuffle = run.state.rng.stream("shuffle").getstate()
    run.start_combat(encounter_id="overgrowth_vantom", cards_per_turn=0)
    p = run.combat.player
    cards = sorted(p.deck.all_cards(), key=lambda card: card.instance_id)
    identities = {card.instance_id: f"card.{i}" for i, card in enumerate(cards)}
    # Match the explicit native midcombat fixture, which starts with an unused
    # Shuffle stream. Mutate the owned stream in place to preserve run aliases.
    p.deck.rng.setstate(initial_shuffle)
    p.deck.draw_pile = []
    p.deck.discard_pile = cards
    p.energy = 0
    apply_power(p, "stratagem", 1)

    def state(engine):
        player = engine.combat.player
        return dict(hand=[identities[c.instance_id] for c in player.hand],
                    draw=[identities[c.instance_id] for c in reversed(player.deck.draw_pile)],
                    discard=[identities[c.instance_id] for c in player.deck.discard_pile],
                    energy=player.energy, block=player.block)

    assert state(run) == row["before"]
    # Same boundary as the oracle's explicit AfterDeath invocation: no death
    # dispatcher, damage command or outer attack is included in this vector.
    push(p, ["death_hook"])
    drain(p)
    assert state(run) == row["paused"]
    assert bool(p.rules.selection) == row["detached"] == (row["fillers"] == 3)
    assert row["selectorCalls"] == int(row["detached"])
    other = RunEngine()
    other.restore(saved(run))
    assert saved(run) == saved(other)
    if p.rules.selection:
        assert [identities[i] for i in p.rules.selection["candidates"]] == row["options"]
        for action in (ChooseCombatCard(p.rules.selection["candidates"][0]), ConfirmCombatSelection()):
            run.apply(action)
            other.apply(action)
            assert saved(run) == saved(other)
    assert state(run) == state(other) == row["after"]
    assert not p.rules.tasks and not p.rules.deferred_hooks and not p.rules.selection
    for engine in (run, other):
        stream = engine.combat.player.deck.rng
        assert stream.counter == row["shuffleCounter"]
        assert stream.next_double() == row["shuffleSuffix"]
