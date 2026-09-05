"""Collection bootstrap for the isolated sibling successor packages."""

from pathlib import Path
import sys


_SUCCESSORS_ROOT = Path(__file__).resolve().parents[2]
if (
    _SUCCESSORS_ROOT.name != "successors"
    or not (_SUCCESSORS_ROOT / "item_transport_v1" / "transport" / "item_transport.py").is_file()
    or not (_SUCCESSORS_ROOT / "item_wire_v1" / "host" / "item_host.py").is_file()
):
    raise ImportError("isolated successor source root mismatch")
_source = str(_SUCCESSORS_ROOT)
if _source not in sys.path:
    sys.path.insert(0, _source)
