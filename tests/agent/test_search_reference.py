"""Independent bounded enumeration of fully visible current-turn lethal tactics."""
import pytest
from game.agent.search import SearchConfig, SearchPolicy
from game.agent.search.model import PublicCombatModel, SearchHistory, action_key
from .test_search import UniformPolicy, fixture


def lethal_returns(world, public):
    """Enumerate card orders through engine forks; unknown later turns stay None.

    These fixtures have no draws, selectors, generation or hidden hand cards.
    The oracle proves current-turn lethal sequences, not an optimal full fight.
    """
    values = {}
    for action in public.candidates:
        if action.kind != 'play_card':
            values[action.ref] = None
            continue
        branch = world.fork()
        before = branch.project()
        after = branch.step(before, action_key(public, action))
        if after is None:
            values[action.ref] = branch.terminal_value
        else:
            successors = [v for v in lethal_returns(branch, after).values() if v is not None]
            values[action.ref] = max(successors) if successors else None
    return values


@pytest.mark.parametrize('attacks', [1, 2, 3])
def test_search_finds_exhaustively_verified_current_turn_lethal(attacks):
    run, adapter = fixture(('strike',) * attacks + ('defend',), enemy_hp=attacks)
    decision = adapter.observe().decision
    original = run.snapshot()
    world, public = PublicCombatModel(decision, SearchHistory()).sample(19)
    values = lethal_returns(world, public)
    best = max(v for v in values.values() if v is not None)
    winning_keys = {action_key(public, a) for a in public.candidates if values[a.ref] == best}
    assert winning_keys
    result = SearchPolicy(UniformPolicy(), SearchConfig(simulations=64, max_depth=4,
        leaf_rollout_steps=4, time_limit=30)).choose(decision)
    chosen = next(a for a in decision.candidates if a.ref == result.action_ref)
    assert action_key(decision, chosen) in winning_keys
    assert result.reason is None and result.cutoff is None
    assert max(result.values.values()) <= best + 1e-8
    assert run.snapshot() == original


def test_root_search_value_matches_enumerated_hidden_draw_outcomes():
    # At one HP, ending the turn loses. Pommel does one damage through Slippery.
    # Its unknown next card is equally likely to be Strike (lethal) or Wound
    # (defeat). The test oracle enumerates synthetic worlds, not the real order.
    run, _ = fixture(('pommel_strike', 'strike') + ('wound',) * 5, hp=1, enemy_hp=2)
    deck = run.combat.player.deck
    cards = list(run.combat.player.hand) + list(deck.draw_pile)
    pommel = next(c for c in cards if c.definition.definition_id == 'pommel_strike')
    strike = next(c for c in cards if c.definition.definition_id == 'strike')
    wounds = [c for c in cards if c.definition.definition_id == 'wound']
    run.combat.player.hand[:] = [pommel, *wounds[:4]]
    deck.draw_pile[:] = [strike, wounds[4]]
    from game.agent.headless import HeadlessAdapter
    from .test_search import card_action
    decision = HeadlessAdapter(run, decision_profile='full_run_v2').observe().decision
    before = run.snapshot()
    key = action_key(decision, card_action(decision, 'pommel_strike'))
    model = PublicCombatModel(decision, SearchHistory())
    returns = []
    for top in ('strike', 'wound'):
        world, public = model.sample(123)
        hypothetical = world._run.combat.player.deck.draw_pile
        hypothetical.sort(key=lambda c: c.definition.definition_id == top)
        successor = world.step(public, key)
        assert successor is not None
        action = next((a for a in successor.candidates if a.kind == 'play_card'),
                      next(a for a in successor.candidates if a.kind == 'end_turn'))
        assert world.step(successor, action_key(successor, action)) is None
        returns.append(world.terminal_value)
    assert returns == pytest.approx([1 + .1 * 7 / 80, 0])
    result = SearchPolicy(UniformPolicy(), SearchConfig(method='root', simulations=512,
        max_depth=1, leaf_rollout_steps=4, time_limit=60, seed=91)).choose(decision)
    pommel_ref = card_action(decision, 'pommel_strike').ref
    assert result.reason is None and result.cutoff is None
    assert result.action_ref == pommel_ref
    assert result.visits[pommel_ref] == 256
    assert result.values[pommel_ref] == pytest.approx(sum(returns) / 2, abs=.08)
    assert result.leaf_work['bootstraps'] == 0
    assert run.snapshot() == before
