"""Resolved, versioned settings for bounded synchronous combat PPO."""
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from pathlib import Path
from game.agent.action_policy import ALL_LEGAL

from .config import TrainingConfig, RUN_SCENARIO_SET
from .rewards import strict_json
from .scenarios import SCENARIO_SET, scenario


@dataclass(frozen=True, slots=True)
class PPOConfig:
    rollout_steps: int = 256
    episode_decisions: int = 96
    episode_seconds: float = 30.0
    batch_size: int = 32
    epochs: int = 4
    learning_rate: float = 0.0003
    gamma: float = 1.0
    gae_lambda: float = 0.95
    clip_ratio: float = 0.2
    entropy_weight: float = 0.01
    value_weight: float = 0.5
    gradient_clip: float = 0.5
    target_kl: float = 0.03
    normalize_advantages: bool = True

    def __post_init__(self):
        for key, maximum in (('rollout_steps', 4096), ('episode_decisions', 4096),
                             ('batch_size', 256), ('epochs', 20)):
            value = getattr(self, key)
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError('Invalid PPO '+key)
        for key in ('episode_seconds', 'learning_rate', 'gamma', 'gae_lambda', 'clip_ratio',
                    'entropy_weight', 'value_weight', 'gradient_clip', 'target_kl'):
            value = getattr(self, key)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError('Invalid finite PPO '+key)
        if (not 0 < self.episode_seconds <= 3600 or self.learning_rate == 0 or self.gradient_clip == 0 or
                not 0 < self.gamma <= 1 or not 0 <= self.gae_lambda <= 1 or not 0 < self.clip_ratio < 1 or
                self.target_kl == 0 or type(self.normalize_advantages) is not bool):
            raise ValueError('Unsupported PPO settings')


@dataclass(frozen=True, slots=True)
class PPOExperiment:
    training: TrainingConfig = field(default_factory=TrainingConfig)
    ppo: PPOConfig = field(default_factory=PPOConfig)
    encounters: tuple[str, ...] = ('overgrowth_nibbit',)
    source: str = SCENARIO_SET
    schema: str = 'sts_ppo_experiment_v1'

    def __post_init__(self):
        if (self.schema not in ('sts_ppo_experiment_v1', 'sts_ppo_experiment_v2') or type(self.training) is not TrainingConfig or
                type(self.ppo) is not PPOConfig or type(self.encounters) is not tuple or
                not 1 <= len(self.encounters) <= 100 or
                any(type(n) is not str or not 0 < len(n) <= 128 for n in self.encounters) or
                len(set(self.encounters)) != len(self.encounters) or
                type(self.source) is not str or not 0 < len(self.source) <= 128):
            raise ValueError('Invalid PPO experiment')
        if (self.schema == 'sts_ppo_experiment_v1') != (self.training.action_policy == ALL_LEGAL):
            raise ValueError('Policy-action restrictions require PPO experiment v2')
        if self.training.mode == 'full_run':
            if (self.source != RUN_SCENARIO_SET or self.ppo.gamma != 1 or
                    not set(self.encounters) <= {'overgrowth', 'underdocks'}):
                raise ValueError('Full-run PPO requires genuine Ironclad A0 regions and gamma=1')
        elif self.source == RUN_SCENARIO_SET:
            raise ValueError('Full-run source cannot enter combat training')
        elif self.source == SCENARIO_SET:
            for name in self.encounters:
                scenario(name)
        elif self.source == 'ironclad_a0_curriculum_v1':
            from .curriculum import start
            if any(start(name).test_only for name in self.encounters):
                raise ValueError('Held-out combinations cannot enter PPO training')

    def to_dict(self):
        return {'schema': self.schema, 'training': self.training.to_dict(), 'ppo': asdict(self.ppo),
                'encounters': list(self.encounters), 'source': self.source}

    @property
    def identity(self):
        return self.schema + ':' + hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True,
            separators=(',', ':'), allow_nan=False).encode()).hexdigest()

    @classmethod
    def from_dict(cls, value):
        if (type(value) is not dict or set(value) != set(cls.__dataclass_fields__) or
                type(value['ppo']) is not dict or set(value['ppo']) != set(PPOConfig.__dataclass_fields__) or
                type(value['encounters']) is not list):
            raise ValueError('Expected a complete resolved PPO experiment')
        return cls(TrainingConfig.from_dict(value['training']), PPOConfig(**value['ppo']),
                   tuple(value['encounters']), value['source'], value['schema'])

    @classmethod
    def load(cls, path):
        return cls.from_dict(strict_json(Path(path).read_text(encoding='utf-8')))
