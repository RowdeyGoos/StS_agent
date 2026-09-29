"""Strict objective contracts and hand-calculated pure public measurements."""
from dataclasses import FrozenInstanceError, asdict, replace
import json

import pytest

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.headless.combat_summary import CombatSummary
from game.agent.training.config import TrainingConfig
from game.agent.training.rewards import RewardComponents, RewardError, RewardSpec, measure


def test_resolved_identity_defaults_and_immutable_configuration(tmp_path):
    default = RewardSpec()
    assert default == RewardSpec({}) == RewardSpec({'combat_win': 1, 'combat_loss': -0.0})
    assert default.identity == RewardSpec(dict(reversed(default.weights))).identity
    assert default == RewardSpec.loads(json.dumps(default.to_dict()))
    assert default.identity != RewardSpec({'combat_loss': -1}).identity
    with pytest.raises(FrozenInstanceError):
        default.weights = ()
    config = TrainingConfig(reward=RewardSpec({'win_hp_fraction': 0.25, 'potion_use_action': -0.02}))
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(config.to_dict()))
    assert TrainingConfig.load(path) == config


@pytest.mark.parametrize('value', [True, None, '1', float('nan'), float('inf'), -float('inf'), 10**400])
def test_nonfinite_or_nonnumeric_weights_reject(value):
    with pytest.raises(RewardError):
        RewardSpec({'combat_win': value})


@pytest.mark.parametrize('value', [
    {'damage_prevented': 0}, {'combat_Win': 1}, [('combat_win', 1)],
    (('combat_win', 1), ('combat_win', 0)), (('combat_win',),),
])
def test_unknown_unavailable_duplicate_or_malformed_weights_reject(value):
    with pytest.raises(RewardError):
        RewardSpec(value)


@pytest.mark.parametrize('text', [
    '{"schema":"sts_training_reward_v1","weights":{"combat_win":1,"combat_win":0}}',
    '{"schema":"sts_training_reward_v1","weights":{"combat_win":NaN}}',
    '{"schema":"sts_training_reward_v1","weights":{"combat_win":1e309}}',
    '{"schema":"sts_training_reward_v2","weights":{}}',
    '{"schema":"sts_training_reward_v1","weights":{},"extra":true}',
    '{"weights":{}}', '[]',
])
def test_strict_reward_json(text):
    with pytest.raises(RewardError):
        RewardSpec.loads(text)


@pytest.mark.parametrize('edit', [
    lambda v: v.update(mode='full_run'), lambda v: v.update(scenario_set='unknown'),
    lambda v: v.update(seed=10), lambda v: v.pop('reward'),
])
def test_unsupported_or_ambiguous_config_rejects(edit):
    value = TrainingConfig().to_dict()
    edit(value)
    with pytest.raises(RewardError):
        TrainingConfig.from_dict(value)


def test_hand_calculated_reward_all_components_and_overflow():
    spec = RewardSpec({'combat_win': 2, 'combat_loss': -1, 'win_hp_fraction': 0.25,
                       'end_turn_action': -0.01, 'potion_use_action': -0.02})
    assert spec.evaluate(RewardComponents(1, 0, 0.5, 0, 1)) == pytest.approx(2.105)
    assert spec.evaluate(RewardComponents(0, 1, 0, 1, 0)) == pytest.approx(-1.01)
    assert spec.evaluate(RewardComponents(0, 0, 0, 0, 0)) == 0
    with pytest.raises(RewardError, match='finite'):
        RewardSpec({'combat_win': 1e308, 'win_hp_fraction': 1e308}).evaluate(RewardComponents(1, 0, 1, 0, 0))


@pytest.mark.parametrize('edit', [
    lambda v: v.pop('win_hp_fraction'), lambda v: v.update(damage_taken=0),
    lambda v: v.update(combat_loss=True), lambda v: v.update(end_turn_action=1.0),
    lambda v: v.update(combat_win=2), lambda v: v.update(win_hp_fraction=0.5),
    lambda v: v.update(win_hp_fraction=float('nan')),
    lambda v: v.update(combat_win=1, combat_loss=1),
    lambda v: v.update(end_turn_action=1, potion_use_action=1),
])
def test_missing_or_impossible_measurements_reject_even_at_zero_weight(edit):
    value = asdict(RewardComponents(0, 0, 0, 0, 0))
    edit(value)
    with pytest.raises(RewardError):
        RewardSpec().evaluate(value)


def test_pure_measurement_and_completed_owner_cannot_pay_again():
    action = f.Candidate('action:0', 'end_turn')
    report = c.ExecutionReport('sts_execution_report_v1', 'reconciled', 'applied', 'none')
    before = CombatSummary('combat:0', 'ongoing', 40, 80, 1)
    after = CombatSummary('combat:0', 'victory', 46, 80, 2)
    expected = RewardComponents(1, 0, 46/80, 1, 0)
    for _ in range(3):
        assert measure(action, report, before, after) == expected
    assert before.hp == 40 and after.hp == 46
    for invalid_before, invalid_after in ((after, after), (before, replace(after, combat_ref='combat:1')),
                                          (before, replace(after, turn=0))):
        with pytest.raises(RewardError):
            measure(action, report, invalid_before, invalid_after)
    for status, mutation, reason in (('rejected', 'none', 'invalid_action'),
                                     ('uncertain', 'unknown', 'timeout'), ('pending', 'queued', 'none')):
        with pytest.raises(RewardError):
            measure(action, replace(report, status=status, mutation=mutation, reason=reason), before, after)
