"""Gymnasium consumer of the public headless adapter, with sparse run reward.

Install ``sts-agent[gym]`` to use this module. The rules, contract, headless
adapter and direct gameplay CLI remain independent of Gymnasium and NumPy.
"""
from numbers import Integral
import time

import gymnasium as gym
import numpy as np

from game.agent import contracts as c
from game.agent.encoding import DEFAULT_PROFILE, EncodingError, PublicEncoder
from game.agent.headless import AdapterFault, HeadlessAdapter, UnsupportedProfile


class EnvironmentFailure(RuntimeError):
    """A failed/uncertain backend stopped the environment; reset is required."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__('Agent environment stopped: ' + reason)


def combat_map_slice(seed):
    """Authored two-combat map, starting in combat; default cutoff is first map.

    This is ordinary engine execution with an explicit supported deck/reward
    pool, not a generated campaign or a full-game victory benchmark.
    """
    from game.headless.map.graph import MapGraph, MapNode
    from game.headless.run.actions import ChooseNode
    from game.headless.run.config import RunConfig
    from game.headless.run.engine import RunEngine
    graph = MapGraph((MapNode('first', 'combat', ('next',), 'overgrowth_nibbit', row=1, column=0),
                      MapNode('next', 'combat', (), 'overgrowth_nibbit', row=2, column=0)), 'first')
    run = RunEngine(seed=seed, card_ids=('neows_fury', 'strike', 'strike', 'defend'),
                    graph=graph, config=RunConfig(reward_cards=('strike', 'defend', 'bash')))
    run.apply(ChooseNode('first'))
    return run


class StsEnv(gym.Env):
    """Fixed candidate-index actions; masked choices are non-mutating rejections.

    ``engine_factory(seed)`` must return a fresh exclusively owned RunEngine.
    Custom factories remain subject to the adapter's declared content coverage.
    ``reset`` options may override max_decisions, time_limit_seconds and stop_at_map
    for that episode. Defaults apply again on the next reset.
    """
    metadata = {'render_modes': ['ansi']}

    def __init__(self, *, engine_factory=combat_map_slice, profile=DEFAULT_PROFILE,
                 max_decisions=256, time_limit_seconds=None, stop_at_map=True,
                 render_mode=None, decision_profile='combat_reward_map_v1'):
        if render_mode not in (None, 'ansi'):
            raise ValueError('Only render_mode=None or ansi is supported')
        if not callable(engine_factory):
            raise TypeError('engine_factory must be callable')
        self.render_mode = render_mode
        self._decision_profile = decision_profile
        if decision_profile == 'full_run_v2':
            from game.agent.encoding.full import FullRunEncoder
            self.encoder = FullRunEncoder(profile)
        elif decision_profile == 'combat_reward_map_v1':
            self.encoder = PublicEncoder(profile)
        else:
            raise ValueError('Unknown public decision profile')
        self.action_space = gym.spaces.Discrete(profile.candidates)
        self.observation_space = self.encoder.space()
        self._factory = engine_factory
        self._defaults = self._options({'max_decisions': max_decisions,
                                       'time_limit_seconds': time_limit_seconds,
                                       'stop_at_map': stop_at_map})
        self._adapter = self._frame = self._encoded = self._outcome = self._public_state = None
        self._done = self._failed = False

    @staticmethod
    def _options(options):
        if type(options) is not dict or set(options) - {'max_decisions', 'time_limit_seconds', 'stop_at_map'}:
            raise ValueError('Unsupported reset options')
        result = dict(options)
        if 'max_decisions' in result:
            value = result['max_decisions']
            if type(value) is not int or value < 1:
                raise ValueError('max_decisions must be a positive integer')
        if 'stop_at_map' in result and type(result['stop_at_map']) is not bool:
            raise ValueError('stop_at_map must be boolean')
        if 'time_limit_seconds' in result:
            value = result['time_limit_seconds']
            if value is not None and (type(value) not in (int, float) or not np.isfinite(value) or value <= 0):
                raise ValueError('time_limit_seconds must be positive and finite, or None')
        return result

    def reset(self, *, seed=None, options=None):
        settings = {**self._defaults, **self._options({} if options is None else options)}
        super().reset(seed=seed)
        self.close()
        self._settings, self._steps = settings, 0
        self._done = self._failed = False
        self._started = time.monotonic()
        # This RNG seeds fresh games only. Engine RNG, action-space sampling and
        # any caller-owned policy RNG are distinct objects with separate state.
        game_seed = int(self.np_random.integers(0, 2**63 - 1))
        try:
            self._adapter = HeadlessAdapter(self._factory(game_seed), decision_profile=self._decision_profile)
            self._refresh(initial=True)
            return self._observation(), self._info()
        except BaseException as error:
            self._failed = True
            self._adapter = self._frame = self._encoded = None
            self._raise_failure(error, 'backend_reset_failure')

    @staticmethod
    def _raise_failure(error, reason):
        if (not isinstance(error, Exception) or
                isinstance(error, (AdapterFault, UnsupportedProfile, EncodingError,
                                   c.ContractError, EnvironmentFailure))):
            raise error
        raise EnvironmentFailure(reason) from error

    def _observation(self):
        # Neither callers nor wrappers can corrupt our mask or dispatch table.
        return {key: value.copy() for key, value in self._encoded.observation.items()}

    @property
    def public_state(self):
        """Immutable structured state from the same owner as the fixed encoding.

        A cutoff retains the final decision. Bindings and engine state remain
        private; callers dispatch a candidate's index through step().
        """
        if self._failed:
            raise EnvironmentFailure('reset_required_after_failure')
        return self._public_state

    def _observe(self):
        return self._adapter.observe()

    def _encode(self, public):
        return self.encoder.encode(public)

    def _dispatch(self, candidate_ref):
        return self._adapter.step(self._frame.binding, candidate_ref)

    def _info(self, report=None):
        return {'encoding': self.encoder.profile.identity,
                'execution': None if report is None else c.to_dict(report),
                'outcome': None if self._outcome is None else c.to_dict(self._outcome)}

    def _finish(self, outcome, *, preserve_decision=False):
        self._outcome = outcome
        if not preserve_decision:
            self._public_state = outcome
            self._encoded = self._encode(outcome)
        self._frame = None
        self._done = True

    def _time_expired(self):
        limit = self._settings['time_limit_seconds']
        return limit is not None and time.monotonic() - self._started >= limit

    def _refresh(self, *, initial=False):
        frame = self._observe()
        if isinstance(frame, c.RunOutcome):
            self._finish(frame)
            return
        reason = None
        if not initial:
            if self._steps >= self._settings['max_decisions']:
                reason = 'decision_budget'
            elif self._time_expired():
                reason = 'time_budget'
            elif self._settings['stop_at_map'] and (isinstance(frame.decision.context, c.MapChoice) or getattr(frame.decision.context, 'kind', None) == 'map'):
                reason = 'slice_complete'
        # Even at a cutoff, an unsupported/capacity observation is a typed
        # failure. It must not be hidden behind successful slice completion.
        encoded = self._encode(frame.decision)
        self._frame, self._encoded = frame, encoded
        self._public_state = frame.decision
        if reason:
            # Nonterminal cutoffs retain the successor state and its legal mask
            # for value bootstrapping. Only flags/info carry the cutoff outcome.
            self._finish(c.RunOutcome('sts_run_outcome_v1', 'truncated', reason), preserve_decision=True)

    def step(self, action):
        if self._failed:
            raise EnvironmentFailure('reset_required_after_failure')
        if self._adapter is None or self._done:
            raise gym.error.ResetNeeded('Call reset before stepping a new episode')
        if self._time_expired():
            self._finish(c.RunOutcome('sts_run_outcome_v1', 'truncated', 'time_budget'), preserve_decision=True)
            return self._observation(), 0.0, False, True, self._info()
        if isinstance(action, np.ndarray) and action.shape == () and np.issubdtype(action.dtype, np.integer):
            action = action.item()
        if (not isinstance(action, Integral) or isinstance(action, (bool, np.bool_)) or
                not 0 <= int(action) < len(self._encoded.candidate_refs)):
            report = c.ExecutionReport('sts_execution_report_v1', 'rejected', 'none', 'invalid_action')
            return self._observation(), 0.0, False, False, self._info(report)
        try:
            report = self._dispatch(self._encoded.candidate_refs[int(action)])
            c.to_dict(report)
            if report.status == 'rejected':
                # Preserve the exact cached public decision, including on stale
                # rejection. No automatic refresh, substitute action or retry.
                return self._observation(), 0.0, False, False, self._info(report)
            if report.status != 'reconciled':
                raise EnvironmentFailure('dispatch_' + report.status)
            self._steps += 1
            self._refresh()
            reward, terminated, truncated = self._task_result()
            return self._observation(), reward, terminated, truncated, self._info(report)
        except BaseException as error:
            self._failed = True
            self._frame = None
            self._raise_failure(error, 'backend_step_failure')

    def _task_result(self):
        outcome = self._outcome
        return (float(outcome is not None and outcome.kind == 'victory'),
                outcome is not None and outcome.kind != 'truncated',
                outcome is not None and outcome.kind == 'truncated')

    def render(self):
        if self.render_mode != 'ansi' or self._encoded is None:
            return None
        if self._failed:
            raise EnvironmentFailure('reset_required_after_failure')
        if self._outcome is not None:
            return c.dumps(self._outcome)
        return self.encoder.contract.dumps(self._frame.decision)

    def close(self):
        self._adapter = self._frame = self._encoded = self._outcome = self._public_state = None
        self._done = True


class FullRunEnv(StsEnv):
    """Full campaign with ordinary HP, all characters and explicit cutoffs."""

    def __init__(self, *, character='ironclad', first_act='overgrowth', ascension=0,
                 max_decisions=4096, profile=None, engine_factory=None, **kwargs):
        from functools import partial
        from game.headless.run.engine import RunEngine
        from game.headless.run.ancient import PROFILE as ANCIENT_PROFILE
        from game.agent.encoding.full import FULL_RUN_PROFILE
        factory = engine_factory or partial(RunEngine.campaign, character=character,
                                            first_act=first_act, ascension=ascension,
                                            ancient_profile=ANCIENT_PROFILE)
        # Campaign's seed is keyword-only; the public environment factory takes
        # a positional seed just like the existing slice factory.
        if engine_factory is None:
            campaign = factory
            factory = lambda seed: campaign(seed=seed)
        super().__init__(engine_factory=factory, profile=profile or FULL_RUN_PROFILE,
                         max_decisions=max_decisions, stop_at_map=False,
                         decision_profile='full_run_v2', **kwargs)
