"""Semantics and ownership boundaries of search-only speed optimizations."""
from dataclasses import dataclass, field, replace

import pytest

torch = pytest.importorskip('torch')
from game.agent.contracts import full as f
from game.agent.headless.full_cards import cached_static, public_static, _immutable_static
from game.agent.headless.errors import UnsupportedProfile
from game.agent.training.features import FeatureEncoder
from game.agent.training.checkpoint import CheckpointPolicy
from game.agent.training.model import ActorCritic, Architecture
from game.agent.training.search_run import OBJECTIVE
from game.agent.search import SearchPolicy, SearchConfig
from game.agent.input_views import apply_view, DETACHED_HISTORY
from .test_training_model import decision, Vocabulary, cpu_threads
from .test_inference_features import same_features


def base_policy(public=None):
    public = public or decision()
    model = ActorCritic(Vocabulary.fit([public], split='train'), Architecture(16, 1), seed=5)
    return CheckpointPolicy(model, OBJECTIVE, 'speed-fixture', {})


def test_static_cache_uses_all_fields_and_exact_types_and_revalidates():
    @dataclass(frozen=True)
    class Content:
        amount: object = field(compare=False)
    _immutable_static.cache_clear()
    for value in (1, 9, True, (1,), (True,)):
        obj = Content(value)
        actual = cached_static(obj, 'mechanic', 'Content')
        assert actual == public_static(obj, 'mechanic', 'Content')
        if type(value) is not tuple:
            assert type(actual.get('amount')) is type(value)
        else:
            assert type(actual.children[0].get('0')) is type(value[0])
    with pytest.raises(UnsupportedProfile):
        cached_static(Content([]), 'mechanic', 'Content')
    @dataclass
    class Mutable:
        amount: int = 1
    obj = Mutable()
    assert cached_static(obj,'mechanic','Mutable').get('amount') == 1
    obj.amount = 2
    assert cached_static(obj,'mechanic','Mutable').get('amount') == 2
    assert _immutable_static.cache_info().maxsize == 2048


def test_prepared_feature_ownership_view_capacity_and_hook_parity(monkeypatch):
    from .test_input_views import historical_decision
    from game.agent.encoding.full import FullRunProfile, FullRunEncoder
    from game.agent.encoding.schema import CapacityError
    public = historical_decision()
    encoder = FeatureEncoder(Vocabulary.fit([public], split='train'), input_view=DETACHED_HISTORY)
    owner = f.PreparedPublic(public)
    same_features(encoder.encode(public).for_rollout(), encoder.encode_prepared(owner.value, owner))
    viewed = apply_view(owner.value,DETACHED_HISTORY)
    assert apply_view(viewed,DETACHED_HISTORY) is viewed
    with pytest.raises(f.ContractError):
        encoder.encode_prepared(replace(owner.value),owner)
    encoder.public.profile = FullRunProfile(nodes=1)
    with pytest.raises(CapacityError):
        encoder.encode_prepared(owner.value,owner)
    seen=[]
    class Custom(FullRunEncoder):
        def pack(self,value):
            seen.append(value)
            return super().pack(value)
    encoder.public=Custom()
    encoder.encode_prepared(owner.value,owner)
    assert len(seen)==1
    # Instance inference hooks that delegate to the original must not recurse.
    encoder.public=FullRunEncoder()
    original=encoder.encode_inference
    monkeypatch.setattr(encoder,'encode_inference',lambda value:(seen.append(value),original(value))[1])
    encoder.encode_prepared(owner.value,owner)
    assert len(seen)==2


def test_prediction_cache_uses_typed_full_public_inputs_and_returns_copies():
    base = base_policy()
    search = SearchPolicy(base)
    search._prediction_cache = {}
    search.prediction_cache_stats = dict(hits=0,misses=0,peak_entries=0)
    def observation(value):
        public=decision()
        return replace(public,run=replace(public.run,fields=(*public.run.fields,f.Field('probe',value))))
    integer, boolean = observation(1), observation(True)
    assert integer == boolean  # Dataclass equality alone would be unsafe.
    for public in (integer,boolean,replace(integer,candidates=integer.candidates[::-1]),observation(2)):
        expected = base.probabilities(public)
        actual = search._predict(public)
        assert actual == expected
    assert search.prediction_cache_stats['misses']==4
    first = search._predict(integer)
    first[0].clear()
    assert search._predict(integer) == base.probabilities(integer)
    assert search.prediction_cache_stats['hits']==2
    for index in range(130):
        search._predict(observation(index+10))
    assert len(search._prediction_cache)==search.prediction_cache_stats['peak_entries']==128


@pytest.mark.parametrize('hook', ['policy','codec','encoder','trainable','forward'])
def test_custom_or_trainable_provider_disables_prediction_reuse(hook):
    base=base_policy()
    if hook=='policy':
        original=base.probabilities
        base.probabilities=lambda value: original(value)
    elif hook=='codec':
        original=base.encoder.public.pack
        base.encoder.public.pack=lambda value: original(value)
    elif hook=='encoder':
        original=base.encoder.encode_inference
        base.encoder.encode_inference=lambda value: original(value)
    elif hook=='trainable':
        base.model.requires_grad_(True)
    else:
        base.model.register_forward_hook(lambda *args: None)
    search=SearchPolicy(base,SearchConfig(simulations=1))
    search.choose(decision())  # Unsupported public fixture still exercises root inference.
    assert search.prediction_cache_stats == dict(hits=0,misses=0,peak_entries=0)
    assert search._prediction_cache is None


def test_cached_search_preserves_private_rng_boundary_and_independent_rollouts():
    from .test_search import fixture
    from game.agent.headless import HeadlessAdapter
    run, adapter=fixture(('strike','defend')*5)
    first=adapter.observe().decision
    config=SearchConfig(simulations=16,max_depth=3,leaf_rollout_steps=3,time_limit=60,seed=12)
    base=base_policy(first)
    before=run.snapshot()
    cached=SearchPolicy(base,config)
    left=cached.choose(first)
    assert run.snapshot()==before
    assert cached.prediction_cache_stats['hits']>0
    run.combat.player.deck.draw_pile.reverse()
    run.combat.rng.random()
    run.combat.player.deck.target_rng.random()
    second=HeadlessAdapter(run,decision_profile=f.PROFILE).observe().decision
    before=run.snapshot()
    original=base.probabilities
    base.probabilities=lambda value: original(value)  # Disable prediction reuse.
    right=SearchPolicy(base,config).choose(second)
    for key in ('action_ref','probabilities','values','visits','simulations','reason','cutoff','leaf_work','tree_work'):
        assert getattr(left,key)==getattr(right,key),key
    assert run.snapshot()==before


def test_prediction_cache_preserves_structural_reference_order():
    from dataclasses import make_dataclass
    public=decision()
    context=replace(public.context,links=(f.Link('order',('card:1','card:0')),))
    keys=('children','links','kind','definition_id','ref','fields')
    custom=make_dataclass('ReorderedNode',[(k,object) for k in keys],frozen=True,
        namespace={'get':f.Node.get,'linked':f.Node.linked})
    public=replace(public,context=custom(**{k:getattr(context,k) for k in keys}))
    base=base_policy(public)
    search=SearchPolicy(base)
    search._prediction_cache={}
    search.prediction_cache_stats=dict(hits=0,misses=0,peak_entries=0)
    assert search._predict(public)==base.probabilities(public)
    assert search._prediction_cache=={}


def test_prepared_policy_preserves_duck_typed_encoder():
    from types import SimpleNamespace
    public=decision();base=base_policy(public)
    expected=base.probabilities(public)
    base.encoder=SimpleNamespace(encode_inference=base.encoder.encode_inference)
    owner=f.PreparedPublic(public)
    assert base.probabilities_prepared(owner.value,owner)==expected


def test_skipped_examples_still_validate_catalog_and_action_policy():
    from types import SimpleNamespace
    from game.agent.training.learner import _corpus_from_episodes
    public=decision();encoder=FeatureEncoder(Vocabulary.fit([public],split='train'))
    public=replace(public,context=replace(public.context,children=(*public.context.children,
        f.Node('card','unregistered-card'))))
    transition=SimpleNamespace(observation=public,action=public.candidates[0])
    step=SimpleNamespace(transition=transition,reward=0.)
    episode=SimpleNamespace(reward_spec=OBJECTIVE,transitions=[step],ending=SimpleNamespace(terminated=False))
    with pytest.raises(ValueError,match='Unknown learned entity identity'):
        _corpus_from_episodes([episode],encoder,split='train',compact=True,selected=[False])


def test_custom_search_does_not_import_optional_inference_stack(monkeypatch):
    import builtins
    from .test_search import UniformPolicy, fixture
    _,adapter=fixture(('strike','defend'),enemy_hp=1)
    original=builtins.__import__
    def checked(name,*args,**kwargs):
        assert name not in ('game.agent.training.checkpoint','game.agent.training.features',
                            'game.agent.training.model','torch'),name
        return original(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',checked)
    result=SearchPolicy(UniformPolicy(),SearchConfig(simulations=2,time_limit=60)).choose(adapter.observe().decision)
    assert result.reason is None
