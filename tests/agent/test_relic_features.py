"""Relic descriptors against native mechanics and frozen learned inputs."""
from dataclasses import replace

import pytest

torch = pytest.importorskip('torch')
np = pytest.importorskip('numpy')
pytest.importorskip('gymnasium')
from game.agent.contracts import full as f
from game.agent.training.catalog import PublicCatalog, public_catalog
from game.agent.training.coverage import catalog_coverage
from game.agent.training.features import Vocabulary, FeatureEncoder, _FEATURE_ARRAYS
from game.agent.training.combat_features import REPRESENTATIONS
from game.agent.training.model import ActorCritic, Architecture, collate
from game.agent.training.relic_features import RELIC_RULES, fields
from game.headless.core.actions import PlayCard
from game.headless.core.resolution import drain, push
from game.headless.monsters.overgrowth import SimpleEnemy
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_relic
from .test_training_model import cpu_threads, decision


def rule(name, index=0):
    entry = next(e for e in public_catalog().entries if (e.kind, e.definition_id) == ('relic', name))
    prefix = f'catalog.effect.{index}.'
    return {v.key.removeprefix(prefix): v.value for v in entry.fields if v.key.startswith(prefix)}


def combat(name, *, cards=('strike', 'defend'), hp=60, counter=None):
    run = RunEngine(seed=0, card_ids=cards, hp=hp, max_hp=80)
    relic = add_relic(run.state, name)
    if counter is not None:
        run.state.relics[0] = replace(relic, counter=counter)
    engine = run.start_combat(cards_per_turn=10, enemy_factory=lambda: SimpleEnemy(max_hp=1000))
    return run, engine


def relic_decision(*names):
    public = decision()
    return replace(public, run=replace(public.run, children=(*public.run.children, *(
        f.Node('relic', name, f'relic:{i}') for i, name in enumerate(names)))))


def test_supported_groups_have_immutable_partial_rules_and_auditable_gaps():
    from game.headless.relics.base import RELICS, RelicDefinition
    from game.headless.relics.combat import COMBAT_RELICS
    from game.headless.relics.character_content import definitions
    assert set(RELIC_RULES) <= set(RELICS)
    assert set(COMBAT_RELICS) <= set(RELIC_RULES)
    assert set(definitions(RelicDefinition)) <= set(RELIC_RULES)
    assert all(type(value) in (str, int, bool)
               for rules in RELIC_RULES.values() for row in rules for _, value in row)
    with pytest.raises(TypeError):
        RELIC_RULES['anchor'] = ()
    detached = fields('anchor')
    detached['effect.0.amount'] = 99
    assert fields('anchor')['effect.0.amount'] == 10
    report = catalog_coverage(Vocabulary.fit((), split='train'))['by_kind']['relic']
    descriptions = report['bundled_description_coverage']
    entries = [e for e in public_catalog().entries if e.kind == 'relic']
    assert descriptions == {'partial': len(RELICS)}
    assert report['identity_only_ids'] == []
    assert report['no_intrinsic_effect_ids'] == [
        'circlet', 'fake_merchants_rug', 'wongo_customer_appreciation_badge']
    assert report['known'] == len(RELICS) and report['unknown'] == 0
    assert all(next(v.value for v in e.fields if v.key == 'catalog.description_complete') is False
               for e in entries)


@pytest.mark.parametrize('loss', (1, 5))
def test_tungsten_amount_applies_to_self_hp_loss_not_only_attacks(loss):
    _, engine = combat('tungsten_rod')
    effect = rule('tungsten_rod')
    assert effect['trigger'] == 'hp_loss'
    before = engine.player.hp
    engine.player.lose_hp(loss)
    drain(engine.player)
    assert before - engine.player.hp == max(effect['minimum_result'], loss - effect['amount'])


@pytest.mark.parametrize('turn_before, block', ((0, 25), (1, 25), (1, 7), (1, 0)))
def test_sturdy_clamp_preserves_existing_block_from_second_turn(turn_before, block):
    from game.headless.powers.ironclad import start_turn
    _, engine = combat('sturdy_clamp')
    effect = rule('sturdy_clamp')
    assert effect['kind'] == 'retain_block'
    player = engine.player
    player.block, player.rules.round_number = block, turn_before
    start_turn(player, 0)
    expected = min(block, effect['maximum']) if turn_before + 1 >= effect['turn_min'] else block
    assert player.block == expected


def test_pen_nib_counter_multiplier_covers_every_hit_of_triggering_card():
    effect = rule('pen_nib')
    assert effect['counter_scope'] == 'run' and effect['duration'] == 'whole_card_play'
    run, engine = combat('pen_nib', cards=('sword_boomerang',), counter=effect['every'] - 1)
    before = engine.enemies[0].hp
    run.apply(PlayCard('run.card.0'))
    assert before - engine.enemies[0].hp == 3 * 3 * effect['amount']
    assert run.state.relics[0].counter == 0


def test_permafrost_scope_does_not_grant_block_for_second_power():
    run, engine = combat('permafrost', cards=('inflame', 'inflame'))
    effect = rule('permafrost')
    assert effect['uses'] == 1 and effect['scope'] == 'combat'
    run.apply(PlayCard('run.card.0'))
    assert engine.player.block == effect['amount']
    run.apply(PlayCard('run.card.1'))
    assert engine.player.block == effect['amount']


def test_red_skull_threshold_is_inclusive_and_bonus_can_be_removed():
    from game.headless.relics.combat import heal
    _, engine = combat('red_skull', hp=40)
    effect = rule('red_skull')
    assert engine.player.hp * 100 == engine.player.max_hp * effect['hp_percent_max']
    assert engine.player.strength == effect['amount']
    assert effect['reversible']
    heal(engine.player, 1)
    assert engine.player.strength == 0


def test_metronome_fires_exactly_once_at_seventh_channel_not_every_seven():
    _, engine = combat('metronome')
    effect = rule('metronome')
    assert effect['counter_scope'] == 'combat' and 'every' not in effect
    before = engine.enemies[0].hp
    for count in range(1, 2 * effect['at_count'] + 1):
        push(engine.player, ['orb_channel', 'frost'])
        drain(engine.player)
        assert before - engine.enemies[0].hp == (effect['amount'] if count >= effect['at_count'] else 0)


@pytest.mark.parametrize('source', ('direct_potion', 'player', 'owned_pet'))
def test_hand_drill_requires_player_or_pet_source_when_block_breaks(source):
    _, engine = combat('hand_drill')
    effect = rule('hand_drill')
    assert effect['damage_source'] == 'player_or_owned_pet'
    enemy = engine.enemies[0]
    enemy.block = 5
    enemy.take_damage(5, is_attack=False,
                      attacker_statuses=engine.player.statuses if source == 'player' else None,
                      pet=source == 'owned_pet')
    assert enemy.block == 0
    assert enemy.statuses.get('vulnerable') == (0 if source == 'direct_potion' else effect['amount'])


@pytest.mark.parametrize('schema', REPRESENTATIONS)
def test_enriched_relic_inputs_support_all_architectures_without_public_graph_changes(schema):
    public = relic_decision('pen_nib', 'metronome', 'runic_pyramid', 'mummified_hand',
                           'fur_coat', 'miniature_tent', 'paels_tooth', 'circlet')
    wire = f.to_dict(public)
    old = Vocabulary.fit([public], split='train', include_catalog=False)
    new = Vocabulary.fit([public], split='train')
    before = FeatureEncoder(old, representation=schema).encode(public)
    after = FeatureEncoder(new, representation=schema).encode(public)
    assert len(after.fields) > len(before.fields)
    assert before.graph.candidate_refs == after.graph.candidate_refs
    assert before.policy_mask == after.policy_mask
    assert np.array_equal(before.candidates, after.candidates)
    assert all(np.array_equal(before.graph.observation[k], after.graph.observation[k]) for k in before.graph.observation)
    assert f.to_dict(public) == wire
    model = ActorCritic(new, Architecture(16, 1, schema), seed=1)
    logits, values = model(collate([after], vocabulary=new))
    assert torch.isfinite(logits).all() and torch.isfinite(values).all()
    (logits.square().mean() + values.square().mean()).backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())


@pytest.mark.parametrize('generation', ('old_hooks', 'identity_only_relics'))
def test_old_v2_hook_fields_and_inference_survive_current_catalog_changes(tmp_path, monkeypatch, generation):
    from game.agent.training.checkpoint import save_checkpoint, load_policy
    from game.agent.training.learner import Corpus, Example, ImitationLearner
    from game.agent.training.rewards import RewardSpec
    import game.agent.training.catalog as module
    public = relic_decision('anchor', 'miniature_tent', 'circlet')
    # Both older v2 generations remain valid: original hook_* fields, and
    # identity-only entries that must not gain today's descriptions on load.
    wire = public_catalog().to_dict()
    anchor = next(e for e in wire['entries'] if (e['kind'], e['definition_id']) == ('relic', 'anchor'))
    anchor['fields'] = [dict(key=key, value=value) for key, value in (
        ('catalog.description_complete', False), ('catalog.hook_amount', 10),
        ('catalog.hook_effect', 'block'), ('catalog.hook_trigger', 'combat_start'), ('catalog.rarity', 'common'))]
    if generation == 'identity_only_relics':
        for entry in wire['entries']:
            if (entry['kind'], entry['definition_id']) in (('relic', 'miniature_tent'), ('relic', 'circlet')):
                entry['coverage'] = 'identity'
                entry['fields'] = [v for v in entry['fields'] if v['key'] in (
                    'catalog.description_complete', 'catalog.rarity')]
    wire['names'] = sorted(set(wire['names']) | {v['key'] for v in anchor['fields']} |
                           {v['value'] for v in anchor['fields'] if type(v['value']) is str})
    saved = PublicCatalog.from_dict(wire)
    old = Vocabulary(tuple(sorted(set(saved.names) | set(Vocabulary.fit(
        [public], split='train', include_catalog=False).names))), saved)
    if generation == 'identity_only_relics':
        coverage = catalog_coverage(old)['by_kind']['relic']
        assert coverage['identity_only_ids'] == ['circlet', 'miniature_tent']
        assert 'circlet' not in coverage['no_intrinsic_effect_ids']
    encoded = FeatureEncoder(old).encode(public)
    corpus = Corpus((Example(encoded, 0, None),), old, RewardSpec(), 'old-v2-relic-fixture', 'train', 1, 0)
    owner = ImitationLearner(ActorCritic(old, Architecture(16, 1), seed=7), corpus)
    path = tmp_path/'saved.sts-model'
    save_checkpoint(path, owner)
    expected = load_policy(path).probabilities(public)
    monkeypatch.setattr(module, 'public_catalog', lambda: pytest.fail('Rebuilt saved catalog'))
    policy = load_policy(path)
    assert policy.model.vocabulary == old and policy.model.vocabulary.catalog == saved
    actual = FeatureEncoder(policy.model.vocabulary).encode(public)
    assert all(np.array_equal(getattr(encoded, k), getattr(actual, k)) for k in _FEATURE_ARRAYS)
    assert policy.probabilities(public) == expected


@pytest.mark.parametrize('name', [name for name, rows in RELIC_RULES.items()
    if any('selection_minimum' in dict(row) and dict(row).get('source') == 'deck' for row in rows)])
@pytest.mark.parametrize('repetitions', (1, 3))
def test_described_pickup_choices_execute_with_native_counts_and_effects(name, repetitions):
    from game.headless.run.actions import ChooseRelicCard, ConfirmRelicSelection
    run = RunEngine(seed=3, card_ids=('strike', 'defend', 'bash', 'inflame') * repetitions)
    run.obtain_relic(name)
    work = run.state.relic_work[0]
    effect = rule(name)
    count = len(work['candidates'])
    assert effect['counts_clipped_to_eligible']
    assert work['minimum'] == min(effect['selection_minimum'], count)
    assert work['maximum'] == min(effect['selection_maximum'], count)
    assert (ConfirmRelicSelection() in run.legal_actions()) == (work['minimum'] == 0)
    chosen = work['candidates'][:work['maximum']]
    originals = {c.instance_id: c for c in run.state.deck}
    before_levels = {c.instance_id: c.upgrade_level for c in run.state.deck}
    for identity in chosen:
        run.apply(ChooseRelicCard(identity))
    run.apply(ConfirmRelicSelection())
    remaining = {c.instance_id: c for c in run.state.deck}
    if effect['kind'] == 'enchant_card':
        assert all(remaining[i].enchantment.definition_id == effect['enchantment']
                   and remaining[i].enchantment.amount == effect['amount'] for i in chosen)
    elif effect['kind'] == 'upgrade_card':
        assert all(remaining[i].upgrade_level == before_levels[i] + 1 for i in chosen)
    elif effect['kind'] == 'copy_card_to_deck':
        assert len(remaining) == len(originals) + len(chosen) and set(originals) <= set(remaining)
    else:
        assert not set(chosen) & set(remaining)
        if effect.get('upgrade_result'):
            assert all(c.upgraded for i, c in remaining.items() if i not in originals)
        if effect['kind'] == 'replace_card':
            assert all(c.definition.definition_id == effect['card'] for i, c in remaining.items() if i not in originals)


@pytest.mark.parametrize('name', ('precarious_shears', 'preserved_fog'))
def test_pickup_drawbacks_apply_with_no_eligible_card(name):
    run = RunEngine(card_ids=(), hp=60)
    effect = rule(name, 1)
    assert effect['also_when_no_eligible_cards']
    run.obtain_relic(name)
    assert not run.state.relic_work
    if effect['kind'] == 'hp_loss':
        assert run.state.hp == 60 - effect['amount']
    else:
        assert [c.definition.definition_id for c in run.state.deck] == [effect['card']]


def test_hefty_tablet_curse_is_not_avoided_by_skipping_reward():
    from game.headless.run.actions import ChooseRelicReward
    run = RunEngine(card_ids=('strike',))
    run.obtain_relic('hefty_tablet')
    assert rule('hefty_tablet')['optional'] and rule('hefty_tablet', 1)['also_when_skipped']
    assert len(run.state.relic_work[0]['offers']) == rule('hefty_tablet')['offers_per_reward']
    run.apply(ChooseRelicReward(None))
    assert [c.definition.definition_id for c in run.state.deck] == ['strike', rule('hefty_tablet', 1)['card']]


@pytest.mark.parametrize('occupied', (0, 3))
@pytest.mark.parametrize('name', ('phial_holster', 'alchemical_coffer'))
def test_potion_grants_respect_capacity_and_separate_added_slots(name, occupied):
    from game.headless.run.inventory import add_potion
    run = RunEngine()
    for _ in range(occupied):
        add_potion(run.state, 'fire_potion')
    capacity = run.state.potion_capacity
    run.obtain_relic(name)
    assert run.state.potion_capacity == capacity + rule(name)['amount']
    assert sum(p is not None for p in run.state.potions) == occupied + min(
        rule(name, 1)['amount'], run.state.potion_capacity - occupied)


def test_cauldron_offers_potions_instead_of_automatically_filling_slots():
    from game.headless.run.actions import ChooseRelicReward
    run = RunEngine()
    run.obtain_relic('cauldron')
    assert len(run.state.relic_work) == rule('cauldron')['amount']
    assert all(p is None for p in run.state.potions)
    assert rule('cauldron')['optional'] and ChooseRelicReward(None) in run.legal_actions()


def test_rest_relics_preserve_once_per_option_and_bonus_healing():
    from game.headless.run.rest_site import begin_rest_site
    from game.headless.run.actions import Rest, Smith
    run = RunEngine(hp=10, max_hp=80)
    run.obtain_relic('miniature_tent')
    run.obtain_relic('regal_pillow')
    begin_rest_site(run.state)
    run.apply(Rest())
    assert run.state.hp == 10 + 80 * 3 // 10 + rule('regal_pillow')['amount']
    assert rule('miniature_tent')['uses_per_distinct_option'] == 1
    assert Rest() not in run.legal_actions() and Smith() in run.legal_actions()


def test_membership_and_courier_discounts_combine_before_rounding():
    from game.headless.run.shop import discounted
    run = RunEngine()
    run.obtain_relic('membership_card')
    run.obtain_relic('the_courier')
    amount = 79
    assert discounted(run.state, amount) == amount * rule('membership_card')['amount'] * rule('the_courier')['amount'] // 10000


def test_tooth_and_toy_box_advance_on_victory_only():
    from game.headless.run.lifecycle import after_combat
    from game.headless.run.actions import ChooseRelicCard, ChooseRelicReward, ConfirmRelicSelection
    run = RunEngine()
    run.obtain_relic('paels_tooth')
    work = run.state.relic_work[0]
    for identity in work['candidates'][:work['maximum']]:
        run.apply(ChooseRelicCard(identity))
    run.apply(ConfirmRelicSelection())
    size = len(run.state.deck)
    tooth = run.state.relics[0]
    stored = len(tooth.data['cards'])
    assert rule('paels_tooth', 1)['trigger'] == 'combat_victory'
    after_combat(run.state, won=False, elite=False)
    assert len(tooth.data['cards']) == stored and len(run.state.deck) == size
    after_combat(run.state, won=True, elite=False)
    assert len(tooth.data['cards']) == stored - rule('paels_tooth', 1)['amount']
    assert len(run.state.deck) == size + 1 and run.state.deck[-1].upgraded

    # Skip generated rewards to isolate expiry of an owned wax relic.
    run = RunEngine()
    run.obtain_relic('toy_box')
    assert len(run.state.relic_work) == rule('toy_box')['amount']
    while run.state.relic_work:
        run.apply(ChooseRelicReward(None))
    wax = run.obtain_relic('anchor')
    wax.data['_wax'] = True
    effect = rule('toy_box', 1)
    assert effect['trigger'] == 'combat_victory'
    after_combat(run.state, won=False, elite=False)
    assert run.state.relics[0].counter == 0
    for i in range(effect['every']):
        after_combat(run.state, won=True, elite=False)
        assert bool(wax.data.get('_melted')) == (i + 1 == effect['every'])


def test_no_intrinsic_effect_relics_keep_owned_identities_without_pickup_effects():
    run = RunEngine(seed=0)
    no_effect = catalog_coverage(Vocabulary.fit((), split='train'))['by_kind']['relic']['no_intrinsic_effect_ids']
    for name in no_effect:
        hp, gold, deck = run.state.hp, run.state.gold, tuple(run.state.deck)
        run.obtain_relic(name)
        assert (run.state.hp, run.state.gold, tuple(run.state.deck)) == (hp, gold, deck)
        assert not run.state.relic_work
    assert [r.definition_id for r in run.state.relics] == no_effect
    assert len({r.instance_id for r in run.state.relics}) == len(no_effect)
