"""Snapshot copying keeps values, container types and mutation ownership."""
from collections import OrderedDict, namedtuple
from copy import deepcopy
from dataclasses import asdict, dataclass
import json

import pytest

from game.headless.core.state_records import state_record


@dataclass
class Record:
    value: object


@dataclass
class TextRecord(str):
    value: str


class CustomLeaf:
    def __init__(self, values):
        self.values = values

    def __deepcopy__(self, memo):
        return CustomLeaf(deepcopy(self.values, memo))


def test_nested_containers_dataclasses_and_atomic_subclasses_match_asdict():
    Pair = namedtuple('Pair', 'left right')
    class Sequence(list):
        pass
    class Text(str):
        pass
    value = Record(OrderedDict([
        ('nested', [Record((None, True, False, -7, 1.5, 'text')), Pair([1], Record(2))]),
        ('subclasses', Sequence([Text('visible'), TextRecord('dataclass')])),
    ]))
    expected, actual = asdict(value), state_record(value)
    assert actual == expected
    assert json.dumps(actual) == json.dumps(expected)
    assert type(actual['value']) is OrderedDict
    assert type(actual['value']['nested'][1]) is Pair
    assert type(actual['value']['subclasses']) is Sequence
    assert type(actual['value']['subclasses'][0]) is Text
    assert actual['value']['subclasses'][1] == {'value': 'dataclass'}
    actual['value']['nested'][1].left.append(9)
    assert value.value['nested'][1].left == [1]
    assert state_record(value) == expected


def test_unknown_leaves_keep_deepcopy_and_each_record_is_detached():
    child = [Record({'cost': [1, 2]})]
    value = Record([child, child, CustomLeaf([3])])
    first, second = state_record(value), state_record(value)
    assert first['value'][0] is not first['value'][1]
    first['value'][0][0]['value']['cost'].append(9)
    first['value'][2].values.append(4)
    assert child[0].value == {'cost': [1, 2]}
    assert second['value'][0][0]['value']['cost'] == [1, 2]
    assert value.value[2].values == second['value'][2].values == [3]


@pytest.mark.parametrize('value', (Record, {}, [], 1, None))
def test_root_requires_a_dataclass_instance(value):
    with pytest.raises(TypeError):
        state_record(value)


@pytest.mark.parametrize('character', ('ironclad', 'silent', 'regent', 'necrobinder', 'defect'))
def test_generated_run_and_combat_snapshots_match_standard_conversion(character, monkeypatch):
    from game.agent.full_policy import choose_action
    from game.agent.headless import HeadlessAdapter
    from game.headless.core import snapshots as combat_snapshots
    from game.headless.run import snapshots as run_snapshots
    from game.headless.run.engine import RunEngine

    run = RunEngine.campaign(character=character, seed=23)
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    frames = 0
    for _ in range(30):
        current = run.snapshot()
        with monkeypatch.context() as patch:
            patch.setattr(run_snapshots, 'state_record', asdict)
            patch.setattr(combat_snapshots, 'state_record', asdict)
            original = run.snapshot()
        assert current == original
        assert json.dumps(current, sort_keys=True) == json.dumps(original, sort_keys=True)
        restored = RunEngine()
        restored.restore(json.loads(json.dumps(current)))
        assert restored.snapshot() == current
        if run.combat is not None:
            assert frames > 0
            # Real transient card state contains dict/list fields even when
            # most flags are immutable scalars.
            card = next(c for pile in combat_snapshots.PILES
                        for c in getattr(run.combat.player.deck, pile))
            saved = combat_snapshots.card_record(card)
            saved['combat_state']['cost_discount_baselines']['external'] = 9
            saved['combat_state']['played_cost_baselines'][0] = 9
            assert card.combat_state.cost_discount_baselines == {}
            assert card.combat_state.played_cost_baselines == [0, 0, 0]
            assert run.snapshot() == current
            return
        frame = adapter.observe()
        action = choose_action(frame.decision)
        assert adapter.step(frame.binding, action.ref).status == 'reconciled'
        frames += 1
    pytest.fail('Fixture never reached combat')


@pytest.mark.parametrize('mutation', ('hp', 'rng', 'card', 'nested'))
def test_guard_still_rejects_external_state_changes(mutation):
    from game.agent.headless import HeadlessAdapter
    from game.headless.run.engine import RunEngine

    run = RunEngine(seed=3)
    run.start_combat()
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    frame = adapter.observe()
    if mutation == 'hp':
        run.state.hp -= 1
    elif mutation == 'rng':
        run.state.rng.random('run.rewards')
    elif mutation == 'card':
        run.combat.player.hand[0].combat_state.extra_damage += 1
    else:
        run.combat.player.hand[0].combat_state.played_cost_baselines[0] = 1
    before = run.snapshot()
    report = adapter.step(frame.binding, frame.decision.candidates[0].ref)
    assert report.status == 'rejected' and report.reason == 'stale_decision'
    assert run.snapshot() == before
