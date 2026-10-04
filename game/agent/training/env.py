"""One combat task over the existing full public adapter and Gym lifecycle."""
from dataclasses import asdict
import time

from game.agent import contracts as c
from game.agent.encoding.full import FULL_RUN_PROFILE
from game.agent.gym_env import EnvironmentFailure, StsEnv
from .scenarios import scenario
from .rewards import DEFEAT_HP_SCHEMA, RewardSpec, measure_combat


class CombatTrainingEnv(StsEnv):
    """Terminate on one fight, including every nested choice owned by it.

    Default task reward is +1 for combat victory, 0 otherwise. The canonical run
    outcome remains independent: a combat win normally cuts off an unfinished
    run. A frozen RewardSpec changes task utility without changing game outcomes.
    Custom factories must return a fresh RunEngine already inside a live fight.
    """

    def __init__(self, *, encounter='overgrowth_nibbit', engine_factory=None,
                 max_decisions=256, time_limit_seconds=30.0, profile=FULL_RUN_PROFILE,
                 render_mode=None, reward_spec=None):
        self._reward_spec = RewardSpec() if reward_spec is None else reward_spec
        if type(self._reward_spec) is not RewardSpec or self._reward_spec.task != 'combat':
            raise ValueError('reward_spec must be a combat RewardSpec')
        self._reward_measurement = self._reward_input = None
        factory = engine_factory if engine_factory is not None else scenario(encounter).make

        def make(seed):
            return self._measure('initialization_seconds', factory, seed)

        super().__init__(engine_factory=make, profile=profile, max_decisions=max_decisions,
                         time_limit_seconds=time_limit_seconds, stop_at_map=False,
                         render_mode=render_mode, decision_profile='full_run_v2')
        self._combat = self._combat_ref = None
        self._timings = {}

    def reset(self, *, seed=None, options=None):
        if options is not None and (type(options) is not dict or
                                   set(options) - {'max_decisions', 'time_limit_seconds'}):
            raise ValueError('Combat reset accepts only decision/time limits')
        self._combat = self._combat_ref = None
        self._reward_measurement = self._reward_input = None
        self._timings = dict.fromkeys(('initialization_seconds', 'simulation_dispatch_seconds',
                                      'projection_seconds', 'encoding_seconds'), 0.0)
        return super().reset(seed=seed, options=options)

    @property
    def reward_spec(self):
        return self._reward_spec

    def step(self, action):
        self._reward_measurement = self._reward_input = None
        return super().step(action)

    @property
    def timings(self):
        """Wall timings for this episode, never included in policy observations.

        Dispatch includes guards/history as well as engine execution. Projection
        includes the observation guard. Encoding excludes returned-array copies.
        """
        return dict(self._timings)

    def _measure(self, key, call, *args):
        before = time.perf_counter()
        try:
            return call(*args)
        finally:
            self._timings[key] += time.perf_counter() - before

    def _observe(self):
        return self._measure('projection_seconds', super()._observe)

    def _encode(self, public):
        return self._measure('encoding_seconds', super()._encode, public)

    def _dispatch(self, candidate_ref):
        action = next(a for a in self._frame.decision.candidates if a.ref == candidate_ref)
        before = self._combat
        public = self._frame.decision
        report = self._measure('simulation_dispatch_seconds', super()._dispatch, candidate_ref)
        self._reward_input = action, report, before, public
        return report

    def _refresh(self, *, initial=False):
        summary = (self._adapter.combat_health_summary if self.reward_spec.schema == DEFEAT_HP_SCHEMA
                   else self._adapter.combat_summary)
        if initial:
            if summary is None or summary.completed:
                raise EnvironmentFailure('combat_start_required')
            self._combat_ref = summary.combat_ref
        if summary is None or summary.combat_ref != self._combat_ref:
            raise EnvironmentFailure('combat_ownership_changed')
        self._combat = summary
        if summary.completed:
            outcome = self._adapter.run_outcome or c.RunOutcome(
                'sts_run_outcome_v1', 'truncated', 'external_stop')
            self._finish(outcome)
        else:
            super()._refresh(initial=initial)

    def _task_result(self):
        action, execution, before, public = self._reward_input
        components = measure_combat(self.reward_spec, action, execution, before, self._combat,
                                    public, self.public_state)
        reward = self.reward_spec.evaluate(components)
        self._reward_measurement = {'spec_id': self.reward_spec.identity,
                                    'components': asdict(components), 'total': reward}
        if self._combat is not None and self._combat.completed:
            return reward, True, False
        _, terminated, truncated = super()._task_result()
        return reward, terminated, truncated

    def _info(self, report=None):
        return {**super()._info(report),
                'combat': None if self._combat is None else asdict(self._combat),
                'training_reward': None if self._reward_measurement is None else {
                    **self._reward_measurement, 'components': dict(self._reward_measurement['components'])}}
