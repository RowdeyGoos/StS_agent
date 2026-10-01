"""Public reward inspection remains useful but cannot cycle indefinitely."""
from dataclasses import replace

import pytest

from game.agent.action_policy import (ALL_LEGAL, COMMIT_SINGLE_CARD,
    COMMIT_CARD_SELECTION, COMMIT_DECISIONS, action_mask)
from game.agent.contracts import full as f
from game.agent.headless import HeadlessAdapter
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.rewards import begin_combat_rewards
from .test_commit_selection import fury_run


def reward_run(seed=3, relics=()):
    run = RunEngine(seed=seed, config=RunConfig())
    for relic in relics:
        run.obtain_relic(relic)
    begin_combat_rewards(run.state, run.cards)
    return run


def attach(run):
    return HeadlessAdapter(run, decision_profile=f.PROFILE)


def step(adapter, kind, subject=None):
    frame = adapter.observe()
    action = next(a for a in frame.decision.candidates
                  if a.kind == kind and (subject is None or a.subject == subject))
    assert adapter.step(frame.binding, action.ref).status == 'reconciled'
    return adapter.observe().decision


def repeated(adapter, subject=None):
    step(adapter, 'open_reward', subject)
    step(adapter, 'close_reward')
    return step(adapter, 'open_reward', subject)


def permits_close(public):
    return any(a.kind == 'close_reward' and ok
               for a, ok in zip(public.candidates, action_mask(public, COMMIT_DECISIONS)))


def test_one_inspection_then_commit_preserves_native_graph_state_and_action_order():
    run = reward_run(); adapter = attach(run); before = run.snapshot()
    opened = step(adapter, 'open_reward')
    assert permits_close(opened)
    step(adapter, 'close_reward')
    reopened = step(adapter, 'open_reward')
    assert not permits_close(reopened)
    assert run.snapshot() == before
    mask = action_mask(reopened, COMMIT_DECISIONS)
    assert [a for a, ok in zip(reopened.candidates, mask) if ok] == [a for a in reopened.candidates if a.kind != 'close_reward']
    for old in (ALL_LEGAL, COMMIT_SINGLE_CARD, COMMIT_CARD_SELECTION):
        assert all(action_mask(reopened, old))
    # Native legality stays complete, even when the new policy excludes close.
    step(adapter, 'close_reward')
    again = step(adapter, 'open_reward')
    assert not permits_close(again)
    step(adapter, 'skip_reward')
    assert run.state.pending['card_resolved']


@pytest.mark.parametrize('order', [(0, 1), (1, 0)])
def test_inspect_both_rewards_before_resolving_them_in_either_order(order):
    adapter = attach(reward_run(relics=('prayer_wheel',)))
    refs = [a.subject for a in adapter.observe().decision.candidates if a.kind == 'open_reward']
    assert len(refs) == 2
    for ref in refs:
        assert permits_close(step(adapter, 'open_reward', ref))
        step(adapter, 'close_reward')
    public = step(adapter, 'open_reward', refs[order[0]])
    assert not permits_close(public)
    step(adapter, 'skip_reward')
    # The actual resolution changes reward refs and resets inspection allowance.
    assert permits_close(step(adapter, 'open_reward'))
    step(adapter, 'skip_reward')
    assert not any(a.kind == 'open_reward' for a in adapter.observe().decision.candidates)


@pytest.mark.parametrize('action', ['claim_gold', 'discard_potion', 'reroll_card_reward'])
def test_gameplay_resets_inspection_including_inventory_and_rerolls(action):
    from game.headless.run.inventory import add_potion
    run = reward_run(relics=('driftwood',))
    add_potion(run.state, 'block_potion')
    adapter = attach(run)
    assert not permits_close(repeated(adapter))
    if action != 'reroll_card_reward':
        # Execute native close to reach the inventory/claim control; legality
        # remains available to external callers outside the learned policy.
        step(adapter, 'close_reward')
    public = step(adapter, action)
    if action != 'reroll_card_reward':
        public = step(adapter, 'open_reward')
    assert permits_close(public)
    step(adapter, 'close_reward')
    assert not permits_close(step(adapter, 'open_reward'))


def test_reroll_and_sacrifice_remain_choices_when_close_is_blocked():
    adapter = attach(reward_run(relics=('driftwood', 'paels_wing')))
    public = repeated(adapter)
    kinds = {a.kind for a, ok in zip(public.candidates, action_mask(public, COMMIT_DECISIONS)) if ok}
    assert kinds == {'choose_reward_card', 'skip_reward', 'reroll_card_reward', 'sacrifice_card_reward'}
    step(adapter, 'sacrifice_card_reward')
    assert not any(a.kind == 'open_reward' for a in adapter.observe().decision.candidates)


def test_event_batch_uses_public_option_labels_and_retains_all_offers():
    from game.headless.run import events
    from game.headless.run.actions import ChooseEventOption
    run = RunEngine(seed=3, config=RunConfig())
    events.begin(run.state, 'colorful_philosophers', cards=run.cards)
    run.apply(next(a for a in run.legal_actions() if isinstance(a, ChooseEventOption)))
    adapter = attach(run)
    public = repeated(adapter)
    assert public.context.get('stage') == 'event_rewards' and not permits_close(public)
    assert all(ok for a, ok in zip(public.candidates, action_mask(public, COMMIT_DECISIONS)) if a.kind != 'close_reward')
    step(adapter, 'choose_event_option')


@pytest.mark.parametrize('change', ['no_history', 'partial_history', 'wrong_open', 'wrong_close',
    'targeted_navigation', 'gameplay_boundary', 'unknown_context', 'unknown_reward',
    'hidden_reward', 'resolved_reward', 'close_only', 'missing_skip', 'missing_offer',
    'wrong_subject', 'unknown_action'])
def test_incomplete_or_unknown_shapes_keep_legal_exits(change):
    public = repeated(attach(reward_run()))
    wire = f.to_dict(public)
    history = next(n for n in wire['run']['children'] if n['kind'] == 'history')
    if change == 'no_history': history['children'].clear()
    if change == 'partial_history': history['children'] = history['children'][-1:]
    if change == 'wrong_open': history['children'][-1]['links'][0]['targets'] = ['reward:999']
    if change == 'wrong_close': history['children'][-2]['links'][0]['targets'] = ['reward:999']
    if change == 'targeted_navigation': history['children'][-2]['links'][1]['targets'] = ['card:999']
    if change == 'gameplay_boundary': history['children'].insert(-1, {'kind':'history_event', 'definition_id':'claim_gold', 'ref':None, 'fields':[], 'links':[], 'children':[]})
    if change == 'unknown_context': wire['context']['kind'] = 'shop'
    close = next(a for a in wire['candidates'] if a['kind'] == 'close_reward')
    reward = next(n for n in wire['context']['children'] if n.get('ref') == close['subject'])
    if change == 'unknown_reward': reward['definition_id'] = 'future_reward'
    if change in ('hidden_reward', 'resolved_reward'):
        key, value = ('presentation', 'summary') if change == 'hidden_reward' else ('resolved', True)
        next(v for v in reward['fields'] if v['key'] == key)['value'] = value
    if change == 'close_only': wire['candidates'] = [close]
    if change == 'missing_skip': wire['candidates'] = [a for a in wire['candidates'] if a['kind'] != 'skip_reward']
    if change == 'missing_offer': wire['candidates'].pop(0)
    if change == 'wrong_subject': wire['candidates'][0]['subject'] = next(n['ref'] for n in wire['context']['children'] if n['kind'] == 'reward' and n['ref'] != close['subject'])
    if change == 'unknown_action': wire['candidates'].append({'ref':'action:999', 'kind':'abandon_run', 'subject':None, 'target':None})
    changed = f.from_dict(wire)
    assert all(action_mask(changed, COMMIT_DECISIONS))


def test_attachment_reference_renaming_permutation_and_card_commitment():
    run = reward_run(); adapter = attach(run)
    public = repeated(adapter)
    # Fresh attachments have no evidence of previous reward navigation.
    assert permits_close(step(attach(run), 'open_reward'))
    wire = f.to_dict(public)
    def rename(value):
        if type(value) is str and ':' in value and value.split(':')[0] in f.NAMESPACES + ('action',):
            prefix, ordinal = value.split(':'); return prefix + ':' + str(int(ordinal) + 100)
        if type(value) is list: return [rename(v) for v in value]
        if type(value) is dict: return {k:rename(v) for k,v in value.items()}
        return value
    wire = rename(wire); wire['candidates'].reverse()
    renamed = f.from_dict(wire)
    assert action_mask(renamed, COMMIT_DECISIONS) == tuple(reversed(action_mask(public, COMMIT_DECISIONS)))
    selected = step(attach(fury_run()), 'select_card')
    assert action_mask(selected, COMMIT_DECISIONS) == action_mask(selected, COMMIT_CARD_SELECTION)


def reward_env(*, encounter, reward_spec, **settings):
    from game.agent.training.run_task import FullRunTrainingEnv
    return FullRunTrainingEnv(reward_spec=reward_spec, engine_factory=reward_run, **settings)


@pytest.mark.parametrize('workers', [1, 2])
def test_reward_loop_mask_in_ppo_replay_checkpoint_and_exact_resume(tmp_path, workers):
    torch = pytest.importorskip('torch'); pytest.importorskip('gymnasium')
    from game.agent.recording import load_trajectory
    from game.agent.training.checkpoint import load_policy, save_ppo_checkpoint, restore_ppo
    from game.agent.training.features import Vocabulary
    from game.agent.training.model import ActorCritic, Architecture
    from game.agent.training.ppo import PPOLearner, replay_batch
    from game.agent.training.ppo_run import _rollout_record
    from .test_action_policy import experiment
    from .test_ppo import comparable
    torch.set_num_threads(1)
    exp = experiment(COMMIT_DECISIONS)
    exp = replace(exp, ppo=replace(exp.ppo, rollout_steps=8, episode_decisions=4))
    model = ActorCritic(Vocabulary(()), Architecture(8, 1), action_policy=COMMIT_DECISIONS)
    with torch.no_grad():
        for parameter in model.parameters(): parameter.zero_()
        for kind in ('open_reward', 'close_reward'):
            model.action.weight[f.ACTIONS.index(kind), 0] = 3
        model.scorer[0].weight[0, 8] = 1
        model.scorer[-1].weight[0, 0] = 100
    with PPOLearner(model, exp, env_factory=reward_env, workers=workers) as owner:
        rollout = owner.collect(output_dir=tmp_path/'records', audit_dir=tmp_path/'audit')
        filtered = [s for s in rollout.steps if not all(s.mask)]
        assert len(filtered) == 2
        for row in rollout.progress['episodes']:
            trace = load_trajectory(tmp_path/'records'/row['trajectory'], split='train')
            assert [t.action.kind for t in trace.transitions[:3]] == ['open_reward', 'close_reward', 'open_reward']
            assert trace.transitions[3].action.kind in ('choose_reward_card', 'skip_reward')
        batch = replay_batch(filtered, model.vocabulary, action_policy=COMMIT_DECISIONS)
        assert not batch['mask'].all()
        with pytest.raises(ValueError): replay_batch(filtered, model.vocabulary, action_policy=COMMIT_CARD_SELECTION)
        record = _rollout_record(rollout, exp)
        assert record['action_policy'] == COMMIT_DECISIONS
        assert all(all(s['legal_mask']) for s in record['steps'])
        assert [s['policy_mask'] for s in record['steps']] == [list(s.mask) for s in rollout.steps]
        owner.update(rollout)
        bundle, state = tmp_path/'saved/model.sts-model', tmp_path/'saved-private/model.resume.pt'
        save_ppo_checkpoint(bundle, owner, resume_path=state)
        loaded = load_policy(bundle)
        assert loaded.model.action_policy == COMMIT_DECISIONS
        assert loaded(trace.transitions[3].observation).kind != 'close_reward'
        with restore_ppo(bundle, state, env_factory=reward_env, workers=workers) as restored:
            assert comparable(owner.collect()) == comparable(restored.collect())
