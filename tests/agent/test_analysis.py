"""Public export integrity, honest outcomes/joins and same-state inspection."""
from copy import deepcopy
from dataclasses import replace
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import sys
import threading

import pytest

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.provenance import Implementation
from game.agent.recording import Metadata, TrajectoryWriter, load_trajectory
from game.agent.analysis.decisions import state_digest, summarize
from game.agent.analysis.report import build_report
from game.agent.analysis.server import AnalysisStore, make_server
from game.agent.analysis.sources import discover, collect_metadata, digest


def public(context='combat', candidates=None, completed=None):
    # Explicit synthetic public fixture, never presented as a generated campaign.
    card=f.Node('card','strike','card:0',fields=(f.Field('name','<img src=x onerror=alert(1)>'),))
    run=f.Node('run','test',fields=tuple(f.Field(k,v) for k,v in dict(act=1,floor=1,hp=20,max_hp=80,gold=9).items()),children=(card,))
    ctx=f.Node(context,'test',fields=tuple(f.Field(k,v) for k,v in ({'completed_act':completed} if completed else {'energy':2,'round':1}).items()))
    return f.PublicDecision(f.SCHEMA,f.PROFILE,run,ctx,candidates or (f.Candidate('action:0','end_turn'),f.Candidate('action:1','play_card','card:0')))


def record(root, *, episode='1'*32, start=None, choices=None, ending=None, policy='test-policy'):
    start=start or public()
    choices=choices if choices is not None else [(start.candidates[0],start)]
    ending=ending or c.RunOutcome('sts_run_outcome_v1','truncated','decision_budget')
    identity=Implementation('controlled-test','a'*64,'b'*64,policy)
    meta=Metadata.create(identity,episode_id=episode,scenario='controlled-test',split='validation',evidence='controlled_fixture')
    path=root/(episode+'.trajectory.jsonl')
    with TrajectoryWriter(path,meta,start) as writer:
        for action,successor in choices:
            writer.append(action,c.ExecutionReport('sts_execution_report_v1','reconciled','applied','none'),successor)
        writer.finish(ending)
    return path


def panel(root, paths, *, policies=None):
    rows=[]
    policies=policies or {load_trajectory(p).metadata.policy:load_trajectory(p).metadata.policy for p in paths}
    for path in paths:
        trace=load_trajectory(path);label=next(k for k,v in policies.items() if v==trace.metadata.policy)
        rows.append({'episode_id':trace.metadata.episode_id,'case_id':'9'*32,'source_group':'9'*32,'first_act':'overgrowth',
                     'policy':label,'status':'truncated','goal':'act1','steps':len(trace.transitions),
                     'trajectory_sha256':trace.sha256,'outcome':c.to_dict(trace.outcome),'act1_cleared':False})
    plan={'models':{k:{'identity':v} for k,v in policies.items()},'episodes':deepcopy(rows)}
    plan_path=root/'baseline-plan.json';plan_path.write_text(json.dumps(plan))
    report={'schema':'sts_act1_pilot_panel_v1','plan_sha256':digest(plan_path),'episodes':rows}
    path=root/'baseline.json';path.write_text(json.dumps(report))
    return path,report


def test_portable_export_inspector_matches_exact_state_and_never_reads_private(tmp_path,monkeypatch):
    root=tmp_path/'input';path=record(root)
    private=root/'run-private';private.mkdir();(private/'ppo.json').write_text('DO NOT READ')
    (private/('0'*32+'.trajectory.jsonl')).write_text('SECRET')
    (root/'unfinished.trajectory.jsonl.partial').write_text('unfinished')
    (root/'linked.trajectory.jsonl').symlink_to(path)
    original=Path.open
    def guarded(self,*args,**kwargs):
        assert 'run-private' not in self.parts
        return original(self,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guarded)
    before=path.read_bytes();output=tmp_path/'analysis'
    report=build_report([root],output,goal='act1')
    assert len(report['runs'])==1 and report['runs'][0]['status']=='cutoff'
    assert path.read_bytes()==before and report['paired_cases_verified']==0
    store=AnalysisStore(output);value=store.decision('1'*32,0)
    assert f.from_dict(value['observation'])==load_trajectory(path).initial
    assert value['state_sha256']==state_digest(load_trajectory(path).initial)
    assert value['candidates'][1]['label'].endswith('<img src=x onerror=alert(1)>')
    assert 'SECRET' not in (output/'report.json').read_text()
    assert 'innerHTML' not in (output/'app.js').read_text()
    with pytest.raises(FileExistsError):build_report([root],output)


def test_act1_boundary_success_is_distinct_from_campaign_victory_and_no_terminal_hp_is_invented(tmp_path):
    start=public('rewards',(f.Candidate('action:0','leave_rewards'),))
    complete=public('act_transition',(f.Candidate('action:0','continue_act'),),completed=1)
    path=record(tmp_path/'clear',start=start,choices=[(start.candidates[0],complete)],
                ending=c.RunOutcome('sts_run_outcome_v1','truncated','external_stop'))
    result=build_report([path],tmp_path/'report',goal='act1')['runs'][0]
    assert result['task_success'] and result['status']=='success' and result['act1_cleared']
    assert result['outcome']['kind']=='truncated' and result['canonical_return']==0
    store=AnalysisStore(tmp_path/'report');assert store.decision(result['id'],0)['after_hud']['hp']==20
    dead=c.RunOutcome('sts_run_outcome_v1','defeat','none')
    path=record(tmp_path/'defeat',choices=[(public().candidates[0],dead)],ending=dead)
    build_report([path],tmp_path/'defeat-report',goal='act1')
    value=AnalysisStore(tmp_path/'defeat-report').decision('1'*32,0)
    assert value['after_hud'] is None and value['delta']=={} and value['hud']['hp']==20


def test_late_campaign_defeat_is_not_an_act1_task_endpoint(tmp_path):
    start=public('rewards',(f.Candidate('action:0','leave_rewards'),))
    complete=public('act_transition',(f.Candidate('action:0','continue_act'),),completed=1)
    dead=c.RunOutcome('sts_run_outcome_v1','defeat','none')
    path=record(tmp_path/'input',start=start,choices=[(start.candidates[0],complete),(complete.candidates[0],dead)],ending=dead)
    with pytest.raises(ValueError,match='completion boundary'):build_report([path],tmp_path/'bad',goal='act1')
    row=build_report([path],tmp_path/'campaign',goal='full_run')['runs'][0]
    assert row['act1_cleared'] and not row['task_success'] and row['status']=='defeat'


def test_loop_signal_is_a_bounded_reversal_span_and_points_to_exact_decisions(tmp_path):
    state=public(candidates=(f.Candidate('action:0','select_card','card:0'),f.Candidate('action:1','deselect_card','card:0')))
    path=record(tmp_path,start=state,choices=[(state.candidates[i%2],state) for i in range(32)])
    result=summarize(load_trajectory(path))
    assert result['flags']==[{'kind':'selection_toggle','level':'warning','start':0,'end':31,
                            'reason':'32 consecutive selection/navigation actions including reversals in the same room/context. The recording ends at a cutoff.'}]
    assert result['categories']=={'selection':32}
    path=record(tmp_path/'no-undo',start=state,choices=[(state.candidates[0],state) for i in range(32)])
    assert not summarize(load_trajectory(path))['flags']


def test_panel_policy_labels_and_pairing_require_matching_canonical_evidence(tmp_path):
    root=tmp_path/'input';first=record(root,policy='one')
    source,report=panel(root,[first],policies={'learner':'one'})
    result=build_report([root],tmp_path/'one')
    assert result['paired_cases_verified']==0
    other=record(root,episode='2'*32,policy='two')
    source,report=panel(root,[first,other],policies={'learner':'one','reference':'two'})
    assert build_report([root],tmp_path/'paired')['paired_cases_verified']==1
    report['episodes'][0]['policy']='reference';source.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='case differs'):build_report([root],tmp_path/'bad-label')
    source,report=panel(root,[first,other],policies={'learner':'one','reference':'two'})
    plan=root/'baseline-plan.json';value=json.loads(plan.read_text());value['models']['learner']['identity']='different'
    plan.write_text(json.dumps(value));report['plan_sha256']=digest(plan);source.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='metadata disagrees'):build_report([root],tmp_path/'bad-model')


def test_no_source_or_export_path_traversal_and_chunk_tampering_reject(tmp_path):
    source=record(tmp_path/'input');build_report([source],tmp_path/'report');store=AnalysisStore(tmp_path/'report')
    for key in ('../secret','/tmp/private','abc'):
        with pytest.raises(ValueError):store.decision(key,0)
    for step in (-1,1,True):
        with pytest.raises(ValueError):store.decision('1'*32,step)
    chunk=next((tmp_path/'report/decisions').iterdir());chunk.write_bytes(chunk.read_bytes()+b'corrupt')
    with pytest.raises(ValueError,match='digest'):store.decision('1'*32,0)
    with pytest.raises(ValueError):discover([tmp_path/'input-private'])


@pytest.mark.parametrize('change', ['schema', 'goal', 'row_goal'])
def test_core_evaluation_goal_cannot_disagree_with_its_pinned_plan(tmp_path, change):
    path=record(tmp_path/'input')
    source,report=panel(path.parent,[path])
    plan_path=source.with_name('act1-plan.json')
    plan={'schema':'sts_act1_evaluation_v1','goal':'act1','policies':{'test-policy':'test-policy'},
          'reward_spec':{'goal':'act1'},'episodes':deepcopy(report['episodes'])}
    report.update(schema=plan['schema'],goal='act1',policies=plan['policies'],reward_spec=plan['reward_spec'])
    if change=='schema':report.update(schema='sts_full_run_evaluation_v1',goal='full_run');report['episodes'][0]['goal']='full_run'
    if change=='goal':report['goal']='full_run'
    if change=='row_goal':plan['episodes'][0]['goal']='full_run'
    plan_path.write_text(json.dumps(plan));report['plan_sha256']=digest(plan_path)
    destination=source.with_name('act1.json');destination.write_text(json.dumps(report))
    with pytest.raises(ValueError):collect_metadata([destination,plan_path])


def test_read_only_http_api_restricts_routes_host_origin_and_checks_indices(tmp_path):
    source=record(tmp_path/'input');build_report([source],tmp_path/'report')
    server=make_server(AnalysisStore(tmp_path/'report'),0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        def request(path,headers=None,method='GET'):
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
            connection.request(method,path,headers=headers or {});response=connection.getresponse();data=response.read();connection.close()
            return response.status,response.headers,data
        status,headers,data=request('/api/report');assert status==200 and json.loads(data)['runs'][0]['id']=='1'*32
        assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
        assert request('/api/report',{'Host':'evil.example'})[0]==403
        assert request('/api/report',{'Origin':'https://evil.example'})[0]==403
        assert request('/api/report',{'Sec-Fetch-Site':'cross-site'})[0]==403
        assert request('/report.json')[0]==404 and request('/../../secret')[0]==404
        assert request('/api/decision?id='+('1'*32)+'&step=-1')[0]==400
        assert request('/api/decision?id='+('1'*32)+'&step=0&step=1')[0]==400
        assert request('/api/report',method='POST')[0]==501
    finally:
        server.shutdown();server.server_close();thread.join(2)


def test_analysis_cli_and_core_export_do_not_require_training_dependencies(tmp_path):
    source=record(tmp_path/'input');root=Path(__file__).resolve().parents[2]
    result=subprocess.run([sys.executable,'-S','-m','game.cli.agent_analyze','build','--input',str(source),
                           '--output-dir',str(tmp_path/'report')],cwd=root,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stderr
    result=subprocess.run([sys.executable,'-S','-m','game.cli.agent_analyze','inspect',str(tmp_path/'report'),
                           '--episode','1'*32,'--step','0','--checkpoint','test=unused.sts-model'],
                          cwd=root,capture_output=True,text=True,timeout=30)
    assert result.returncode==1 and 'sts-agent[train]' in result.stderr and 'Traceback' not in result.stderr
