"""Preserve old scope conflicts before any repaired-shop publication."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).absolute().parent))
import manage_live_campaign as manager
import manage_live_campaign_fixtures as fixtures
from tool_common import ToolFailure

def main():
    checks=0
    with tempfile.TemporaryDirectory(prefix="shop-map-conflicts-",dir="/private/tmp") as scratch:
        for kind,name in (("state",manager.LEGACY_STATE_ROOT_NAME),("state",manager.ITEM_STATE_ROOT_NAME),
                          ("state",manager.ROOM_STATE_ROOT_NAME),("state",manager.DIAGNOSTIC_STATE_ROOT_NAME),
                          ("overlay",manager.LEGACY_OVERLAY_ROOT_NAME),("overlay",manager.ITEM_OVERLAY_ROOT_NAME),
                          ("overlay",manager.DIAGNOSTIC_OVERLAY_ROOT_NAME)):
            tree=fixtures.FixtureTree(Path(scratch)/str(checks),preexisting_mods=True)
            conflict=(tree.application_support if kind=="state" else tree.mods_parent)/name
            conflict.mkdir(mode=0o700);sentinel=conflict/"sentinel";sentinel.write_bytes(b"preserve")
            before=conflict.stat();filler=fixtures.CredentialFiller()
            try:fixtures._install(tree,filler)
            except ToolFailure as failure:assert failure.error_code=="target_exists"
            else:raise AssertionError("conflict accepted")
            after=conflict.stat()
            assert (before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)
            assert sentinel.read_bytes()==b"preserve" and not filler.buffers
            assert not tree.state_root.exists() and not tree.operator_parent.exists() and not tree.overlay_root.exists()
            checks+=1
    print(json.dumps({"schema_version":1,"status":"passed","suite":"shop_map_permission_predecessor_conflicts","check_count":checks},separators=(",",":")))
if __name__=="__main__":main()
