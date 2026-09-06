"""Prove the repaired fixtures retain the accepted predecessor test sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).absolute().parents[1]
SUCCESSORS = ROOT.parent

_INTEGRATION_SOURCE = SUCCESSORS / "room_flows_v1/integration/Program.cs"
_INTEGRATION_SOURCE_SHA256 = "f836ca1fe736347ac8cba96bc595a0a74742589cf1cd62ca1204179880c9e6bf"
_INTEGRATION_REPLACEMENTS = (
    (
        b"Run,Room,Inventory,InventoryModel,Player,Map,true,!Closed,!Closed,false,Left,Left,false,",
        b"Run,Room,Inventory,InventoryModel,Player,Map,true,!Closed,!Closed,false,Left,true,false,",
    ),
    (
        b"Run,Room,Inventory,InventoryModel,Player,Map,!Left,!Closed,!Closed,false,Left,Left,false,",
        b"Run,Room,Inventory,InventoryModel,Player,Map,!Left,!Closed,!Closed,false,Left,true,false,",
    ),
)

_RUNTIME_COMPILES = {
    "../../room_release_v1/runtime_tests/Program.cs": "c75dd553ace08a14d7bef3be11494549ac9082bed2b3d5352f0fb13d4a055c82",
    "../../room_release_v1/runtime/RoomFlowTransportContracts.cs": "78b803563e21c9625ce93360871ec5a17e6ebd584f63d17d7f4b7241567d785b",
    "../../room_release_v1/runtime/RoomFlowTransportConfiguration.cs": "ef91d71b5278ea7f43e464f950ec90ffe9cdd2a26667f07c45f2f09ba7eb8bff",
    "../../room_release_v1/runtime/RoomFlowTransportProtocol.cs": "0a43e018ea94e0fa6a4f2ca0316c3ab1e76fd915ee5bc79cca32d3e936482114",
    "../../room_release_v1/runtime/OwnedByteFrameQueue.cs": "58f073d6b4faba5e26390ec4df10737f1859147c7cb9e60202ce6d13a005838b",
    "../../room_release_v1/runtime/RoomFlowTransportRuntime.cs": "4167956d8953787d6b205ea672c93029bd6b019029cffceb5c7b4dfcd784c884",
    "../../item_transport_v1/runtime/kernel/FixedTimeAuthenticator.cs": "de70823fa89b41bd6fc54e273f30cb2ef2bfcb4eec44e4ccb80e9a4b431edd25",
    "../../item_transport_v1/runtime/kernel/MonotonicTokenBucket.cs": "21be7a793d672eb9dc98c69475fe59d0bd7506ea1730ac4d0f5e5429a3743494",
}


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    checks = 0
    source = _INTEGRATION_SOURCE.read_bytes()
    if _sha256(source) != _INTEGRATION_SOURCE_SHA256:
        raise ValueError("integration_source_identity")
    checks += 1

    expected = source
    for old, new in _INTEGRATION_REPLACEMENTS:
        if expected.count(old) != 1 or new in expected:
            raise ValueError("integration_replacement_boundary")
        expected = expected.replace(old, new)
    if expected != (ROOT / "integration/Program.cs").read_bytes():
        raise ValueError("integration_derivation")
    checks += 1

    project_path = ROOT / "runtime_tests/Sts2AgentBridge.ShopMapPermissionV1.Transport.Tests.csproj"
    project = ET.fromstring(project_path.read_bytes())
    compiles = {
        node.attrib["Include"]
        for node in project.iter("Compile")
    }
    references = {
        node.attrib["Include"]
        for node in project.iter("ProjectReference")
    }
    if compiles != set(_RUNTIME_COMPILES) or references != {
        "../wire/Sts2AgentBridge.ShopMapPermissionV1.Wire.csproj"
    }:
        raise ValueError("runtime_project_closure")
    for relative, digest in _RUNTIME_COMPILES.items():
        if _sha256((project_path.parent / relative).resolve().read_bytes()) != digest:
            raise ValueError("runtime_source_identity")
    checks += 1

    print(json.dumps(
        {
            "schema_version": 1,
            "status": "passed",
            "suite": "shop_map_permission_fixture_derivation",
            "check_count": checks,
        },
        separators=(",", ":"),
    ))


if __name__ == "__main__":
    main()
