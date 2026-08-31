from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from game.backends.live import r0i_wire


VECTORS = Path("bridge/Sts2AgentBridge/contracts/live_probe_v0/vectors")


def _decision_vectors():
    return sorted(VECTORS.glob("*_decision_*.json"))


def _receipt_vectors():
    return sorted(VECTORS.glob("*_receipt_*.json"))


def test_accepted_inventory_is_exactly_bound() -> None:
    assert r0i_wire.accepted_vector_inventory(VECTORS) == (
        36,
        3511,
        "8dfc1e1e2571e66ea5a9652b1c45a80500209dc1b26b4a6bbfe87a44eb1ea1fe",
    )
    r0i_wire.verify_accepted_vector_inventory(VECTORS)


def test_every_accepted_decision_round_trips_byte_for_byte() -> None:
    assert len(_decision_vectors()) == 16
    for path in _decision_vectors():
        decision = r0i_wire.parse_decision(path.read_bytes())
        assert r0i_wire.encode_decision(decision) == path.read_bytes()
        assert "token" not in decision.__dict__


def test_every_accepted_receipt_round_trips_with_explicit_family() -> None:
    assert len(_receipt_vectors()) == 20
    for path in _receipt_vectors():
        family = path.name.split("_", 1)[0]
        receipt = r0i_wire.parse_receipt(path.read_bytes(), family=family)
        assert r0i_wire.encode_receipt(receipt) == path.read_bytes()


def test_reward_and_room_proceed_receipts_need_route_context() -> None:
    reward = (VECTORS / "reward_receipt_accepted.json").read_bytes()
    room = (VECTORS / "room_receipt_accepted.json").read_bytes()
    assert reward == room
    assert r0i_wire.parse_receipt(reward, family="reward").family == "reward"
    assert r0i_wire.parse_receipt(room, family="room").family == "room"


def test_error_envelopes_are_not_normal_receipts() -> None:
    for path in sorted(VECTORS.glob("error_*.json")):
        error = r0i_wire.parse_error_envelope(path.read_bytes())
        assert r0i_wire.encode_error_envelope(error) == path.read_bytes()
        with pytest.raises(r0i_wire.R0iWireError):
            r0i_wire.parse_receipt(path.read_bytes(), family="combat")


@pytest.mark.parametrize(
    "body",
    [
        b'{"schema_version":1,"status":"ready","decision_kind":"combat","actionable":true,"decision_id":"0000000000000000000000000000000000000000000000000000000000000000","round":1,"player":null,"enemies":[],"hand":[],"legal_actions":[],"outcome":null,"extra":true}',
        b'{"schema_version":1,"schema_version":1}',
        b'{"schema_version":2}',
    ],
)
def test_unknown_duplicate_and_wrong_schema_reject(body: bytes) -> None:
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_decision(body)


def test_binding_mismatch_and_inventory_mismatch_reject(tmp_path: Path) -> None:
    ready = (VECTORS / "combat_decision_ready.json").read_bytes()
    wrong = r0i_wire.BridgeBinding(r0i_wire.PROTOCOL, "1" * 64)
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_decision(ready, binding=wrong)
    (tmp_path / "combat_decision_ready.json").write_bytes(ready)
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.verify_accepted_vector_inventory(tmp_path)


def test_mismatched_parser_protocol_or_schema_identity_rejects() -> None:
    r0i_wire.verify_parser_manifest(r0i_wire.PARSER_MANIFEST)
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.verify_parser_manifest(replace(r0i_wire.PARSER_MANIFEST, protocol="other"))
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.verify_parser_manifest(replace(r0i_wire.PARSER_MANIFEST, schema_version=2))
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.verify_parser_manifest(replace(r0i_wire.PARSER_MANIFEST, schema_version=True))


def test_control_token_is_separate_from_public_decision() -> None:
    decision = r0i_wire.parse_decision((VECTORS / "map_decision_ready.json").read_bytes())
    assert decision.binding is not None
    control = r0i_wire.ControlAction(decision.binding, "select:0", "test-control-token")
    assert control.authorization_token == "test-control-token"
    assert "authorization_token" not in decision.__dict__


def test_receipt_family_requires_its_own_action_grammar() -> None:
    map_rejected = (VECTORS / "map_receipt_stale_decision.json").read_bytes()
    map_accepted = (VECTORS / "map_receipt_accepted.json").read_bytes()
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_receipt(map_rejected, family="combat")
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_receipt(map_accepted, family="reward")


def test_encoder_bounds_and_linkage_invariants_reject() -> None:
    map_ready = (VECTORS / "map_decision_ready.json").read_bytes()
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_decision(map_ready.replace(b'"col":2', b'"col":999', 1))
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_decision(map_ready.replace(b'"action_id":"select:0"', b'"action_id":"select:7"', 1))
    room_unsupported = (VECTORS / "room_decision_unsupported.json").read_bytes()
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_decision(room_unsupported.replace(b'"screen_kind":"event"', b'"screen_kind":"bogus"'))
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_decision(room_unsupported.replace(b'"room_ordinal":4', b'"room_ordinal":1000'))


def test_csharp_int32_domain_and_ready_zero_max_hp_are_exact() -> None:
    ready = (VECTORS / "combat_decision_ready.json").read_bytes()
    maximum = ready.replace(b'"round":1', b'"round":2147483647', 1)
    assert r0i_wire.encode_decision(r0i_wire.parse_decision(maximum)) == maximum
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_decision(
            ready.replace(b'"round":1', b'"round":2147483648', 1)
        )

    zero_max_hp = ready.replace(b'"hp":48,"max_hp":48', b'"hp":0,"max_hp":0', 1)
    assert r0i_wire.encode_decision(r0i_wire.parse_decision(zero_max_hp)) == zero_max_hp


@pytest.mark.parametrize(
    "body",
    [
        (VECTORS / "combat_decision_ready.json").read_bytes().replace(
            b'{"schema_version"', b'{ "schema_version"', 1
        ),
        (VECTORS / "combat_decision_ready.json").read_bytes().replace(
            b'{"schema_version":1,"status":"ready"',
            b'{"status":"ready","schema_version":1',
            1,
        ),
    ],
)
def test_noncanonical_whitespace_and_field_order_reject(body: bytes) -> None:
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.parse_decision(body)


def test_encoders_share_parser_invariants() -> None:
    decision = r0i_wire.parse_decision((VECTORS / "map_decision_ready.json").read_bytes())
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.encode_decision(replace(decision, actionable=False))
    receipt = r0i_wire.parse_receipt((VECTORS / "combat_receipt_accepted.json").read_bytes(), family="combat")
    with pytest.raises(r0i_wire.R0iWireError):
        r0i_wire.encode_receipt(replace(receipt, status="rejected"))


def test_public_payload_is_deeply_immutable() -> None:
    decision = r0i_wire.parse_decision((VECTORS / "map_decision_ready.json").read_bytes())
    with pytest.raises(TypeError):
        decision.fields["run_id"] = "invented"  # type: ignore[index]
    with pytest.raises(TypeError):
        decision.fields["candidates"][0]["col"] = 99  # type: ignore[index]
