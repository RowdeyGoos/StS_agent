"""Executable v1 consumer boundary, including malformed and unavailable data."""
import ast
from copy import deepcopy
from dataclasses import FrozenInstanceError, dataclass, replace
import json
from pathlib import Path
from typing import Literal, Union

import pytest

from game.agent.contracts import (
    ContractError, UnsupportedDecision, known, unknown, not_applicable, to_dict,
    from_dict, dumps, loads, missing_fields, require_ready, RunOutcome,
    ExecutionReport, Power, Counter, OstyState, Orb, History, Candidate, Relic, Reward, Rewards,
)
from tests.agent.examples import combat_decision, selection_decision, rewards_decision, map_decision

FIXTURES = Path(__file__).parent / 'fixtures'


@pytest.mark.parametrize('decision', [combat_decision(c) for c in
                         ('ironclad', 'silent', 'regent', 'necrobinder', 'defect')]
                         + [selection_decision(), selection_decision(('card:5', 'card:4')),
                            rewards_decision(), rewards_decision(opened=True), map_decision()])
def test_first_slice_round_trip_and_readiness(decision):
    assert require_ready(decision) is decision
    assert loads(dumps(decision)) == decision
    assert dumps(from_dict(to_dict(decision))) == dumps(decision)
    with pytest.raises(FrozenInstanceError):
        decision.profile = 'changed'


def test_shared_wire_example_and_invalid_replacements():
    baseline = json.loads((FIXTURES / 'neows_fury_v1.json').read_text())
    assert require_ready(from_dict(baseline)) == selection_decision()
    for case in json.loads((FIXTURES / 'invalid_v1.json').read_text()):
        mutated = deepcopy(baseline)
        parent = mutated
        for key in case['path'][:-1]:
            parent = parent[key]
        parent[case['path'][-1]] = case['value']
        with pytest.raises(ContractError):
            from_dict(mutated)


def test_cached_generic_schema_preserves_per_parse_substitutions():
    from game.agent.contracts.codec import _read
    from game.agent.contracts.models import Observed
    cases = (
        (int, 7, 7, (True, '7', 7.0)),
        (str, 'visible', 'visible', (7, False, [])),
        (bool, True, True, (1, 'true', [])),
        (tuple[Counter, ...], [{'key': 'strength', 'amount': 2}],
         (Counter('strength', 2),), ([{'key': 'strength', 'amount': True}], {})),
    )
    # Every instantiation uses the same Observed class cache entry. Revisit it
    # in the opposite order to catch cached substitutions and accepted values.
    for annotation, value, expected, invalid in (*cases, *reversed(cases)):
        assert _read({'status': 'known', 'value': value}, Observed[annotation], '$') == known(expected)
        for bad in invalid:
            with pytest.raises(ContractError):
                _read({'status': 'known', 'value': bad}, Observed[annotation], '$')
        for bad in ({'status': 'known'}, {'status': 'known', 'value': value, 'hidden': 1}):
            with pytest.raises(ContractError):
                _read(bad, Observed[annotation], '$')


def test_cached_schema_does_not_reuse_a_previous_wire_validation():
    wire = to_dict(combat_decision())
    assert from_dict(wire) == combat_decision()
    wire['run']['hp'] = True  # bool must not become an integer after warming.
    with pytest.raises(ContractError):
        from_dict(wire)
    wire['run']['hp'] = 80
    wire['run']['private_rng'] = 1
    with pytest.raises(ContractError):
        from_dict(wire)
    del wire['run']['private_rng']
    del wire['run']['history']
    with pytest.raises(ContractError):
        from_dict(wire)


@pytest.mark.parametrize('annotation,accepted,rejected', [
    (int, (0, 1, -3), (True, False, 1.0, '1', None)),
    (bool, (True, False), (0, 1, 'true', None)),
    (str | int | bool | None, ('', 1, True, None), (1.0, [], {})),
    (Union[int, str], (1, 'one'), (True, None, 1.0)),
    (Literal[1] | bool, (1, True, False), (0, 2, 1.0, None)),
    (Literal[False] | int, (False, 0, 1), (True, 0.0, None)),
    (tuple[int, ...] | None, ([], [1, 2], None), ([True], (), '')),
])
def test_primitive_fast_paths_preserve_exact_types_and_literals(annotation, accepted, rejected):
    from game.agent.contracts.codec import _read
    for value in accepted:
        result = _read(value, annotation, '$')
        expected = tuple(value) if type(value) is list else value
        assert type(result) is type(expected) and result == expected
    for value in rejected:
        with pytest.raises(ContractError):
            _read(value, annotation, '$')


def test_union_member_order_and_generic_substitutions_stay_local():
    from game.agent.contracts.codec import _read
    from game.agent.contracts.models import Observed, T

    @dataclass(frozen=True)
    class First:
        value: int

    @dataclass(frozen=True)
    class Second:
        value: int

    for annotation, expected in ((First | Second, First), (Second | First, Second)):
        assert type(_read({'value': 2}, annotation, '$')) is expected
    mapping = {T: str}
    assert _read({'value': 2}, First, '$', mapping) == First(2)
    assert _read({'status': 'known', 'value': 3}, Observed[int], '$', mapping) == known(3)
    assert _read('still a string', T, '$', mapping) == 'still a string'
    assert mapping == {T: str}


def test_serialization_fast_path_keeps_subclass_and_mutability_rejections():
    from game.agent.contracts.codec import _wire

    class Text(str):
        pass

    @dataclass(frozen=True)
    class TextRecord(str):
        value: str

    @dataclass(frozen=True)
    class Wrapper:
        value: tuple[int, ...]

    assert _wire(('visible', 1, False, None, (2,))) == ['visible', 1, False, None, [2]]
    assert _wire(TextRecord('visible')) == {'value': 'visible'}
    assert _wire(Wrapper((1, 2))) == {'value': [1, 2]}
    for value in (Text('visible'), ['mutable'], {'mutable': 1}, Wrapper, 1.5):
        with pytest.raises(ContractError):
            _wire(value)


def test_known_empty_zero_not_applicable_and_unavailable_are_distinct():
    decision = combat_decision('regent')
    assert decision.context.resources.stars == known(0)
    assert decision.context.resources.osty == not_applicable()
    assert decision.run.history == known(History('run_start', ()))
    partial = replace(decision, run=replace(decision.run, history=unknown()))
    assert loads(dumps(partial)) == partial  # Valid diagnostics, unusable policy input.
    assert missing_fields(partial) == ('$.run.history',)
    with pytest.raises(UnsupportedDecision) as exc:
        require_ready(partial)
    assert exc.value.missing == ('$.run.history',)
    for invalid in (known(None), replace(unknown(), value=())):
        with pytest.raises(ContractError):
            dumps(replace(decision, run=replace(decision.run, history=invalid)))
    with pytest.raises(ContractError):
        dumps(replace(decision, run=replace(decision.run, history=not_applicable())))


def test_duplicate_cards_and_instanced_powers_retain_public_identity():
    choice = selection_decision(('card:5', 'card:4'))
    restored = loads(dumps(choice))
    assert restored.context.selected == ('card:5', 'card:4')
    assert restored.context.options == ('card:4', 'card:5')
    combat = combat_decision()
    powers = known((Power('power:0', 'the_bomb', 40, known((Counter('turns', 1),))),
                    Power('power:1', 'the_bomb', 40, known((Counter('turns', 2),)))))
    assert require_ready(replace(combat, context=replace(combat.context, powers=powers)))


def test_cross_character_resources_and_known_absent_osty():
    decision = combat_decision()
    resources = replace(decision.context.resources, stars=known(2), sovereign_blades=known(()),
                        osty=known(OstyState(None)), orb_slots=known(1),
                        orbs=known((Orb('orb:0', 'lightning', 3, 8),)))
    decision = replace(decision, context=replace(decision.context, resources=resources))
    assert require_ready(loads(dumps(decision))) == decision
    for character, field in [('regent', 'stars'), ('regent', 'sovereign_blades'),
                             ('necrobinder', 'osty'), ('defect', 'orb_slots')]:
        base = combat_decision(character)
        bad = replace(base.context.resources, **{field: not_applicable()})
        with pytest.raises(ContractError):
            dumps(replace(base, context=replace(base.context, resources=bad)))


def test_attachment_history_and_unobservable_deck_origins():
    base = combat_decision()
    # At attachment, duplicate originals can be indistinguishable. Do not read a
    # private origin association just to fill a policy field.
    hand = base.context.piles[0]
    hand = replace(hand, cards=known((replace(hand.cards.value[0], origin=unknown()),)))
    attached = replace(base, run=replace(base.run, history=known(History('attachment', ()))),
                       context=replace(base.context, piles=(hand, *base.context.piles[1:])))
    assert require_ready(loads(dumps(attached))) == attached
    assert attached.run.history != base.run.history


def test_reward_parent_hides_precomputed_offers_and_child_owns_actions():
    parent, child = rewards_decision(), rewards_decision(opened=True)
    assert require_ready(parent).context.entries[1].cards == not_applicable()
    assert [c.kind for c in parent.candidates] == ['claim_reward', 'open_card_reward', 'leave_rewards']
    assert child.context.entries[1].cards.value[0].definition_id == child.context.entries[1].cards.value[1].definition_id
    assert child.candidates[0].target != child.candidates[1].target
    for candidate in parent.candidates:
        with pytest.raises(ContractError):
            dumps(replace(child, candidates=(candidate,)))
    for candidate in child.candidates:
        with pytest.raises(ContractError):
            dumps(replace(parent, candidates=(candidate,)))
    premature = replace(parent.context.entries[1], cards=child.context.entries[1].cards)
    with pytest.raises(ContractError):
        dumps(replace(parent, context=replace(parent.context, entries=(premature,))))
    # Two unopened rewards retain distinct parents, while only one child may open.
    second = replace(parent.context.entries[1], ref='reward:2')
    board = replace(parent, context=replace(parent.context, entries=(*parent.context.entries, second)),
                    candidates=(*parent.candidates, Candidate('action:3', 'open_card_reward', 'reward:2')))
    assert require_ready(loads(dumps(board))) == board
    extra = replace(second, presentation='choice', cards=unknown())
    with pytest.raises(ContractError):
        dumps(replace(child, context=replace(child.context, entries=(*child.context.entries, extra))))


def test_resolved_reward_preserves_acquired_item_identity_in_inventory():
    base = rewards_decision()
    item = Relic('relic:1', 'vajra', known(()))
    claimed = Reward('reward:2', 'relic', 'summary', not_applicable(), not_applicable(),
                     not_applicable(), not_applicable(), True)
    post_claim = replace(base, run=replace(base.run, relics=known((*base.run.relics.value, item))),
                         context=Rewards('rewards', (claimed,)),
                         candidates=(Candidate('action:0', 'leave_rewards'),))
    assert require_ready(loads(dumps(post_claim))) == post_claim
    with pytest.raises(ContractError):
        dumps(replace(post_claim, context=Rewards('rewards', (replace(claimed, relic=known(item)),))))


@pytest.mark.parametrize('raw', ['{}', 'null', '[]', '{',
    '{"schema":"sts_run_outcome_v1","schema":"sts_run_outcome_v1","kind":"victory","reason":"none"}',
    '{"schema":"sts_run_outcome_v1","kind":"victory","reason":NaN}'])
def test_malformed_json_rejected(raw):
    with pytest.raises(ContractError):
        loads(raw)


@pytest.mark.parametrize('kind,reason', [('victory', 'none'), ('defeat', 'none'), ('abandoned', 'none')]
                         + [('truncated', r) for r in ('decision_budget', 'time_budget', 'slice_complete', 'act_complete', 'external_stop')])
def test_game_outcomes_are_separate_from_execution(kind, reason):
    outcome = RunOutcome('sts_run_outcome_v1', kind, reason)
    assert loads(dumps(outcome)) == outcome


@pytest.mark.parametrize('status,mutation,reason', [
    ('pending', 'queued', 'none'), ('reconciled', 'applied', 'none'),
    ('rejected', 'none', 'stale_decision'), ('rejected', 'none', 'invalid_action'),
    ('unsupported', 'none', 'missing_public_fields'), ('unsupported', 'none', 'unsupported_version'),
    ('uncertain', 'unknown', 'deadline'), ('faulted', 'applied', 'cleanup_failure')])
def test_execution_taxonomy(status, mutation, reason):
    report = ExecutionReport('sts_execution_report_v1', status, mutation, reason)
    assert loads(dumps(report)) == report


@pytest.mark.parametrize('message', [
    RunOutcome('sts_run_outcome_v1', 'victory', 'act_complete'),
    RunOutcome('sts_run_outcome_v1', 'truncated', 'none'),
    ExecutionReport('sts_execution_report_v1', 'rejected', 'applied', 'invalid_action'),
    ExecutionReport('sts_execution_report_v1', 'uncertain', 'none', 'deadline'),
    ExecutionReport('sts_execution_report_v1', 'reconciled', 'unknown', 'none'),
    ExecutionReport('sts_execution_report_v1', 'unsupported', 'queued', 'unsupported_capability'),
])
def test_impossible_outcomes_or_execution_states_rejected(message):
    with pytest.raises(ContractError):
        dumps(message)


def test_contracts_do_not_depend_on_backends_and_engine_does_not_import_consumers():
    root = Path(__file__).parents[2] / 'game'
    for directory, forbidden in ((root / 'headless', ('game.agent', 'gymnasium')),
                                  (root / 'agent/contracts', ('game.headless', 'bridge', 'gymnasium', 'numpy'))):
        for path in directory.rglob('*.py'):
            for node in ast.walk(ast.parse(path.read_text())):
                names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ''] if isinstance(node, ast.ImportFrom) else []
                assert not any(name == prefix or name.startswith(prefix + '.') for name in names for prefix in forbidden), path
