"""Verify exact reviewed derivation bytes without accessing installed material."""
from __future__ import annotations
import difflib,hashlib,json
from pathlib import Path
ROOT=Path(__file__).absolute().parents[1]
def verify():
    repository=ROOT.parents[3]
    spec=json.loads((ROOT/'derivation.json').read_bytes())
    assert spec['schema_version']==1
    seen=set()
    for row in spec['derived']:
        source,target=Path(row['source']),Path(row['target'])
        assert not source.is_absolute() and not target.is_absolute() and '..' not in source.parts and '..' not in target.parts
        assert str(target) not in seen;seen.add(str(target))
        before,after=(repository/source).read_bytes(),(repository/target).read_bytes()
        assert hashlib.sha256(before).hexdigest()==row['source_sha256'] and hashlib.sha256(after).hexdigest()==row['target_sha256']
        assert ''.join(difflib.unified_diff(before.decode().splitlines(True),after.decode().splitlines(True),fromfile=str(source),tofile=str(target)))==row['unified_diff']
    return len(seen)
if __name__=='__main__':print(json.dumps(dict(schema_version=1,status='passed',suite='generic_event_release_derivation',check_count=verify()),separators=(',',':')))
