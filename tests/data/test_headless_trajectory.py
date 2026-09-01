from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import pytest

from game.backends.headless.fixture_backend import FixtureBackend
from game.contracts.headless_v0 import (
    ActionRequest,
    ComponentEvidence,
    DecisionState,
    DecisionStatus,
    EvidenceLabel,
    HeadlessBinding,
    PolicyView,
    canonical_json,
)
from game.data.headless_trajectory import (
    HindsightTargetRecord,
    InterruptionPoint,
    PolicyReplayRecord,
    StreamRole,
    SyntheticAuditRecord,
    TrajectoryCompletion,
    TrajectoryIntegrityError,
    TrajectoryInterruptedError,
    TrajectoryRecorder,
    TrajectoryValidationError,
    decode_policy_replay,
    load_trajectory,
    policy_view_for,
    validate_trajectory,
)


def _record_fixture(
    fixture_id: str = "combat", trajectory_id: str = "fixture-combat-001"
):
    backend = FixtureBackend()
    decision = backend.reset(fixture_id)
    recorder = TrajectoryRecorder(trajectory_id, backend.manifest())
    while decision.status is DecisionStatus.ACTIONABLE:
        chosen = decision.candidates[0].candidate_id
        recorder.record_boundary(decision, chosen)
        transition = backend.apply(
            ActionRequest(HeadlessBinding.for_candidate(decision, chosen))
        )
        recorder.record_transition(transition)
        decision = transition.next_decision
    recorder.record_boundary(decision)
    return recorder.finalize()


def _validate(finalized):
    return validate_trajectory(
        finalized.manifest_json,
        finalized.policy_replay_jsonl,
        finalized.hindsight_target_jsonl,
        finalized.synthetic_audit_jsonl,
        expected_manifest_sha256=finalized.manifest_sha256,
    )


def _jsonl(raw: bytes) -> list[dict[str, object]]:
    return [json.loads(line) for line in raw.splitlines()]


def _manifest_digest(raw: bytes | str) -> str:
    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    return sha256(encoded).hexdigest()


def _manifest_with_stream(
    finalized, role: StreamRole, raw: bytes, *, completion: str | None = None
) -> bytes:
    value = json.loads(finalized.manifest_json)
    if completion is not None:
        value["completion"] = completion
    for stream in value["streams"]:
        if stream["role"] == role.value:
            stream["sha256"] = sha256(raw).hexdigest()
            stream["record_count"] = len(raw.splitlines())
    return canonical_json(value).encode("utf-8")


def _coordinated_rewrite(
    finalized,
    *,
    policy_hp: int | None = None,
    backend_fingerprint: str | None = None,
    evidence_label: str | None = None,
):
    manifest = json.loads(finalized.manifest_json)
    policy_values = _jsonl(finalized.policy_replay_jsonl)
    audit_values = _jsonl(finalized.synthetic_audit_jsonl)
    if policy_hp is not None:
        policy_values[0]["observation"]["data"]["player"]["hp"] = policy_hp
    if backend_fingerprint is not None:
        manifest["backend_fingerprint"] = backend_fingerprint
    if evidence_label is not None:
        manifest["evidence"][0]["label"] = evidence_label

    for policy_value, audit_value in zip(policy_values, audit_values):
        policy = PolicyReplayRecord.from_dict(policy_value)
        correlation = audit_value["decision_correlation"]
        decision = DecisionState.create(
            backend_id=manifest["backend_id"],
            backend_version=manifest["backend_version"],
            backend_fingerprint=manifest["backend_fingerprint"],
            content_version=manifest["content_version"],
            content_fingerprint=manifest["content_fingerprint"],
            rules_version=manifest["rules_version"],
            rules_fingerprint=manifest["rules_fingerprint"],
            run_id=correlation["run_id"],
            decision_sequence=correlation["decision_sequence"],
            status=policy.status,
            phase=policy.phase,
            observation=policy.observation,
            candidates=policy.candidates,
            public_events=policy.public_events,
        )
        correlation["decision_hash"] = decision.decision_hash

    for current, following in zip(audit_values, audit_values[1:]):
        if current["receipt"] is not None:
            next_correlation = following["decision_correlation"]
            current["receipt"]["next_run_id"] = next_correlation["run_id"]
            current["receipt"]["next_decision_sequence"] = next_correlation[
                "decision_sequence"
            ]
            current["receipt"]["next_decision_hash"] = next_correlation[
                "decision_hash"
            ]

    provenance = {
        "backend_fingerprint": manifest["backend_fingerprint"],
        "backend_id": manifest["backend_id"],
        "backend_version": manifest["backend_version"],
        "content_fingerprint": manifest["content_fingerprint"],
        "content_version": manifest["content_version"],
        "contract": manifest["contract"],
        "contract_fingerprint": manifest["contract_fingerprint"],
        "evidence": manifest["evidence"],
        "rules_fingerprint": manifest["rules_fingerprint"],
        "rules_version": manifest["rules_version"],
    }
    provenance_hash = sha256(
        b"headless_trajectory_v0.manifest_provenance.v1\0"
        + canonical_json(provenance).encode("utf-8")
    ).hexdigest()
    for audit_value in audit_values:
        audit_value["manifest_provenance_hash"] = provenance_hash

    policy_raw = b"".join(
        canonical_json(item).encode("utf-8") + b"\n" for item in policy_values
    )
    audit_raw = b"".join(
        canonical_json(item).encode("utf-8") + b"\n" for item in audit_values
    )
    for stream in manifest["streams"]:
        if stream["role"] == StreamRole.POLICY_REPLAY.value:
            stream["sha256"] = sha256(policy_raw).hexdigest()
            stream["record_count"] = len(policy_values)
        elif stream["role"] == StreamRole.SYNTHETIC_AUDIT.value:
            stream["sha256"] = sha256(audit_raw).hexdigest()
            stream["record_count"] = len(audit_values)
    manifest_raw = canonical_json(manifest).encode("utf-8")
    return manifest_raw, policy_raw, audit_raw


def test_golden_fixture_outputs_are_byte_deterministic_and_manifest_bound() -> None:
    first = _record_fixture()
    second = _record_fixture()

    assert first == second
    assert [item.role for item in first.manifest.streams] == [
        StreamRole.POLICY_REPLAY,
        StreamRole.HINDSIGHT_TARGET,
        StreamRole.SYNTHETIC_AUDIT,
    ]
    assert [item.record_count for item in first.manifest.streams] == [3, 1, 3]
    assert [item.sha256 for item in first.manifest.streams] == [
        "3679d08f05d652d7b62b3baff7c54912e67028e774b001d1eff5552ca53e414c",
        "33f3e1fafdf35bf49d3f39cc1542b8d1712923236bceae9e5c5e90d848a3e92a",
        "540393b3022c81bccb600df3f9a32d0d294e4a1cbca9cef2554a28596a9d5d77",
    ]
    assert sha256(first.manifest_json).hexdigest() == (
        "46612f63fdfc593372c4052ea77cca736e8e6088479a1b27a25c29c874a5c978"
    )
    assert _validate(first) == first


def test_policy_replay_has_only_then_current_public_fields_and_choice() -> None:
    finalized = _record_fixture()
    records = _jsonl(finalized.policy_replay_jsonl)

    assert set(records[0]) == {
        "candidates",
        "chosen_action",
        "observation",
        "phase",
        "public_events",
        "status",
    }
    assert records[0]["public_events"] == []
    assert records[1]["public_events"] == [
        {
            "data": {
                "card_definition_id": "strike",
                "target_enemy_definition_id": "jaw_worm",
            },
            "event_type": "combat.card_played",
            "phase": "combat",
            "sequence": 0,
        }
    ]
    assert records[2]["status"] == "terminal"
    assert records[2]["observation"]["data"]["outcome"] == "victory"
    assert b'"victory"' not in finalized.policy_replay_jsonl.splitlines()[0]
    assert b'"victory"' not in finalized.policy_replay_jsonl.splitlines()[1]

    forbidden = (
        b'"binding"',
        b'"control_token"',
        b'"decision_hash"',
        b'"future_state"',
        b'"hidden_offer"',
        b'"receipt"',
        b'"rng_state"',
        b'"run_id"',
        b'"snapshot_key"',
        b'"terminal_outcome"',
        b'"trajectory_id"',
    )
    assert all(item not in finalized.policy_replay_jsonl for item in forbidden)


def test_target_is_explicit_hindsight_and_audit_is_synthetic_operational_data() -> None:
    finalized = _record_fixture()
    [target] = _jsonl(finalized.hindsight_target_jsonl)
    audits = _jsonl(finalized.synthetic_audit_jsonl)

    assert target == {
        "completion": "terminal",
        "interruption_point": None,
        "label_timing": "hindsight",
        "policy_record_count": 3,
        "target_kind": "terminal_outcome",
        "terminal_outcome": "victory",
        "terminal_policy_record_index": 2,
        "trajectory_id": "fixture-combat-001",
    }
    assert [item["local_sequence"] for item in audits] == [0, 1, 2]
    assert [item["policy_record_index"] for item in audits] == [0, 1, 2]
    assert all(item["audit_scope"] == "synthetic_headless" for item in audits)
    assert all("decision_correlation" in item and "receipt" in item for item in audits)
    assert all(item["receipt"]["result"] == "accepted" for item in audits[:-1])
    assert audits[-1]["decision_correlation"]["candidate_id"] is None
    assert audits[-1]["receipt"] is None


def test_policy_conversion_is_type_gated_away_from_both_sidecars() -> None:
    finalized = _record_fixture()
    policy = _jsonl(finalized.policy_replay_jsonl)
    target = HindsightTargetRecord.from_dict(_jsonl(finalized.hindsight_target_jsonl)[0])
    audit = SyntheticAuditRecord.from_dict(_jsonl(finalized.synthetic_audit_jsonl)[0])

    view = policy_view_for(PolicyReplayRecord.from_dict(policy[0]))
    assert isinstance(view, PolicyView)
    assert not hasattr(target, "policy_view")
    assert not hasattr(audit, "policy_view")
    with pytest.raises(TypeError, match="Only PolicyReplayRecord"):
        policy_view_for(target)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Only PolicyReplayRecord"):
        policy_view_for(audit)  # type: ignore[arg-type]
    with pytest.raises(TrajectoryValidationError):
        decode_policy_replay(finalized.hindsight_target_jsonl)
    with pytest.raises(TrajectoryValidationError):
        decode_policy_replay(finalized.synthetic_audit_jsonl)


@pytest.mark.parametrize(
    "role",
    [
        StreamRole.POLICY_REPLAY,
        StreamRole.HINDSIGHT_TARGET,
        StreamRole.SYNTHETIC_AUDIT,
    ],
)
def test_modifying_or_truncating_each_stream_breaks_manifest_validation(role) -> None:
    finalized = _record_fixture()
    streams = {
        StreamRole.POLICY_REPLAY: finalized.policy_replay_jsonl,
        StreamRole.HINDSIGHT_TARGET: finalized.hindsight_target_jsonl,
        StreamRole.SYNTHETIC_AUDIT: finalized.synthetic_audit_jsonl,
    }
    modified = dict(streams)
    modified[role] = streams[role][:-1] + b" "
    with pytest.raises(TrajectoryIntegrityError, match="stream hash"):
        validate_trajectory(
            finalized.manifest_json,
            modified[StreamRole.POLICY_REPLAY],
            modified[StreamRole.HINDSIGHT_TARGET],
            modified[StreamRole.SYNTHETIC_AUDIT],
            expected_manifest_sha256=finalized.manifest_sha256,
        )

    truncated = dict(streams)
    truncated[role] = streams[role][:-1]
    with pytest.raises(TrajectoryIntegrityError, match="stream hash"):
        validate_trajectory(
            finalized.manifest_json,
            truncated[StreamRole.POLICY_REPLAY],
            truncated[StreamRole.HINDSIGHT_TARGET],
            truncated[StreamRole.SYNTHETIC_AUDIT],
            expected_manifest_sha256=finalized.manifest_sha256,
        )


def test_swapping_stream_roles_or_trajectories_breaks_manifest_validation() -> None:
    combat = _record_fixture()
    reward = _record_fixture("reward", "fixture-reward-001")

    with pytest.raises(TrajectoryIntegrityError, match="stream hash"):
        validate_trajectory(
            combat.manifest_json,
            combat.hindsight_target_jsonl,
            combat.policy_replay_jsonl,
            combat.synthetic_audit_jsonl,
            expected_manifest_sha256=combat.manifest_sha256,
        )
    with pytest.raises(TrajectoryIntegrityError, match="stream hash"):
        validate_trajectory(
            combat.manifest_json,
            reward.policy_replay_jsonl,
            combat.hindsight_target_jsonl,
            combat.synthetic_audit_jsonl,
            expected_manifest_sha256=combat.manifest_sha256,
        )
    with pytest.raises(TrajectoryIntegrityError, match="stream hash"):
        validate_trajectory(
            combat.manifest_json,
            combat.policy_replay_jsonl,
            reward.hindsight_target_jsonl,
            combat.synthetic_audit_jsonl,
            expected_manifest_sha256=combat.manifest_sha256,
        )
    with pytest.raises(TrajectoryIntegrityError, match="stream hash"):
        validate_trajectory(
            combat.manifest_json,
            combat.policy_replay_jsonl,
            combat.hindsight_target_jsonl,
            reward.synthetic_audit_jsonl,
            expected_manifest_sha256=combat.manifest_sha256,
        )


def test_cross_stream_correlations_fail_even_if_a_tampered_stream_is_rehashed() -> None:
    finalized = _record_fixture()
    audits = _jsonl(finalized.synthetic_audit_jsonl)
    audits[0]["decision_correlation"]["candidate_id"] = "cand." + "0" * 64
    audit_raw = b"".join(
        canonical_json(item).encode("utf-8") + b"\n" for item in audits
    )
    manifest = _manifest_with_stream(finalized, StreamRole.SYNTHETIC_AUDIT, audit_raw)

    with pytest.raises(TrajectoryIntegrityError, match="chosen policy action"):
        validate_trajectory(
            manifest,
            finalized.policy_replay_jsonl,
            finalized.hindsight_target_jsonl,
            audit_raw,
            expected_manifest_sha256=_manifest_digest(manifest),
        )


def test_rehashed_policy_fact_change_fails_authoritative_decision_reconstruction() -> None:
    finalized = _record_fixture()
    records = _jsonl(finalized.policy_replay_jsonl)
    assert records[0]["observation"]["data"]["player"]["hp"] == 61
    records[0]["observation"]["data"]["player"]["hp"] = 60
    policy_raw = b"".join(
        canonical_json(item).encode("utf-8") + b"\n" for item in records
    )
    manifest = _manifest_with_stream(
        finalized, StreamRole.POLICY_REPLAY, policy_raw
    )

    with pytest.raises(TrajectoryIntegrityError, match="audit decision identity"):
        validate_trajectory(
            manifest,
            policy_raw,
            finalized.hindsight_target_jsonl,
            finalized.synthetic_audit_jsonl,
            expected_manifest_sha256=_manifest_digest(manifest),
        )


def test_manifest_backend_fingerprint_change_fails_boundary_reconstruction() -> None:
    finalized = _record_fixture()
    manifest = json.loads(finalized.manifest_json)
    manifest["backend_fingerprint"] = "0" * 64
    manifest_raw = canonical_json(manifest)

    with pytest.raises(TrajectoryIntegrityError, match="audit decision identity"):
        validate_trajectory(
            manifest_raw,
            finalized.policy_replay_jsonl,
            finalized.hindsight_target_jsonl,
            finalized.synthetic_audit_jsonl,
            expected_manifest_sha256=_manifest_digest(manifest_raw),
        )

    evidence_manifest = json.loads(finalized.manifest_json)
    evidence_manifest["evidence"][0]["label"] = "combat_v0"
    evidence_manifest_raw = canonical_json(evidence_manifest)
    with pytest.raises(TrajectoryIntegrityError, match="Audit provenance"):
        validate_trajectory(
            evidence_manifest_raw,
            finalized.policy_replay_jsonl,
            finalized.hindsight_target_jsonl,
            finalized.synthetic_audit_jsonl,
            expected_manifest_sha256=_manifest_digest(evidence_manifest_raw),
        )

    [target] = _jsonl(finalized.hindsight_target_jsonl)
    target["terminal_outcome"] = "defeat"
    target_raw = canonical_json(target).encode("utf-8") + b"\n"
    manifest = _manifest_with_stream(
        finalized, StreamRole.HINDSIGHT_TARGET, target_raw
    )
    with pytest.raises(TrajectoryIntegrityError, match="observable terminal"):
        validate_trajectory(
            manifest,
            finalized.policy_replay_jsonl,
            target_raw,
            finalized.synthetic_audit_jsonl,
            expected_manifest_sha256=_manifest_digest(manifest),
        )


@pytest.mark.parametrize(
    "rewrite",
    (
        {"policy_hp": 60},
        {"backend_fingerprint": "0" * 64},
        {"evidence_label": "combat_v0"},
    ),
)
def test_coordinated_rewrites_fail_the_original_trusted_manifest_anchor(rewrite) -> None:
    finalized = _record_fixture()
    manifest_raw, policy_raw, audit_raw = _coordinated_rewrite(
        finalized, **rewrite
    )
    rewritten_digest = _manifest_digest(manifest_raw)
    assert rewritten_digest != finalized.manifest_sha256

    # The rewrite is internally self-consistent, which is deliberately not an
    # immutability claim without the caller's previously retained digest.
    validate_trajectory(
        manifest_raw,
        policy_raw,
        finalized.hindsight_target_jsonl,
        audit_raw,
        expected_manifest_sha256=rewritten_digest,
    )
    with pytest.raises(TrajectoryIntegrityError, match="trusted expected SHA-256"):
        validate_trajectory(
            manifest_raw,
            policy_raw,
            finalized.hindsight_target_jsonl,
            audit_raw,
            expected_manifest_sha256=finalized.manifest_sha256,
        )


def test_public_validation_requires_a_strict_external_manifest_anchor() -> None:
    finalized = _record_fixture()
    arguments = (
        finalized.manifest_json,
        finalized.policy_replay_jsonl,
        finalized.hindsight_target_jsonl,
        finalized.synthetic_audit_jsonl,
    )

    with pytest.raises(TypeError, match="expected_manifest_sha256"):
        validate_trajectory(*arguments)
    for invalid in ("0" * 63, "A" * 64, "not-a-digest"):
        with pytest.raises(TrajectoryValidationError, match="canonical form"):
            validate_trajectory(*arguments, expected_manifest_sha256=invalid)
    with pytest.raises(TrajectoryIntegrityError, match="trusted expected SHA-256"):
        validate_trajectory(*arguments, expected_manifest_sha256="0" * 64)
    noncanonical = b" " + finalized.manifest_json
    with pytest.raises(TrajectoryValidationError, match="not canonical"):
        validate_trajectory(
            noncanonical,
            *arguments[1:],
            expected_manifest_sha256=_manifest_digest(noncanonical),
        )


def test_unknown_duplicate_and_noncanonical_policy_fields_fail_closed() -> None:
    finalized = _record_fixture()
    [first, *rest] = finalized.policy_replay_jsonl.splitlines()
    value = json.loads(first)
    value["receipt"] = {"result": "accepted"}
    raw = canonical_json(value).encode("utf-8") + b"\n"
    raw += b"".join(line + b"\n" for line in rest)
    manifest = _manifest_with_stream(finalized, StreamRole.POLICY_REPLAY, raw)
    with pytest.raises(TrajectoryValidationError, match="unknown field"):
        validate_trajectory(
            manifest,
            raw,
            finalized.hindsight_target_jsonl,
            finalized.synthetic_audit_jsonl,
            expected_manifest_sha256=_manifest_digest(manifest),
        )

    duplicate = first[:-1] + b',"status":"actionable"}'
    raw = duplicate + b"\n" + b"".join(line + b"\n" for line in rest)
    manifest = _manifest_with_stream(finalized, StreamRole.POLICY_REPLAY, raw)
    with pytest.raises(TrajectoryValidationError, match="Duplicate JSON field"):
        validate_trajectory(
            manifest,
            raw,
            finalized.hindsight_target_jsonl,
            finalized.synthetic_audit_jsonl,
            expected_manifest_sha256=_manifest_digest(manifest),
        )

    raw = b" " + finalized.policy_replay_jsonl
    manifest = _manifest_with_stream(finalized, StreamRole.POLICY_REPLAY, raw)
    with pytest.raises(TrajectoryValidationError, match="not canonical"):
        validate_trajectory(
            manifest,
            raw,
            finalized.hindsight_target_jsonl,
            finalized.synthetic_audit_jsonl,
            expected_manifest_sha256=_manifest_digest(manifest),
        )


def test_interruption_before_choice_is_explicit_and_validated() -> None:
    backend = FixtureBackend()
    decision = backend.reset("combat")
    recorder = TrajectoryRecorder("interrupted-before-choice", backend.manifest())
    recorder.record_boundary(decision)

    with pytest.raises(TrajectoryInterruptedError):
        recorder.finalize()
    finalized = recorder.finalize_interrupted()

    assert finalized.manifest.completion is TrajectoryCompletion.INTERRUPTED
    assert finalized.manifest.interruption_point is InterruptionPoint.BEFORE_CHOICE
    assert finalized.manifest.descriptor(StreamRole.SYNTHETIC_AUDIT).record_count == 1
    [audit] = _jsonl(finalized.synthetic_audit_jsonl)
    assert audit["decision_correlation"]["decision_hash"] == decision.decision_hash
    assert audit["decision_correlation"]["candidate_id"] is None
    assert audit["receipt"] is None
    [target] = _jsonl(finalized.hindsight_target_jsonl)
    assert target["terminal_outcome"] is None
    assert target["label_timing"] == "hindsight"
    assert _validate(finalized) == finalized


def test_interruption_between_choice_receipt_and_next_boundary_is_detected() -> None:
    backend = FixtureBackend()
    decision = backend.reset("combat")

    awaiting = TrajectoryRecorder("interrupted-awaiting-receipt", backend.manifest())
    chosen = decision.candidates[0].candidate_id
    awaiting.record_boundary(decision, chosen)
    finalized = awaiting.finalize_interrupted()
    assert finalized.manifest.interruption_point is InterruptionPoint.AWAITING_RECEIPT
    [audit] = _jsonl(finalized.synthetic_audit_jsonl)
    assert audit["decision_correlation"]["candidate_id"] == chosen
    assert audit["receipt"] is None
    assert _validate(finalized) == finalized

    backend = FixtureBackend()
    decision = backend.reset("combat")
    before_next = TrajectoryRecorder("interrupted-before-next", backend.manifest())
    chosen = decision.candidates[0].candidate_id
    before_next.record_boundary(decision, chosen)
    transition = backend.apply(
        ActionRequest(HeadlessBinding.for_candidate(decision, chosen))
    )
    before_next.record_transition(transition)
    finalized = before_next.finalize_interrupted()
    assert finalized.manifest.interruption_point is InterruptionPoint.BEFORE_NEXT_BOUNDARY
    [audit] = _jsonl(finalized.synthetic_audit_jsonl)
    assert audit["receipt"]["result"] == "accepted"
    assert _validate(finalized) == finalized


def test_unsupported_fixture_has_separate_unavailable_hindsight_target() -> None:
    finalized = _record_fixture("unsupported", "fixture-unsupported-001")
    [target] = _jsonl(finalized.hindsight_target_jsonl)

    assert finalized.manifest.completion is TrajectoryCompletion.UNSUPPORTED
    assert target["completion"] == "unsupported"
    assert target["terminal_outcome"] is None
    assert target["terminal_policy_record_index"] is None
    [audit] = _jsonl(finalized.synthetic_audit_jsonl)
    assert audit["decision_correlation"]["decision_sequence"] == 0
    assert audit["decision_correlation"]["candidate_id"] is None
    assert audit["receipt"] is None


def test_rehashed_missing_boundary_correlation_rejects_unsupported_and_interrupted() -> None:
    unsupported = _record_fixture("unsupported", "missing-unsupported-correlation")

    backend = FixtureBackend()
    decision = backend.reset("combat")
    recorder = TrajectoryRecorder("missing-interrupted-correlation", backend.manifest())
    recorder.record_boundary(decision)
    interrupted = recorder.finalize_interrupted()

    for finalized in (unsupported, interrupted):
        manifest = _manifest_with_stream(
            finalized, StreamRole.SYNTHETIC_AUDIT, b""
        )
        with pytest.raises(TrajectoryValidationError, match="Every policy boundary"):
            validate_trajectory(
                manifest,
                finalized.policy_replay_jsonl,
                finalized.hindsight_target_jsonl,
                b"",
                expected_manifest_sha256=_manifest_digest(manifest),
            )


def test_recorder_rejects_live_or_nonfixture_evidence_and_provenance_mismatch() -> None:
    backend = FixtureBackend()
    manifest = backend.manifest()
    live_capabilities = replace(manifest.capabilities, live_truth=True)
    live_manifest = replace(manifest, capabilities=live_capabilities)
    with pytest.raises(TrajectoryValidationError, match="Live audit"):
        TrajectoryRecorder("live-forbidden", live_manifest)

    live_evidence = tuple(
        ComponentEvidence(
            item.component,
            EvidenceLabel.LIVE_OBSERVED,
            item.version,
            item.fingerprint,
        )
        for item in manifest.evidence
    )
    with pytest.raises(TrajectoryValidationError, match="only combat_v0"):
        TrajectoryRecorder(
            "live-evidence-forbidden", replace(manifest, evidence=live_evidence)
        )

    decision = backend.reset("combat")
    recorder = TrajectoryRecorder(
        "wrong-provenance", replace(manifest, backend_fingerprint="0" * 64)
    )
    with pytest.raises(TrajectoryValidationError, match="provenance"):
        recorder.record_boundary(decision, decision.candidates[0].candidate_id)


def test_rejected_next_boundary_choice_is_atomic_and_retry_matches_clean_recording() -> None:
    clean = _record_fixture()
    backend = FixtureBackend()
    decision = backend.reset("combat")
    recorder = TrajectoryRecorder("fixture-combat-001", backend.manifest())

    first_choice = decision.candidates[0].candidate_id
    recorder.record_boundary(decision, first_choice)
    wrong_backend = FixtureBackend()
    wrong_backend.reset("combat")
    wrong_decision = wrong_backend.reset("combat")
    wrong_choice = wrong_decision.candidates[0].candidate_id
    wrong_transition = wrong_backend.apply(
        ActionRequest(HeadlessBinding.for_candidate(wrong_decision, wrong_choice))
    )
    with pytest.raises(TrajectoryValidationError, match="does not correlate"):
        recorder.record_transition(wrong_transition)
    first_transition = backend.apply(
        ActionRequest(HeadlessBinding.for_candidate(decision, first_choice))
    )
    recorder.record_transition(first_transition)
    next_decision = first_transition.next_decision

    with pytest.raises(TrajectoryValidationError, match="not advertised"):
        recorder.record_boundary(next_decision, "cand." + "0" * 64)

    second_choice = next_decision.candidates[0].candidate_id
    recorder.record_boundary(next_decision, second_choice)
    second_transition = backend.apply(
        ActionRequest(HeadlessBinding.for_candidate(next_decision, second_choice))
    )
    recorder.record_transition(second_transition)
    recorder.record_boundary(second_transition.next_decision)

    assert recorder.finalize() == clean


def test_file_set_is_physical_exclusive_and_manifest_is_written_last(tmp_path: Path) -> None:
    finalized = _record_fixture()
    paths = finalized.write_to(tmp_path)

    assert paths.policy_replay.read_bytes() == finalized.policy_replay_jsonl
    assert paths.hindsight_target.read_bytes() == finalized.hindsight_target_jsonl
    assert paths.synthetic_audit.read_bytes() == finalized.synthetic_audit_jsonl
    assert paths.manifest.read_bytes() == finalized.manifest_json
    assert load_trajectory(
        tmp_path,
        finalized.manifest.trajectory_id,
        expected_manifest_sha256=finalized.manifest_sha256,
    ) == finalized
    with pytest.raises(FileExistsError):
        finalized.write_to(tmp_path)


def test_disk_load_requires_anchor_and_rejects_requested_id_renames(tmp_path: Path) -> None:
    finalized = _record_fixture(trajectory_id="actual-trajectory")
    source = finalized.write_to(tmp_path / "source")

    with pytest.raises(TypeError, match="expected_manifest_sha256"):
        load_trajectory(tmp_path / "source", "actual-trajectory")
    with pytest.raises(TrajectoryValidationError, match="canonical form"):
        load_trajectory(
            tmp_path / "source",
            "actual-trajectory",
            expected_manifest_sha256="A" * 64,
        )
    with pytest.raises(TrajectoryIntegrityError, match="trusted expected SHA-256"):
        load_trajectory(
            tmp_path / "source",
            "actual-trajectory",
            expected_manifest_sha256="0" * 64,
        )

    renamed_root = tmp_path / "renamed"
    renamed_root.mkdir()
    requested = "requested-trajectory"
    renamed = type(source).in_directory(renamed_root, requested)
    renamed.policy_replay.write_bytes(source.policy_replay.read_bytes())
    renamed.hindsight_target.write_bytes(source.hindsight_target.read_bytes())
    renamed.synthetic_audit.write_bytes(source.synthetic_audit.read_bytes())
    renamed.manifest.write_bytes(source.manifest.read_bytes())

    with pytest.raises(TrajectoryIntegrityError, match="Requested trajectory ID"):
        load_trajectory(
            renamed_root,
            requested,
            expected_manifest_sha256=finalized.manifest_sha256,
        )


def test_missing_manifest_or_stream_is_detected_as_interrupted(tmp_path: Path) -> None:
    finalized = _record_fixture()
    paths = finalized.write_to(tmp_path / "complete")
    paths.synthetic_audit.unlink()
    with pytest.raises(TrajectoryInterruptedError, match="incomplete"):
        load_trajectory(
            tmp_path / "complete",
            finalized.manifest.trajectory_id,
            expected_manifest_sha256=finalized.manifest_sha256,
        )

    partial = tmp_path / "partial"
    partial.mkdir()
    partial_paths = type(paths).in_directory(partial, finalized.manifest.trajectory_id)
    partial_paths.policy_replay.write_bytes(finalized.policy_replay_jsonl)
    with pytest.raises(TrajectoryInterruptedError, match="incomplete"):
        load_trajectory(
            partial,
            finalized.manifest.trajectory_id,
            expected_manifest_sha256=finalized.manifest_sha256,
        )


def test_manifest_and_records_are_frozen_and_stream_file_names_are_role_bound() -> None:
    finalized = _record_fixture()
    with pytest.raises((AttributeError, TypeError)):
        finalized.manifest.trajectory_id = "other"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        finalized.manifest.streams[0].sha256 = "0" * 64  # type: ignore[misc]

    value = json.loads(finalized.manifest_json)
    value["streams"][0]["file_name"] = "other.policy.jsonl"
    with pytest.raises(TrajectoryValidationError, match="file names"):
        manifest_raw = canonical_json(value)
        validate_trajectory(
            manifest_raw,
            finalized.policy_replay_jsonl,
            finalized.hindsight_target_jsonl,
            finalized.synthetic_audit_jsonl,
            expected_manifest_sha256=_manifest_digest(manifest_raw),
        )
