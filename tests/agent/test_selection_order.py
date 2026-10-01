"""Concrete game outcomes that prevent treating card selections as unordered."""
import pytest

from game.agent.action_policy import ALL_LEGAL, COMMIT_CARD_SELECTION, COMMIT_DECISIONS, action_mask
from game.agent.headless import HeadlessAdapter
from game.headless.run.engine import RunEngine
from game.headless.run.actions import ChooseRelicCard, ConfirmRelicSelection
from game.headless.core.actions import PlayCard, ChooseCombatCard, ConfirmCombatSelection
from game.headless.powers.ironclad import apply_power
from game.headless.monsters.overgrowth import SimpleEnemy


def combat(names):
    run = RunEngine(seed=2, card_ids=names, rng_profile='native')
    run.start_combat(enemy_factory=lambda: SimpleEnemy(max_hp=200), cards_per_turn=0)
    player = run.combat.player
    cards = {c.definition.definition_id:c for c in player.deck.all_cards()}
    player.deck.draw_pile.clear()
    return run, player, cards


def apply_order(run, commands, policy):
    adapter = HeadlessAdapter(run, decision_profile='full_run_v2')
    for command in commands:
        frame = adapter.observe()
        candidate = next(a for a in frame.decision.candidates if adapter._commands[a.ref] == command)
        assert action_mask(frame.decision, policy)[frame.decision.candidates.index(candidate)]
        assert adapter.step(frame.binding, candidate.ref).status == 'reconciled'


def fury(order, policy=ALL_LEGAL):
    run, player, cards = combat(('neows_fury','strike','defend','bash'))
    player.hand.append(cards['neows_fury'])
    player.deck.discard_pile.extend(cards[n] for n in ('strike','defend','bash'))
    run.apply(PlayCard(cards['neows_fury'].instance_id,0))
    apply_order(run, [*[ChooseCombatCard(cards[name].instance_id) for name in order], ConfirmCombatSelection()], policy)
    return [c.definition.definition_id for c in player.hand]


@pytest.mark.parametrize('policy', [ALL_LEGAL, COMMIT_CARD_SELECTION, COMMIT_DECISIONS])
def test_neows_fury_preserves_order_and_reselection_has_a_direct_equivalent(policy):
    assert fury(('strike','defend'),policy)==['strike','defend']
    assert fury(('defend','strike'),policy)==['defend','strike']
    # Native free-slot reuse, not append-on-reselect. The same ordered result
    # remains attainable from an empty selector without undoing any selection.
    assert fury(('strike','defend','strike','defend','bash','strike'))==fury(('strike','bash'),policy)


@pytest.mark.parametrize('policy', [ALL_LEGAL, COMMIT_CARD_SELECTION, COMMIT_DECISIONS])
def test_astrolabe_order_changes_seeded_transform_results(policy):
    def transform(order):
        run=RunEngine(seed=2,card_ids=('strike','injury','secret_weapon','defend'),rng_profile='native')
        identities={c.definition.definition_id:c.instance_id for c in run.state.deck}
        run.obtain_relic('astrolabe')
        apply_order(run, [*[ChooseRelicCard(identities[name]) for name in order], ConfirmRelicSelection()], policy)
        return [c.definition.definition_id for c in run.state.deck]
    forward=transform(('strike','injury','secret_weapon'))
    reverse=transform(('secret_weapon','injury','strike'))
    assert forward!=reverse
    assert forward==['defend','sword_boomerang','curse_of_the_bell','panic_button']
    assert reverse==['defend','splash','curse_of_the_bell','mangle']


@pytest.mark.parametrize('policy', [ALL_LEGAL, COMMIT_CARD_SELECTION, COMMIT_DECISIONS])
def test_purity_exhaust_order_changes_energy_through_draw_hooks(policy):
    def exhaust(order):
        run, player, cards=combat(('purity','drum_of_battle','strike','void','defend'))
        player.hand.extend(cards[n] for n in ('purity','drum_of_battle','strike'))
        player.deck.draw_pile.extend(cards[n] for n in ('void','defend'))
        player.energy=0
        apply_power(player,'dark_embrace',1)
        run.apply(PlayCard(cards['purity'].instance_id))
        apply_order(run, [*[ChooseCombatCard(cards[name].instance_id) for name in order], ConfirmCombatSelection()], policy)
        return player.energy
    assert exhaust(('drum_of_battle','strike'))==1
    assert exhaust(('strike','drum_of_battle'))==2


@pytest.mark.parametrize('policy', [ALL_LEGAL, COMMIT_CARD_SELECTION, COMMIT_DECISIONS])
def test_gambling_chip_discard_order_changes_sly_autoplay_block(policy):
    def discard(order):
        run=RunEngine(seed=2,card_ids=('abrasive','untouchable','defend'),rng_profile='native')
        run.obtain_relic('gambling_chip')
        run.start_combat(enemy_factory=lambda:SimpleEnemy(max_hp=200),cards_per_turn=3)
        player=run.combat.player
        cards={c.definition.definition_id:c for c in player.hand}
        apply_order(run, [*[ChooseCombatCard(cards[name].instance_id) for name in order], ConfirmCombatSelection()], policy)
        return player.block
    assert discard(('abrasive','untouchable'))==7
    assert discard(('untouchable','abrasive'))==6
