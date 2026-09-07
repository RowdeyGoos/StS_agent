# Generic event lifecycle evidence

2026-09-07. Read-only audit of retained, hash-bound target metadata following
GENERIC-EVENT-V1-SMOKE-V1. No fresh game inspection, code execution, profile/save
access or live operation. Target: Steam build23811903, sts2 SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

The retained outputs under `/private/tmp/sts-mr-api-v47tiwjy` were rehashed against
`disposable_output_sha256` in PHASE_1_MISSING_ROOM_API_SELECTION.json:

| Output | SHA256 |
| --- | --- |
| NEventRoom--OptionButtonClicked.il.jsonl | 0bc8a9c44d569a492848d066b8b3328b18b4df76595aec1dd44aeeb7b5d72714 |
| NEventLayout--ClearOptions.il.jsonl | f8dd610ba7bba533e8416f3e11ba42b9da1ecde5cbd9c5f831747ce91989e0d4 |

OptionButtonClicked rejects locked options first. Proceed calls Chosen directly
at IL18. Other nonshared options call Layout.ClearOptions at IL49 before obtaining
EventSynchronizer at IL59 and calling ChooseLocalOption at IL65. ClearOptions
copies the container's children, removes each at IL40 and queues each for freeing
at IL46. Thus an ordinary choice's button is disposable presentation state, not
a live controller required throughout the option callback and child selection.

Frozen GenericEventV3Binding.ContextValid requires Valid(Controller), Event and
Option getter access after dispatch. GenericEventV3CardAdapter, RemovalAdapter
and RewardAdapter repeat those getters in initial and ongoing foreground checks.
The native fixtures' ForceClick invokes Chosen directly and never frees the
button. This mismatch can explain an immediate unsupported second read after the
chooser opens while Chosen/request ownership remains intact. The live result did
not include a rejection reason, so this is not proof it was the only failing
predicate or that real synchronizer causality was preserved.

The lifecycle contract separates strict live-button reservation before dispatch
from opaque retained receipt identity afterward. Scoped exact Chosen/request/
creation ownership, live run/player/room/layout/map/overlays, immutable option key,
whole-deck/offers, exact tasks and child lineage remain mandatory. No event-name
admission or fallback to global armed state is added. Test evidence and remaining
release/live gates belong in the acceptance ledger.
