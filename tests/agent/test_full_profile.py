"""Full public surface: command census, rare branches and adversarial views."""
from copy import deepcopy
from dataclasses import is_dataclass, replace

import pytest
np = pytest.importorskip('numpy')

from game.agent import contracts as c
from game.agent.contracts import full as f
from game.agent.encoding.full import FullRunEncoder, FullRunProfile
from game.agent.full_policy import choose_action
from game.agent.headless import HeadlessAdapter, AdapterFault
from game.agent.headless.full_cards import card_node
from game.agent.headless.full_projection import COMMANDS, Presentation
from game.headless.core import actions as ca
from game.headless.run import actions as ra
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion, add_relic
from game.headless.run.state import RunPhase

ENCODER = FullRunEncoder()


def attach(run):
    return HeadlessAdapter(run, decision_profile=f.PROFILE)


def check(adapter, *, encode=True):
    before = adapter._engine.snapshot()
    frame = adapter.observe()
    assert adapter.observe() is frame
    visible, pending, visited = set(), [adapter], set()
    while pending:
        twin = pending.pop()
        if twin._opened in visited:
            continue
        visited.add(twin._opened)
        twin.observe()
        for ref, command in tuple(twin._commands.items()):
            if isinstance(command, Presentation):
                child = deepcopy(twin)
                child.step(child._frame.binding, ref)
                pending.append(child)
            else:
                visible.add(command)
    assert visible == set(adapter._engine.legal_actions())
    assert len(frame.decision.candidates) == len(adapter._commands)
    assert f.loads(f.dumps(frame.decision)) == frame.decision
    if encode:
        encoded = ENCODER.encode(frame.decision)
        prepared = ENCODER.encode_prepared(frame.decision, adapter.prepared_for(frame.decision))
        assert prepared.candidate_refs == encoded.candidate_refs
        assert prepared.reference_refs == encoded.reference_refs
        assert all(np.array_equal(v, prepared.observation[k]) for k, v in encoded.observation.items())
        decoded = ENCODER.decode(encoded.observation)
        reencoded = ENCODER.encode(decoded)
        assert all(np.array_equal(v, reencoded.observation[k]) for k, v in encoded.observation.items())
        assert set(encoded.candidate_refs) == {a.ref for a in frame.decision.candidates}
    assert adapter._engine.snapshot() == before
    return frame


def dispatch(adapter, command=None, *, encode=True):
    frame = check(adapter, encode=encode)
    if command is None:
        candidate = choose_action(frame.decision)
        command = adapter._commands[candidate.ref]
    else:
        if command not in adapter._commands.values():
            for ref, presentation in tuple(adapter._commands.items()):
                if isinstance(presentation, Presentation):
                    twin = deepcopy(adapter)
                    twin.step(twin._frame.binding, ref)
                    twin.observe()
                    if command in twin._commands.values():
                        adapter.step(frame.binding, ref)
                        frame = adapter.observe()
                        break
        candidate = next(a for a in frame.decision.candidates if adapter._commands[a.ref] == command)
    twin = deepcopy(adapter._engine)
    if not isinstance(command, Presentation):
        twin.apply(command)
    assert adapter.step(frame.binding, candidate.ref).status == 'reconciled'
    assert adapter._engine.snapshot() == twin.snapshot()
    assert adapter.step(frame.binding, candidate.ref).reason == 'stale_decision'
    return type(command)


def first(adapter, command_type, **matching):
    return next(a for a in adapter._engine.legal_actions() if type(a) is command_type
                and all(getattr(a, key) == value for key, value in matching.items()))


def act(adapter, command_type, **matching):
    return dispatch(adapter, first(adapter, command_type, **matching))


def finish_choices(adapter, seen=None, limit=100):
    run = adapter._engine
    for _ in range(limit):
        if run.combat or not run.state.relic_work and run.state.phase in (RunPhase.ROUTE, RunPhase.ACT_COMPLETE, RunPhase.VICTORY, RunPhase.DEFEAT):
            return
        cls = dispatch(adapter, encode=False)
        if seen is not None:
            if cls is not Presentation:
                seen.add(cls)
    pytest.fail('Choice continuation exceeded its controlled test bound')


def test_command_inventory_matches_every_engine_command():
    classes = {value for module in (ca, ra) for value in vars(module).values()
               if isinstance(value, type) and is_dataclass(value) and value.__module__ == module.__name__}
    assert classes == set(COMMANDS)
    assert set(COMMANDS.values()) <= set(f.ACTIONS)


def test_every_card_level_projects_without_per_card_registration():
    from game.headless.cards.catalog import DEFAULT_CARDS, CardCatalog
    from game.headless.cards.base import CardDefinition
    for definition in DEFAULT_CARDS.definitions:
        for level in range(len(definition.levels)):
            card_node(DEFAULT_CARDS.create(definition.definition_id, upgrade_level=level))
    original = DEFAULT_CARDS.definition('strike')
    custom = replace(original, definition_id='test_existing_attack_mechanic')
    from game.headless.cards.base import Card
    assert card_node(Card(custom)).definition_id == custom.definition_id


def test_all_command_classes_have_real_dispatch_fixtures():
    from tests.agent.test_headless_adapter import fury_game
    from game.headless.run import rest_site, shop, treasure, events, rewards
    from game.headless.run.ancient import PROFILE
    seen = set()
    a = attach(fury_game())
    seen.add(act(a, ca.PlayCard))
    seen.add(act(a, ca.ChooseCombatCard))
    # Select, deselect and explicit zero-card confirmation.
    selected = a._engine.combat.player.rules.selection['selected'][0]
    seen.add(dispatch(a, ca.ChooseCombatCard(selected)))
    seen.add(act(a, ca.ConfirmCombatSelection))
    seen.add(act(a, ca.EndTurn))
    run = RunEngine(config=RunConfig())
    add_potion(run.state, 'fire_potion')
    add_potion(run.state, 'block_potion')
    run.start_combat()
    a = attach(run)
    seen.add(act(a, ra.UsePotion))
    seen.add(act(a, ra.DiscardPotion))

    run = RunEngine.act1(seed=0, ancient_profile=PROFILE)
    a = attach(run)
    seen.add(act(a, ra.ChooseAncientRelic))
    finish_choices(a, seen)
    seen.add(act(a, ra.ChooseNode))

    for option in (ra.Rest, ra.Smith, ra.Hatch, ra.Lift, ra.Dig, ra.UseRestRelic):
        run = RunEngine(config=RunConfig(), card_ids=('strike', 'strike', 'defend', 'byrdonis_egg'))
        for relic in ('girya', 'shovel', 'meat_cleaver'):
            add_relic(run.state, relic, cards=run.cards)
        rest_site.begin_rest_site(run.state)
        a = attach(run)
        seen.add(act(a, option))
        if option is ra.Smith:
            seen.add(dispatch(a, ra.ChooseUpgrade(None)))
            act(a, ra.Smith)
            seen.add(act(a, ra.ChooseUpgrade, instance_id=run.state.deck[0].instance_id))
        if option is ra.UseRestRelic:
            seen.add(dispatch(a, ra.ChooseCookCard(None)))
            act(a, ra.UseRestRelic)
            seen.add(act(a, ra.ChooseCookCard, instance_id=run.state.deck[0].instance_id))
            seen.add(act(a, ra.ChooseCookCard, instance_id=run.state.deck[1].instance_id))
            seen.add(act(a, ra.ConfirmCook))
        finish_choices(a, seen)
        assert not run.state.relic_work
        if ra.LeaveRest() in run.legal_actions():
            seen.add(act(a, ra.LeaveRest))

    run = RunEngine(gold=2000, config=RunConfig())
    shop.begin(run.state, run.cards)
    a = attach(run)
    seen.add(act(a, ra.BuyShopItem))
    seen.add(act(a, ra.BeginShopRemoval))
    seen.add(dispatch(a, ra.ChooseShopRemoval(None)))
    act(a, ra.BeginShopRemoval)
    seen.add(act(a, ra.ChooseShopRemoval, instance_id=run.state.deck[0].instance_id))
    seen.add(act(a, ra.LeaveShop))

    run = RunEngine(config=RunConfig())
    treasure.begin(run.state)
    a = attach(run)
    seen.add(act(a, ra.OpenChest))
    seen.add(act(a, ra.ClaimTreasureRelic))
    finish_choices(a, seen)
    if ra.LeaveTreasure() in run.legal_actions():
        seen.add(act(a, ra.LeaveTreasure))

    run = RunEngine(config=RunConfig(), seed=2)
    for relic in ('white_beast_statue', 'prayer_wheel', 'driftwood', 'paels_wing'):
        add_relic(run.state, relic, cards=run.cards)
    rewards.begin_combat_rewards(run.state, run.cards, encounter_id='overgrowth_bygone_effigy', extra_cards=1)
    a = attach(run)
    for cls in (ra.ClaimGold, ra.ClaimPotion, ra.ClaimRelic):
        seen.add(act(a, cls))
        while run.state.relic_work:
            seen.add(dispatch(a))
    seen.add(act(a, ra.RerollCardReward, index=-1))
    seen.add(act(a, ra.ChooseRewardCard))
    seen.add(act(a, ra.SacrificeCardReward))
    # An independent extra reward for its non-skip action.
    run2 = RunEngine(config=RunConfig(), seed=2)
    rewards.begin_combat_rewards(run2.state, run2.cards, extra_cards=1)
    b = attach(run2)
    seen.add(act(b, ra.ChooseExtraReward))
    seen.add(act(a, ra.LeaveRewards))

    for relic in ('dollys_mirror', 'orrery'):
        run = RunEngine(config=RunConfig())
        run.obtain_relic(relic)
        a = attach(run)
        if relic == 'dollys_mirror':
            seen.add(act(a, ra.ChooseRelicCard))
            seen.add(act(a, ra.ConfirmRelicSelection))
        else:
            seen.add(act(a, ra.ChooseRelicReward))

    run = RunEngine(config=RunConfig(), gold=1000)
    events.begin(run.state, 'aroma_of_chaos', cards=run.cards)
    a = attach(run)
    seen.add(act(a, ra.ChooseEventOption))
    seen.add(act(a, ra.ChooseEventCard))
    seen.add(act(a, ra.LeaveEvent))

    from tests.headless.test_act2_run import complete_act
    run = RunEngine.campaign(seed=2)
    run.state.hp = run.state.max_hp = 10000  # Explicit controlled endpoint fixture.
    complete_act(run)
    a = attach(run)
    seen.add(act(a, ra.ContinueAct))
    assert seen == set(COMMANDS), {t.__name__ for t in set(COMMANDS) - seen}


from game.headless.events.catalog import EVENTS


@pytest.mark.parametrize('name', EVENTS)
def test_every_event_initial_branch_and_nested_continuation(name):
    from game.headless.run import events
    from tests.headless.test_act2_run import win
    run = RunEngine(seed=7, config=RunConfig(), gold=1000)
    run.state.act_index = 1
    add_potion(run.state, 'foul_potion')
    events.begin(run.state, name, cards=run.cards)
    initial = list(events.legal_actions(run.state))
    for action in initial:
        trial = deepcopy(run)
        a = attach(trial)
        dispatch(a, action)
        for i in range(80):
            if trial.combat:
                check(a)
                win(trial)  # Controlled combat boundary, not policy victory evidence.
                a = attach(trial)
            if not trial.state.relic_work and trial.state.phase in (RunPhase.ROUTE, RunPhase.VICTORY, RunPhase.DEFEAT):
                break
            dispatch(a, encode=i == 0)
        else:
            pytest.fail('Event did not finish: ' + name)


@pytest.mark.parametrize('relic', ['sea_glass', 'scroll_boxes', 'lost_coffer', 'precise_scissors',
                                  'precarious_shears', 'claws', 'paels_tooth', 'toy_box'])
def test_relic_grid_bundle_queue_and_multiple_selections(relic):
    run = RunEngine(seed=7, config=RunConfig())
    run.obtain_relic(relic)
    a = attach(run)
    check(a)
    finish_choices(a)
    assert not run.state.relic_work


def test_draw_selector_permutation_and_private_identity_are_not_features():
    from game.headless.monsters.overgrowth import SimpleEnemy
    run = RunEngine(card_ids=('secret_weapon', 'strike', 'bash', 'iron_wave', 'pommel_strike'))
    run.start_combat(cards_per_turn=0, enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    p = run.combat.player
    card = next(c for c in p.deck.draw_pile if c.definition.definition_id == 'secret_weapon')
    p.deck.draw_pile.remove(card)
    p.hand.append(card)
    other = deepcopy(run)
    other.combat.player.deck.draw_pile.reverse()
    run.apply(ca.PlayCard(card.instance_id))
    other.apply(ca.PlayCard(card.instance_id))
    a, b = attach(run), attach(other)
    da, db = check(a).decision, check(b).decision
    assert f.dumps(da) == f.dumps(db)
    sa = next(n for n in f.walk(da.context) if n.kind == 'selection')
    assert sa.get('destination') == 'hand' and sa.linked('source')
    ea, eb = ENCODER.encode(da), ENCODER.encode(db)
    assert all(np.array_equal(ea.observation[k], eb.observation[k]) for k in ea.observation)


def test_reward_visibility_modal_ownership_reroll_and_stale_capability():
    from game.headless.run.rewards import begin_combat_rewards
    run = RunEngine(seed=3, config=RunConfig())
    run.obtain_relic('prayer_wheel')
    run.obtain_relic('driftwood')
    begin_combat_rewards(run.state, run.cards)
    a = attach(run)
    frame = check(a)
    cards = [n for n in f.walk(frame.decision.context) if n.kind == 'card']
    assert not cards
    assert all(c.kind != 'choose_reward_card' for c in frame.decision.candidates)
    opened = next(c for c in frame.decision.candidates if c.kind == 'open_reward')
    before = run.snapshot()
    a.step(frame.binding, opened.ref)
    assert run.snapshot() == before
    child = check(a)
    assert {c.kind for c in child.decision.candidates} == {'choose_reward_card', 'skip_reward', 'reroll_card_reward', 'close_reward'}
    assert len([n for n in f.walk(child.decision.context) if n.kind == 'card']) == 3
    act(a, ra.RerollCardReward, index=-1)
    assert a.step(child.binding, child.decision.candidates[0].ref).reason == 'stale_decision'
    current = a.observe()
    close = next(c for c in current.decision.candidates if c.kind == 'close_reward')
    a.step(current.binding, close.ref)
    assert not [n for n in f.walk(a.observe().decision.context) if n.kind == 'card']


def test_hidden_chest_and_future_relic_queue_do_not_change_public_features():
    from game.headless.run import treasure
    run = RunEngine(seed=2, config=RunConfig())
    treasure.begin(run.state)
    other = deepcopy(run)
    other.state.pending['relic_id'] = 'anchor' if run.state.pending['relic_id'] != 'anchor' else 'vajra'
    assert f.dumps(attach(run).observe().decision) == f.dumps(attach(other).observe().decision)
    run = RunEngine(config=RunConfig())
    run.obtain_relic('orrery')
    other = deepcopy(run)
    other.state.relic_work[1]['offers'].reverse()
    assert f.dumps(attach(run).observe().decision) == f.dumps(attach(other).observe().decision)


def test_crystal_sphere_hidden_cells_excluded_visible_fragments_preserved():
    from game.headless.run import events
    run = RunEngine(seed=7, config=RunConfig(), gold=1000)
    run.state.act_index = 1
    events.begin(run.state, 'crystal_sphere', cards=run.cards)
    run.apply(ra.ChooseEventOption(run.state.pending['event_instance_id'], 'payment_plan'))
    before = attach(run).observe().decision
    twin = deepcopy(run)
    board = twin.state.pending['data']['pages'][-1]['context']['board']
    for item in board['items']:
        item['kind'] = 'hidden_sentinel'
        item['subscriptions'] += 10
    assert f.dumps(before) == f.dumps(attach(twin).observe().decision)
    board = run.state.pending['data']['pages'][-1]['context']['board']
    x, y = next(item['cells'][0] for item in board['items'] if item['cells'])
    run.apply(ra.ChooseEventOption(run.state.pending['event_instance_id'], f'small_{x}_{y}'))
    after = check(attach(run)).decision
    assert any(n.kind == 'cell' and n.get('x') == x and n.get('y') == y and n.definition_id != 'empty' for n in f.walk(after.context))


@pytest.mark.parametrize('name,key', [('sunken_treasury', 'small'), ('sunken_treasury', 'large')])
def test_visible_event_amounts(name, key):
    from game.headless.run import events
    run = RunEngine(seed=7, config=RunConfig())
    events.begin(run.state, name, cards=run.cards)
    decision = check(attach(run)).decision
    assert decision.context.get(key) == run.state.pending['data']['pages'][-1]['context'][key]


def test_offered_ancient_card_and_character_payloads():
    from game.headless.run import events
    for name, option in (('darv', 'dusty_tome'), ('orobas', 'sea_glass')):
        for seed in range(30):
            run = RunEngine(seed=seed, config=RunConfig())
            run.state.act_index = 1
            events.begin(run.state, name, cards=run.cards)
            context = run.state.pending['data']['pages'][-1]['context']
            if option in context['options']:
                break
        else:
            pytest.fail('No controlled Ancient offer seed')
        d = check(attach(run)).decision
        if name == 'darv':
            assert any(n.definition_id == context['tome_card'] and n.kind == 'card' for n in f.walk(d.context))
        else:
            assert d.context.get('sea_glass_family') == context['family']


def test_effective_strength_nightmare_and_relic_counter():
    from game.headless.monsters.overgrowth import SimpleEnemy
    run = RunEngine(config=RunConfig(character='silent'), card_ids=('dark_shackles', 'nightmare', 'strike', 'defend'))
    run.obtain_relic('metronome')
    run.start_combat(cards_per_turn=10, energy_per_turn=10, enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    a = attach(run)
    p = run.combat.player
    shackles = next(c for c in p.hand if c.definition.definition_id == 'dark_shackles')
    dispatch(a, ca.PlayCard(shackles.instance_id, 0))
    enemy = next(n for n in f.walk(a.observe().decision.context) if n.kind == 'enemy')
    assert enemy.get('strength') == -9
    nightmare = next(c for c in p.hand if c.definition.definition_id == 'nightmare')
    dispatch(a, ca.PlayCard(nightmare.instance_id))
    selected = next(c for c in p.hand if c.definition.definition_id == 'strike')
    act(a, ca.ChooseCombatCard, instance_id=selected.instance_id)
    act(a, ca.ConfirmCombatSelection)
    power = next(n for n in f.walk(a.observe().decision.context) if n.kind == 'power' and n.definition_id == 'nightmare')
    assert power.get('selected_definition_id') == 'strike'
    from game.headless.core.resolution import push, drain
    push(p, ['orb_channel', 'lightning'])
    drain(p)
    run.sync_combat_loot()
    d = check(a).decision
    relic = next(n for n in f.walk(d.run) if n.kind == 'relic' and n.definition_id == 'metronome')
    assert relic.get('show_counter') and relic.get('display_counter') == 1


def test_fur_coat_public_map_marks():
    from game.headless.relics.ancient_map import update
    run = RunEngine.campaign(seed=3)
    run.obtain_relic('fur_coat')
    update(run)
    d = check(attach(run)).decision
    expected = set(map(tuple, next(r for r in run.state.relics if r.definition_id == 'fur_coat').data['coordinates']))
    actual = {(n.get('row'), n.get('column')) for n in f.walk(d.run) if n.kind == 'node' and n.get('fur_coat_marked')}
    assert actual == expected and len(actual) == 7


def test_trial_confirmation_reports_abandonment():
    from game.headless.run import events
    run = RunEngine(config=RunConfig())
    events.begin(run.state, 'trial', cards=run.cards)
    a = attach(run)
    for label in ('reject', 'double_down'):
        act(a, ra.ChooseEventOption, option_id=label)
    frame = check(a)
    abandon = next(c for c in frame.decision.candidates if c.kind == 'abandon_run')
    a.step(frame.binding, abandon.ref)
    assert a.observe() == c.RunOutcome('sts_run_outcome_v1', 'abandoned', 'none')


def test_capacity_and_malformed_full_contract_fail_closed():
    from game.agent.encoding import CapacityError
    run = RunEngine.campaign(seed=0)
    d = attach(run).observe().decision
    with pytest.raises(CapacityError):
        FullRunEncoder(FullRunProfile(nodes=10)).encode(d)
    wire = f.to_dict(d)
    wire['schema'] = 'sts_public_decision_v99'
    with pytest.raises(c.ContractError):
        f.from_dict(wire)
    wire = f.to_dict(d)
    wire['candidates'][0]['subject'] = 'node:999999'
    with pytest.raises(c.ContractError):
        f.from_dict(wire)


def test_repeated_identical_orrery_offer_has_new_identity_after_acquisition():
    run = RunEngine(seed=0, config=RunConfig())
    run.obtain_relic('orrery')
    a = attach(run)
    for _ in range(3):
        dispatch(a, ra.ChooseRelicReward(None))
    frame = check(a)
    claim = next(c for c in frame.decision.candidates if a._commands[c.ref] == ra.ChooseRelicReward(0))
    acquired = next(n for n in f.walk(frame.decision.context) if n.ref == claim.subject)
    a.step(frame.binding, claim.ref)
    after = check(a).decision
    matches = [n for n in f.walk(after.context) if n.kind == 'card' and n.definition_id == acquired.definition_id]
    assert matches and all(n.ref != acquired.ref for n in matches)
    assert any(n.ref == acquired.ref for n in f.walk(after.run))


def test_hopper_returned_reward_preserves_exact_upgrade():
    from tests.headless.test_hive import start, kill
    run = start('thieving_hopper', ('inflame', 'strike', 'defend'), draw=0)
    original = next(c for c in run.state.deck if c.definition.definition_id == 'inflame')
    original.upgrade()
    run.apply(ca.EndTurn())
    kill(run, run.combat.enemies[0])
    run.finish_combat()
    a = attach(run)
    d = check(a).decision
    card = next(n for n in f.walk(d.context) if n.definition_id == 'inflame')
    assert card.get('upgrade_level') == 1
    action = next(c for c in d.candidates if c.target == card.ref)
    a.step(a.observe().binding, action.ref)
    after = check(a).decision
    assert any(n.ref == card.ref and n.get('upgrade_level') == 1 for n in f.walk(after.run))


def test_relic_labels_hide_hook_memory_and_clamp_displayed_counters():
    from game.headless.monsters.overgrowth import SimpleEnemy
    run = RunEngine(config=RunConfig())
    for name in ('metronome', 'kunai', 'self_forming_clay', 'mini_regent', 'emotion_chip', 'silver_crucible'):
        add_relic(run.state, name, cards=run.cards)
    run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    r = run.combat.player.rules
    relics = {x.definition_id: x for x in run.state.relics}
    for name, data in (('metronome', {'count': 8}), ('kunai', {'turn_attacks': 5}),
                       ('self_forming_clay', {'next_block': 6}), ('emotion_chip', {'damaged': True})):
        r.relic_data[relics[name].instance_id].update(data)
    d = check(attach(run)).decision
    labels = {n.definition_id: n for n in f.walk(d.run) if n.kind == 'relic'}
    assert labels['metronome'].get('display_counter') is None
    assert labels['kunai'].get('display_counter') == 2 and labels['kunai'].get('status') == 'active'
    assert labels['silver_crucible'].get('display_counter') == 3
    assert labels['emotion_chip'].get('status') == 'active'
    assert any(n.kind == 'power' and n.definition_id == 'self_forming_clay' and n.get('amount') == 6 for n in f.walk(d.context))
    twin = deepcopy(run)
    tr = twin.combat.player.rules
    tr.relic_data[relics['metronome'].instance_id]['count'] = 9
    tr.relic_data[relics['mini_regent'].instance_id]['turn_plays'] = 999
    tr.relic_data[relics['emotion_chip'].instance_id]['previous_damage'] = True
    next(x for x in twin.state.relics if x.definition_id == 'silver_crucible').data['treasures'] = 99
    assert f.dumps(d) == f.dumps(check(attach(twin)).decision)


def test_power_labels_and_void_form_costs_exclude_private_sentinels():
    run = RunEngine(config=RunConfig(character='regent'), card_ids=('strike', 'strike', 'defend'))
    run.start_combat(cards_per_turn=1)
    p = run.combat.player
    p.rules.powers.update(void_form=2, orbit=1, feral=2, tender=3, monologue=2, toric_toughness=1)
    p.rules.auxiliaries.update(void_form=999999999, orbit=5, feral=7, tender=2, monologue=4, toric_toughness=15)
    d = check(attach(run)).decision
    assert '999999999' not in f.dumps(d)
    powers = {n.definition_id: n for n in f.walk(d.context) if n.kind == 'power'}
    expected = {'orbit': ('energy_until_refund', 3), 'feral': ('returns_remaining', 0),
                'tender': ('cards_played', 2), 'monologue': ('strength_applied', 4),
                'toric_toughness': ('block', 15)}
    for name, (label, amount) in expected.items():
        assert powers[name].children == (f.Node('counter', label, fields=(f.Field('amount', amount),)),)
    p.rules.auxiliaries['void_form'] = 0
    active = check(attach(run)).decision
    piles = {n.definition_id: n for n in f.walk(active.context) if n.kind == 'pile'}
    assert all(n.get('energy') == 0 for n in piles['hand'].children)
    assert all(n.get('energy') == 1 for n in piles['draw'].children)
    twin = deepcopy(run)
    twin.combat.player.rules.auxiliaries.update(orbit=9, feral=12)
    assert f.dumps(active) == f.dumps(check(attach(twin)).decision)


def test_dampen_and_unobserved_power_pile_preserve_public_information_boundary():
    from tests.headless.test_glory import start
    run = start('knights', ('strike', 'defend'))
    strike = next(c for c in run.combat.player.hand if c.definition.definition_id == 'strike')
    strike.upgrade()
    run.apply(ca.EndTurn())
    run.apply(ca.EndTurn())
    d = check(attach(run)).decision
    assert any(n.kind == 'power' and n.definition_id == 'dampen' for n in f.walk(d.context))
    assert 'dampened_levels' not in f.dumps(d)
    twin = RunEngine()
    twin.restore(run.snapshot())
    for card in twin.combat.player.deck.all_cards():
        card.combat_state.dampened_levels = 0
    private_power = run.cards.create('inflame')
    twin.combat.player.deck._ensure_identity(private_power)
    twin.combat.player.deck.powers.append(private_power)
    assert f.dumps(d) == f.dumps(check(attach(twin)).decision)


def test_maximum_contract_depth_and_outcome_codec_round_trip():
    leaf = f.Node('leaf', 'leaf')
    for _ in range(24):
        leaf = f.Node('branch', 'branch', children=(leaf,))
    d = f.PublicDecision(f.SCHEMA, f.PROFILE, f.Node('run', 'run'), leaf,
                         (f.Candidate('action:1', 'end_turn'),))
    decoded = ENCODER.decode(ENCODER.encode(d).observation)
    assert f.loads(f.dumps(decoded)) == decoded
    with pytest.raises(c.ContractError):
        f.to_dict(replace(d, context=f.Node('branch', 'branch', children=(leaf,))))
    outcome = c.RunOutcome('sts_run_outcome_v1', 'victory', 'none')
    assert f.loads(f.dumps(outcome)) == outcome
    assert ENCODER.decode(ENCODER.encode(outcome).observation) == outcome


from game.headless.potions.base import POTIONS


@pytest.mark.parametrize('name', POTIONS)
def test_every_potion_and_its_suspended_choices(name):
    from game.headless.monsters.overgrowth import SimpleEnemy
    run = RunEngine(config=RunConfig(), card_ids=('strike', 'defend', 'bash', 'armaments', 'defend'))
    add_potion(run.state, name)
    run.start_combat(cards_per_turn=3, enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    # These potion selectors require a nonempty discard/exhaust pile.
    p = run.combat.player
    card = p.deck.draw_pile.pop()
    p.deck.exhaust_pile.append(card)
    card = p.deck.draw_pile.pop()
    p.deck.discard_pile.append(card)
    a = attach(run)
    cls = ra.DiscardPotion if POTIONS[name].usage == 'automatic' else ra.UsePotion
    act(a, cls)
    for _ in range(30):
        frame = check(a)
        if not p.rules.selection and not p.pending_play:
            break
        source = next(n for n in f.walk(frame.decision.context) if n.kind == 'selection')
        assert source.linked('source')
        dispatch(a)
    else:
        pytest.fail('Potion selector exceeded bound')


@pytest.mark.parametrize('character,name', [('ironclad', 'burning_pact'), ('silent', 'prepared'),
                                           ('regent', 'foregone_conclusion'), ('necrobinder', 'snap'),
                                           ('defect', 'hologram')])
def test_character_selectors_use_exact_instances(character, name):
    from game.headless.monsters.overgrowth import SimpleEnemy
    run = RunEngine(config=RunConfig(character=character), card_ids=(name, 'strike', 'defend', 'bash', 'defend'))
    run.start_combat(cards_per_turn=10, energy_per_turn=20, enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    p = run.combat.player
    p.rules.stars = 20
    p.deck.discard_pile.append(p.hand.pop())
    a = attach(run)
    card = next(c for c in p.hand if c.definition.definition_id == name)
    dispatch(a, ca.PlayCard(card.instance_id, 0 if card.spec.uses_target else None))
    for _ in range(30):
        check(a)
        if not p.rules.selection and not p.pending_play:
            break
        dispatch(a)
    else:
        pytest.fail('Character selector exceeded bound')


def test_large_deck_mask_capacity_and_hidden_combat_history():
    run = RunEngine(config=RunConfig(), card_ids=('strike',) * 128)
    run.start_combat()
    d = check(attach(run)).decision
    assert len([n for n in f.walk(d.run) if n.kind == 'card']) == 128
    assert len([n for n in f.walk(d.context) if n.kind == 'card']) == 128
    other = deepcopy(run)
    other.combat.player.rules.drawn_combat += 999
    other.combat.player.rules.hp_loss_events += 777
    other.combat.player.rules.auxiliaries['block_gains'] = 555
    assert f.dumps(d) == f.dumps(check(attach(other)).decision)


def test_reviving_enemy_and_infinite_hp_are_public_displays():
    from tests.headless.test_glory import start, kill
    run = start('test_subject', ('strike', 'defend'))
    enemy = run.combat.enemies[0]
    kill(run, enemy)
    d = check(attach(run)).decision
    e = next(n for n in f.walk(d.context) if n.kind == 'enemy')
    assert e.get('hp') == 0 and not e.get('alive')
    assert {n.definition_id for n in e.children if n.kind == 'intent'} == {'heal', 'buff'}
    assert any(n.definition_id == 'reviving' and n.get('amount') for n in e.children)
    from tests.headless.test_underdocks import start as underdocks_start
    run = underdocks_start('waterfall_giant', cards=('strike',))
    run.apply(ca.EndTurn())  # Pressurize establishes the public Steam power.
    enemy = run.combat.enemies[0]
    enemy.take_damage(10000, is_attack=False)
    run.combat.resolve_external_effect()
    d = attach(run).observe().decision
    e = next(n for n in f.walk(d.context) if n.kind == 'enemy')
    assert e.get('infinite_hp') and e.get('hp') is None and e.get('max_hp') is None
    assert not any(n.definition_id in ('pressure_gun', 'explosion_damage') for n in e.children)


def test_shop_restock_replaces_offer_keeps_acquisition_and_rejects_old_binding():
    from game.headless.run import shop
    run = RunEngine(config=RunConfig(), gold=2000)
    add_relic(run.state, 'the_courier', cards=run.cards)
    shop.begin(run.state, run.cards)
    a = attach(run)
    offer = next(o for o in run.state.pending['offers'] if o['kind'] == 'card')
    frame = check(a)
    action = next(c for c in frame.decision.candidates if a._commands[c.ref] == ra.BuyShopItem(offer['offer_id']))
    public = next(n for n in f.walk(frame.decision.context) if n.ref == action.subject)
    card = next(n for n in public.children if n.kind == 'card')
    gold, price = run.state.gold, public.get('price')
    a.step(frame.binding, action.ref)
    after = check(a).decision
    assert run.state.gold == gold - price
    assert any(n.ref == card.ref for n in f.walk(after.run))
    restocked = next(n for n in f.walk(after.context) if n.kind == 'offer' and n.get('slot') == public.get('slot'))
    assert restocked.ref != public.ref and not restocked.get('sold')
    assert any(c.kind == 'buy_shop_item' and c.subject == restocked.ref for c in after.candidates)
    assert a.step(frame.binding, action.ref).reason == 'stale_decision'


def test_cheese_multi_pick_reuses_acquired_card_as_link_not_duplicate_entity():
    from game.headless.run import events
    run = RunEngine(seed=7, config=RunConfig())
    events.begin(run.state, 'room_full_of_cheese', cards=run.cards)
    a = attach(run)
    act(a, ra.ChooseEventOption, option_id='gorge')
    frame = check(a)
    chosen = next(c for c in frame.decision.candidates if c.target and c.target.startswith('card:'))
    a.step(frame.binding, chosen.ref)
    after = check(a).decision
    assert any(n.ref == chosen.target for n in f.walk(after.run))
    assert chosen.target in after.context.linked('selected')
    assert not any(n.ref == chosen.target for n in f.walk(after.context))
    finish_choices(a)


def test_reroll_changes_only_its_owned_offer_references():
    from game.headless.run.rewards import begin_combat_rewards
    run = RunEngine(seed=3, config=RunConfig())
    run.obtain_relic('prayer_wheel')
    run.obtain_relic('driftwood')
    begin_combat_rewards(run.state, run.cards)
    a = attach(run)
    def present(key, opened):
        frame = a.observe()
        action = next(c for c in frame.decision.candidates if a._commands[c.ref] == Presentation(key, opened))
        a.step(frame.binding, action.ref)
        return check(a).decision
    main = present(-1, True)
    original = [(n.ref, n.definition_id) for n in f.walk(main.context) if n.kind == 'card']
    present(-1, False)
    extra = present(0, True)
    old_extra_refs = {n.ref for n in f.walk(extra.context) if n.kind == 'card'}
    act(a, ra.RerollCardReward, index=0)
    assert old_extra_refs.isdisjoint(n.ref for n in f.walk(a.observe().decision.context) if n.kind == 'card')
    present(0, False)
    main = present(-1, True)
    assert original == [(n.ref, n.definition_id) for n in f.walk(main.context) if n.kind == 'card']


def test_reward_parent_identity_survives_nested_relic_pickup():
    from game.headless.run.rewards import begin_combat_rewards
    run = RunEngine(seed=3, config=RunConfig())
    run.obtain_relic('driftwood')
    begin_combat_rewards(run.state, run.cards)
    run.state.pending.update(relic='dollys_mirror', relic_claimed=False)
    a = attach(run)
    def present(opened):
        frame = a.observe()
        action = next(c for c in frame.decision.candidates if a._commands[c.ref] == Presentation(-1, opened))
        a.step(frame.binding, action.ref)
        return check(a).decision
    present(True)
    act(a, ra.RerollCardReward, index=-1)
    before = a.observe().decision
    refs = [(n.kind, n.ref, n.definition_id) for n in f.walk(before.context) if n.kind in ('card', 'reward')]
    present(False)
    act(a, ra.ClaimRelic)
    act(a, ra.ChooseRelicCard)
    act(a, ra.ConfirmRelicSelection)
    after = present(True)
    assert refs == [(n.kind, n.ref, n.definition_id) for n in f.walk(after.context) if n.kind in ('card', 'reward')]


def test_consumed_potion_cannot_donate_its_identity_to_generated_replacement():
    run = RunEngine(config=RunConfig(reward_potions=('entropic_brew',)))
    run.state.potion_capacity, run.state.potions = 1, [None]
    add_potion(run.state, 'entropic_brew')
    run.start_combat()
    a = attach(run)
    before = check(a).decision
    original = next(n.ref for n in f.walk(before.run) if n.kind == 'potion')
    act(a, ra.UsePotion)
    after = check(a).decision
    replacement = next(n.ref for n in f.walk(after.run) if n.kind == 'potion')
    assert replacement != original


def test_membership_discount_keeps_surviving_shop_offer_identity():
    from game.headless.run import shop
    run = RunEngine(seed=7, rng_profile='native', gold=2000,
                    config=RunConfig(shop_relics=('membership_card', 'anchor', 'vajra')))
    shop.begin(run.state, run.cards)
    a = attach(run)
    before = check(a).decision
    cards = [(n.ref, n.children[0].ref, n.get('price')) for n in before.context.children
             if n.kind == 'offer' and n.definition_id == 'card']
    offer = next(o for o in run.state.pending['offers'] if o['definition_id'] == 'membership_card')
    dispatch(a, ra.BuyShopItem(offer['offer_id']))
    after = check(a).decision
    discounted = [(n.ref, n.children[0].ref, n.get('price')) for n in after.context.children
                  if n.kind == 'offer' and n.definition_id == 'card']
    assert len(cards) == 7
    assert [(o, c) for o, c, p in cards] == [(o, c) for o, c, p in discounted]
    assert all(new <= old // 2 for (_, _, old), (_, _, new) in zip(cards, discounted))
