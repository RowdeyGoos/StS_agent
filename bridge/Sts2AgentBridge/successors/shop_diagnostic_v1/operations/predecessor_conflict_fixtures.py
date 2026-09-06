"""All predecessor conflicts are preserved before any diagnostic publication."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).absolute().parent))
import manage_live_campaign as manager
import manage_live_campaign_fixtures as fixtures
from tool_common import ToolFailure

def main():
    checks=0
    with tempfile.TemporaryDirectory(prefix="shop-diagnostic-conflicts-",dir="/private/tmp") as scratch:
        for kind, name in (("state",manager.LEGACY_STATE_ROOT_NAME),("state",manager.ITEM_STATE_ROOT_NAME),
                           ("state",manager.ROOM_STATE_ROOT_NAME),("overlay",manager.LEGACY_OVERLAY_ROOT_NAME),
                           ("overlay",manager.ITEM_OVERLAY_ROOT_NAME),("overlay",manager.ROOM_OVERLAY_ROOT_NAME)):
            tree=fixtures.FixtureTree(Path(scratch)/str(checks),preexisting_mods=True)
            conflict=(tree.application_support if kind=="state" else tree.mods_parent)/name
            conflict.mkdir(mode=0o700); sentinel=conflict/"sentinel";sentinel.write_bytes(b"preserve")
            before=conflict.stat();filler=fixtures.CredentialFiller()
            try:fixtures._install(tree,filler)
            except ToolFailure as failure:
                assert failure.error_code=="target_exists"
            else:raise AssertionError("conflict accepted")
            after=conflict.stat()
            assert (before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)
            assert sentinel.read_bytes()==b"preserve" and not filler.buffers
            assert not tree.state_root.exists() and not tree.operator_parent.exists()
            assert not tree.overlay_root.exists()
            checks+=1
        for extra in (("--flow-kind","shop"),("--flow-kind","event"),("--flow-kind","shop_diagnostic")):
            args=["--mode","install","--user-profile","/synthetic","--effective-uid","501","--artifact-root","/synthetic-artifacts",*extra]
            try:manager.parse_args(args)
            except ToolFailure:pass
            else:raise AssertionError("selection flag accepted")
            checks+=1
    print(json.dumps({"schema_version":1,"status":"passed","suite":"shop_diagnostic_predecessor_conflicts","check_count":checks},separators=(",",":")))
if __name__=="__main__":main()
