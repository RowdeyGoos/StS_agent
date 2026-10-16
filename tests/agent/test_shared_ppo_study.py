"""Shared PPO recipes, legacy identity, bounded updates and paired selection."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
from pathlib import Path
import zipfile

import pytest

torch = pytest.importorskip('torch')
from game.agent.training.checkpoint import save_ppo_checkpoint, restore_ppo
from game.agent.training.config import TrainingConfig
from game.agent.training.features import Vocabulary
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_config import PPOConfig, PPOExperiment
from game.agent.training.study import hyperparameters as h
from game.agent.training.study.projection import study_catalog
from game.agent.training.study.spec import StudyArchitecture, FeatureSpec
from .test_ppo import controlled_env, comparable, owner
from .test_training_model import cpu_threads


def commit_owner(config, workers=1, env_factory=controlled_env):
    with owner() as old:
        vocabulary = old.model.vocabulary
        experiment = replace(old.experiment, training=replace(old.experiment.training,action_policy='commit_decisions_v1'),
            ppo=config, schema='sts_ppo_experiment_v3' if config.kl_check=='minibatch_v1' else 'sts_ppo_experiment_v2')
    return PPOLearner(ActorCritic(vocabulary,Architecture(16,1),seed=13,action_policy='commit_decisions_v1'),
        experiment, seed=23, env_factory=env_factory, workers=workers)


def config():
    return h.load_config(Path(__file__).parents[2]/'configs/training/vantom_shared_ppo_study.json')


def parent():
    c=config()
    rows={}
    for name in c['calibration_models']+c['transfer_models']:
        name=name.replace('compact_pooled_mlp','pooled_mlp')
        kind,identity,richness=name.rsplit('-',2)
        a=StudyArchitecture(16,kind,FeatureSpec(richness=richness,identities=identity=='ids').to_dict(),study_catalog().to_dict())
        rows[name]=dict(architecture=asdict(a),vocabulary=Vocabulary(('strike',) if identity=='ids' else ()).to_dict())
    experiment=PPOExperiment(training=TrainingConfig(action_policy='commit_decisions_v1'),
        ppo=PPOConfig(rollout_steps=4096,episode_decisions=512,episode_seconds=120.,batch_size=16,epochs=2),schema='sts_ppo_experiment_v2')
    return dict(configurations=rows,ppo=experiment.to_dict())


def test_old_serialization_and_new_kl_semantics_are_separately_bound():
    old=PPOExperiment().to_dict()
    assert 'kl_check' not in old['ppo']
    assert PPOExperiment.from_dict(old).to_dict()==old
    legacy=parent()['ppo']
    assert PPOExperiment.from_dict(legacy).to_dict()==legacy
    new=deepcopy(legacy); new['schema']='sts_ppo_experiment_v3';new['ppo']['kl_check']='minibatch_v1'
    updated=PPOExperiment.from_dict(new)
    assert updated.to_dict()==new and updated.identity!=PPOExperiment.from_dict(legacy).identity
    for bad in [dict(new,schema='sts_ppo_experiment_v2'),dict(legacy,schema='sts_ppo_experiment_v3')]:
        with pytest.raises(ValueError):PPOExperiment.from_dict(bad)
    with pytest.raises(ValueError):PPOConfig(kl_check='unchecked')
    with pytest.raises(ValueError):PPOExperiment(ppo=PPOConfig(kl_check='minibatch_v1'))


def test_minibatch_guard_stops_before_additional_steps_and_keeps_full_measurement():
    settings=PPOConfig(rollout_steps=32,batch_size=4,epochs=3,learning_rate=.05,target_kl=.000001,kl_check='minibatch_v1')
    with commit_owner(settings) as learner:
        update=learner.update(learner.collect())
        assert update['kl_stop_at']=='minibatch' and update['kl_early_stop']
        assert 0<update['optimizer_steps']<8
        assert update['kl_minibatch_checks']==update['optimizer_steps']+1
        assert update['max_minibatch_kl']>settings.target_kl
        assert update['optimizer_unique_decisions']==update['optimizer_decision_visits']==update['optimizer_steps']*4
        assert update['kl_unvisited_decisions']==32-update['optimizer_unique_decisions']
        assert set(update['after']) >= {'approx_kl','entropy','clip_fraction','value_mse'}
    with commit_owner(replace(settings,kl_check='epoch_v1')) as legacy:
        update=legacy.update(legacy.collect())
        assert update['optimizer_steps']>=8 and update['kl_minibatch_checks']==0
        assert update['optimizer_unique_decisions']==32 and update['kl_unvisited_decisions']==0
        assert update['optimizer_decision_visits']==update['optimizer_steps']*4


def test_full_updates_count_unique_decisions_and_repeated_visits():
    with commit_owner(PPOConfig(rollout_steps=16,batch_size=4,epochs=2,target_kl=100.,kl_check='minibatch_v1')) as learner:
        update=learner.update(learner.collect())
        assert update['optimizer_unique_decisions']==16
        assert update['optimizer_decision_visits']==32 and update['kl_unvisited_decisions']==0


def test_zero_signal_has_no_optimizer_coverage_and_is_not_a_kl_discard():
    from .test_ppo import long_env
    from .test_ppo_no_signal import constant_critic
    with commit_owner(PPOConfig(rollout_steps=4,episode_decisions=1,batch_size=2,kl_check='minibatch_v1'),env_factory=long_env) as learner:
        constant_critic(learner)
        update=learner.update(learner.collect())
        assert update['status']=='skipped'
        assert update['optimizer_unique_decisions']==update['optimizer_decision_visits']==update['kl_unvisited_decisions']==0


def test_preupdate_behavior_mismatch_fails_without_publishing_invalid_resume(monkeypatch):
    from game.agent.training import ppo
    actual=ppo.objective
    def shifted(*args,**kwargs):
        loss,parts=actual(*args,**kwargs)
        return loss,dict(parts,approx_kl=torch.tensor(1.))
    with commit_owner(PPOConfig(rollout_steps=4,batch_size=2,kl_check='minibatch_v1')) as learner:
        rollout=learner.collect()
        weights={k:v.clone() for k,v in learner.model.state_dict().items()}
        monkeypatch.setattr(ppo,'objective',shifted)
        with pytest.raises(ValueError,match='before the first'):learner.update(rollout)
        assert learner.phase=='failed' and learner.updates==learner.decisions==0
        assert all(torch.equal(weights[k],v) for k,v in learner.model.state_dict().items())


@pytest.mark.parametrize('workers',[1,2])
def test_new_guard_exact_checkpoint_continuation_and_recipe_rejection(tmp_path,workers):
    settings=PPOConfig(rollout_steps=16,batch_size=4,epochs=2,kl_check='minibatch_v1')
    with commit_owner(settings,workers) as learner:
        learner.update(learner.collect())
        bundle=tmp_path/'public/model.sts-model';resume=tmp_path/'private/model.resume.pt'
        save_ppo_checkpoint(bundle,learner,resume_path=resume)
        experiment=learner.experiment
        expected_rollout=learner.collect();learner.update(expected_rollout)
        with restore_ppo(bundle,resume,env_factory=controlled_env,workers=workers) as restored:
            actual_rollout=restored.collect();restored.update(actual_rollout)
            assert comparable(actual_rollout)==comparable(expected_rollout)
            assert restored.updates==learner.updates and restored.decisions==learner.decisions
            assert torch.equal(restored.action_generator.get_state(),learner.action_generator.get_state())
            assert torch.equal(restored.update_generator.get_state(),learner.update_generator.get_state())
            assert all(torch.equal(v,restored.model.state_dict()[k]) for k,v in learner.model.state_dict().items())
        changed=replace(experiment,ppo=replace(settings,batch_size=8))
        with pytest.raises(ValueError,match='cannot change'):
            restore_ppo(bundle,resume,env_factory=controlled_env,experiment=changed)
        epoch=replace(experiment,ppo=replace(settings,kl_check='epoch_v1'),schema='sts_ppo_experiment_v2')
        with pytest.raises(ValueError,match='cannot change'):
            restore_ppo(bundle,resume,env_factory=controlled_env,experiment=epoch)


def test_twenty_combinations_change_only_registered_ppo_fields_and_keep_model_weights_paired():
    c=config();p=parent()
    recipes,rows=h.configurations(p,c,'controlled_strike_or_die_v1')
    assert len(recipes)==4 and len(rows)==20
    for name in c['calibration_models']+c['transfer_models']:
        base=rows['reference__'+name]
        for recipe in recipes:
            row=rows[recipe+'__'+name]
            assert row['architecture']==base['architecture'] and row['vocabulary']==base['vocabulary']
            assert row['parameters']==base['parameters'] and row['architecture']['hidden_size']==64
            assert row['ppo']['ppo']['kl_check']=='minibatch_v1'
            changed={k for k,v in row['ppo']['ppo'].items() if v!=base['ppo']['ppo'][k]}
            assert changed<=h.RECIPE_FIELDS
    manifest=dict(configuration=c,configurations=rows,transfer_seeds=c['transfer_seeds'])
    transfer=h.transfer_schedule(manifest,'smaller_lr')
    assert len(transfer)==12 and len({tuple(v) for v in transfer})==12
    assert {s for _,s in transfer}=={71,101,137}
    assert all(rows[n]['model_id'] not in c['calibration_models'] for n,_ in transfer)
    assert h.effective_manifest(manifest,'smaller_lr__'+c['calibration_models'][0])['ppo']==recipes['smaller_lr']


def test_model_weighting_preserves_fight_and_seed_pairs():
    models=['a','b','c'];seeds=[11,29]
    wins={'r__'+model:{s:{'fight1':float(i==0),'fight2':float(i!=0)} for s in seeds} for i,model in enumerate(models)}
    average=h.aggregate(wins,'r',models,seeds)
    assert average[11]=={'fight1':pytest.approx(1/3),'fight2':pytest.approx(2/3)}
    del wins['r__c'][29]['fight2']
    with pytest.raises(ValueError,match='paired'):h.aggregate(wins,'r',models,seeds)


def test_selection_does_not_hide_large_model_regression_or_use_transfer_results():
    models=['flat','graph','attention'];m=dict(configuration=dict(calibration_models=models,seeds=[11,29]),recipes={k:{} for k in ('reference','fragile','balanced','weak')})
    results={}
    scores=dict(reference=[.2,.2,.2],fragile=[.6,.1,.6],balanced=[.25,.25,.25],weak=[.1,.1,.1])
    for recipe,values in scores.items():
        for model,value in zip(models,values):
            results[recipe+'__'+model]=[dict(development=dict(win_rate=value),sampled=dict(win_rate=value),
                learning=dict(iterations=[dict(update=dict(after=dict(approx_kl=.01)))])) for _ in (11,29)]
    stats=h.recipe_statistics(m,results)
    assert not stats['fragile']['eligible'] and h.select_challenger(stats)=='balanced'
    results['fragile__held_out_pooled']=[dict(development=dict(win_rate=1.))]
    assert h.recipe_statistics(m,results)==stats
    with pytest.raises(ValueError):h.select_challenger({'reference':stats['reference']})


@pytest.mark.parametrize('change',[{'transfer_seeds':[11,71,101]}, {'seeds':[True,29]},
    {'calibration_models':['pooled_mlp-mechanical-context']}, {'collectors':True}, {'hidden_size':True}])
def test_invalid_study_design_is_rejected(tmp_path,change):
    c=config();c.update(change);p=tmp_path/'config.json';p.write_text(json.dumps(c))
    with pytest.raises(ValueError):h.load_config(p)


def test_no_test_phase_can_be_invoked(tmp_path):
    with pytest.raises(ValueError,match='no TEST'):
        h.run(tmp_path/'missing.json',tmp_path/'output',phase='confirm')
    assert not (tmp_path/'output').exists()


def test_selection_recovers_interruption_between_publications_without_reselection(tmp_path,monkeypatch):
    c=config()
    rows={r+'__'+m:dict(recipe=r,model_id=m) for r in c['recipes'] for m in c['calibration_models']+c['transfer_models']}
    manifest=dict(configuration=c,configurations=rows,transfer_seeds=c['transfer_seeds'])
    stats={r:dict(eligible=True,mean_greedy=.3,worst_model_delta=0.,severe_kl_rate=0.,mean_seed_std=0.,mean_sampled=.2)
           for r in c['recipes']}
    report=dict(manifest_sha256='a'*64,recipe_statistics=stats,
        results={n:[dict(seed=s,checkpoint_sha256=str(s)) for s in c['seeds']]
                 for n,v in rows.items() if v['model_id'] in c['calibration_models']})
    publish=h.publish
    def interrupted(path,payload):
        if path.name=='selection.json':raise InterruptedError('after snapshot')
        return publish(path,payload)
    monkeypatch.setattr(h,'publish',interrupted)
    with pytest.raises(InterruptedError):h.freeze_selection(tmp_path,manifest,report)
    assert (tmp_path/'calibration-report.json').is_file() and not (tmp_path/'selection.json').exists()
    snapshot=(tmp_path/'calibration-report.json').read_bytes()
    monkeypatch.setattr(h,'publish',publish)
    first=h.freeze_selection(tmp_path,manifest,report)
    assert h.freeze_selection(tmp_path,manifest,report)==first
    assert (tmp_path/'calibration-report.json').read_bytes()==snapshot
    changed=deepcopy(report);changed['recipe_statistics']['lower_entropy']['mean_greedy']=.9
    with pytest.raises(ValueError,match='snapshot changed'):h.freeze_selection(tmp_path,manifest,changed)


def header_fixture():
    row=next(iter(parent()['configurations'].values()))
    row=json.loads(json.dumps(dict(row,ppo=parent()['ppo'])))
    architecture=StudyArchitecture(**row['architecture'])
    header=dict(architecture=row['architecture'],vocabulary=row['vocabulary'],learner_config=row['ppo'],
        feature_identity=architecture.identity(Vocabulary.from_dict(row['vocabulary'])),implementation={'synthetic':'unit'},
        algorithm='ppo',action_policy='commit_decisions_v1',updates=0,weights_sha256='weights-0',resume_state_sha256='resume-0')
    return row,header


def test_model_header_rejects_substituted_architecture_vocabulary_and_recipe():
    row,header=header_fixture()
    h.validate_model_header(header,row,header['implementation'])
    for key,value in [('architecture',dict(header['architecture'],hidden_size=32)),('vocabulary',Vocabulary(()).to_dict()),
                      ('feature_identity','substituted'),('learner_config',{}),('action_policy','all_legal_v1')]:
        changed=dict(header);changed[key]=value
        with pytest.raises(ValueError,match='registered learner'):h.validate_model_header(changed,row,header['implementation'])


def test_checkpoint_chain_accepts_republished_bundle_bytes_but_rejects_changed_state(tmp_path):
    # Synthetic metadata-only bundles exercise chain bindings, not model loading.
    row,header=header_fixture()
    def bundle(path,value,comment=b''):
        path.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(path,'w') as z:
            z.writestr('manifest.json',json.dumps(value));z.comment=comment
        return h._sha_file(path)
    path=tmp_path/'initialization/initial.sts-model'
    previous=bundle(path,header)
    reports=[];start=0
    for endpoint in h.CHUNKS:
        folder=tmp_path/'training'/f'{endpoint:06}'
        initial=bundle(folder/'initial.sts-model',header,b'republished')
        assert initial!=previous
        header=dict(header,updates=header['updates']+1,weights_sha256=f'weights-{endpoint}',resume_state_sha256=f'resume-{endpoint}')
        final=folder/'final.sts-model';current=bundle(final,header)
        report=dict(status='complete',experiment=row['ppo'],implementation=header['implementation'],
            initialization=dict(checkpoint='ppo_v1:'+previous,resumed=True),initial_sha256=initial,final_sha256=current,
            start_decisions=start,summary=dict(accepted_decisions=endpoint-start,processed_decisions=endpoint-start))
        report_path=folder/'ppo.json';report_path.write_text(json.dumps(report));reports.append(str(report_path))
        previous,start=current,endpoint
    manifest=dict(configurations={'model':row},implementation=header['implementation'])
    learner=dict(configuration_id='model',reports=reports,checkpoint=str(final),checkpoint_sha256=current)
    checkpoints=h.validate_checkpoints(manifest,learner,tmp_path)
    assert set(checkpoints)=={str(n) for n in h.MILESTONES}
    first=Path(reports[0]);report=json.loads(first.read_text())
    report['initial_sha256']=report['initialization']['checkpoint'].split(':')[1]
    first.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='decision binding'):h.validate_checkpoints(manifest,learner,tmp_path)
    initial=first.parent/'initial.sts-model'
    with zipfile.ZipFile(initial) as z:changed=json.loads(z.read('manifest.json'))
    changed['resume_state_sha256']='different-optimizer-or-rng'
    report['initial_sha256']=bundle(initial,changed);first.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='exact preceding state'):h.validate_checkpoints(manifest,learner,tmp_path)


@pytest.mark.parametrize('key',['0','100000','sampled','training'])
def test_evaluation_exactly_binds_learner_seed_checkpoint_modes_limits_and_fights(key):
    split='train' if key=='training' else 'validation'
    modes=[['sampled',0],['sampled',1]] if key=='sampled' else [['greedy',0]]
    manifest=dict(source_identity='verified-source',training_content=['strike'],
        opening_cases={split:{'a':'fight-a','b':'fight-b'}})
    checkpoint=(Path('/synthetic/final.sts-model'),'bound-sha')
    binding=dict(source='verified-source',split=split,policies={'model':dict(checkpoint=str(checkpoint[0]),sha256=checkpoint[1])},
        modes=modes,seed=11,training_content=['strike'],limits=h.LIMITS)
    episodes=[dict(case_id=case,combat_id=fight,policy='model',mode=mode,repeat=repeat,split=split,status='terminated')
              for case,fight in manifest['opening_cases'][split].items() for mode,repeat in modes]
    evaluation=dict(status='complete',binding=binding,episodes=episodes)
    h.validate_evaluation(evaluation,manifest,'model',11,key,checkpoint)
    for field,value in [('seed',29),('policies',{'other':binding['policies']['model']}),
                        ('limits',dict(h.LIMITS,decisions=513)),('modes',[['sampled',9]])]:
        bad=deepcopy(evaluation);bad['binding'][field]=value
        with pytest.raises(ValueError,match='Evaluation differs'):h.validate_evaluation(bad,manifest,'model',11,key,checkpoint)
    for field,value in [('case_id','unknown'),('combat_id','other-fight'),('mode','other'),('repeat',4),('policy','other')]:
        bad=deepcopy(evaluation);bad['episodes'][0][field]=value
        with pytest.raises(ValueError,match='Evaluation differs'):h.validate_evaluation(bad,manifest,'model',11,key,checkpoint)
    bad=deepcopy(evaluation);bad['episodes'][0]=deepcopy(bad['episodes'][-1])
    with pytest.raises(ValueError,match='Evaluation differs'):h.validate_evaluation(bad,manifest,'model',11,key,checkpoint)
