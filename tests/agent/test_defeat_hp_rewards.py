"""Terminal partial credit uses public final enemy health, never guessed HP."""
from dataclasses import asdict, replace
import json

import pytest

torch = pytest.importorskip('torch')
pytest.importorskip('gymnasium')
from game.agent import contracts as c
from game.agent.headless import AdapterFault, HeadlessAdapter
from game.agent.headless.combat_summary import CombatHealthSummary, EnemyHealth
from game.agent.training.config import TrainingConfig
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.rewards import (DEFEAT_HP_SCHEMA, DefeatHPRewardComponents,
    RewardSpec, RewardError, public_summary, measure_combat)
from game.agent.training.records import CombatTrainingRecorder, load_training_episode
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_run import _rollout_record
from game.agent.training.checkpoint import save_ppo_checkpoint, restore_ppo
from .test_combat_training import fixture, act
from .test_training_records import metadata, record
from .test_training_model import cpu_threads


def spec(weight=.5):
    return RewardSpec.defeat_hp_combat({'win_hp_fraction': .1, 'loss_enemy_damage_fraction': weight})


def test_spec_roundtrip_and_explicit_objective():
    value = spec()
    assert value.schema == DEFEAT_HP_SCHEMA and value.task == 'combat'
    assert value == RewardSpec.loads(json.dumps(value.to_dict()))
    assert value.identity != RewardSpec({'win_hp_fraction': .1}).identity
    assert value.identity != spec(.25).identity
    with pytest.raises(RewardError):
        RewardSpec({'loss_enemy_damage_fraction': .5})
    with pytest.raises(RewardError):
        RewardSpec(value.weights, value.schema, discount=1)


@pytest.mark.parametrize('remaining', [100, 50, 1])
@pytest.mark.parametrize('weight', [0, .25, .5])
def test_final_missing_health_on_defeat_including_continuation_starts(tmp_path, remaining, weight):
    run = fixture(3, hp=1, enemy_hp=100, relics=())
    run.combat.enemies[0].hp = remaining  # A continuation may already be damaged.
    snapshot = run.snapshot()
    path = tmp_path/'fight.trajectory.jsonl.gz'
    with CombatTrainingEnv(engine_factory=lambda seed: run, reward_spec=spec(weight)) as env:
        _, info = env.reset(seed=0)
        assert run.snapshot() == snapshot
        with CombatTrainingRecorder(path, metadata(), env.public_state, info['combat'], reward_spec=spec(weight)) as writer:
            choice = next(a for a in env.public_state.candidates if a.kind == 'end_turn')
            _, reward, done, cut, info = env.step(env.action_index(choice))
            assert done and not cut and reward == pytest.approx(weight*(1-remaining/100))
            assert info['combat']['enemies'] == ({'slot': 0, 'hp': remaining, 'max_hp': 100},)
            writer.append(choice, c.from_dict(info['execution']), env.public_state,
                          combat_summary=info['combat'], reward=reward, terminated=done, truncated=cut)
            writer.finish(c.from_dict(info['outcome']), combat_summary=info['combat'], terminated=done, truncated=cut)
    episode = load_training_episode(path, writer.path, split='train')
    assert episode.transitions[0].components.loss_enemy_damage_fraction == 1-remaining/100
    assert episode.transitions[0].reward == reward
    plain = load_training_episode(path, writer.path, split='train', reward_spec=RewardSpec())
    assert plain.transitions[0].reward == 0


@pytest.mark.parametrize('mode', ['win', 'loss', 'cutoff'])
def test_old_artifacts_remain_unchanged_and_missing_health_cannot_be_invented(tmp_path, mode):
    old = record(tmp_path, mode=mode, spec=RewardSpec({'win_hp_fraction': .1}))
    before = old[1].read_bytes()
    load_training_episode(*old, split='train')
    with pytest.raises(ValueError, match='summary schema|enemy health'):
        load_training_episode(*old, split='train', reward_spec=spec())
    assert old[1].read_bytes() == before
    new = record(tmp_path, mode=mode, spec=spec())
    episode = load_training_episode(*new, split='train')
    assert episode.transitions[0].components.loss_enemy_damage_fraction == 0
    if mode == 'win':
        assert episode.ending.combat.hp == 46
        assert episode.ending.combat.enemies[0].hp == 0
        assert episode.transitions[0].reward == 1+.1*46/80
    assert json.loads(new[1].read_text())['schema'] == 'sts_combat_training_v3'


def test_damage_on_a_nonterminal_action_is_not_paid_and_death_reads_the_successor():
    run = fixture(3, hp=1, enemy_hp=100, relics=())
    run.combat.enemies[0].hp = 7
    with CombatTrainingEnv(engine_factory=lambda seed: run, reward_spec=spec()) as env:
        env.reset(seed=0)
        _, reward, done, cut, _ = act(env, 'play_card')
        assert reward == 0 and not done and not cut
        _, reward, done, cut, info = act(env, 'end_turn')
        assert done and not cut and reward == .495
        assert info['combat']['enemies'][0]['hp'] == 1


@pytest.mark.parametrize('revival', ['fairy_in_a_bottle', 'lizard_tail'])
def test_revival_is_not_defeat_and_rejections_and_timeouts_never_pay(revival, monkeypatch):
    run = fixture(3, hp=1, enemy_hp=100, relics=(revival,) if revival == 'lizard_tail' else (),
                  potions=(revival,) if revival == 'fairy_in_a_bottle' else ())
    run.combat.enemies[0].hp = 1
    with CombatTrainingEnv(engine_factory=lambda seed: run, reward_spec=spec()) as env:
        env.reset(seed=0)
        before = env._adapter.combat_health_summary
        _, reward, done, cut, info = env.step(-1)
        assert reward == 0 and info['training_reward'] is None
        assert env._adapter.combat_health_summary is before
        _, reward, done, cut, info = act(env, 'end_turn')
        assert reward == 0 and not done and not cut and info['combat']['hp'] > 0
        monkeypatch.setattr(env, '_time_expired', lambda: True)
        _, reward, done, cut, info = env.step(0)
        assert reward == 0 and not done and cut and info['training_reward'] is None


def test_unknown_health_stays_unknown_without_breaking_legacy_profile():
    run = fixture(1, enemy_hp=100)
    run.combat.enemies[0].about_to_blow = True
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    state = run.snapshot()
    old = adapter.combat_summary
    assert old.schema == 'sts_combat_summary_v1' and 'enemies' not in asdict(old)
    health = public_summary(adapter.combat_health_summary)
    assert health.enemies == (EnemyHealth(0, None, None),) and run.snapshot() == state
    public = adapter.observe().decision
    chosen = next(a for a in public.candidates if a.kind == 'end_turn')
    with pytest.raises(RewardError, match='known finite'):
        measure_combat(spec(0), chosen, c.ExecutionReport('sts_execution_report_v1','reconciled','applied','none'),
                       health, health, public, public)
    adapter._faulted = True
    with pytest.raises(AdapterFault):
        _ = adapter.combat_health_summary
    with pytest.raises(ValueError, match='full_run_v2'):
        _ = HeadlessAdapter(fixture(1)).combat_health_summary


@pytest.mark.parametrize('change', ['component','hp','initial_hp','schema','extra','slot','unknown'])
def test_forged_sidecar_rejects_even_when_reweighting(tmp_path, change):
    paths = record(tmp_path, mode='loss', spec=spec())
    raw = json.loads(paths[1].read_text())
    if change == 'component': raw['transitions'][0]['components']['loss_enemy_damage_fraction'] = .1
    if change == 'hp': raw['transitions'][0]['combat']['enemies'][0]['hp'] -= 1
    if change == 'initial_hp': raw['initial_combat']['enemies'][0]['hp'] -= 1
    if change == 'schema': raw['schema'] = 'sts_combat_training_v1'
    if change == 'extra': raw['ending']['combat']['enemies'][0]['rng'] = 123
    if change == 'slot': raw['initial_combat']['enemies'][0]['slot'] = 1
    if change == 'unknown': raw['initial_combat']['enemies'][0]['hp'] = None
    paths[1].write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        load_training_episode(*paths, split='train', reward_spec=RewardSpec())


def test_multi_enemy_fraction_keeps_dead_slots_and_checks_scalar_types():
    with CombatTrainingEnv(engine_factory=fixture, reward_spec=spec()) as env:
        env.reset(seed=1);before = env._combat;public = env.public_state
        after = replace(before, outcome='defeat', hp=0,
                        enemies=(EnemyHealth(0,0,100), EnemyHealth(1,50,100)))
        chosen = next(a for a in public.candidates if a.kind == 'end_turn')
        result = measure_combat(spec(), chosen,c.ExecutionReport('sts_execution_report_v1','reconciled','applied','none'),
                                before,after,public,c.RunOutcome('sts_run_outcome_v1','defeat','none'))
        assert result.loss_enemy_damage_fraction == .75
        # Terminal RunOutcome has no enemy HUD: preserve known slots there too.
        full_before = replace(before, enemies=(EnemyHealth(0,100,100),EnemyHealth(1,50,100)))
        dropped = replace(after, enemies=(EnemyHealth(0,0,100),))
        with pytest.raises(RewardError, match='retain existing combat slots'):
            measure_combat(spec(),chosen,c.ExecutionReport('sts_execution_report_v1','reconciled','applied','none'),
                           full_before,dropped,public,c.RunOutcome('sts_run_outcome_v1','defeat','none'))
        for enemy in (EnemyHealth(True,1,100),EnemyHealth(0,True,100),EnemyHealth(0,1,0),EnemyHealth(0,-1,100)):
            with pytest.raises(RewardError):public_summary(replace(after,enemies=(enemy,)))
        with pytest.raises(RewardError):DefeatHPRewardComponents(1,0,.5,0,0,.1)


def training_env(**settings):
    return CombatTrainingEnv(engine_factory=lambda seed: fixture(seed,cards=('strike','strike'),hp=1,enemy_hp=18),**settings)


def test_parallel_checkpoint_resume_and_versioned_journal(tmp_path):
    cfg = PPOExperiment(training=TrainingConfig(reward=spec()),
        ppo=PPOConfig(rollout_steps=16,episode_decisions=5,batch_size=8,epochs=1),
        encounters=('defeat_hp_test',),source='controlled_defeat_hp_test_v1')
    with training_env() as env:
        env.reset(seed=1);vocabulary=Vocabulary.fit([env.public_state],split='train')
    with PPOLearner(ActorCritic(vocabulary,Architecture(16,1),seed=8),cfg,seed=8,
                   env_factory=training_env,workers=2) as owner:
        rollout = owner.collect(output_dir=tmp_path/'rollout',audit_dir=tmp_path/'rollout-private')
        assert any(s.components['loss_enemy_damage_fraction'] > 0 for s in rollout.steps)
        journal = _rollout_record(rollout,cfg)
        assert journal['schema']=='sts_ppo_rollout_v6' and journal['reward_spec']==spec().to_dict()
        for row in rollout.progress['episodes']:
            load_training_episode(tmp_path/'rollout'/row['trajectory'],tmp_path/'rollout'/row['training'],split='train')
        owner.update(rollout)
        bundle,resume=tmp_path/'checkpoint/model.sts-model',tmp_path/'checkpoint-private/model.resume.pt'
        save_ppo_checkpoint(bundle,owner,resume_path=resume)
        expected=owner.collect();owner.update(expected)
        tensors={k:v.clone() for k,v in owner.model.state_dict().items()}
    with restore_ppo(bundle,resume,experiment=cfg,env_factory=training_env,workers=2) as restored:
        repeated=restored.collect()
        assert [(s.reward,s.value,s.next_value,s.action) for s in repeated.steps]==[(s.reward,s.value,s.next_value,s.action) for s in expected.steps]
        restored.update(repeated)
        assert all(torch.equal(tensors[k],v) for k,v in restored.model.state_dict().items())
    with pytest.raises(ValueError):
        restore_ppo(bundle,resume,experiment=replace(cfg,training=TrainingConfig(reward=spec(.25))),
                    env_factory=training_env,workers=2)
