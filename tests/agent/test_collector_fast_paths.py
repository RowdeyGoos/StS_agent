"""Collector fast paths stay exact on real campaign decisions.

The state guard, prepared-record clone, wire conversion and specialized table
packing each have a generic reference path; these tests compare them directly.
"""
import hashlib
import json
import random

import numpy as np
import pytest

from game.agent.contracts import codec
from game.agent.contracts import full as f
from game.agent.encoding.full import FullRunEncoder
from game.agent.headless import HeadlessAdapter
from game.agent.headless import adapter as adapter_module
from game.agent.headless.adapter import DecisionFrame
from game.headless.run.engine import RunEngine


def played(seed, steps=48):
    """Seeded random play across event, map, combat and reward screens."""
    adapter = HeadlessAdapter(RunEngine.campaign(seed=seed, character='ironclad'), decision_profile=f.PROFILE)
    rng = random.Random(seed)
    for _ in range(steps):
        frame = adapter.observe()
        if not isinstance(frame, DecisionFrame):
            return
        yield adapter, frame
        assert adapter.step(frame.binding, rng.choice(frame.decision.candidates).ref).status == 'reconciled'


@pytest.mark.parametrize('seed', (0, 5))
def test_guard_digest_hashes_the_complete_sorted_snapshot(seed):
    contexts = set()
    for adapter, frame in played(seed):
        contexts.add(frame.decision.context.kind)
        text = json.dumps(adapter._engine.snapshot(), sort_keys=True, separators=(',', ':'))
        assert adapter._guard() == hashlib.sha256(text.encode()).digest()
    assert {'combat', 'map'} <= contexts


def test_content_text_is_reused_only_for_the_same_held_object():
    adapter_module._CONTENT_TEXT.clear()
    first, equal, changed = {'b': [1, 2], 'a': None}, {'b': [1, 2], 'a': None}, {'b': [3]}
    assert adapter_module._content_text(first) == '{"a":null,"b":[1,2]}'
    assert adapter_module._content_text(equal) == '{"a":null,"b":[1,2]}'
    assert adapter_module._content_text(changed) == '{"b":[3]}'
    assert adapter_module._CONTENT_TEXT[id(first)][0] is first
    for index in range(40):
        assert adapter_module._content_text({'n': index}) == '{"n":%d}' % index
    assert len(adapter_module._CONTENT_TEXT) <= 16


@pytest.mark.parametrize('seed', (0, 5))
def test_prepared_clone_and_wire_equal_the_generic_reader_and_writer(seed, monkeypatch):
    clone = f._clone_decision
    with monkeypatch.context() as generic:
        # Reference decisions owned through the generic schema reader only.
        generic.setattr(f, '_clone_decision', lambda _: None)
        decisions = [frame.decision for _, frame in played(seed)]
    assert any(node.links for d in decisions for root in (d.run, d.context) for node in f.walk(root))
    fast = [json.dumps(f.to_dict(d)) for d in decisions]
    for decision in decisions:
        assert clone(decision) == f._read_record(decision, f.PublicDecision, '$') == decision
    monkeypatch.setattr(codec, '_EXACT_WIRE', {})
    for decision, wire in zip(decisions, fast):
        # Same content, element order and key order as the structural writer.
        assert wire == json.dumps(f.to_dict(decision))


@pytest.mark.parametrize('bad', [
    lambda d: f.PublicDecision(d.schema, d.profile, d.run, d.context, list(d.candidates)),
    lambda d: f.PublicDecision(d.schema, d.profile, f.Node('run', 'run', fields=[f.Field('hp', 1)]),
                               d.context, d.candidates),
    lambda d: f.PublicDecision(d.schema, d.profile, f.Node('run', 'run', fields=(f.Field('hp', 1.5),)),
                               d.context, d.candidates),
    lambda d: f.PublicDecision(d.schema, d.profile, f.Node('run', 'run', fields=(f.Link('hp', ()),)),
                               d.context, d.candidates),
    lambda d: f.PublicDecision(d.schema, d.profile, f.Node('run', 'run', links=(f.Link('to', ['card:1']),)),
                               d.context, d.candidates),
    lambda d: f.PublicDecision(d.schema, d.profile, d.run, f.Node('combat', 7), d.candidates),
])
def test_malformed_records_fail_identically_with_and_without_the_clone(bad, monkeypatch):
    _, frame = next(played(0))
    value = bad(frame.decision)
    with pytest.raises(codec.ContractError) as fast:
        f.PreparedPublic(value)
    monkeypatch.setattr(f, '_clone_decision', lambda _: None)
    with pytest.raises(codec.ContractError) as generic:
        f.PreparedPublic(value)
    assert str(fast.value) == str(generic.value)


@pytest.mark.parametrize('seed', (0, 5))
def test_specialized_packing_equals_generic_tables_on_real_decisions(seed):
    encoder = FullRunEncoder()
    for _, frame in played(seed):
        decision, owner = frame.decision, frame.prepared
        expected = encoder.pack(decision)
        actual = encoder._pack_prepared(decision, owner)
        assert (actual.candidate_refs, actual.reference_refs) == (expected.candidate_refs, expected.reference_refs)
        assert list(actual.observation) == list(expected.observation)
        for key, value in expected.observation.items():
            assert actual.observation[key].dtype == value.dtype and np.array_equal(actual.observation[key], value)
        mapping = encoder.mapping_prepared(decision, owner)
        assert mapping.candidate_refs == expected.candidate_refs
        assert mapping.reference_refs == expected.reference_refs
        assert mapping.legal_mask == tuple(bool(v) for v in expected.observation['action_mask'])
