"""Validated, public experiment configuration for the implemented combat task."""
from dataclasses import dataclass
from pathlib import Path
from game.agent.action_policy import ALL_LEGAL, validate_policy

from .rewards import RewardError, RewardSpec, strict_json
from .scenarios import SCENARIO_SET
RUN_SCENARIO_SET = 'ironclad_a0_full_run_v1'


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    mode: str = 'combat'
    scenario_set: str = SCENARIO_SET
    reward: RewardSpec = RewardSpec()
    action_policy: str = ALL_LEGAL

    def __post_init__(self):
        validate_policy(self.action_policy)
        if (type(self.reward) is not RewardSpec or self.reward.task != self.mode or
                (self.mode, self.scenario_set) not in (('combat', SCENARIO_SET), ('full_run', RUN_SCENARIO_SET))):
            raise RewardError('Unsupported training mode, scenario set or reward specification')

    @classmethod
    def full_run(cls):
        return cls('full_run', RUN_SCENARIO_SET, RewardSpec.full_run())

    def to_dict(self):
        return {'mode': self.mode, 'scenario_set': self.scenario_set, 'reward': self.reward.to_dict(),
                **({'action_policy': self.action_policy} if self.action_policy != ALL_LEGAL else {})}

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) not in ({'mode', 'scenario_set', 'reward'},
                {'mode', 'scenario_set', 'reward', 'action_policy'}):
            raise RewardError('Expected mode, scenario_set and reward configuration')
        return cls(value['mode'], value['scenario_set'], RewardSpec.from_dict(value['reward']),
                   value.get('action_policy', ALL_LEGAL))

    @classmethod
    def load(cls, path):
        return cls.from_dict(strict_json(Path(path).read_text(encoding='utf-8')))
