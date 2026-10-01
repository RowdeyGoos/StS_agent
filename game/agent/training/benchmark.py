"""Paired frozen combat evaluation, development selection, and held-out locking."""
from dataclasses import asdict, replace
import hashlib
from pathlib import Path
import time

from game.agent.provenance import implementation
from game.agent.runner import prepare_directories
from .benchmark_suite import data, digest, load_registry, load_suite, snapshot_factory
from .comparison import choose, conclusion, summarize
from .config import TrainingConfig
from .curriculum import SOURCE, start
from .evaluation import BaselineCase, _episode
from .rewards import strict_json


def _bound(path):
    path=Path(path).resolve()
    return {'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}


def _validate_development(report,suite):
    if (report.get('schema')!='sts_combat_comparison_v1' or report.get('split')!='validation' or
            report.get('suite_sha256')!=digest(suite) or report.get('implementation')!=asdict(implementation()) or
            report.get('protocol')!=suite['protocol'] or report.get('limits')!=suite['config']):
        raise ValueError('Development report belongs to another suite/source/protocol')
    cases={r['case_id']:r for r in suite['cases'] if r['split']=='validation'}
    policies=report['policies']
    if not {'random_legal','heuristic','imitation'}<=set(policies):
        raise ValueError('Missing required comparison policy')
    expected={(case,name) for case in cases for name in policies}
    actual={(r['case_id'],r['policy']) for r in report['episodes']}
    if expected!=actual or len(actual)!=len(report['episodes']) or any(
            any(row[k]!=v for k,v in cases[row['case_id']].items()) for row in report['episodes']):
        raise ValueError('Development report does not contain the frozen planned cases')
    computed=summarize(report['episodes'],policies)
    if any(report[k]!=v for k,v in computed.items()):
        raise ValueError('Development summary disagrees with its case outcomes')


def _selection(path, suite):
    value=strict_json(Path(path).read_text())
    if (value.get('schema')!='sts_combat_selection_v1' or value.get('suite_sha256')!=digest(suite) or
            value.get('implementation')!=asdict(implementation())):
        raise ValueError('Selection does not match the frozen suite/source')
    report=value['development_report']
    if _bound(report['path'])!=report:
        raise ValueError('Development report changed after selection')
    development=strict_json(Path(report['path']).read_text())
    _validate_development(development,suite)
    if choose(development)!=value['selected'] or development['suite_sha256']!=digest(suite):
        raise ValueError('Selection disagrees with the development criterion')
    if value['policies']!=development['policies']:
        raise ValueError('Selection policy bindings changed')
    return value


def select_checkpoint(suite_path, development_report, output_path):
    from .checkpoint import publish
    path,suite,_=load_suite(suite_path)
    if (path.parent/'test-opened.json').exists():
        raise ValueError('Held-out population has been opened; do not select again on this suite')
    report=strict_json(Path(development_report).read_text())
    _validate_development(report,suite)
    name=choose(report)
    value={'schema':'sts_combat_selection_v1','suite_sha256':digest(suite),
           'implementation':asdict(implementation()), 'development_report':_bound(development_report),
           'selected':name, 'policies':report['policies'], 'criterion':suite['protocol']['selection']}
    output=Path(output_path).resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    publish(output,data(value))
    return output,value


def evaluate_benchmark(*, suite_path, output_dir, checkpoints=None, split='validation',
                       selection_path=None, cancel=None):
    from .checkpoint import load_policy, publish, runtime
    path,suite,private=load_suite(suite_path)
    if split not in ('validation','test'):
        raise ValueError('Benchmark supports development or held-out evaluation')
    selected=None
    lock=binding=None
    if split=='test':
        if selection_path is None or checkpoints:
            raise ValueError('Held-out evaluation requires a locked selection, without new checkpoints')
        selection=_selection(selection_path,suite)
        selected=selection['selected']
        chosen={name:p for name,p in selection['policies'].items() if name in ('imitation',selected)}
        checkpoints={name:p['artifact']['path'] for name,p in chosen.items()}
        # Commit the selection before opening any held-out snapshot. Subsequent
        # replays may use this same lock; a different development selection may not.
        lock=path.parent/'test-opened.json'
        binding={'schema':'sts_test_opened_v1','selection_sha256':_bound(selection_path)['sha256'],
                 'suite_sha256':digest(suite)}
        if lock.exists() and strict_json(lock.read_text())!=binding:
            raise ValueError('Held-out suite is already bound to another selection')
    elif selection_path is not None or (path.parent/'test-opened.json').exists():
        raise ValueError('Development evaluation is closed once held-out evaluation starts')
    checkpoints={} if checkpoints is None else checkpoints
    if (type(checkpoints) is not dict or not 1<=len(checkpoints)<=8 or 'imitation' not in checkpoints or
            any(type(n) is not str or not n or len(n)>64 or n in ('random_legal','heuristic') for n in checkpoints)):
        raise ValueError('Name the imitation comparison and one or more PPO checkpoints')
    identity=implementation()
    policies={'random_legal':{'identity':'random_legal_v1:'+identity.build,'algorithm':'random_legal'},
              'heuristic':{'identity':identity.policy,'algorithm':'heuristic'}}
    loaded={}
    for name,bundle in checkpoints.items():
        learned=load_policy(bundle, task='combat')
        if learned.reward_spec!=TrainingConfig().reward or (name=='imitation')!=(learned.algorithm=='imitation'):
            raise ValueError('Use one imitation and PPO bundles with the declared victory objective')
        loaded[name]=learned
        policies[name]={'identity':learned.identity,'algorithm':learned.algorithm,'artifact':_bound(bundle)}
        if split=='test' and policies[name]!=selection['policies'][name]:
            raise ValueError('Held-out checkpoint changed after development selection')
    identities=[p['identity'] for p in policies.values() if p['algorithm']=='ppo']
    if len(set(identities))!=len(identities):
        raise ValueError('Name distinct PPO learner checkpoints')
    registry=load_registry(suite,private)
    cases=[r for r in suite['cases'] if r['split']==split]
    output=Path(output_dir).resolve()
    output,audit=prepare_directories(output,output.with_name(output.name+'-private'))
    report_path=output/'benchmark.json'
    # Reserve before gameplay. A duplicate cannot overwrite evidence.
    reservation=report_path.with_name(report_path.name+'.partial')
    if report_path.exists():
        raise FileExistsError(report_path)
    with reservation.open('x'):
        pass
    if lock is not None:
        try:
            publish(lock,data(binding))
        except FileExistsError:
            if strict_json(lock.read_text())!=binding:
                raise ValueError('Held-out suite is already bound to another selection')
    started=time.perf_counter()
    rows=[{**case,'policy':name,'status':'unattempted','steps':0,'combat':None,'failure':None,
           'potion_use_actions':0,'task_return':0.,'encounter':registry[case['case_id']]['encounter']}
          for case in cases for name in policies]
    report={'schema':'sts_combat_comparison_v1','suite_sha256':digest(suite),'implementation':asdict(identity),
        'runtime':runtime(),'protocol':suite['protocol'],'split':split,'policies':policies,
        'status':'complete','episodes':rows, 'limits':suite['config'],'selected':selected}
    stop=False
    try:
        for index,case in enumerate(cases):
            if cancel is not None and cancel.is_set():
                report['status']='interrupted'
                break
            try:
                factory=snapshot_factory(case,registry,private)
            except Exception as error:
                row=rows[index*len(policies)]
                row.update(status='failed',failure='frozen_source:'+type(error).__name__)
                report['status']='failed'
                break
            seed=registry[case['case_id']]
            trial=BaselineCase(case['scenario'],split,seed['reset_seed'],seed['policy_seed'],
                               suite['config']['max_decisions'],suite['config']['time_limit_seconds'])
            for offset,(name,policy) in enumerate(policies.items()):
                result=_episode(trial,name,replace(identity,policy=policy['identity']),output,audit,TrainingConfig(),
                    chooser=loaded.get(name),engine_factory=factory,scenario_set=SOURCE,cancel=cancel)
                result['encounter']=seed['encounter']
                result.update(case,policy=name,start_sha256=seed['snapshot_sha256'])
                rows[index*len(policies)+offset]=result
                if result['status'] not in ('terminated','truncated'):
                    report['status'],stop=result['status'],True
                    break
            if stop:
                break
    except KeyboardInterrupt:
        report['status']='interrupted'
    except Exception as error:
        report.update(status='failed',failure=type(error).__name__)
    report.update(summarize(rows,policies))
    report['by_encounter']={name:summarize([r for r in rows if r['encounter']==name],policies)
                            for name in sorted({r['encounter'] for r in rows})}
    report['by_scenario']={name:summarize([r for r in rows if r['scenario']==name],policies)
                           for name in sorted({r['scenario'] for r in rows})}
    report['total_seconds']=time.perf_counter()-started
    if split=='test':
        report['primary_conclusion']=conclusion(report,selected)
        report['selection_sha256']=_bound(selection_path)['sha256']
    # The reserved file is private to this process. Publication remains exclusive.
    reservation.write_bytes(data(report))
    import os
    with reservation.open('rb') as source:
        os.fsync(source.fileno())
    os.link(reservation,report_path)
    reservation.unlink()
    from game.agent.tracking import report_progress
    report_progress(report_path, report)
    return report_path,report
