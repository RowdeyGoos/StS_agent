"""Information removals, history replay, paired statistics and study control."""
import copy
from dataclasses import replace
import gzip
import hashlib
import json
from pathlib import Path
import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')
from game.agent.contracts import full as f
from game.agent.training.study.history import PublicHistory
from game.agent.training.study.spec import FeatureSpec, StudyArchitecture, ARCHITECTURES, RICHNESS, channels
from game.agent.training.study.model import match_capacity, collate_study
from game.agent.training.study.run import schedule, rng_seed, CHUNKS, MILESTONES, load_config, SCHEMA
from game.agent.training.study.report import paired_interval, outcomes, compare, metrics, common_outcome_health
from game.agent.training.study.recording import write_history, read_history, collect_history
from game.agent.training.features import Vocabulary
from game.agent.recording import load_trajectory
from .test_feature_study import make, public, fields, edit, study_catalog
from .test_training_model import cpu_threads


def test_capacity_all_24_and_frozen_order_and_rng_streams():
    pairs = [(StudyArchitecture(8, a, FeatureSpec(r,i).to_dict(), study_catalog().to_dict()),
              Vocabulary(('one','two') if i else ())) for a in ARCHITECTURES for i in (True,False) for r in RICHNESS]
    target, matched = match_capacity(pairs)
    assert len(matched)==24 and target in (250000,500000,1000000,2000000)
    assert all(abs(p['total']-target)<=target*.05 for _,p in matched)
    assert all(p['embedding']==0 for (a,_),(_,p) in zip(pairs,matched) if not a.features['identities'])
    names = [str(i) for i in range(24)]
    order = schedule(names,[11,29,47])
    assert order == schedule(reversed(names),[11,29,47])
    assert len(order)==72 and all(sum(s==seed for _,s in order)==24 for seed in (11,29,47))
    assert len({rng_seed(11,s) for s in ('initialization','action-sampling','environment','minibatches')})==4
    assert CHUNKS[-1]==100000 and set(MILESTONES)-{0} <= set(CHUNKS)
    assert max(b-a for a,b in zip((0,*CHUNKS),CHUNKS)) <= 20000


def test_counter_guard_ignores_content_spelling_and_reads_relic_mechanics():
    p=public()
    card=next(n for n in f.walk(p.context) if n.kind=='card')
    renamed=edit(p,lambda n:replace(n,definition_id='one_two_punch') if n.ref==card.ref else n)
    a,b=PublicHistory(),PublicHistory()
    a.reset(p,opening=True,reveals=[]);b.reset(renamed,opening=True,reveals=[])
    assert a.counts==b.counts
    e=make().encoder()
    relic=f.Node('relic','throwing_axe','relic:99999')
    p=replace(p,run=replace(p.run,children=(*p.run.children,f.Node('relics','relics',children=(relic,)))))
    e.history.reset(p,opening=True,reveals=[])
    assert e.history.counts['plays'] is None
    catalog=dict(e.history.catalog);catalog['relic','renamed']=catalog['relic','throwing_axe']
    h=PublicHistory(catalog=catalog)
    h.reset(edit(p,lambda n:replace(n,definition_id='renamed') if n.ref==relic.ref else n),opening=True,reveals=[])
    assert h.counts==e.history.counts


def test_history_recency_missing_phase_and_export_detachment():
    p=public();h=make().encoder().history;h.reset(p,opening=True,reveals=[])
    saved=h.export(p)
    for index in range(4):
        action=next(a for a in p.candidates if a.kind=='end_turn')
        q=replace(p,context=fields(p.context,round=p.context.get('round')+1))
        h.observe(p,action,q,[]);p=q
    assert not saved['profiles']
    rows=next(iter(h.profiles.values()))
    assert len(rows)==3 and [r['round'] for r in rows]==sorted((r['round'] for r in rows),reverse=True)
    relic=f.Node('relic','paels_eye','relic:99999')
    p=replace(p,run=replace(p.run,children=(*p.run.children,f.Node('relics','relics',children=(relic,)))))
    h.reset(p,opening=True,reveals=[])
    q=replace(p,context=fields(p.context,round=p.context.get('round')+1))
    h.observe(p,next(a for a in p.candidates if a.kind=='end_turn'),q,[])
    assert next(iter(h.profiles.values()))[0]['phase_observed'] is None


def test_prefix_rebinds_attachment_history_but_compact_binding_stays_strict():
    p=public()
    history=f.Node('history','history',fields=(f.Field('coverage','attachment'),),
                   children=(f.Node('event','play_card'),))
    recorded=replace(p,run=replace(p.run,children=tuple(n for n in p.run.children if n.kind!='history')+(history,)))
    anchor=dict(opening=f.to_dict(recorded),opening_reveals=[],transitions=[])
    h=PublicHistory();h.restore(anchor,p)
    compact=h.export(p)
    PublicHistory().restore(compact,p)
    with pytest.raises(ValueError,match='endpoint changed'):
        PublicHistory().restore(compact,recorded)
    changed=edit(p,lambda n:fields(n,hp=1) if n.kind=='combat' else n)
    with pytest.raises(ValueError,match='does not end'):
        PublicHistory().restore(anchor,changed)
    native=edit(recorded,lambda n:fields(n,coverage='native') if n.kind=='history' else n)
    with pytest.raises(ValueError,match='does not end'):
        PublicHistory().restore(dict(anchor,opening=f.to_dict(native)),p)


def test_power_owned_selection_and_derived_completeness_removals():
    p=public()
    power=f.Node('power','strength','power:99999',fields=(f.Field('amount',3),))
    choice=f.Node('selection','exhaust',links=(f.Link('source',(power.ref,)),))
    p=replace(p,context=replace(p.context,children=(*p.context.children,power,choice)))
    q=edit(p,lambda n:replace(n,definition_id='upgrade') if n.kind=='selection' else n)
    e=make(spec=FeatureSpec(ablations=('powers',))).encoder()
    assert np.array_equal(e.encode(p).values,e.encode(q).values)
    for group in ('card','powers','items'):
        e=make(spec=FeatureSpec(ablations=(group,))).encoder()
        e.history.reset(p,opening=True,reveals=[])
        a=e.encode(p)
        e.history.counts=dict.fromkeys(e.history.counts,None)
        assert np.array_equal(a.values,e.encode(p).values)


def test_attachment_played_power_log_is_excluded_but_active_stacks_remain():
    p=public()
    card=replace(next(n for n in f.walk(p.context) if n.kind=='card'),ref='card:99999')
    card=replace(card,children=(*card.children,f.Node('enchantment','historical_enchantment')))
    log=f.Node('pile','powers',fields=(f.Field('count',1),f.Field('coverage','observed_plays')),children=(card,))
    q=replace(p,context=replace(p.context,children=tuple(n for n in p.context.children
        if not(n.kind=='pile' and n.definition_id=='powers'))+(log,)))
    anchor=dict(opening=f.to_dict(q),opening_reveals=[],transitions=[])
    h=PublicHistory();h.restore(anchor,p)
    assert h.counts['plays']==0
    compact=h.export(p)
    with pytest.raises(ValueError,match='endpoint changed'):
        PublicHistory().restore(compact,q)
    native=edit(q,lambda n:fields(n,coverage='native') if n.kind=='pile' and n.definition_id=='powers' else n)
    with pytest.raises(ValueError,match='does not end'):
        PublicHistory().restore(dict(anchor,opening=f.to_dict(native)),p)
    for richness in RICHNESS:
        for kind in ARCHITECTURES:
            model=make(kind,spec=FeatureSpec(richness=richness));model.eval();e=model.encoder()
            e.history.reset(p,opening=True,reveals=[]);a=e.encode(p)
            e.history.reset(q,opening=True,reveals=[]);b=e.encode(q)
            assert e.history.counts['plays']==0
            assert np.array_equal(a.values,b.values) and np.array_equal(a.candidates,b.candidates)
            left=model(collate_study([a],model.vocabulary));right=model(collate_study([b],model.vocabulary))
            assert all(torch.equal(x,y) for x,y in zip(left,right))
    active=f.Node('powers','powers',children=(f.Node('power','strength',fields=(f.Field('amount',3),)),))
    changed=replace(p,context=replace(p.context,children=(*p.context.children,active)))
    e=make().encoder()
    assert not np.array_equal(e.encode(p).values,e.encode(changed).values)
    with pytest.raises(ValueError,match='does not end'):
        PublicHistory().restore(anchor,changed)
    selection=f.Node('selection','exhaust',links=(f.Link('source',(card.ref,)),))
    bad=replace(q,context=replace(q.context,children=(*q.context.children,selection)))
    with pytest.raises(ValueError,match='Historical played-card'):
        e.encode(bad)


def test_history_context_and_threat_removals_keep_parent_dimensions():
    p=public()
    for group in ('enemy_history','turn_context','threat'):
        e=make(spec=FeatureSpec(ablations=(group,))).encoder()
        e.history.reset(p,opening=True,reveals=[])
        a=e.encode(p)
        if group=='enemy_history':
            for enemy in [n for n in f.walk(p.context) if n.kind=='enemy']:
                e.history.profiles[enemy.get('slot')]=[dict(present=True,damage=900,hits=7,icons=['attack'],round=e.history.round-1,phase_observed=True)]
            b=e.encode(p)
        elif group=='turn_context':
            e.history.counts=dict.fromkeys(e.history.counts,999)
            b=e.encode(p)
        else:
            b=e.encode(p)
            assert all(np.count_nonzero(a.values[:,i])==0 for i,(family,_) in enumerate(channels('context')) if family=='threat')
        assert np.array_equal(a.values,b.values)
        assert a.values.shape[1]==len(channels('context'))


def test_richness_nested_and_offered_choice_reaches_actor_and_critic():
    p=public(); representations={}
    for richness in RICHNESS:
        e=make(spec=FeatureSpec(richness=richness)).encoder();e.history.reset(p,opening=True,reveals=[])
        value=e.encode(p)
        # The shared player row and each keyed entity carry equal basic facts.
        representations[richness]=(e,value)
    basic_e,basic=representations['basic']
    for e,value in representations.values():
        for _,name in channels('basic'):
            assert value.values[0,e.indexes[name]]==basic.values[0,basic_e.indexes[name]]
    card=next(n for n in f.walk(p.context) if n.kind=='card')
    offered=replace(card,ref='card:99999')
    p=replace(p,context=replace(p.context,children=(*p.context.children,f.Node('pile','offered',fields=(f.Field('count',1),),children=(offered,)))))
    q=edit(p,lambda n:fields(n,energy=99) if n.ref==offered.ref else n)
    for kind in ARCHITECTURES:
        model=make(kind);model.eval();e=model.encoder()
        a=model(collate_study([e.encode(p)],model.vocabulary))
        b=model(collate_study([e.encode(q)],model.vocabulary))
        assert not torch.equal(a[0],b[0]) and not torch.equal(a[1],b[1])


def test_paired_statistics_keep_repeats_and_campaigns_out_of_fight_count():
    rows=[dict(combat_id=fight,source_group='same_campaign',policy='p',mode='sampled',combat={'outcome':outcome})
          for fight,outcome in [('a','victory'),('a','defeat'),('b','victory'),('b','victory')]]
    assert outcomes({'episodes':rows})=={'a':.5,'b':1.}
    a={s:{'a':1.,'b':1.} for s in (11,29,47)}
    b={s:{'a':0.,'b':0.} for s in (11,29,47)}
    result=compare(a,b,confidence=1-.05/3)
    assert result['mean']==1 and result['interval']==[1.,1.] and result['fights']==2


def test_common_outcome_health_excludes_unpaired_wins_and_averages_repeats():
    def report(hp, outcomes):
        return dict(episodes=[dict(combat_id=fight,mode='sampled',repeat=repeat,status='terminated',
            boss_hp=0 if outcome=='victory' else hp,
            combat=dict(outcome=outcome,hp=hp,max_hp=100))
            for fight,repeat,outcome in outcomes])
    left=report(30,[('a',0,'victory'),('a',1,'victory'),('b',0,'victory'),('c',0,'defeat')])
    right=report(20,[('a',0,'victory'),('a',1,'victory'),('b',0,'defeat'),('c',0,'defeat')])
    result=common_outcome_health({s:left for s in (11,29,47)},{s:right for s in (11,29,47)})
    wins=result['winning_player_hp']
    assert wins['mean']==10 and wins['source_fights']==1 and wins['seed_fight_pairs']==3
    assert wins['paired_repetitions']==6 and wins['interval']==[10.,10.]
    assert result['common_failure_boss_hp']['mean']==10


def test_printed_fallbacks_preserve_bash_status_and_block_based_damage():
    from game.agent.training.study.projection import _card_effect
    spec=f.Node('spec','bash',fields=(f.Field('applies_status_name','vulnerable'),f.Field('applies_status_stacks',2)))
    effect=_card_effect(f.Node('effect','ApplyTargetStatus'),0,spec)
    assert effect['status']=='vulnerable' and effect['amount']==2
    spec=f.Node('spec','body_slam',fields=(f.Field('base_damage',0),f.Field('damage_equals_player_block',True)))
    effect=_card_effect(f.Node('effect','DealDamage'),0,spec)
    assert effect['expression']=='block' and effect['factor']==1 and effect['hits']==1


def test_displayed_threat_does_not_resolve_damage_prevention():
    p=public();e=make().encoder()
    a=e.encode(p)
    protection=f.Node('powers','powers',children=(f.Node('power','intangible',fields=(f.Field('amount',1),)),))
    q=replace(p,context=replace(p.context,children=(*p.context.children,protection)))
    b=e.encode(q)
    columns=[i for i,(group,_) in enumerate(channels('context')) if group=='threat']
    assert np.array_equal(a.values[0,columns],b.values[0,columns])
    assert a.values[0,e.indexes['power.intangible.scaled']] != b.values[0,e.indexes['power.intangible.scaled']]


def test_study_parallel_exact_resume_preserves_weights_and_rng(tmp_path):
    from game.agent.training.ppo import PPOLearner
    from game.agent.training.ppo_config import PPOConfig,PPOExperiment
    from game.agent.training.config import TrainingConfig
    from game.agent.training.checkpoint import save_ppo_checkpoint,restore_ppo
    from .test_ppo import controlled_env,comparable
    from .test_ppo_parallel import child_pids
    config=PPOExperiment(TrainingConfig(action_policy='commit_decisions_v1'),
        PPOConfig(rollout_steps=8,batch_size=4,epochs=1),('strike_or_die',),'controlled_study_parallel_v1',
        'sts_ppo_experiment_v2')
    before=child_pids()
    with PPOLearner(make(),config,seed=19,env_factory=controlled_env,workers=2) as learner:
        learner.update(learner.collect())
        checkpoint,state=tmp_path/'public/model.sts-model',tmp_path/'private/model.resume.pt'
        save_ppo_checkpoint(checkpoint,learner,resume_path=state)
        with restore_ppo(checkpoint,state,env_factory=controlled_env) as restored:
            a,b=learner.collect(),restored.collect()
            assert comparable(a)==comparable(b)
            learner.update(a);restored.update(b)
            assert all(torch.equal(v,restored.model.state_dict()[k]) for k,v in learner.model.state_dict().items())
            assert torch.equal(learner.action_generator.get_state(),restored.action_generator.get_state())
            assert torch.equal(learner.update_generator.get_state(),restored.update_generator.get_state())
    assert child_pids()==before


def test_public_history_artifact_binding_and_optional_analysis_dependency(tmp_path):
    from .test_analysis import record
    path=record(tmp_path/'input',start=public());trajectory=load_trajectory(path)
    h=PublicHistory();h.reset(trajectory.initial,opening=True,reveals=[])
    rows=[h.export(trajectory.initial)]
    sha=write_history(path.parent,trajectory.metadata.episode_id,trajectory.sha256,rows)
    supplement=path.with_name(trajectory.metadata.episode_id+'.public-history.json.gz')
    assert read_history(supplement,trajectory,sha)==json.loads(json.dumps(rows))
    tampered=json.loads(gzip.decompress(supplement.read_bytes()));tampered['records'][0]['counts']['plays']=99
    supplement.write_bytes(gzip.compress(json.dumps(tampered).encode()))
    with pytest.raises(ValueError,match='changed'):
        read_history(supplement,trajectory,sha)


def test_heldout_reservation_closes_cached_train_and_never_retries(tmp_path,monkeypatch):
    from game.agent.training.study import source as module
    owner=tmp_path/'owner';owner.mkdir();(owner/'corpus.json').write_text('{}')
    source=object.__new__(module.StudySource)
    source.reservation=None;source.identity='test-source';source.report={'owner':str(owner/'corpus.json')}
    source.cases={str(i):dict(case_id=str(i),split='test',start_kind='opening') for i in range(57)}
    checkpoint=tmp_path/'model';checkpoint.write_bytes(b'controlled mock checkpoint')
    policies={'heuristic':{'kind':'heuristic'},'random_legal':{'kind':'random_legal'}}
    for kind in ('identity','no_vocabulary'):
        for seed in (11,29,47):
            policies[f'{kind}-{seed}']=dict(checkpoint=str(checkpoint),sha256=module._sha_file(checkpoint),
                                            learner_seed=seed,configuration_id=kind)
    reservation=tmp_path/'reservation.json';output=tmp_path/'test'
    binding=module.reserve_test(source,reservation,policies=policies,manifest_sha256='f'*64,
        limits=dict(max_decisions=512,time_limit_seconds=120.),execution_output=output)
    with pytest.raises(ValueError,match='closed'):
        source.restore('unused',split='train')
    source.reservation=str(reservation);source.binding=binding;source.private=owner
    source.registry={k:dict(case=row,snapshot_sha256='a'*64) for k,row in source.cases.items()}
    output.mkdir();(output/'plan.json').write_text('{}')
    calls=[]
    monkeypatch.setattr(module,'_state',lambda *args:(calls.append(args) or 'mock state',))
    assert source.restore_test('0',policy='identity-11',mode='greedy',repeat=0)=='mock state'
    with pytest.raises(FileExistsError):
        source.restore_test('0',policy='identity-11',mode='greedy',repeat=0)
    assert len(calls)==1
    with pytest.raises(ValueError,match='Unregistered'):
        source.restore_test('0',policy='unregistered',mode='greedy',repeat=0)


def test_native_study_evaluation_records_settled_health_and_verified_history(tmp_path):
    from dataclasses import asdict
    from game.agent.provenance import implementation
    from game.agent.training.checkpoint import save_ppo_checkpoint,load_policy
    from game.agent.training.ppo import PPOLearner
    from game.agent.training.ppo_config import PPOExperiment,PPOConfig
    from game.agent.training.config import TrainingConfig
    from game.agent.training.evaluation import _episode,BaselineCase
    from game.agent.training.study.evaluate import StudyPolicy
    from game.agent.training.rewards import RewardSpec
    from game.agent.training.scenarios import scenario
    from game.agent.analysis.report import build_report
    from game.agent.analysis.server import AnalysisStore
    from game.agent.runner import prepare_directories
    objective=RewardSpec({'combat_win':1.,'win_hp_fraction':.1})
    config=TrainingConfig(reward=objective,action_policy='commit_decisions_v1')
    experiment=PPOExperiment(config,PPOConfig(rollout_steps=4),schema='sts_ppo_experiment_v2')
    checkpoint=tmp_path/'model/model.sts-model'
    with PPOLearner(make(),experiment) as learner:
        save_ppo_checkpoint(checkpoint,learner,resume_path=tmp_path/'model-private/state.pt')
    policy=load_policy(checkpoint)
    public_dir,private=prepare_directories(tmp_path/'public',tmp_path/'private')
    result=_episode(BaselineCase('overgrowth_nibbit','validation',11,47,4,30.),'controlled',
        replace(implementation(),policy=policy.identity),public_dir,private,config,
        chooser=StudyPolicy(policy,mode='greedy',seed=47),public_health=True,
        planning_start=lambda p:dict(opening=f.to_dict(p),opening_reveals=None,transitions=[]))
    assert result['status'] in ('terminated','truncated'),result
    assert result['settled_public_health']['enemies']
    assert result['trajectory'].endswith('.gz') and result['public_history_sha256']
    (public_dir/'evaluation.json').write_text(json.dumps(dict(schema='sts_feature_study_evaluation_v1',episodes=[result])))
    build_report([public_dir],tmp_path/'inspector')
    store=AnalysisStore(tmp_path/'inspector')
    assert store.decision(result['episode_id'],0)['public_history_verified']


def test_report_and_mlflow_keep_collected_steps_and_idempotent_points(tmp_path):
    pytest.importorskip('mlflow')
    from game.agent.training.study.report import build_report
    from game.agent.tracking.store import TrackingStore
    from dataclasses import asdict
    model=make();name='graph-mechanical-context'
    configuration=dict(architecture=asdict(model.architecture),vocabulary=model.vocabulary.to_dict(),
                       parameters=dict(total=1000,embedding=0,trunk=1000))
    def write(path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value));return str(path)
    write(tmp_path/'manifest.json',dict(configuration=dict(seeds=[11,29,47])))
    evaluations={}
    for step in ('0','100000','sampled','training'):
        row=dict(combat_id='fight',policy=name,mode='sampled' if step=='sampled' else 'greedy',repeat=0,
            combat=dict(outcome='defeat' if step=='0' else 'victory',hp=20,max_hp=100),
            status='terminated',steps=8,boss_hp=10 if step=='0' else 0,inference_seconds=.1)
        evaluations[step]=write(tmp_path/(step+'.json'),dict(episodes=[row],seconds=1.))
    ppo=write(tmp_path/'ppo.json',dict(summary=dict(accepted_decisions=8,trained_decisions=0,
        skipped_decisions=8,skipped_updates=1,wins=0,episode_attempts=1),total_seconds=1.,peak_process_rss_bytes=1000,
        iterations=[dict(iteration=0,collection=dict(steps=8,seconds=.5,episodes=[dict(steps=8,task_return=0)]),
            update=dict(decisions=0,mean_update={'entropy':.3}))]))
    write(tmp_path/'learners'/name/'11'/'learner.json',dict(configuration_id=name,configuration=configuration,
        seed=11,evaluations=evaluations,reports=[ppo],checkpoint='synthetic_test_fixture',checkpoint_sha256='a'*64))
    for _ in range(2):
        report=build_report(tmp_path)
        assert report['status']=='in_progress' and report['collected_decisions']==8
        assert report['results'][name][0]['learning']['skipped_decisions']==8
    with TrackingStore(tmp_path/'mlflow',experiment='Vantom feature study') as store:
        run=next(r for r in store.client.search_runs([store.experiment_id]) if r.data.tags['sts.kind']=='feature_study')
        assert len(store.client.get_metric_history(run.info.run_id,'development/greedy_win_rate'))==2
        points=store.client.get_metric_history(run.info.run_id,'ppo/entropy')
        assert len(points)==1 and points[0].step==8


def test_inspector_examples_copy_only_validated_public_siblings(tmp_path):
    from game.agent.training.study.report import inspector_examples
    from game.agent.analysis.server import AnalysisStore
    from .test_analysis import record
    output=tmp_path/'study';output.mkdir()
    (output/'selection.json').write_text(json.dumps(dict(winners=dict(identity='ids',no_vocabulary='mechanics'))))
    learners=[]
    for index,name in enumerate(('ids','mechanics')):
        evaluations={}
        for j,step in enumerate(('0','100000')):
            folder=tmp_path/name/step;episode=f'{index*2+j+1:032x}'
            path=record(folder,episode=episode,start=public());trajectory=load_trajectory(path)
            compressed=path.with_suffix(path.suffix+'.gz')
            compressed.write_bytes(gzip.compress(path.read_bytes(),mtime=0));path.unlink()
            h=PublicHistory();h.reset(trajectory.initial,opening=True,reveals=[])
            sha=write_history(folder,episode,trajectory.sha256,[h.export(trajectory.initial)])
            row=dict(case_id='a'*32,episode_id=episode,trajectory=compressed.name,public_history_sha256=sha)
            report=folder/'evaluation.json';report.write_text(json.dumps(dict(episodes=[row])))
            evaluations[step]=str(report)
        learners.append(dict(configuration_id=name,seed=11,evaluations=evaluations,
            checkpoint=str(tmp_path/name/'11/training/100000/final.sts-model')))
    result=inspector_examples(output,learners)
    assert len(result['examples'])==4
    store=AnalysisStore(Path(result['directory']))
    assert all(store.decision(r['episode_id'],0)['public_history_verified'] for r in result['examples'])
    unsafe=tmp_path/'unsafe';unsafe.mkdir()
    (unsafe/'selection.json').write_bytes((output/'selection.json').read_bytes())
    report=Path(learners[0]['evaluations']['0']);value=json.loads(report.read_text())
    secret=tmp_path/'source-private'/'secret.json';secret.parent.mkdir();secret.write_bytes(b'private test sentinel')
    value['episodes'][0]['trajectory']=str(secret);report.write_text(json.dumps(value))
    with pytest.raises(ValueError,match='basename'):
        inspector_examples(unsafe,learners)
    assert not list((unsafe/'inspector-public-sources').iterdir())
