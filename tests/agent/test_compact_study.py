"""Semantic preservation, ownership and native PPO for typed combat features."""
from copy import deepcopy
from dataclasses import replace, asdict
import pytest
torch=pytest.importorskip('torch')
np=pytest.importorskip('numpy')
from game.agent.contracts import full as f
from game.agent.training.study.spec import FeatureSpec, StudyArchitecture, COMPACT_ARCHITECTURES, ROLES, PILES, channels, ABLATIONS
from game.agent.training.study.projection import StudyFeatures
from game.agent.training.study.compact import compact, layout, CompactFeatures
from game.agent.training.study.entity_study import configurations, comparisons, secondary_comparisons
from game.agent.training.model import collate
from game.agent.training.features import Vocabulary
from .test_feature_study import make, public, edit, fields, study_catalog
from .test_feature_study import test_random_checkpoint_and_exact_native_ppo_resume as check_native_resume
from .test_training_model import cpu_threads


def expand(s):
    """Independent recovery of the original semantic columns from compact data."""
    names=[n for _,n in channels(s.richness)]; idx={n:i for i,n in enumerate(names)}
    result=np.zeros((len(s.roles),len(names)),np.float32)
    for i,(role,pile) in enumerate(zip(s.roles,s.piles)):
        result[i,idx['role='+ROLES[role]]]=1
        if pile>=0: result[i,idx['pile='+PILES[pile]]]=1
    def insert(row,name,value):
        result[row,idx[name]]=value
        if name.endswith('.log'):
            result[row,idx[name[:-4]+'.scaled']]=np.sign(value)*np.expm1(np.abs(value))/100
        elif name.endswith('.scaled'):
            result[row,idx[name[:-7]+'.log']]=np.sign(value)*np.log1p(np.abs(value)*100)
    role_fields,effect_fields=layout(s.richness)
    for role,(rows,values) in s.typed.items():
        for row,v in zip(rows,values):
            for value,(name,scale) in zip(v,role_fields[role]): insert(row,name,value/scale)
    for row,pos,v in zip(s.effect_owners,s.effect_positions,s.effects):
        for value,(name,scale) in zip(v,effect_fields): insert(row,f'mechanics.effect.{pos}.'+name,value/scale)
    return result


@pytest.mark.parametrize('spec',[FeatureSpec(richness=r) for r in ('basic','mechanics','context')]+
                         [FeatureSpec(ablations=(a,)) for a in ABLATIONS])
def test_compact_preserves_all_original_semantic_facts(spec):
    p=public(); old=make('pooled_mlp',spec=spec).encoder().encode(p)
    new=make('compact_pooled_mlp',spec=spec).encoder().encode(p)
    np.testing.assert_array_equal(old.values,new.values)
    np.testing.assert_allclose(expand(new),old.values,atol=1e-6,rtol=2e-6)
    np.testing.assert_array_equal(old.candidates,new.candidates)
    assert old.candidate_refs==new.candidate_refs and old.policy_mask==new.policy_mask
    assert new.for_rollout().values is None and new.for_rollout().nbytes<old.for_rollout().nbytes
    # Unexpected nonzero fields on another role must fail instead of disappearing.
    bad=replace(old,values=old.values.copy())
    enemy=int(np.flatnonzero(new.roles==ROLES.index('enemy'))[0])
    idx={n:i for i,(_,n) in enumerate(channels(spec.richness))}
    bad.values[enemy,idx['actions.play_card.known']]=1
    with pytest.raises(ValueError,match='Unmapped'): compact(bad,spec.richness)


@pytest.mark.parametrize('kind',COMPACT_ARCHITECTURES)
def test_compact_renaming_and_no_dense_input_path(kind):
    p=public(); model=make(kind); e=model.encoder(); a=e.encode(p)
    def rename(n):
        if n.kind in ('card','enemy','potion','relic'): n=replace(n,definition_id='rename_'+n.definition_id)
        if n.kind=='spec': n=fields(n,name='Another display name')
        return n
    catalog=deepcopy(study_catalog().to_dict())
    for entry in catalog['entries']:
        if entry['kind'] in ('card','enemy','potion','relic'): entry['definition_id']='rename_'+entry['definition_id']
    catalog['entries'].sort(key=lambda n:(n['kind'],n['definition_id']))
    catalog['names']=sorted(set(catalog['names'])|{e['definition_id'] for e in catalog['entries']})
    renamed_model=make(kind,catalog=catalog)
    b=renamed_model.encoder().encode(edit(p,rename))
    x=model(collate([a],vocabulary=model.vocabulary)); y=renamed_model(collate([b],vocabulary=model.vocabulary))
    assert all(torch.equal(u,v) for u,v in zip(x,y))
    a.values[:]=np.nan  # Audit rows cannot influence the new network.
    packed=a.for_rollout(); batch=collate([packed],vocabulary=model.vocabulary)
    assert 'study_values' not in batch and len(batch['owners'])==len(a.roles)
    assert all(torch.equal(u,v) for u,v in zip(x,model(batch)))
    assert not any('content' in n for n,_ in model.named_parameters())


@pytest.mark.parametrize('kind',COMPACT_ARCHITECTURES)
def test_entity_permutation_candidate_mapping_and_batch_isolation(kind):
    p=public(); m=make(kind); e=m.encoder(); s=e.encode(p)
    order=np.r_[0,np.arange(len(s.roles)-1,0,-1)]; inverse=np.argsort(order)
    candidates=s.candidates.copy()
    candidates[:,1:]=np.where(candidates[:,1:]>=0,inverse[candidates[:,1:].clip(0)],-1)
    parents=np.where(s.parents[order]>=0,inverse[s.parents[order].clip(0)],-1)
    raw=StudyFeatures(**{k:getattr(s,k) for k in StudyFeatures.__dataclass_fields__})
    changed=compact(replace(raw,values=s.values[order],identities=s.identities[order],
                            parents=parents,candidates=candidates),'context')
    a=m(collate([s],vocabulary=m.vocabulary)); b=m(collate([changed],vocabulary=m.vocabulary))
    assert all(torch.allclose(x,y,atol=2e-6,rtol=2e-6) for x,y in zip(a,b))
    other=e.encode(edit(p,lambda n:fields(n,hp=3) if n.kind=='combat' else n))
    joined=m(collate([other,s],vocabulary=m.vocabulary))
    assert all(torch.allclose(x[0],y[1],atol=2e-6,rtol=2e-6) for x,y in zip(a,joined))
    bad=replace(s,effect_owners=np.full_like(s.effect_owners,len(s.roles)))
    with pytest.raises(ValueError,match='ownership'): collate([bad],vocabulary=m.vocabulary)


@pytest.mark.parametrize('kind',COMPACT_ARCHITECTURES)
def test_piles_offered_choices_and_unknown_zero_reach_both_heads(kind):
    p=public(); card=next(n for n in f.walk(p.context) if n.kind=='card')
    offered=replace(card,ref='card:99999')
    p=replace(p,context=replace(p.context,children=(*p.context.children,
        f.Node('pile','offered',fields=(f.Field('count',1),),children=(offered,)))))
    q=edit(p,lambda n:fields(n,energy=99) if n.ref==offered.ref else n)
    m=make(kind); e=m.encoder()
    a=m(collate([e.encode(p)],vocabulary=m.vocabulary)); b=m(collate([e.encode(q)],vocabulary=m.vocabulary))
    assert all(not torch.equal(x,y) for x,y in zip(a,b))
    s=e.encode(p); ix=next(i for i,(_,n) in enumerate(channels('context')) if n=='damage.known')
    row=int(np.flatnonzero(s.roles==ROLES.index('card'))[0])
    raw=StudyFeatures(**{k:getattr(s,k) for k in StudyFeatures.__dataclass_fields__})
    unknown=raw.values.copy(); unknown[row,ix:ix+3]=0
    zero=unknown.copy(); zero[row,ix]=1
    u=compact(replace(raw,values=unknown),'context'); z=compact(replace(raw,values=zero),'context')
    assert not np.array_equal(u.typed['card'][1],z.typed['card'][1])
    swapped=raw.values.copy(); names={n:i for i,(_,n) in enumerate(channels('context'))}
    swapped[row,[names['pile='+v] for v in PILES]]=0
    swapped[row,names['pile=exhaust']]=1
    other=compact(replace(raw,values=swapped),'context')
    assert not np.array_equal(other.typed['card'][1],s.typed['card'][1])


@pytest.mark.parametrize('kind',COMPACT_ARCHITECTURES)
def test_effect_sequence_is_not_an_unordered_pool(kind):
    m=make(kind); s=m.encoder().encode(public())
    raw=StudyFeatures(**{k:getattr(s,k) for k in StudyFeatures.__dataclass_fields__})
    values=raw.values.copy(); idx={n:i for i,(_,n) in enumerate(channels('context'))}
    row=int(s.effect_owners[0])
    first=[i for n,i in idx.items() if n.startswith('mechanics.effect.0.')]
    second=[i for n,i in idx.items() if n.startswith('mechanics.effect.1.')]
    values[row,second]=values[row,first]
    values[row,idx['mechanics.effect.1.amount.log']]=np.log1p(99)
    values[row,idx['mechanics.effect.1.amount.scaled']]=.99
    values[row,idx['mechanics.effect.1.amount.known']]=1
    swapped=values.copy(); swapped[row,first]=values[row,second];swapped[row,second]=values[row,first]
    a=m(collate([compact(replace(raw,values=values),'context')],vocabulary=m.vocabulary))
    b=m(collate([compact(replace(raw,values=swapped),'context')],vocabulary=m.vocabulary))
    assert all(not torch.equal(x,y) for x,y in zip(a,b))


@pytest.mark.parametrize('kind',COMPACT_ARCHITECTURES)
def test_compact_native_checkpoint_and_exact_ppo_resume(tmp_path,kind):
    check_native_resume(tmp_path,kind)


@pytest.mark.parametrize('kind',COMPACT_ARCHITECTURES)
def test_compact_parallel_exact_resume(tmp_path,monkeypatch,kind):
    from . import test_feature_study_protocol as protocol
    monkeypatch.setattr(protocol,'make',lambda **kw:make(kind,**kw))
    protocol.test_study_parallel_exact_resume_preserves_weights_and_rng(tmp_path)


def test_eight_configurations_preserve_features_and_fixed_width():
    parent={'configurations':{}}
    for kind in ('flat_mlp','pooled_mlp'):
        for level in ('basic','context'):
            a=StudyArchitecture(16,kind,FeatureSpec(richness=level).to_dict(),study_catalog().to_dict())
            parent['configurations'][f'{kind}-mechanical-{level}']=dict(architecture=asdict(a),vocabulary=Vocabulary(()).to_dict())
    rows=configurations(parent,64)
    assert len(rows)==8 and len(comparisons())==6 and len(secondary_comparisons())==6
    for name,row in rows.items():
        assert row['architecture']['hidden_size']==64 and row['parameters']['embedding']==0
        assert row['architecture']['features']==FeatureSpec(richness=name.split('-')[-1]).to_dict()
    assert len({StudyArchitecture(**r['architecture']).identity(Vocabulary(())) for r in rows.values()})==4


@pytest.mark.parametrize('kind',COMPACT_ARCHITECTURES)
def test_native_multicard_selection_and_capacity_boundary(kind):
    from game.agent.action_policy import action_mask
    from .test_commit_selection import fury_run, attach, step
    run=fury_run(); adapter=attach(run); model=make(kind)
    selected=[]
    for count in range(3):
        p=adapter.observe().decision; before=run.snapshot()
        old=make('pooled_mlp').encoder().encode(p)
        state=model.encoder().encode(p)
        assert run.snapshot()==before
        np.testing.assert_allclose(expand(state),old.values,atol=1e-6,rtol=2e-6)
        np.testing.assert_array_equal(state.candidates,old.candidates)
        assert state.candidate_refs==old.candidate_refs
        assert tuple(state.policy_mask)==tuple(action_mask(p,'commit_decisions_v1'))
        selected.append(state.typed['selection'][1].copy())
        logits,value=model(collate([state],vocabulary=model.vocabulary))
        assert torch.isfinite(logits).all() and torch.isfinite(value).all()
        if count<2: step(adapter,'select_card')
    assert all(not np.array_equal(a,b) for a,b in zip(selected,selected[1:]))
    assert [a.kind for a,ok in zip(p.candidates,state.policy_mask) if ok]==['confirm_selection']
    step(adapter,'confirm_selection')
    assert run.combat.player.rules.selection is None
    with pytest.raises(ValueError,match='overflow'):
        make(kind,spec=FeatureSpec(entities=8)).encoder().encode(public())
