"""Real-engine curriculum, frozen paired populations and development/test gates."""
from dataclasses import asdict, replace
import json
import math
from pathlib import Path
import threading

import pytest
torch=pytest.importorskip('torch')
pytest.importorskip('gymnasium')

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.headless.adapter import HeadlessAdapter
from game.agent.provenance import implementation
from game.agent.training import benchmark as b
from game.agent.training.benchmark_suite import (BenchmarkConfig, data, digest, freeze_suite,
                                                 load_registry, load_suite, snapshot_factory)
from game.agent.training.checkpoint import load_policy, save_checkpoint, save_ppo_checkpoint
from game.agent.training.comparison import choose, conclusion, interval, paired, summarize, summary
from game.agent.training.curriculum import STARTS, SOURCE, environment, start, training_names
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.learner import ImitationLearner
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.headless.run.snapshots import restore_run
from .test_training_model import cpu_threads, tiny_corpus


@pytest.mark.parametrize('item',STARTS,ids=lambda s:s.name)
def test_declared_start_is_native_owned_and_restores_independently(item):
    run=item.make(17)
    assert run.state.config.character=='ironclad' and run.state.config.ascension==0
    assert run.combat is not None and run.state.rng.native
    snapshot=run.snapshot()
    a,b=restore_run(snapshot),restore_run(snapshot)
    aa,bb=HeadlessAdapter(a,decision_profile=f.PROFILE),HeadlessAdapter(b,decision_profile=f.PROFILE)
    left,right=aa.observe(),bb.observe()
    assert left.decision==right.decision
    if item.prefix:
        assert any(n.kind=='selection' for n in f.walk(left.decision.context))
        assert any(x.kind in ('select_card','confirm_selection') for x in left.decision.candidates)
    action=left.decision.candidates[0]
    result=aa.step(left.binding,action.ref)
    assert result.status=='reconciled' and b.snapshot()==snapshot
    if item.campaign_combat:
        assert run.state.current_node_id and run.state.encounter_progression


def test_curriculum_excludes_test_combinations_and_exercises_selectors():
    assert len(training_names(0))==4 and len(training_names(4))==14
    with pytest.raises(ValueError):
        PPOExperiment(source=SOURCE,encounters=('transfer_choice_fuzzy',))
    with pytest.raises(ValueError):
        environment(encounter='transfer_choice_fuzzy')
    for name in ('armaments_choice','colorless_choice','gamblers_choice'):
        with environment(encounter=name) as env:
            env.reset(seed=0)
            choice=next(x for x in env.public_state.candidates if x.kind=='select_card')
            result=env.step(env.action_index(choice))
            assert result[4]['execution']['status']=='reconciled'


def row(case='a',group=None,*,policy='ppo',status='terminated',win=True,hp=40):
    return {'case_id':case,'source_group':group or case,'policy':policy,'status':status,
        'combat':{'outcome':'victory' if win else 'defeat','hp':hp,'max_hp':80,'turn':3},
        'start_hp':80,'end_hp':hp,'potion_use_actions':1,'task_return':float(win),'steps':3}


def test_grouped_bounds_and_planned_denominators():
    rows=[row('a','campaign'),row('b','campaign'),row('c',status='truncated'),
          row('d',status='failed'),row('e',status='unattempted')]
    result=summary(rows)
    assert result['planned']==5 and result['wins']==2 and result['win_rate']==.4
    assert (result['cutoffs'],result['failures'],result['unattempted'])==(1,1,1)
    expected=math.sqrt(math.log(40)*(4+1+1+1)/2)/5
    assert interval(.4,rows)==pytest.approx([max(0,.4-expected),min(1,.4+expected)])
    baseline=[dict(r,policy='heuristic',status='terminated',combat=dict(r['combat'],outcome='defeat')) for r in rows]
    assert paired(rows,baseline)['win_rate_difference']==.4
    assert paired(rows,baseline)['difference_group_hoeffding_95']==pytest.approx(
        [max(-1,.4-2*expected),min(1,.4+2*expected)])
    with pytest.raises(ValueError): paired(rows,baseline[:-1])


def test_development_choice_is_win_first_and_rejects_incomplete_or_test():
    names=('random_legal','heuristic','imitation','ppo_a','ppo_b','ppo_c')
    rows=[row(str(i),policy=name,win=(i==0 if name=='ppo_a' else True),hp=80 if name=='ppo_a' else 40)
          for i in range(2) for name in names]
    report={'split':'validation','status':'complete','episodes':rows,
            'policies':{n:{'algorithm':'ppo' if n.startswith('ppo') else n} for n in names},**summarize(rows,names)}
    assert choose(report)=='ppo_b'
    for key,value in (('split','test'),('status','failed')):
        with pytest.raises(ValueError): choose(dict(report,**{key:value}))
    assert conclusion(dict(report,split='test'),'ppo_b')=='inconclusive'


@pytest.fixture
def frozen(tmp_path):
    # Minimum stratified suite, two decisions per episode for bounded integration.
    path,_=freeze_suite(tmp_path/'suite',BenchmarkConfig(14,16,2,10.))
    path,value,private=load_suite(path)
    return path,value,private,load_registry(value,private)


def test_frozen_roots_are_grouped_disjoint_private_and_have_exact_snapshots(frozen):
    path,suite,private,registry=frozen
    assert private.stat().st_mode & 0o777==0o700
    assert all(p.stat().st_mode & 0o777==0o600 for p in private.iterdir())
    for split in ('validation','test'):
        cases=[c for c in suite['cases'] if c['split']==split and c['scenario'].startswith('campaign_')]
        assert len({c['source_group'] for c in cases})==1
        assert len({registry[c['case_id']]['reset_seed'] for c in cases})==1
        assert all(registry[c['case_id']]['encounter'].startswith('overgrowth_') for c in cases)
    roots=[registry[c['case_id']]['reset_seed'] for c in suite['cases'] if not c['scenario'].startswith('campaign_')]
    assert len(set(roots))==len(roots)
    case=next(c for c in suite['cases'] if c['scenario']=='colorless_choice')
    factory=snapshot_factory(case,registry,private)
    a,b=factory(1),factory(999)
    assert a is not b and a.snapshot()==b.snapshot()
    raw=json.loads(path.read_text())
    assert 'reset_seed' not in json.dumps(raw) and 'engine' not in raw
    raw['cases'][0]['scenario']='starter_fuzzy'
    with pytest.raises(ValueError): load_registry(raw,private)
    target=private/(case['case_id']+'.start.json')
    target.write_text('{}')
    with pytest.raises(ValueError,match='snapshot'): snapshot_factory(case,registry,private)


def bundles(tmp_path):
    from game.agent.training.model import ActorCritic,Architecture
    data_set=tiny_corpus()
    learner=ImitationLearner(ActorCritic(data_set.vocabulary,Architecture(16,1)),data_set)
    imitation=tmp_path/'bundles/imitation.sts-model'
    save_checkpoint(imitation,learner)
    result={'imitation':imitation}
    for seed in range(3):
        owner=PPOLearner(ActorCritic(data_set.vocabulary,Architecture(16,1),seed=seed),
                         PPOExperiment(ppo=PPOConfig(rollout_steps=1)),seed=seed)
        path=tmp_path/f'bundles/ppo-{seed}.sts-model'
        save_ppo_checkpoint(path,owner,resume_path=tmp_path/f'bundles-private/ppo-{seed}.resume.pt')
        result[f'ppo_{seed}']=path
    return result


def test_frozen_evaluation_and_selection_lock(frozen,tmp_path):
    path,suite,private,registry=frozen
    checkpoints=bundles(tmp_path)
    result_path,result=b.evaluate_benchmark(suite_path=path,output_dir=tmp_path/'dev',checkpoints=checkpoints)
    assert result['status']=='complete' and len(result['episodes'])==14*6
    assert all(r['status'] in ('terminated','truncated') for r in result['episodes'])
    selection,value=b.select_checkpoint(path,result_path,tmp_path/'selection.json')
    selected=value['selected']
    final_path,final=b.evaluate_benchmark(suite_path=path,output_dir=tmp_path/'test',split='test',selection_path=selection)
    assert final['status']=='complete' and len(final['episodes'])==16*4
    assert set(final['policies'])=={'random_legal','heuristic','imitation',selected}
    assert final['primary_conclusion'] in ('improved','worse','inconclusive')
    assert (path.parent/'test-opened.json').exists()
    with pytest.raises(ValueError,match='opened'): b.select_checkpoint(path,result_path,tmp_path/'second.json')
    with pytest.raises(ValueError,match='closed'):
        b.evaluate_benchmark(suite_path=path,output_dir=tmp_path/'dev-again',checkpoints=checkpoints)


def test_failure_keeps_all_planned_cases_and_cannot_select(frozen,tmp_path,monkeypatch):
    path,suite,private,registry=frozen
    def broken(*args): raise ValueError('controlled source corruption')
    monkeypatch.setattr(b,'snapshot_factory',broken)
    result_path,result=b.evaluate_benchmark(suite_path=path,output_dir=tmp_path/'failed',checkpoints=bundles(tmp_path))
    assert result['status']=='failed'
    assert result['summary']['random_legal']['planned']==14
    assert result['summary']['random_legal']['failures']==1
    assert result['summary']['heuristic']['unattempted']==14
    with pytest.raises(ValueError): b.select_checkpoint(path,result_path,tmp_path/'selection.json')


def test_concurrent_different_test_lock_cannot_open_snapshots(frozen,tmp_path,monkeypatch):
    path,suite,private,registry=frozen
    checkpoints=bundles(tmp_path)
    policies={name:{'identity':load_policy(bundle).identity,
                    'algorithm':load_policy(bundle).algorithm,'artifact':b._bound(bundle)}
              for name,bundle in checkpoints.items()}
    selection=tmp_path/'selection.json'
    selection.write_text('{}')
    monkeypatch.setattr(b,'_selection',lambda *_:{'selected':'ppo_0','policies':policies})
    original=b.load_registry
    def another_evaluation_wins(*args):
        result=original(*args)
        (path.parent/'test-opened.json').write_bytes(data({
            'schema':'sts_test_opened_v1','selection_sha256':'f'*64,'suite_sha256':digest(suite)}))
        return result
    monkeypatch.setattr(b,'load_registry',another_evaluation_wins)
    opened=[]
    monkeypatch.setattr(b,'snapshot_factory',lambda *args:opened.append(args))
    with pytest.raises(ValueError,match='another selection'):
        b.evaluate_benchmark(suite_path=path,output_dir=tmp_path/'racing-test',
                             split='test',selection_path=selection)
    assert not opened


def test_cancelled_benchmark_keeps_denominators(frozen,tmp_path):
    stop=threading.Event();stop.set()
    _,result=b.evaluate_benchmark(suite_path=frozen[0],output_dir=tmp_path/'cancelled',
                                 checkpoints=bundles(tmp_path),cancel=stop)
    assert result['status']=='interrupted'
    assert all(s['unattempted']==14 and s['win_rate']==0 for s in result['summary'].values())


def test_curriculum_command_owner_runs_all_stages_without_private_seed_leak(tmp_path):
    from game.agent.training.curriculum_run import CurriculumConfig,run_curriculum
    checkpoints=bundles(tmp_path)
    config=CurriculumConfig((1,1,1,1,1),PPOConfig(rollout_steps=1,batch_size=1,epochs=1),30.)
    path,report=run_curriculum(checkpoint=checkpoints['imitation'],config=config,
                               output_dir=tmp_path/'curriculum')
    assert report['status']=='complete' and len(report['replicates'])==3
    assert all(len(r['stages'])==5 and r['status']=='complete' for r in report['replicates'])
    assert all(load_policy(r['checkpoint']).algorithm=='ppo' for r in report['replicates'])
    public=path.read_text()
    assert '"seeds"' not in public and '"reset_seed"' not in public
    private=tmp_path/'curriculum-private'
    assert private.stat().st_mode & 0o777==0o700
    for state in private.rglob('*.resume.pt'):
        assert state.stat().st_mode & 0o777==0o600


def test_selection_checks_planned_population_and_recomputes_summary():
    from game.agent.training.benchmark_suite import protocol
    cases=[{'case_id':f'{i:032x}','source_group':f'{i:032x}','split':'validation','scenario':'starter_nibbit'} for i in range(4)]
    names=('random_legal','heuristic','imitation','ppo_1','ppo_2','ppo_3')
    suite={'cases':cases,'protocol':protocol(),'config':{}}
    rows=[dict(row(policy=name),**case) for case in cases for name in names]
    report={'schema':'sts_combat_comparison_v1','suite_sha256':digest(suite),'implementation':asdict(implementation()),
            'split':'validation','protocol':protocol(),'limits':{},'episodes':rows,
            'policies':{n:{'algorithm':'ppo' if n.startswith('ppo') else n} for n in names},**summarize(rows,names)}
    b._validate_development(report,suite)
    with pytest.raises(ValueError,match='planned'):
        b._validate_development(dict(report,episodes=rows[:-1]),suite)
    report['summary']['ppo_1']['wins']=1000
    with pytest.raises(ValueError,match='summary'):
        b._validate_development(report,suite)
