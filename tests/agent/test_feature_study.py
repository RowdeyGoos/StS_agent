"""Study factors, public-history uncertainty and native PPO compatibility."""
from dataclasses import replace
import copy
import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')
pytest.importorskip('gymnasium')
from game.agent.contracts import full as f
from game.agent.training.study.spec import FeatureSpec, StudyArchitecture, ARCHITECTURES, channels
from game.agent.training.study.projection import StudyEncoder, study_catalog, _card_effect, _item_effects
from game.agent.training.study.history import PublicHistory, intent
from game.agent.training.study.model import StudyActorCritic, match_capacity
from game.agent.training.features import Vocabulary
from game.agent.training.model import collate
from game.agent.training.env import CombatTrainingEnv
from game.agent.training.ppo import PPOLearner
from game.agent.training.ppo_config import PPOExperiment, PPOConfig
from game.agent.training.config import TrainingConfig
from game.agent.training.checkpoint import save_ppo_checkpoint, load_policy, restore_ppo
from .test_training_model import cpu_threads
from .test_ppo import controlled_env, comparable


def make(kind='graph', *, spec=None, seed=13, catalog=None):
    return StudyActorCritic(Vocabulary(()), StudyArchitecture(16, kind, (spec or FeatureSpec()).to_dict(),
        catalog or study_catalog().to_dict()), seed=seed, action_policy='commit_decisions_v1')


def public():
    with CombatTrainingEnv(encounter='overgrowth_nibbit') as env:
        env.reset(seed=11)
        return env.public_state


def edit(public, fn):
    def visit(node):
        return fn(replace(node, children=tuple(visit(n) for n in node.children)))
    return replace(public, run=visit(public.run), context=visit(public.context))


def fields(node, **values):
    return replace(node, fields=tuple(f.Field(k, v) for k, v in {**{v.key:v.value for v in node.fields}, **values}.items()))


@pytest.mark.parametrize('kind', ARCHITECTURES)
def test_no_vocabulary_renaming_batch_isolation_and_padding(kind):
    p = public()
    model = make(kind)
    model.eval()
    e = model.encoder()
    a = e.encode(p)
    def rename(n):
        if n.kind in ('card', 'enemy', 'potion', 'relic'):
            n = replace(n, definition_id='renamed_' + n.definition_id)
        if n.kind == 'spec':
            n = fields(n, name='Different display title')
        return n
    changed = edit(p, rename)
    catalog = copy.deepcopy(study_catalog().to_dict())
    for entry in catalog['entries']:
        if entry['kind'] in ('card', 'enemy', 'potion', 'relic'):
            entry['definition_id'] = 'renamed_' + entry['definition_id']
    catalog['entries'].sort(key=lambda n:(n['kind'],n['definition_id']))
    catalog['names'] = sorted(set(catalog['names']) | {e['definition_id'] for e in catalog['entries']})
    other = make(kind, catalog=catalog)
    b = other.encoder().encode(changed)
    assert np.array_equal(a.values, b.values)
    assert np.array_equal(a.identities, b.identities)
    assert np.array_equal(a.candidates, b.candidates)
    batch = collate([a], vocabulary=model.vocabulary)
    expected = model(batch)
    alternate = e.encode(edit(p, lambda n: fields(n,hp=3) if n.kind=='combat' else n))
    joined = model(collate([alternate, a], vocabulary=model.vocabulary))
    assert torch.allclose(expected[0][0], joined[0][1], atol=3e-6, rtol=2e-6)
    assert torch.allclose(expected[1][0], joined[1][1], atol=3e-6, rtol=2e-6)
    batch['study_values'][0, len(a.values):] = 1234
    assert all(torch.equal(x, y) for x, y in zip(expected, model(batch)))
    (expected[0].square().mean()+expected[1].square().mean()).backward()
    assert all(p.grad is not None for p in model.parameters())
    assert not any('content' in n for n,_ in model.named_parameters())


@pytest.mark.parametrize('group', ('card', 'powers', 'intent', 'items', 'piles'))
def test_ablation_removes_direct_and_derived_paths(group):
    p = public()
    e = make(spec=FeatureSpec(ablations=(group,))).encoder()
    before = e.encode(p)
    def mutation(n):
        if group == 'card' and n.kind == 'spec':
            return fields(n, base_damage=123, block_gain=84, draw_count=7)
        if group == 'powers' and n.kind in ('combat','enemy'):
            return fields(n, strength=123)
        if group == 'intent' and n.kind == 'intent':
            return fields(n, damage=123, hits=87)
        if group == 'items' and n.kind == 'relic':
            return fields(n, display_counter=87, melted=True, status='disabled')
        if group == 'piles' and n.kind == 'pile' and n.definition_id in ('draw','discard','exhaust'):
            return replace(n, children=tuple(fields(c, permanent_damage=999) for c in n.children))
        return n
    after = e.encode(edit(p, mutation))
    assert np.array_equal(before.values, after.values)
    assert np.array_equal(before.candidates, after.candidates)


def test_intent_mixed_buff_unknown_and_zero_hp_threat():
    enemy = f.Node('enemy','x',fields=(f.Field('alive',True),),children=(
        f.Node('intent','attack',fields=(f.Field('damage',7),f.Field('hits',2))),
        f.Node('intent','buff',fields=(f.Field('damage',None),f.Field('hits',None)))))
    assert intent(enemy)['damage'] == 14 and intent(enemy)['hits'] == 2
    assert intent(replace(enemy, children=(f.Node('intent','unknown'),)))['damage'] is None
    p=edit(public(),lambda n:fields(n,hp=0) if n.kind=='combat' else n)
    e=make().encoder(); s=e.encode(p)
    assert s.values[0,e.indexes['threat.pressure_hp_ratio.known']] == 0
    assert np.isfinite(s.values).all()


def test_history_receipts_round_reset_free_x_and_missing_flags():
    p=public()
    card=next(n for n in f.walk(p.context) if n.kind=='card' and any(a.subject==n.ref and a.kind=='play_card' for a in p.candidates))
    p=edit(p,lambda n:fields(n,energy=0) if n.ref==card.ref else fields(n,x_cost=True) if n.kind=='spec' else n)
    action=next(a for a in p.candidates if a.subject==card.ref and a.kind=='play_card')
    h=PublicHistory();h.reset(p,opening=True,reveals=[])
    successor=replace(p)
    h.observe(p,action,successor,[])
    assert h.counts['energy_spent']==0 and h.counts['plays']==1
    end=next(a for a in successor.candidates if a.kind=='end_turn')
    next_turn=replace(successor,context=fields(successor.context,round=successor.context.get('round')+1))
    h.observe(successor,end,next_turn,[{'kind':'draw','value':['unknown_status',0]}])
    assert h.counts['plays']==0 and h.counts['status_draws'] is None
    assert len(next(iter(h.profiles.values())))==1
    saved=h.export(next_turn); restored=PublicHistory();restored.restore(saved,next_turn)
    assert restored.export(next_turn)==saved
    restored.reset(next_turn)
    assert all(v is None for v in restored.counts.values()) and not restored.complete


def test_semantic_selection_operands_and_potion_duration():
    exhaust=f.Node('mechanic','SelectHandCard',fields=(f.Field('operation','exhaust'),f.Field('mode','choose')))
    upgrade=fields(exhaust,operation='upgrade',mode='all')
    assert _card_effect(exhaust,0)!=_card_effect(upgrade,0)
    entries={(e.kind,e.definition_id):e for e in study_catalog().entries}
    temporary=_item_effects(entries['potion','speed_potion'])[0]
    assert temporary['kind']=='status' and temporary['status']=='dexterity'
    assert temporary['amount']==5 and temporary['duration']=='turn'


@pytest.mark.parametrize('kind', ARCHITECTURES)
def test_random_checkpoint_and_exact_native_ppo_resume(tmp_path,kind):
    model=make(kind,spec=FeatureSpec(entities=32))
    experiment=PPOExperiment(training=TrainingConfig(action_policy='commit_decisions_v1'),
        ppo=PPOConfig(rollout_steps=8,batch_size=4,epochs=2), encounters=('strike_or_die',),
        source='controlled_strike_or_die_v1',schema='sts_ppo_experiment_v2')
    with PPOLearner(model,experiment,seed=123,env_factory=controlled_env,workers=1) as left:
        initial=tmp_path/'public/initial.sts-model'; resume=tmp_path/'private/initial.resume.pt'
        save_ppo_checkpoint(initial,left,resume_path=resume)
        assert load_policy(initial).manifest['updates']==0
        assert not left.optimizer.state
        left.update(left.collect())
        bundle=tmp_path/'public/next.sts-model';resume=tmp_path/'private/next.resume.pt'
        save_ppo_checkpoint(bundle,left,resume_path=resume)
        with restore_ppo(bundle,resume,env_factory=controlled_env) as right:
            a,b=left.collect(),right.collect()
            assert comparable(a)==comparable(b)
            left.update(a); right.update(b)
            assert all(torch.equal(v,right.model.state_dict()[k]) for k,v in left.model.state_dict().items())


def test_overflow_is_explicit():
    with pytest.raises(ValueError,match='overflow'):
        make(spec=FeatureSpec(entities=8)).encoder().encode(public())


@pytest.mark.parametrize('enchanted', (0, -1))
def test_history_restore_accepts_fresh_names_for_equal_copies(enchanted):
    from copy import deepcopy
    from game.agent.contracts import full as f
    from game.agent.headless import HeadlessAdapter
    from game.agent.headless.full_projection import FullProjection
    from game.agent.headless.identity import Identities
    from game.agent.training.study.history import PublicHistory
    from game.headless.enchantments.base import enchant
    from game.headless.run.engine import RunEngine
    from .test_campaign_search import fixture
    deck = ('defend',) * 4 + ('strike',) * 4 + ('bash',)
    names = Identities()
    def edit(run):
        # Public names precede the enchantment, as for a starting card enchanted later.
        FullProjection(run, names, [], {}, 'attachment', 0, False).run()
        enchant([c for c in run.state.deck if c.definition.definition_id == 'defend'][enchanted], 'spiral')
    run, _, anchor = fixture(deck=deck, edit=edit, names=names)
    restored = RunEngine()
    restored.restore(deepcopy(run.snapshot()))
    # Corpus starts observe through a fresh adapter, which names equal copies by content.
    fresh = HeadlessAdapter(restored, decision_profile=f.PROFILE).observe().decision
    history = PublicHistory()
    history.restore(anchor, fresh)
    assert history.current is fresh and history.complete
    _, _, plain = fixture(deck=deck)
    with pytest.raises(ValueError, match='History prefix'):
        PublicHistory().restore(plain, fresh)
