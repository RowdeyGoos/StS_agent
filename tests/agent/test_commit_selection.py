"""No-undo policy reachability and concrete optional/multiple selection loops."""
from copy import deepcopy
from dataclasses import replace
from itertools import permutations

import pytest

from game.agent.action_policy import ALL_LEGAL, COMMIT_SINGLE_CARD, COMMIT_CARD_SELECTION, action_mask
from game.agent.contracts import full as f
from game.agent.headless import HeadlessAdapter
from game.headless.core import choices
from game.headless.core.actions import PlayCard, ChooseCombatCard
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion
from game.headless.run.rest_site import begin_rest_site
from game.headless.monsters.overgrowth import SimpleEnemy


def fury_run(seed=2):
    run = RunEngine(seed=seed, card_ids=('neows_fury','strike','defend','bash'), rng_profile='native', config=RunConfig())
    run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=200), cards_per_turn=0)
    player = run.combat.player
    cards = {c.definition.definition_id:c for c in player.deck.all_cards()}
    player.deck.draw_pile.clear()
    player.hand.append(cards['neows_fury'])
    player.deck.discard_pile.extend(cards[n] for n in ('strike','defend','bash'))
    run.apply(PlayCard(cards['neows_fury'].instance_id,0))
    return run


def attach(run):
    return HeadlessAdapter(run, decision_profile=f.PROFILE)


def allowed(public, policy=COMMIT_CARD_SELECTION):
    return tuple(a for a, ok in zip(public.candidates, action_mask(public, policy)) if ok)


def step(adapter, kind, subject=None):
    frame = adapter.observe()
    action = next(a for a in allowed(frame.decision) if a.kind == kind and (subject is None or a.subject == subject))
    assert adapter.step(frame.binding, action.ref).status == 'reconciled'
    return adapter.observe().decision


def test_optional_fury_keeps_zero_one_and_two_confirms_and_removes_only_undo():
    run=fury_run();adapter=attach(run);initial=adapter.observe().decision
    assert all(action_mask(initial,COMMIT_CARD_SELECTION))
    assert any(a.kind=='confirm_selection' for a in allowed(initial))
    first=next(a.subject for a in initial.candidates if a.kind=='select_card')
    one=step(adapter,'select_card',first)
    assert any(a.kind=='deselect_card' for a in one.candidates)  # Native graph remains complete.
    assert all(action_mask(one,COMMIT_SINGLE_CARD))
    assert {a.kind for a in allowed(one)}=={'select_card','confirm_selection'}
    before=run.snapshot()
    assert [a.ref for a in allowed(one)]==[a.ref for a in one.candidates if a.kind!='deselect_card']
    assert run.snapshot()==before
    two=step(adapter,'select_card')
    assert [a.kind for a in allowed(two)]==['confirm_selection']
    step(adapter,'confirm_selection')
    assert run.combat.player.rules.selection is None


def test_every_native_fury_order_can_be_reached_without_undo():
    run=fury_run();player=run.combat.player;initial=deepcopy(player.rules.selection)
    pending=[initial];seen=set();orders=set()
    # Exhaust the actual bounded native slot states, including holes and LIFO reuse.
    while pending:
        state=pending.pop()
        key=(tuple(state['selected']),tuple(state.get('order_slots',())),tuple(state.get('free_slots',())))
        if key in seen: continue
        seen.add(key)
        if len(state['selected'])>=state['minimum']: orders.add(tuple(state['selected']))
        player.rules.selection=deepcopy(state)
        actions=choices.actions(player)
        for action in actions:
            if not isinstance(action,ChooseCombatCard): continue
            player.rules.selection=deepcopy(state)
            choices.toggle(player,action.instance_id)
            pending.append(deepcopy(player.rules.selection))
    expected={order for size in range(3) for order in permutations(initial['candidates'],size)}
    assert orders==expected and len(orders)==10
    names={c.instance_id:c.definition.definition_id for c in player.deck.all_cards()}
    for order in orders:
        fresh=fury_run();adapter=attach(fresh)
        public=adapter.observe().decision
        refs={n.definition_id:n.ref for n in f.walk(public.context) if n.kind=='card'}
        for identity in order: step(adapter,'select_card',refs[names[identity]])
        step(adapter,'confirm_selection')
        assert [c.definition.definition_id for c in fresh.combat.player.hand]==[names[i] for i in order]


@pytest.mark.parametrize('relic,minimum,maximum', [('kifuda',0,3),('astrolabe',3,3),('precarious_shears',2,2),('new_leaf',1,1)])
def test_relic_selectors_commit_until_separate_legal_confirmation(relic,minimum,maximum):
    run=RunEngine.campaign(seed=2);run.obtain_relic(relic);adapter=attach(run)
    initial=adapter.observe().decision
    assert (initial.context.get('minimum'),initial.context.get('maximum'))==(minimum,maximum)
    assert any(a.kind=='confirm_relic_selection' for a in allowed(initial))==(minimum==0)
    for count in range(1,maximum+1):
        public=step(adapter,'choose_relic_card')
        assert not any(a.kind=='deselect_relic_card' for a in allowed(public))
        assert any(a.kind=='confirm_relic_selection' for a in allowed(public))==(count>=minimum)
        assert any(a.kind=='choose_relic_card' for a in allowed(public))==(count<maximum)
    step(adapter,'confirm_relic_selection')
    assert not run.state.relic_work


def test_cook_preserves_cancel_and_potion_actions_without_reenabling_undo():
    run=RunEngine(config=RunConfig());run.obtain_relic('meat_cleaver')
    add_potion(run.state,'block_potion');begin_rest_site(run.state)
    adapter=attach(run);step(adapter,'use_rest_relic')
    one=step(adapter,'choose_cook_card')
    assert not any(a.kind=='deselect_cook_card' for a in allowed(one))
    assert any(a.kind=='cancel_selection' for a in allowed(one))
    assert any(a.kind=='discard_potion' for a in allowed(one))
    after=step(adapter,'discard_potion')
    assert not any(a.kind=='deselect_cook_card' for a in allowed(after))
    two=step(adapter,'choose_cook_card')
    assert {a.kind for a in allowed(two)}=={'confirm_cook','cancel_selection'}
    step(adapter,'confirm_cook');assert len(run.state.deck)==8 and run.state.max_hp==89
    other=RunEngine(config=RunConfig());other.obtain_relic('meat_cleaver');begin_rest_site(other.state)
    adapter=attach(other);step(adapter,'use_rest_relic');step(adapter,'choose_cook_card')
    step(adapter,'cancel_selection');assert other.state.pending['stage']=='options' and len(other.state.deck)==10


@pytest.mark.parametrize('indexes', [(),(1,0),tuple(range(15))])
def test_sea_glass_blocks_selected_offer_toggles_and_preserves_acquisition_order(indexes):
    run=RunEngine.campaign(seed=7);run.obtain_relic('sea_glass');adapter=attach(run)
    public=adapter.observe().decision
    assert public.context.definition_id=='card_grid'
    offers=public.context.children[0].children
    picked=tuple(offers[i] for i in indexes)
    initial_deck=len(run.state.deck)
    assert any(a.kind=='confirm_relic_selection' for a in allowed(public))
    for node in picked:
        public=step(adapter,'choose_relic_reward',node.ref)
        assert any(a.kind=='choose_relic_reward' and a.subject==node.ref for a in public.candidates)
        assert not any(a.subject in public.context.linked('selected') for a in allowed(public))
        assert any(a.kind=='confirm_relic_selection' for a in allowed(public))
    step(adapter,'confirm_relic_selection')
    assert [c.definition.definition_id for c in run.state.deck[initial_deck:]]==[n.definition_id for n in picked]


def test_preselected_attachment_commits_members_and_retains_native_hole_order():
    run=fury_run();player=run.combat.player
    a,b,c=player.rules.selection['candidates']
    for identity in (a,b,a):run.apply(ChooseCombatCard(identity))
    assert player.rules.selection['selected']==[b]
    adapter=attach(run);public=adapter.observe().decision
    assert all(action_mask(public,COMMIT_SINGLE_CARD))  # Existing policy's attachment behavior is unchanged.
    assert not any(a.kind=='deselect_card' for a in allowed(public))
    names={card.instance_id:card.definition.definition_id for card in player.deck.all_cards()}
    refs={n.definition_id:n.ref for n in f.walk(public.context) if n.kind=='card'}
    step(adapter,'select_card',refs[names[c]])
    assert player.rules.selection['selected']==[c,b]  # The engine reuses its earlier free slot.
    step(adapter,'confirm_selection')
    assert [card.instance_id for card in player.hand]==[c,b]


@pytest.mark.parametrize('change',['immediate','missing_options','boolean_bound','missing_confirm','wrong_undo','unknown_extra','wrong_context'])
def test_unknown_or_incomplete_selector_shapes_are_not_restricted(change):
    adapter=attach(fury_run());public=step(adapter,'select_card');selection=next(n for n in f.walk(public.context) if n.kind=='selection')
    if change in ('immediate','boolean_bound'):
        key,value=('manual_confirmation',False) if change=='immediate' else ('minimum',True)
        selection=replace(selection,fields=tuple(replace(v,value=value) if v.key==key else v for v in selection.fields))
    if change=='missing_options': selection=replace(selection,links=tuple(l for l in selection.links if l.key!='options'))
    context=replace(public.context,children=tuple(selection if n.kind=='selection' else n for n in public.context.children))
    public=replace(public,context=context)
    if change=='wrong_context':public=replace(public,context=replace(public.context,kind='event'))
    if change=='missing_confirm':public=replace(public,candidates=tuple(a for a in public.candidates if a.kind!='confirm_selection'))
    if change=='wrong_undo':public=replace(public,candidates=tuple(replace(a,target=a.subject) if a.kind=='deselect_card' else a for a in public.candidates))
    if change=='unknown_extra':public=replace(public,candidates=public.candidates+(f.Candidate('action:999','abandon_run'),))
    assert all(action_mask(public,COMMIT_CARD_SELECTION))


def test_reference_renaming_and_candidate_order_do_not_change_commitment():
    adapter=attach(fury_run());public=step(adapter,'select_card')
    wire=f.to_dict(public)
    def rename(value):
        if type(value) is str and ':' in value and value.split(':')[0] in f.NAMESPACES+('action',):
            prefix,ordinal=value.split(':');return prefix+':'+str(int(ordinal)+100)
        if type(value) is list:return [rename(v) for v in value]
        if type(value) is dict:return {k:rename(v) for k,v in value.items()}
        return value
    changed=rename(wire);changed['candidates'].reverse();public2=f.from_dict(changed)
    assert [a.kind for a in allowed(public2)]==[a.kind for a in reversed(allowed(public))]
