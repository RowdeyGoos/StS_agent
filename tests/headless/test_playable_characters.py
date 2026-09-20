"""Character starts, shared ownership and the newly introduced rule boundaries."""
from copy import deepcopy
import json
import pytest

from game.headless.characters import CHARACTERS, STARTER_UPGRADES, potion_pool, relic_pool
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.actions import PlayCard, EndTurn
from game.headless.run.engine import RunEngine
from game.headless.run.config import RunConfig
from game.headless.run.actions import ChooseExtraReward
from game.headless.relics.base import RELICS
from game.headless.relics.combat import memory, owned
from game.headless.monsters.overgrowth import SimpleEnemy


def saved(run):
    return json.loads(json.dumps(run.snapshot()))


def clone(run):
    other = RunEngine(); other.restore(saved(run))
    assert saved(other) == saved(run)
    assert other.legal_actions() == run.legal_actions()
    return other


def setup(character, *relics, cards=None):
    run = RunEngine(seed=2, config=RunConfig(character=character), card_ids=cards)
    for relic in relics:
        run.obtain_relic(relic)
    run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=1000), cards_per_turn=10)
    return run


@pytest.mark.parametrize('character', CHARACTERS)
def test_native_run_setup_pools_and_character_bound_restore(character):
    run = RunEngine.campaign(character=character, seed=2)
    start = CHARACTERS[character]
    assert (run.state.hp, run.state.max_hp, run.state.gold) == (start.max_hp, start.max_hp, 99)
    assert tuple(c.definition.definition_id for c in run.state.deck) == start.deck
    assert run.state.relics[0].definition_id == start.relic
    assert {run.cards.definition(n).pool for n in run.state.config.reward_cards} == {character}
    assert set(run.state.config.reward_potions) == set(potion_pool(character))
    assert len(run.state.config.reward_potions) == 48
    from game.headless.generation.merchant import populate
    offers = populate(run.state, run.cards)
    assert {run.cards.definition(o['definition_id']).pool for o in offers[:5]} == {character}
    assert all(o['definition_id'] in relic_pool(character, shop=True) for o in offers[7:10])
    clone(run)
    bad = saved(run)
    foreign = next(n for c,d in CHARACTERS.items() if c != character for n in d.relic_pool if RELICS[n].rarity == 'common')
    bad['state']['relic_bags']['player']['common'].append(foreign)
    before = saved(run)
    with pytest.raises(ValueError, match='Foreign character'): run.restore(bad)
    assert saved(run) == before


@pytest.mark.parametrize('character', list(CHARACTERS)[1:])
def test_exclusive_relics_share_turn_and_snapshot_lifecycle(character):
    # One combined inventory per character; the interaction checks below test
    # behavior, while this catches omitted ownership/serialization wiring.
    run = setup(character, *CHARACTERS[character].relic_pool)
    for _ in range(3):
        other = clone(run)
        run.apply(EndTurn()); other.apply(EndTurn())
        assert saved(other) == saved(run)
    clone(run)


def test_bookmark_discount_survives_turn_setter_and_clears_after_play():
    from game.headless.core.card_costs import free_this_turn, mark_setter
    from game.headless.powers.ironclad import local_cost
    run = setup('necrobinder', 'bookmark', cards=['capture_spirit'])
    card = run.combat.player.hand[0]
    card.combat_state.until_played_discount = 1
    free_this_turn(card)
    assert local_cost(card) == 0
    card.combat_state.turn_cost_override = None
    assert local_cost(card) == max(0, card.cost - 1)
    card.combat_state.combat_cost_override = 0
    mark_setter(card.combat_state, 'combat')
    clone(run)
    run.apply(PlayCard(card.instance_id, 0))
    assert card.combat_state.until_played_discount == 0
    assert card.combat_state.cost_discount_baselines == {}
    assert local_cost(card) == 0
    bad = saved(run)
    # Direct record validator: an absolute setter cannot have observed a larger
    # past discount than the monotonic live discount total.
    from game.headless.core.snapshots import card_record, restore_card
    record = card_record(card); record['combat_state']['cost_discount_baselines'] = {'combat': 9}
    with pytest.raises(ValueError): restore_card(record)


def test_emotion_chip_counts_hp_costs_but_not_current_turn_damage():
    from game.headless.core.orbs import execute
    from game.headless.core.resolution import drain
    from game.headless.relics.character_hooks import hook, start
    run = setup('defect', 'emotion_chip', cards=['defend_defect'])
    p = run.combat.player; relic = owned(p, 'emotion_chip')
    execute(p, 'orb_channel', ['frost']); drain(p)
    p.lose_hp(1); drain(p)
    p.rules.round_number += 1
    start(p, relic, 5)
    p.lose_hp(1); drain(p)  # belongs to the new turn, must survive this trigger
    hook(p, relic, 'after_draw', ''); drain(p)
    assert p.block == 2 and memory(p, relic)['damaged']
    hook(p, relic, 'after_draw', ''); drain(p)
    assert p.block == 2
    clone(run)


def test_character_damage_counters_and_orb_passives():
    from game.headless.relics.character_hooks import spent
    from game.headless.core.orbs import execute, value
    from game.headless.core.resolution import drain
    run = setup('regent', 'galactic_dust', 'mini_regent', cards=['defend_regent'])
    p=run.combat.player
    spent(p, 7); spent(p, 5)
    assert (p.block, p.strength, owned(p, 'galactic_dust')['counter']) == (10, 1, 2)
    run = setup('defect', 'infused_core', 'gold_plated_cables', cards=['defend_defect'])
    p=run.combat.player; enemy=run.combat.enemies[0]; before=enemy.hp
    first=p.rules.orb_order[0]
    assert value(p,p.rules.orbs[first],'evoke') == 9
    execute(p,'orb_trigger',[first,'passive',None]); drain(p)
    assert before-enemy.hp == 8
    clone(run)


def test_ancient_powers_artifact_and_owned_removal_rewards():
    from game.headless.powers.silent import execute
    run=setup('silent', cards=['wraith_form'])
    run.apply(PlayCard(run.combat.player.hand[0].instance_id))
    p=run.combat.player; p.statuses.add('artifact',1)
    execute(p,'silent_side_start',['wraith_form'])
    assert p.statuses.get('artifact') == 0 and p.rules.powers.get('dexterity',0) == 0
    execute(p,'silent_side_start',['wraith_form'])
    assert p.rules.powers['dexterity'] == -1
    clone(run)
    run=setup('necrobinder', cards=['forbidden_grimoire','strike_necrobinder'])
    card=next(c for c in run.combat.player.hand if c.definition.definition_id=='forbidden_grimoire')
    run.apply(PlayCard(card.instance_id)); run.combat.enemies[0].take_damage(10000,is_attack=False)
    run.combat.resolve_external_effect(); run.finish_combat()
    actions=[a for a in run.legal_actions() if isinstance(a,ChooseExtraReward)]
    grimoire=next(c for c in run.state.deck if c.definition.definition_id=='forbidden_grimoire')
    assert actions and all(a.definition_id != grimoire.instance_id for a in actions)
    other=clone(run); action=next(a for a in actions if a.definition_id is not None)
    run.apply(action);other.apply(action)
    assert saved(other)==saved(run) and len(run.state.deck)==1
    clone(run)


def test_helical_dart_and_speed_keep_separate_artifact_expirations():
    from game.headless.powers.ironclad import apply_power
    from game.headless.potions.powers import after_end
    run=setup('silent','helical_dart',cards=['shiv'])
    run.apply(PlayCard(run.combat.player.hand[0].instance_id,0))
    p=run.combat.player
    apply_power(p,'dexterity',5);apply_power(p,'temporary_dexterity',5)
    p.statuses.add('artifact',1)
    clone(run)
    for key in tuple(p.rules.powers): after_end(p,key)
    assert p.rules.powers['dexterity']==1 and p.statuses.get('artifact')==0
    clone(run)


def test_doom_batch_heals_after_horn_and_hellraiser():
    from game.headless.core.resolution import push, drain
    from game.headless.powers.necrobinder import doom_tasks
    run=RunEngine(config=RunConfig(character='necrobinder'),card_ids=['strike_necrobinder'],hp=33)
    for name in ('book_repair_knife','gremlin_horn','red_skull'):run.obtain_relic(name)
    engine=run.start_combat(encounter_factory=lambda _: [SimpleEnemy(max_hp=100),SimpleEnemy(max_hp=100)],cards_per_turn=0)
    p=engine.player; first,second=engine.enemies
    p.rules.powers['hellraiser']=1
    first.hp=1;first.statuses.add('doom',1)
    # End of Days uses the same emitted batch; this isolated boundary omits the
    # attack and tests death/Horn/automatic Strike before the batch heal.
    push(p,*doom_tasks(p));drain(p)
    assert (second.hp,p.hp,p.strength)==(91,36,0)
    assert not p.rules.pending_events


def test_new_character_hooks_cannot_be_forged_into_a_card_choice():
    run=setup('defect','cracked_core',cards=['armaments','defend','strike'])
    p=run.combat.player
    run.apply(PlayCard(next(c.instance_id for c in p.hand if c.definition.definition_id=='armaments')))
    before=saved(run)
    # No producer emitted this opening callback or its receipt.
    bad=deepcopy(before)
    rules=bad['combat']['player']['rules']
    rules['tasks'].append(['character_relic_hook',p.rules.relics[0]['instance_id'],'before_side_start',''])
    with pytest.raises(ValueError):run.restore(bad)
    assert saved(run)==before


def test_cli_selects_unselected_cards_in_multiple_choices():
    from game.cli.headless_play import choose_demo_action
    from game.headless.core.actions import ChooseCombatCard
    run=setup('regent',cards=['charge','strike_regent','defend_regent'])
    p=run.combat.player
    # Charge chooses cards in draw/discard piles; move the two candidates there.
    for c in tuple(p.hand):
        if c.definition.definition_id!='charge':p.hand.remove(c);p.deck.draw_pile.append(c)
    run.apply(PlayCard(p.hand[0].instance_id))
    if p.rules.selection:
        first=choose_demo_action(run);run.apply(first)
        second=choose_demo_action(run)
        assert isinstance(first,ChooseCombatCard) and first!=second


def test_character_power_callbacks_precede_relics_at_terminal_boundary():
    from game.headless.powers.regent import spend
    run=setup('regent','galactic_dust','mini_regent',cards=['defend_regent'])
    p=run.combat.player
    p.rules.powers.update(child_of_the_stars=1,juggernaut=6)
    p.rules.stars=1;owned(p,'galactic_dust')['counter']=9
    run.combat.enemies[0].hp=6
    spend(p,0,1)
    assert (p.block,p.strength,owned(p,'galactic_dust')['counter'])==(1,0,0)


def test_terminal_doom_still_earns_knife_healing():
    from game.headless.core.resolution import push,drain
    from game.headless.powers.necrobinder import doom_tasks
    run=setup('necrobinder','book_repair_knife',cards=['defend_necrobinder'])
    p=run.combat.player;p.hp=20
    run.combat.enemies[0].statuses.add('doom',1000)
    push(p,*doom_tasks(p));drain(p)
    assert p.hp==23 and p.combat_is_ending


@pytest.mark.parametrize('character',list(CHARACTERS)[1:])
@pytest.mark.parametrize('ascension,first_act',[(0,'overgrowth'),(10,'underdocks')])
def test_boosted_three_act_character_campaign(character,ascension,first_act):
    from game.cli.headless_play import choose_demo_action
    from game.headless.run.state import RunPhase
    run=RunEngine.campaign(character=character,seed=2,ascension=ascension,first_act=first_act)
    run.state.max_hp=run.state.hp=1000000
    # Real legal actions and combat resolution. HP is the sole assistance;
    # these are integration runs, not native whole-campaign comparisons.
    for index in range(6000):
        if index%100==0 or run.combat is None:clone(run)
        if run.state.phase in (RunPhase.VICTORY,RunPhase.DEFEAT):break
        run.apply(choose_demo_action(run,rest_choice='rest'))
    assert run.state.phase is RunPhase.VICTORY
    assert run.state.act_index==2 and run.state.combats_completed>=20


def test_doom_batch_receipt_keeps_captured_victims(monkeypatch):
    from game.headless.core import resolution
    run=RunEngine(config=RunConfig(character='necrobinder'),card_ids=['end_of_days'])
    run.obtain_relic('book_repair_knife')
    run.start_combat(encounter_factory=lambda _: [SimpleEnemy(max_hp=1000),SimpleEnemy(max_hp=1000)])
    p=run.combat.player;p.energy=10;p.hp=20
    run.combat.enemies[0].hp=10
    captures=[]; original=resolution.execute
    def execute(player,task):
        original(player,task)
        if task[0]=='nec_doom_kill':
            # Inspect the actual emitted batch after its victim dies. This is
            # internal execution, not an exportable player-decision boundary.
            from game.headless.core.necrobinder_snapshots import validate_task
            batch=next(t for t in player.rules.tasks if t[0]=='nec_doom_after')
            assert dict(context=player.rules.active_hook,task=batch) in player.rules.pending_events
            validate_task(batch,player.rules,player,player.rules.active_hook)
            # Death does not invalidate the captured kill if an earlier callback
            # killed that target before its own iteration.
            validate_task(task,player.rules,player,player.rules.active_hook)
            captures.append(deepcopy(batch))
    monkeypatch.setattr(resolution,'execute',execute)
    run.apply(PlayCard(p.hand[0].instance_id))
    assert captures and p.hp==23
