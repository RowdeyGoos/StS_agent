"""Full campaign acceptance; controlled victories are labelled separately."""
import pytest

gym = pytest.importorskip('gymnasium')
np = pytest.importorskip('numpy')

from gymnasium.utils.env_checker import check_env
from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action
from game.agent.gym_env import FullRunEnv
from game.agent.headless import HeadlessAdapter
from game.headless.run.engine import RunEngine
from game.headless.run.state import RunPhase
from game.headless.run.actions import ContinueAct, ChooseEventOption


def test_full_gym_checker_reproducibility_independence_and_budget():
    with FullRunEnv(max_decisions=12) as a, FullRunEnv(max_decisions=12) as b:
        check_env(a, skip_render_check=True)
        oa, _ = a.reset(seed=42)
        ob, _ = b.reset(seed=42)
        assert all(np.array_equal(v, ob[k]) for k, v in oa.items())
        before = b._adapter._engine.snapshot()
        bad, reward, terminated, truncated, info = a.step(a.action_space.n - 1)
        assert info['execution']['status'] == 'rejected'
        assert all(np.array_equal(v, bad[k]) for k, v in oa.items())
        for _ in range(12):
            public = a.encoder.decode(oa)
            candidate = choose_action(public)
            oa, reward, terminated, truncated, info = a.step(public.candidates.index(candidate))
            assert reward == 0.0 and not terminated
        assert truncated and info['outcome']['reason'] == 'decision_budget'
        assert oa['action_mask'].any()
        assert b._adapter._engine.snapshot() == before


@pytest.mark.parametrize('character', ['ironclad', 'silent', 'regent', 'necrobinder', 'defect'])
@pytest.mark.parametrize('first_act', ['overgrowth', 'underdocks'])
@pytest.mark.parametrize('ascension', [0, 10])
def test_normal_hp_campaign_public_policy(character, first_act, ascension):
    with FullRunEnv(character=character, first_act=first_act, ascension=ascension, max_decisions=600) as env:
        obs, info = env.reset(seed=1)
        assert env.observation_space.contains(obs)
        total_reward, contexts = 0, set()
        for count in range(1, 601):
            public = env.encoder.decode(obs)
            assert isinstance(public, f.PublicDecision)
            assert public.run.get('character') == character
            assert public.run.get('ascension') == ascension
            contexts.add(public.context.kind)
            candidate = choose_action(public)
            index = public.candidates.index(candidate)
            assert obs['action_mask'][index] == 1
            obs, reward, terminated, truncated, info = env.step(index)
            assert info['execution']['status'] == 'reconciled'
            total_reward += reward
            if terminated or truncated:
                break
        assert env.observation_space.contains(obs)
        outcome = info['outcome']
        assert outcome and {'combat', 'map'} <= contexts
        assert (total_reward == 1.0) == (outcome['kind'] == 'victory')
        assert terminated == (outcome['kind'] != 'truncated')
        if outcome['kind'] == 'defeat':
            assert env._adapter._engine.state.hp == 0
        elif outcome['kind'] == 'truncated':
            assert outcome['reason'] == 'decision_budget' and count == 600
        print(f'{character}/{first_act}/A{ascension}: {outcome["kind"]}, {count} decisions')


@pytest.mark.parametrize('first_act,ascension', [('overgrowth', 0), ('underdocks', 10)])
def test_controlled_campaign_all_acts_second_boss_and_architect_reward(first_act, ascension):
    from tests.headless.test_act2_run import win
    from game.agent.encoding.full import FullRunEncoder
    run = RunEngine.campaign(seed=4, first_act=first_act, ascension=ascension)
    run.state.max_hp = run.state.hp = 10000  # Controlled route fixture, not natural policy success.
    encoder = FullRunEncoder()
    a = HeadlessAdapter(run, decision_profile=f.PROFILE)
    bosses, transitions = [], []
    for _ in range(650):
        frame = a.observe()
        if isinstance(frame, c.RunOutcome):
            pytest.fail('Architect must be completed through Gym for terminal reward validation')
        encoded = encoder.encode(frame.decision)
        public = encoder.decode(encoded.observation)
        if run.combat:
            if run.graph.node(run.state.current_node_id).kind == 'boss':
                bosses.append((run.state.act_index, run.state.active_encounter_id))
            win(run)
            # Controlled mutation explicitly ends adapter ownership. Reattach;
            # ordinary rollouts above always dispatch only through the adapter.
            a = HeadlessAdapter(run, decision_profile=f.PROFILE)
            continue
        if public.context.definition_id == 'the_architect':
            break
        if run.state.phase is RunPhase.ACT_COMPLETE:
            transitions.append(run.state.act_completion.act)
            assert [x.kind for x in public.candidates] == ['continue_act']
        chosen = choose_action(public)
        # Tensor refs are normalized; dispatch by the corresponding fixed slot.
        original_ref = encoded.candidate_refs[public.candidates.index(chosen)]
        assert a.step(frame.binding, original_ref).status == 'reconciled'
    else:
        pytest.fail('Controlled route did not reach Architect')
    assert transitions == [1, 2, 3]
    assert len([x for x in bosses if x[0] == 2]) == (2 if ascension == 10 else 1)
    with FullRunEnv(engine_factory=lambda seed: run) as env:
        obs, _ = env.reset(seed=0)
        public = env.encoder.decode(obs)
        assert public.context.definition_id == 'the_architect'
        chosen = choose_action(public)
        obs, reward, terminated, truncated, info = env.step(public.candidates.index(chosen))
        assert (reward, terminated, truncated) == (1.0, True, False)
        assert env.encoder.decode(obs) == c.RunOutcome('sts_run_outcome_v1', 'victory', 'none')
        assert not obs['action_mask'].any()
        assert info['outcome']['kind'] == 'victory'
