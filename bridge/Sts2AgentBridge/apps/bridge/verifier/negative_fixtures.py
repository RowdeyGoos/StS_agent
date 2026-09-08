"""The metadata verifier rejects incomplete and non-production assemblies."""
from pathlib import Path
import subprocess
import sys
import tempfile


dotnet, verifier, candidate, fixture = sys.argv[1:]
with tempfile.TemporaryDirectory(prefix='sts-unified-verifier-', dir='/private/tmp') as scratch:
    truncated = Path(scratch) / 'truncated.dll'
    truncated.write_bytes(Path(candidate).read_bytes()[:128])
    for path in (truncated, Path(fixture)):
        result = subprocess.run([dotnet, verifier, str(path)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        if result.returncode != 3:
            raise AssertionError('invalid assembly accepted')
print('Rejected truncated PE and non-production fixture assembly.')
