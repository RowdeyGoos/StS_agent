"""Full campaign task hooks; game mechanics remain owned by FullRunEnv."""
from copy import deepcopy
from dataclasses import asdict

import numpy as np

from game.agent.gym_env import FullRunEnv
from game.agent.gym_env import EnvironmentFailure
from game.agent import contracts as c
from game.agent.progress import completed_act
from .rewards import RewardSpec, ACT_RUN_SCHEMA, SHAPED_RUN_SCHEMAS, measure_act_run, measure_full_run
from .scenarios import episode_seed


def campaign_seed(split, index):
    """Match Gym's reset-to-engine seed mapping for runner demonstrations/eval."""
    return int(np.random.default_rng(episode_seed(split, index)).integers(0, 2**63-1))


def environment(*, encounter, reward_spec, **kwargs):
    if (encounter not in ('overgrowth', 'underdocks') or type(reward_spec) is not RewardSpec or
            reward_spec.task != 'full_run'):
        raise ValueError('Unsupported full-run task')
    if reward_spec.schema in SHAPED_RUN_SCHEMAS:
        return FullRunTrainingEnv(reward_spec=reward_spec, first_act=encounter,
                                  character='ironclad', ascension=0, **kwargs)
    return FullRunEnv(first_act=encounter, character='ironclad', ascension=0, **kwargs)


class FullRunTrainingEnv(FullRunEnv):
    """Configurable rewards and Act 1/full-campaign task boundaries."""

    def __init__(self, *, reward_spec, **kwargs):
        if type(reward_spec) is not RewardSpec or reward_spec.schema not in SHAPED_RUN_SCHEMAS:
            raise ValueError('Expected a shaped campaign training reward')
        self.reward_spec = reward_spec
        self._reward_input = self._reward_measurement = None
        self._act_success = False
        super().__init__(**kwargs)

    def reset(self, *, seed=None, options=None):
        self._reward_input = self._reward_measurement = None
        self._act_success = False
        return super().reset(seed=seed, options=options)

    def step(self, action):
        self._reward_input = self._reward_measurement = None
        return super().step(action)

    def _dispatch(self, candidate_ref):
        action = next(a for a in self._frame.decision.candidates if a.ref == candidate_ref)
        before = self._adapter.combat_summary
        before_act = completed_act(self.public_state)
        report = super()._dispatch(candidate_ref)
        self._reward_input = action, report, before, before_act
        return report

    def _refresh(self, *, initial=False):
        super()._refresh(initial=initial)
        if self.reward_spec.episode_goal == 'act1':
            act = completed_act(self.public_state)
            if initial and (act is not None or not hasattr(self.public_state, 'run') or
                            self.public_state.run.get('act') != 1):
                raise EnvironmentFailure('unfinished_act1_start_required')
            if act == 1:
                self._act_success = True
                # Task termination takes precedence over a simultaneous budget
                # cutoff. Preserve the actual continuation decision for records.
                self._finish(c.RunOutcome('sts_run_outcome_v1', 'truncated', 'external_stop'),
                             preserve_decision=True)

    def _task_result(self):
        action, report, before, before_act = self._reward_input
        after = self._adapter.combat_summary
        measured = (measure_act_run(action, report, self.public_state, before, after, before_act)
                    if self.reward_spec.schema == ACT_RUN_SCHEMA else
                    measure_full_run(action, report, self.public_state, before, after))
        reward = self.reward_spec.evaluate(measured)
        self._reward_measurement = {'spec_id':self.reward_spec.identity,
            'components':asdict(measured),'total':reward,
            'context':{'before_combat':None if before is None else asdict(before),
                       'after_combat':None if after is None else asdict(after),
                       **({'before_act':before_act} if self.reward_spec.schema == ACT_RUN_SCHEMA else {})}}
        _, terminated, truncated = super()._task_result()
        return (reward, True, False) if self._act_success else (reward, terminated, truncated)

    def _info(self, report=None):
        return {**super()._info(report), 'training_reward':deepcopy(self._reward_measurement),
                **({'goal':self.reward_spec.episode_goal} if self.reward_spec.schema == ACT_RUN_SCHEMA else {}),
                **({'act1_cleared':self._act_success} if self.reward_spec.episode_goal == 'act1' else {})}
