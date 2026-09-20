"""Fresh native shared bags refill independently of ownership and caller filters."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib
import json

import pytest

from game.headless.core.native_rng import NativeRng
from game.headless.generation import relics
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.actions import ChooseNode, OpenChest, ClaimTreasureRelic, LeaveTreasure
from game.headless.run.config import RunConfig
from tests.headless.test_act2_run import clone, saved, step

ROOT = Path(__file__).parents[2]
RECORD = json.loads((ROOT / 'tests/fixtures/headless_relic_refill_vectors.json').read_text())


def test_executed_oracle_identity():
    assert hashlib.sha256((ROOT / 'tools/native_eligibility_oracle/oracle.cs').read_bytes()).hexdigest() == RECORD['fixtureSha256']


@pytest.mark.parametrize('row', RECORD['rows'], ids=lambda r: r['mode'])
def test_native_refill_filter_fallback_and_ownership(row):
    raw = NativeRng(0)
    # Native populates just this shared-content bag before authoring its deques.
    from game.headless.core.content_order import SHAREDRELICPOOL
    from game.headless.relics.base import RELICS, RelicInstance
    groups = {}
    for name in SHAREDRELICPOOL:
        groups.setdefault(RELICS[name].rarity, []).append(name)
    for bag in groups.values():
        raw.shuffle(bag)
    assert raw.counter == row['counterBefore']
    owner = 'player' if row['mode'] == 'player_empty' else 'shared'
    bags = {'shared': deepcopy(row['initial']), 'player': {}}
    bags[owner] = deepcopy(row['initial'])
    state = SimpleNamespace(relic_bags=bags, visited_room_count=row['floor'],
                            relics=[RelicInstance('amethyst_aubergine', 'owned')] if row['mode'] == 'owned_repeat' else [])
    allowed = ('molten_egg',) if row['mode'] in ('filtered_nonempty', 'fallback_empty') else None
    assert relics.pull(state, rarity=row['rarity'], owner=owner, back=row['mode'] == 'empty_back', allowed=allowed) == row['selected']
    assert bags[owner] == row['final']
    assert raw.counter == row['counterAfter']
    assert raw.next_double() == row['suffix']
    if row['mode'] == 'owned_repeat':
        assert row['owned'] == ['amethyst_aubergine'] * 2


def test_repeated_native_chest_offers_and_pickups_survive_json(monkeypatch):
    graph = MapGraph((MapNode('a', 'treasure', ('b',)), MapNode('b', 'treasure', ('fight',)),
                      MapNode('fight', 'combat', (), 'overgrowth_nibbit')), 'a')
    run = RunEngine(seed=2, graph=graph, config=RunConfig(), rng_profile='native')
    monkeypatch.setattr(relics, 'roll', lambda *args, **kwargs: 'common')
    for node in ('a', 'b'):
        run.state.relic_bags['shared']['common'] = []
        step(run, ChooseNode(node))
        assert run.state.pending['relic_id'] == 'strawberry'
        step(run, OpenChest())
        step(run, ClaimTreasureRelic(run.state.pending['treasure_id']))
        step(run, LeaveTreasure())
    assert run.state.treasure_relics_drawn == ['strawberry'] * 2
    assert len({r.instance_id for r in run.state.relics}) == 2
    assert saved(clone(run)) == saved(run)
    step(run, ChooseNode('fight'))
    assert len(run.combat.player.rules.relics) == 2


def test_native_duplicate_max_hp_pickups_are_independent():
    run = RunEngine(rng_profile='native')
    hp = run.state.max_hp
    a = add_relic(run.state, 'strawberry')
    b = add_relic(run.state, 'strawberry')
    assert a.instance_id != b.instance_id
    assert run.state.max_hp == hp + 14
    assert saved(clone(run)) == saved(run)


def test_old_bag_semantics_reject_without_mutation():
    run = RunEngine(rng_profile='native')
    before = saved(run)
    bad = deepcopy(before)
    bad['schema'] = 'headless_run_state_v56'
    with pytest.raises(ValueError):
        run.restore(bad)
    assert saved(run) == before


def test_duplicate_horns_resume_independent_draws_after_stratagem():
    from game.headless.core.combat import CombatEngine
    from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection
    from game.headless.relics.base import RelicInstance
    from game.headless.powers.ironclad import apply_power
    from game.headless.monsters.hive_normal import Chomper
    from game.headless.cards.catalog import DEFAULT_CARDS
    combat = CombatEngine(cards_per_turn=0, deck_factory=lambda: [DEFAULT_CARDS.create('defend') for _ in range(4)],
                          encounter_factory=lambda rng: [Chomper(rng), Chomper(rng)])
    combat.reset(relics=[RelicInstance('gremlin_horn', 'horn.1'), RelicInstance('gremlin_horn', 'horn.2')])
    p = combat.player
    p.deck.discard_pile[:] = p.deck.draw_pile
    p.deck.draw_pile.clear()
    apply_power(p, 'stratagem', 1)
    energy = p.energy
    combat.enemies[0].take_damage(1000, is_attack=False)
    assert p.energy == energy + 2
    assert p.rules.selection is not None
    while p.rules.selection is not None:
        restored = CombatEngine()
        restored.restore(json.loads(json.dumps(combat.snapshot())))
        action = next(a for a in combat.legal_actions() if isinstance(a, ChooseCombatCard))
        for candidate in (combat, restored):
            candidate.apply(action)
            candidate.apply(ConfirmCombatSelection())
        assert combat.snapshot() == restored.snapshot()
    assert len(p.hand) == 3  # Two Horn draws plus Stratagem's selected card.
    assert not p.rules.deferred_hooks


@pytest.mark.parametrize('forgery', ['reopen', 'old_copy'])
def test_chest_claim_receipt_rejects_reopen_and_preexisting_copy(forgery, monkeypatch):
    graph = MapGraph((MapNode('chest', 'treasure', ()),), 'chest')
    run = RunEngine(graph=graph, config=RunConfig(), rng_profile='native')
    previous = add_relic(run.state, 'strawberry')
    monkeypatch.setattr(relics, 'roll', lambda *args, **kwargs: 'common')
    run.state.relic_bags['shared']['common'] = []
    step(run, ChooseNode('chest'))
    step(run, OpenChest())
    if forgery == 'reopen':
        step(run, ClaimTreasureRelic(run.state.pending['treasure_id']))
    before = saved(run)
    bad = deepcopy(before)
    pending = bad['state']['pending']
    if forgery == 'reopen':
        pending.update(stage='open', claimed_instance_id=None)
    else:
        pending.update(stage='claimed', claimed_instance_id=previous.instance_id)
    with pytest.raises(ValueError, match='[Cc]hest'):
        run.restore(bad)
    assert saved(run) == before
