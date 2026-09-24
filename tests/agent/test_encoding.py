"""Semantic, identity, privacy and capacity checks for the padded public format."""
from copy import deepcopy
from dataclasses import replace

import pytest

np = pytest.importorskip('numpy')

from game.agent import contracts as c
from game.agent.encoding import CapacityError, DEFAULT_PROFILE, EncodingError, PublicEncoder
from game.agent.encoding.schema import INTEGER_MAX
from game.agent.headless import HeadlessAdapter
from game.headless.monsters.overgrowth import SimpleEnemy
from tests.agent.examples import (card, combat_decision, map_decision,
                                 rewards_decision, selection_decision)
from tests.agent.test_headless_adapter import action, game


def same_arrays(left, right):
    assert left.keys() == right.keys()
    for key in left:
        np.testing.assert_array_equal(left[key], right[key], err_msg=key)


def normalize(decision, encoded):
    """Independent expected public view: only names and candidate order change."""
    names = {ref: f'{ref.split(":")[0]}:{i}' for i, ref in enumerate(encoded.reference_refs)}
    names.update({ref: f'action:{i}' for i, ref in enumerate(encoded.candidate_refs)})
    def rename(value):
        if type(value) is dict:
            return {k: rename(v) for k, v in value.items()}
        if type(value) is list:
            return [rename(v) for v in value]
        return names.get(value, value) if type(value) is str else value
    result = rename(c.to_dict(decision))
    result['candidates'].sort(key=lambda a: int(a['ref'].split(':')[1]))
    return result


@pytest.mark.parametrize('decision', [*(combat_decision(k) for k in
    ('ironclad', 'silent', 'regent', 'necrobinder', 'defect')),
    selection_decision(), selection_decision(('card:5', 'card:4')),
    rewards_decision(), rewards_decision(True), map_decision()])
def test_every_public_field_candidate_and_visible_order_round_trips(decision):
    encoder = PublicEncoder()
    encoded = encoder.encode(decision)
    recovered = encoder.decode(encoded.observation)
    assert c.to_dict(recovered) == normalize(decision, encoded)
    same_arrays(encoded.observation, encoder.encode(recovered).observation)
    assert int(encoded.observation['action_mask'].sum()) == len(decision.candidates)
    for index, ref in enumerate(encoded.candidate_refs):
        original = next(a for a in decision.candidates if a.ref == ref)
        assert recovered.candidates[index].kind == original.kind


def test_raw_reference_names_and_candidate_permutations_are_not_features():
    public = selection_decision(('card:5',))
    original = PublicEncoder().encode(public)
    names = {r: r.split(':')[0] + ':' + str(93000-i*7)
             for i, r in enumerate((*original.reference_refs, *original.candidate_refs))}
    def rename(value):
        if type(value) is list:
            return [rename(v) for v in value]
        if type(value) is dict:
            return {k: rename(v) for k, v in value.items()}
        return names.get(value, value) if type(value) is str else value
    wire = rename(c.to_dict(public))
    wire['candidates'].reverse()
    renamed = PublicEncoder().encode(c.from_dict(wire))
    same_arrays(original.observation, renamed.observation)
    assert original.candidate_refs != renamed.candidate_refs


def test_duplicates_powers_counters_history_and_optional_availability_survive():
    base = combat_decision('defect')
    context = replace(base.context, powers=c.known((
        c.Power('power:91', 'strength', 2, c.known((c.Counter('turns', 3),))),
        c.Power('power:92', 'strength', 2, c.known((c.Counter('turns', 1),))),)))
    history = c.History('attachment', (
        c.HistoryEvent('card_played', c.known('card:999'), c.known('enemy:777'), (c.Counter('damage', 9),)),))
    public = replace(base, context=context, run=replace(base.run, history=c.known(history)))
    encoder = PublicEncoder()
    encoded = encoder.encode(public)
    assert c.to_dict(encoder.decode(encoded.observation)) == normalize(public, encoded)
    assert np.count_nonzero(encoded.observation['references'][:, 1] == 0) >= 2
    hand = next(p for p in context.piles if p.kind == 'hand')
    unknown = replace(hand, cards=c.known((replace(hand.cards.value[0], origin=c.unknown()),)))
    absent = replace(hand, cards=c.known((replace(hand.cards.value[0], origin=c.not_applicable()),)))
    variants = [replace(public, context=replace(context, piles=tuple(h if p.kind == 'hand' else p
                for p in context.piles))) for h in (unknown, absent)]
    assert c.dumps(encoder.decode(encoder.encode(variants[0]).observation)) != c.dumps(
        encoder.decode(encoder.encode(variants[1]).observation))
    with pytest.raises(c.UnsupportedDecision):
        encoder.encode(replace(public, run=replace(public.run, deck=c.unknown())))


def test_hidden_game_state_is_not_an_encoded_feature_and_visible_changes_are():
    run = game(cards=('strike', 'strike', 'defend', 'bash'))
    adapter, encoder = HeadlessAdapter(run), PublicEncoder()
    before = encoder.encode(adapter.observe().decision).observation
    player = run.combat.player
    player.deck.draw_pile.reverse()
    player.deck.rng.random()
    player.deck.selection_rng.random()
    run.state.next_card_id += 100
    run.state.next_item_id += 100
    run.state.potion_drop_chance = 90
    run.graph = replace(run.graph, nodes=tuple(replace(n, encounter_id='overgrowth_shrinker_beetle')
                                             for n in run.graph.nodes))
    snapshot = run.snapshot()
    same_arrays(before, encoder.encode(adapter.observe().decision).observation)
    assert snapshot == run.snapshot()
    player.energy += 1
    after = encoder.encode(adapter.observe().decision).observation
    assert not np.array_equal(before['nodes'], after['nodes'])


def large_target_decision():
    run = game(cards=('strike',) * 128)
    player = run.combat.player
    player.hand.extend(player.deck.draw_pile[:10])
    del player.deck.draw_pile[:10]
    for _ in range(7):
        enemy = SimpleEnemy(max_hp=40)
        enemy.combat_player = player
        run.combat.enemies.append(enemy)
    return run, HeadlessAdapter(run).observe().decision


def large_selector():
    run = game(cards=('neows_fury',) + ('strike',) * 127)
    player = run.combat.player
    originals = list(player.deck.draw_pile)
    player.deck.draw_pile.clear()
    player.hand.extend(card for card in originals if card.definition.definition_id == 'neows_fury')
    player.deck.discard_pile.extend(card for card in originals if card.definition.definition_id == 'strike')
    adapter = HeadlessAdapter(run)
    action(adapter, 'play_card')
    return run, adapter


def test_capacity_prototype_large_decks_targets_history_and_multi_selection():
    encoder = PublicEncoder()
    run, public = large_target_decision()
    history = c.History('attachment', tuple(c.HistoryEvent('end_turn', c.not_applicable(),
                           c.not_applicable(), ()) for _ in range(256)))
    public = replace(public, run=replace(public.run, history=c.known(history)))
    snapshot = run.snapshot()
    encoded = encoder.encode(public)
    assert len(public.candidates) == 81  # Ten hand cards × eight targets + end turn.
    assert c.to_dict(encoder.decode(encoded.observation)) == normalize(public, encoded)
    assert run.snapshot() == snapshot
    run, adapter = large_selector()
    public = adapter.observe().decision
    assert len(public.context.options) == 127
    assert len(public.candidates) == 128
    for _ in range(2):
        action(adapter, 'select_card')
    public = adapter.observe().decision
    encoded = encoder.encode(public)
    assert len(encoder.decode(encoded.observation).context.selected) == 2
    assert c.to_dict(encoder.decode(encoded.observation)) == normalize(public, encoded)


def test_repeated_offer_identity_and_many_reward_entries_are_lossless():
    public = rewards_decision(True)
    child = replace(public.context.entries[1], cards=c.known(tuple(card(6+i, 'bash') for i in range(32))))
    summaries = tuple(replace(public.context.entries[0], ref=f'reward:{i}', amount=c.known(i))
                      for i in range(2, 9))
    candidates = tuple(c.Candidate(f'action:{i}', 'choose_reward_card', child.ref, offer.ref)
                       for i, offer in enumerate(child.cards.value)) + (c.Candidate('action:32', 'skip_reward', child.ref),)
    public = replace(public, context=c.Rewards('rewards', (child, *summaries)), candidates=candidates)
    encoded = PublicEncoder().encode(public)
    recovered = PublicEncoder().decode(encoded.observation)
    assert len({a.target for a in recovered.candidates if a.kind == 'choose_reward_card'}) == 32
    assert c.to_dict(recovered) == normalize(public, encoded)


@pytest.mark.parametrize('dimension,capacity', [('nodes', 10), ('references', 1), ('strings', 1),
                                              ('string_bytes', 3), ('candidates', 1)])
def test_each_capacity_overflow_is_explicit_and_leaves_public_adapter_usable(dimension, capacity):
    run = game()
    adapter = HeadlessAdapter(run)
    run.combat.player.hand.extend(run.combat.player.deck.draw_pile)
    run.combat.player.deck.draw_pile.clear()
    frame, before = adapter.observe(), run.snapshot()
    with pytest.raises(CapacityError) as error:
        PublicEncoder(replace(DEFAULT_PROFILE, **{dimension: capacity})).encode(frame.decision)
    assert error.value.dimension == dimension
    assert error.value.required > error.value.capacity
    assert run.snapshot() == before and adapter.observe() is frame
    assert PublicEncoder().decode(PublicEncoder().encode(frame.decision).observation)


def test_numeric_values_remain_exact_and_do_not_silently_overflow():
    encoder, public = PublicEncoder(), combat_decision()
    for gold in (2**24+1, INTEGER_MAX):
        public = replace(public, run=replace(public.run, gold=gold))
        assert encoder.decode(encoder.encode(public).observation).run.gold == gold
    with pytest.raises(CapacityError, match='integer_magnitude'):
        encoder.encode(replace(public, run=replace(public.run, gold=INTEGER_MAX+1)))


@pytest.mark.parametrize('kind,reason', [('victory', 'none'), ('defeat', 'none'), ('abandoned', 'none'),
    ('truncated', 'slice_complete'), ('truncated', 'decision_budget'), ('truncated', 'time_budget'),
    ('truncated', 'act_complete'), ('truncated', 'external_stop')])
def test_outcome_encoding_has_no_invented_state_or_legal_action(kind, reason):
    outcome = c.RunOutcome('sts_run_outcome_v1', kind, reason)
    encoded = PublicEncoder().encode(outcome)
    assert encoded.candidate_refs == encoded.reference_refs == ()
    assert not encoded.observation['action_mask'].any()
    assert not encoded.observation['node_mask'].any()
    assert PublicEncoder().decode(encoded.observation) == outcome


@pytest.mark.parametrize('mutation', ['version', 'dtype', 'mask', 'padding', 'parent', 'namespace',
                                     'target', 'definition', 'text', 'extra'])
def test_decoder_rejects_malformed_tensors(mutation):
    encoder = PublicEncoder()
    obs = encoder.encode(combat_decision()).observation
    if mutation == 'version': obs['layout'][0] += 1
    elif mutation == 'dtype': obs['nodes'] = obs['nodes'].astype(np.float64)
    elif mutation == 'mask': obs['action_mask'][0] = 0
    elif mutation == 'padding': obs['candidates'][-1, 0] = 1
    elif mutation == 'parent': obs['nodes'][0, 0] = 1
    elif mutation == 'namespace': obs['references'][0, 0] = -1
    elif mutation == 'target': obs['candidates'][0, 2] = 100000
    elif mutation == 'definition': obs['references'][0, 1] += 1
    elif mutation == 'text': obs['strings'][0, 0] = 255
    elif mutation == 'extra': obs['seed'] = np.array([123])
    with pytest.raises(EncodingError):
        encoder.decode(obs)


def test_fixed_batch_collation_preserves_masks_values_and_profile_identity():
    encoder = PublicEncoder()
    observations = [encoder.encode(d).observation for d in (combat_decision(), selection_decision(), map_decision())]
    batch = encoder.collate(observations)
    for i, original in enumerate(observations):
        same_arrays(original, {key: value[i] for key, value in batch.items()})
    with pytest.raises(EncodingError):
        encoder.collate([])
    smaller = PublicEncoder(replace(DEFAULT_PROFILE, candidates=10)).encode(combat_decision()).observation
    with pytest.raises(EncodingError):
        encoder.collate([observations[0], smaller])
