"""Reject each exact predecessor conflict before installation or credential read."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).absolute().parent))
import manage_live_campaign as manager
import manage_live_campaign_fixtures as fixtures
from tool_common import ToolFailure


def main():
    checks = 0
    conflicts = (("state", manager.LEGACY_STATE_ROOT_NAME), ("state", manager.ITEM_STATE_ROOT_NAME),
        ("state", manager.ROOM_STATE_ROOT_NAME), ("state", manager.DIAGNOSTIC_STATE_ROOT_NAME),
        ("state", manager.SHOP_MAP_STATE_ROOT_NAME), ("state", manager.CARD_SELECTION_STATE_ROOT_NAME),
        ("state", manager.CARD_COMPLETION_STATE_ROOT_NAME),
        ("overlay", manager.CARD_OVERLAY_ROOT_NAME),
        ("overlay", manager.LEGACY_OVERLAY_ROOT_NAME),
        ("overlay", manager.ITEM_OVERLAY_ROOT_NAME), ("overlay", manager.ROOM_OVERLAY_ROOT_NAME),
        ("overlay", manager.DIAGNOSTIC_OVERLAY_ROOT_NAME))
    with tempfile.TemporaryDirectory(prefix="card-selection-conflicts-", dir="/private/tmp") as scratch:
        for stage in ("install", "client"):
            for kind, name in conflicts:
                tree = fixtures.FixtureTree(Path(scratch) / str(checks), preexisting_mods=True)
                if stage == "client":
                    fixtures._install(tree)
                conflict = (tree.application_support if kind == "state" else tree.mods_parent) / name
                conflict.mkdir(mode=0o700)
                sentinel = conflict / "sentinel"
                sentinel.write_bytes(b"preserve")
                before = conflict.stat()
                filler = fixtures.CredentialFiller()
                try:
                    if stage == "install":
                        fixtures._install(tree, filler)
                    else:
                        layout = replace(tree.layout, user_profile=Path('/synthetic-profile'))
                        with (mock.patch.object(manager.pwd, 'getpwuid', return_value=SimpleNamespace(pw_dir='/synthetic-profile')),
                              mock.patch.object(manager, '_production_layout', return_value=layout),
                              mock.patch.object(manager, 'CANONICAL_ARTIFACTS', fixtures._POLICY),
                              mock.patch.object(manager, '_read_mutable_file', side_effect=AssertionError('credential read'))):
                            manager.validate_installed_for_client(tree.state_sha256)
                except ToolFailure as failure:
                    assert failure.error_code == "target_exists"
                else:
                    raise AssertionError("predecessor conflict accepted")
                after = conflict.stat()
                assert (before.st_dev, before.st_ino) == (after.st_dev, after.st_ino)
                assert sentinel.read_bytes() == b"preserve" and not filler.buffers
                if stage == "install":
                    assert not tree.state_root.exists() and not tree.operator_parent.exists() and not tree.overlay_root.exists()
                checks += 1
    print(json.dumps({"schema_version":1,"status":"passed","suite":"generic_event_release_predecessor_conflicts","check_count":checks}, separators=(",", ":")))


if __name__ == '__main__':
    main()
