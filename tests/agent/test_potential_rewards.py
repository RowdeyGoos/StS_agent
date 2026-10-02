"""Potential shaping preserves combat utility and genuine cutoff continuation."""
from dataclasses import asdict, replace
import hashlib
import json
import math

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent import contracts as c
from game.agent.training.config import TrainingConfig
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.rewards import (RewardSpec, RewardError, POTENTIAL_SCHEMA,
    health_potentials, measure_combat)
from game.agent.training.records import CombatTrainingRecorder, load_training_episode
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.rollout import RolloutStep, advantages
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner
from game.agent.training.checkpoint import save_ppo_checkpoint, restore_ppo, load_policy
from game.agent.training.run_corpus import transfer_run_objective
from game.agent.training.learner import load_corpus
from .test_combat_training import fixture, act
from .test_training_records import record, metadata
from .test_training_model import cpu_threads


def shaped(gamma=1, enemy=.5, player=.25):
    return RewardSpec.potential_combat({'win_hp_fraction':.1,
        'enemy_hp_potential':enemy, 'player_hp_potential':player}, discount=gamma)


def phi(state, spec):
    enemy, player = health_potentials(state)
    w = dict(spec.weights)
    return w['enemy_hp_potential']*enemy + w['player_hp_potential']*player


def test_versioned_spec_roundtrip_gamma_and_legacy_identity():
    old = RewardSpec({'win_hp_fraction':.1})
    assert old.to_dict()=={'schema':'sts_training_reward_v1','weights':dict(old.weights)}
    spec = shaped(.9)
    assert spec.task=='combat' and spec.schema==POTENTIAL_SCHEMA
    assert spec==RewardSpec.loads(json.dumps(spec.to_dict()))
    assert spec.identity!=shaped(1).identity!=old.identity
    with pytest.raises(ValueError, match='discount.*gamma'):
        PPOExperiment(training=TrainingConfig(reward=spec))
    assert PPOExperiment(training=TrainingConfig(reward=spec),ppo=PPOConfig(gamma=.9)).training.reward==spec
    with pytest.raises(RewardError):
        RewardSpec(discount=1)


@pytest.mark.parametrize('discount',[None,0,-1,1.01,True,'1',float('inf'),float('nan')])
def test_invalid_discounts(discount):
    with pytest.raises(RewardError):
        shaped(discount)


@pytest.mark.parametrize('gamma',[1,.9])
@pytest.mark.parametrize('mode',['win','loss','cutoff'])
def test_terminal_and_cutoff_telescoping_and_offline_conversion(tmp_path,gamma,mode):
    spec=shaped(gamma);paths=record(tmp_path,mode=mode,spec=spec)
    episode=load_training_episode(*paths,split='train')
    plain=load_training_episode(*paths,split='train',reward_spec=RewardSpec({'win_hp_fraction':.1}))
    first=episode.transitions[0].transition.observation
    last=episode.transitions[-1].transition.successor
    terminal=episode.ending.terminated
    residual=math.fsum(gamma**i*(a.reward-b.reward) for i,(a,b) in enumerate(zip(episode.transitions,plain.transitions)))
    expected=-phi(first,spec)+(0 if terminal else gamma**len(episode.transitions)*phi(last,spec))
    assert residual==pytest.approx(expected)
    assert episode.trajectory.sha256==plain.trajectory.sha256
    assert all(t.reward==0 for t in episode.trajectory.transitions)
    if mode=='win':
        assert episode.trajectory.outcome.kind=='truncated' and terminal
        assert episode.ending.combat.hp==46  # Healing must not enter terminal Phi.
        assert residual==pytest.approx(.5-.25*.5)
    elif mode=='loss':
        assert residual>0  # Correct final compensation, never clamped away.
    else:
        assert not terminal and episode.ending.truncated
        assert residual!=pytest.approx(-phi(first,spec))
    oldpaths=record(tmp_path,mode=mode,spec=RewardSpec({'win_hp_fraction':.1}))
    upgraded=load_training_episode(*oldpaths,split='train',reward_spec=spec)
    assert [x.reward for x in upgraded.transitions]==[x.reward for x in episode.transitions]


def multi_record(tmp_path,spec):
    path=tmp_path/'multi.trajectory.jsonl'
    with CombatTrainingEnv(engine_factory=lambda seed:fixture(seed,cards=('strike','strike'),enemy_hp=18),
                           reward_spec=spec,max_decisions=32) as env:
        _,info=env.reset(seed=2)
        with CombatTrainingRecorder(path,metadata(),env.public_state,info['combat'],reward_spec=spec) as writer:
            for _ in range(32):
                actions=env.public_state.candidates
                choice=next((a for a in actions if a.kind=='play_card'),next(a for a in actions if a.kind=='end_turn'))
                _,reward,done,cut,info=env.step(env.action_index(choice))
                writer.append(choice,c.from_dict(info['execution']),env.public_state,combat_summary=info['combat'],
                              reward=reward,terminated=done,truncated=cut)
                if done or cut:break
            writer.finish(c.from_dict(info['outcome']),combat_summary=info['combat'],terminated=done,truncated=cut)
    return path,writer.path


@pytest.mark.parametrize('gamma',[1,.95])
def test_multistep_dense_signal_telescopes_and_imitation_uses_discount(tmp_path,gamma):
    spec=shaped(gamma);paths=multi_record(tmp_path,spec)
    ep=load_training_episode(*paths,split='train')
    base=load_training_episode(*paths,split='train',reward_spec=RewardSpec({'win_hp_fraction':.1}))
    assert ep.ending.terminated and len(ep.transitions)>=4
    assert any(s.reward>0 for s in ep.transitions[:-1])
    assert any(s.reward<0 for s in ep.transitions[:-1])
    assert math.fsum(gamma**i*(a.reward-b.reward) for i,(a,b) in enumerate(zip(ep.transitions,base.transitions)))==pytest.approx(
        -phi(ep.trajectory.initial,spec))
    corpus=load_corpus([paths],split='train')
    for i,example in enumerate(corpus.examples):
        expected=sum(gamma**j*t.reward for j,t in enumerate(ep.transitions[i:]))
        assert example.value_target==pytest.approx(expected)


@pytest.mark.parametrize('change',['component','reward','schema','discount'])
def test_forged_measurements_reject_even_when_reweighted(tmp_path,change):
    paths=record(tmp_path,mode='cutoff',spec=shaped())
    raw=json.loads(paths[1].read_text())
    if change=='component':raw['transitions'][0]['components']['enemy_hp_potential']+=.1
    if change=='reward':raw['transitions'][0]['reward']+=.1
    if change=='schema':raw['schema']='sts_combat_training_v1'
    if change=='discount':
        raw['reward_spec']['discount']=.9
        raw['reward_spec_id']=RewardSpec.from_dict(raw['reward_spec']).identity
    paths[1].write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_training_episode(*paths,split='train',reward_spec=RewardSpec())


def test_zero_potential_matches_original_rewards_and_rejection_is_rewardless(tmp_path,monkeypatch):
    paths=multi_record(tmp_path,shaped(enemy=0,player=0))
    a=load_training_episode(*paths,split='train')
    b=load_training_episode(*paths,split='train',reward_spec=RewardSpec({'win_hp_fraction':.1}))
    assert [s.reward for s in a.transitions]==[s.reward for s in b.transitions]
    with CombatTrainingEnv(engine_factory=fixture,reward_spec=shaped()) as env:
        env.reset(seed=1)
        public=env.public_state
        _,reward,done,cut,info=env.step(-1)
        assert reward==0 and info['training_reward'] is None and env.public_state is public
        monkeypatch.setattr(env,'_time_expired',lambda:True)
        _,reward,done,cut,info=env.step(0)
        assert reward==0 and not done and cut and info['training_reward'] is None
        assert env.public_state is public


def test_public_unknown_nested_context_and_dead_slots_have_declared_potential():
    with CombatTrainingEnv(engine_factory=fixture) as env:
        env.reset(seed=1);public=env.public_state
        assert health_potentials(public)==(-1.,.5)
        assert health_potentials(replace(public,context=replace(public.context,kind='relic_choice')))==(0.,0.)
        group=next(n for n in public.context.children if n.kind=='enemies');enemy=group.children[0]
        def with_enemies(children):
            return replace(public,context=replace(public.context,children=tuple(
                replace(n,children=children) if n is group else n for n in public.context.children)))
        unknown=replace(enemy,fields=tuple(replace(f,value=None) if f.key=='hp' else f for f in enemy.fields))
        assert health_potentials(with_enemies((unknown,)))==(0.,0.)
        dead=replace(enemy,ref='enemy:999',fields=tuple(replace(f,value=0) if f.key=='hp' else
             replace(f,value=False) if f.key=='alive' else f for f in enemy.fields))
        assert health_potentials(with_enemies((enemy,dead)))==(-.5,.5)


@pytest.mark.parametrize('terminal',[True,False])
def test_shaped_critic_coordinate_shift_cancels_in_gae_including_cutoff(terminal):
    gamma=.9;pot=[-.4,-.2,0 if terminal else -.1]
    base=[RolloutStep(None,(),(),0,-.5,.3,.6,0,{},False,False,'a',0),
          RolloutStep(None,(),(),0,-.5,.6,0 if terminal else .7,1 if terminal else 0,{},terminal,not terminal,'a',1)]
    shifted=[replace(s,value=s.value-pot[i],next_value=s.next_value-pot[i+1],
                     reward=s.reward+gamma*pot[i+1]-pot[i]) for i,s in enumerate(base)]
    adv,returns=advantages(base,gamma=gamma)
    new_adv,new_returns=advantages(shifted,gamma=gamma)
    assert torch.allclose(adv,new_adv,atol=1e-7)
    assert torch.allclose(returns-torch.tensor(pot[:-1]),new_returns,atol=1e-7)


def training_env(**settings):
    return CombatTrainingEnv(engine_factory=lambda seed:fixture(seed,cards=('strike','strike'),hp=10,enemy_hp=18),**settings)


@pytest.mark.parametrize('workers',[1,2])
def test_parallel_collection_checkpoint_resume_and_combat_objective_transfer(tmp_path,workers):
    cfg=PPOExperiment(training=TrainingConfig(reward=shaped()),
        ppo=PPOConfig(rollout_steps=16,episode_decisions=5,batch_size=8,epochs=1),
        encounters=('potential_test',),source='controlled_potential_test_v1')
    with training_env() as env:
        env.reset(seed=1);vocabulary=Vocabulary.fit([env.public_state],split='train')
    with PPOLearner(ActorCritic(vocabulary,Architecture(16,1),seed=8),cfg,seed=8,
                   env_factory=training_env,workers=workers) as owner:
        rollout=owner.collect(output_dir=tmp_path/'rollout',audit_dir=tmp_path/'rollout-private')
        assert len(rollout.steps)==16 and any(s.truncated for s in rollout.steps)
        for row in rollout.progress['episodes']:
            ep=load_training_episode(tmp_path/'rollout'/row['trajectory'],tmp_path/'rollout'/row['training'],split='train')
            assert ep.reward_spec==cfg.training.reward
        owner.update(rollout)
        bundle,resume=tmp_path/'checkpoint/model.sts-model',tmp_path/'checkpoint-private/model.resume.pt'
        save_ppo_checkpoint(bundle,owner,resume_path=resume)
        expected=owner.collect();owner.update(expected)
        tensors={k:v.clone() for k,v in owner.model.state_dict().items()}
    with restore_ppo(bundle,resume,experiment=cfg,env_factory=training_env,workers=workers) as restored:
        repeated=restored.collect()
        assert [(s.reward,s.value,s.next_value,s.action) for s in repeated.steps]==[(s.reward,s.value,s.next_value,s.action) for s in expected.steps]
        restored.update(repeated)
        assert all(torch.equal(tensors[k],v) for k,v in restored.model.state_dict().items())
    bad=replace(cfg,training=TrainingConfig(reward=shaped(enemy=.7)))
    with pytest.raises(ValueError):restore_ppo(bundle,resume,experiment=bad,env_factory=training_env,workers=workers)
    policy=load_policy(bundle,task='combat')
    model,info=transfer_run_objective(policy,RewardSpec(),seed=11)
    assert info['kind']=='combat_objective_transfer_v1'
    assert all(torch.equal(v,model.state_dict()[k]) for k,v in policy.model.state_dict().items() if not k.startswith('value.'))
    assert model.value[-1].weight.count_nonzero()==model.value[-1].bias.count_nonzero()==0
