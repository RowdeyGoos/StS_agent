# Phase 1 event card preview candidate evidence scope

- Date: 2026-09-06
- Status: proposed; independently review before any target invocation
- Disposable source root: `/private/tmp/event-card-preview-a`
- Evidence boundary: hash-verified retained static outputs and inert synthetic
  managed assemblies only

## Question and retained evidence

The generic event-card adapter needs an authoritative way to map every visible
multi-upgrade preview model back to the exact original model selected before
dispatch. It must not infer that relationship from card keys, order, upgrade
levels, or cleared grid highlights.

The retained selection authority
`PHASE_1_CARD_SELECTION_API_SELECTION.json` has SHA-256
`ec8b8d53858182e8e75d4efebe2a843de7a6d9b74b9de2f5b9c1c2252ad349b9`.
The following retained raw outputs were rehashed against its
`raw_output_hashes` map before this scope was prepared:

- `CardModel` public member inventory:
  `400a026fad1fced511b8f375385efc61cd96f1f748922a17a5821fb4cba3b92d`;
- `NDeckUpgradeSelectScreen.OnCardClicked(CardModel)`:
  `01bf27c78e87361d13a7eb87550cafa44a4157ef035d01e522642b7ef3bbf3cb`;
- `NDeckCardSelectScreen.PreviewSelection()` overload set:
  `fc41fd1ae51c4d2b852ab7490385a3900a7e2d28211f6c1a600f337c69dc677e`;
- `NCardHolder.get_CardModel()`:
  `d1ee29e35c1a4e5f2f267eeea522ccb76c2809121bbdd6859ccb5f0a2f96ec59`.

Those bytes establish these limited facts:

1. multi-upgrade preview construction calls
   `ICardScope.CloneCard(original)` at IL offset 283, calls
   `UpgradeInternal()` on that returned model at 290, passes it to
   `NCard.Create` at 304, and passes that card to
   `NPreviewCardHolder.Create` at 319;
2. ordinary deck-card removal preview passes the selected original directly to
   `NCard.Create` at 130 and then to `NPreviewCardHolder.Create` at 139, so no
   clone-to-original inference is required for that path;
3. `NCardHolder.get_CardModel()` obtains `CardNode` and returns
   `NCard.get_Model()`; and
4. `CardModel` declares public `get_CloneOf()`, `get_IsClone()`, and
   `CreateClone()` members with the expected return types.

The retained bytes do not contain those three `CardModel` bodies, the concrete
`ICardScope.CloneCard` candidates, or the `NPreviewCardHolder.Create` body.
They do not prove interface dispatch or the preview clone's original.

## Exact finite selection

The proposed metadata-only tool reads one managed image only after its byte
identity and regular non-linked file-shape checks pass. It selects exactly:

- `CardModel.get_CloneOf()`;
- `CardModel.get_IsClone()`;
- `CardModel.CreateClone()`;
- the bodyless declaration `ICardScope.CloneCard(CardModel)`;
- `NCardHolder.get_CardModel()`;
- `NPreviewCardHolder.Create(NCard,bool,bool)` and the preview holder's exact
  immediate base.

It enumerates at most 32 concrete types assignable to the exact `ICardScope`
definition. For each type it emits its bounded local hierarchy and interface
closure, every exact-signature `CloneCard(CardModel):CardModel` method candidate
found on that hierarchy, every default-interface candidate body, and every
exact `MethodImpl` table row. Candidate methods, bodies, and mappings carry
their metadata tokens, flags, signature result, and stable identity. Distinct
method definitions that collapse to one textual identity fail closed; repeated
discovery of the same handle is allowed. Distinct `MethodImpl` rows retain
their separate tokens and are never collapsed.

The packet deliberately does not select or claim the method invoked by CLR
interface dispatch. In particular, a derived public `new CloneCard` and an
inherited base implementation are both emitted as candidates unless an exact
`MethodImpl` row proves a mapping. Result-level review may bind a concrete
runtime type only from the finite returned evidence.

The canonical result contains only the fixed schema, image hash, fixed
declaration/holder facts, implementer hierarchies, interfaces, bounded method
candidates and mappings, and decoded instructions for the selected bodies.
User strings are represented only as `user_string`. Bounds are 32 implementers,
64 local ancestors, 128 interfaces and candidates per implementer, 128
`MethodImpl` rows, 48 bodies, 2,500 instructions per body, 50,000 total
instructions, and 100,000,000 input bytes. The capture layer separately caps
the complete serialized stdout at 2,097,152 bytes. The owned image buffer is
zeroed after inspection. Linked files or ancestors, changed files, ambiguous
exact definitions, ancestry cycles, missing bodies, malformed IL, and every
bound overflow fail closed.

Target mode is pinned to the already accepted `sts2.dll` byte identity:

- size: `9,363,456` bytes;
- SHA-256:
  `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.

The tool requires fully qualified paths, rejects linked ancestors,
directories/devices and zero-length special files before opening, and verifies
stable length/time around its read. The wrapper independently requires a
regular non-linked input immediately before launch. The tool uses
`System.Reflection.Metadata`/`PEReader`; it never loads or executes the
inspected assembly.

## Private bounded capture

`capture.py` rejects a linked bundle before enumeration and verifies all three
exact bundle files before inspecting an input. It launches without stdin,
drains stdout/stderr concurrently, and kills and reaps on a 30-second deadline
or byte overflow. Stdout is capped at 2,097,152 bytes and stderr at 4,096 bytes.

Immediately after the child is reaped, the wrapper creates `stdout.bin` and
`stderr.bin` exactly once with `O_EXCL`, mode `0600`, and `fsync`, inside a
fresh direct child of `/private/tmp` created with mode `0700`. This persistence
happens before checking the exit code, stderr, JSON schema, canonical encoding,
or semantic counts. A target-only failure therefore retains bounded private
diagnostic bytes without a public summary. A successful result is validated
from the persisted stdout bytes and only then emits a count/hash summary.
Existing output roots, linked paths, malformed/noncanonical JSON, unexpected
stderr, nonzero exits, deadlines and output overflows emit no summary.

The release tool was built twice in separate disposable roots and all three
files compared byte-for-byte:

- `EventCardPreview.dll` (55,296 bytes):
  `caa81357e3c1a212e7999ab9d51267366ccc8c7fbe1dafa12a7362f819b5745c`;
- `EventCardPreview.deps.json` (418 bytes):
  `dbb1ee80c2eec9ddbd00ff9bf2140de8617a01e55ae6cc363ffa96629e686d18`;
- `EventCardPreview.runtimeconfig.json` (328 bytes):
  `4719954ee973dde9617a64d30002c1df89df2f75ab40e6b01db8b3126388ce5f`.

## Disposable packet identities

The 12-file source manifest is
`/private/tmp/event-card-preview-a/source_manifest.json`, size 1,886 bytes,
SHA-256 `57a66b5d69c19c2c01aadff7c71dcca1fd3b9972a9f14687c6a9ca0aab93972e`.
Its principal identities are:

- `Program.cs`:
  `abf480ba2b3705ed9f8a0982718705a1221aa4087add89e12a54e35bd202c53a`;
- `capture.py`:
  `8f823279dc59938b87d6e30d8753b40259343878613beb583db211d1be1cbb49`;
- `run_fixtures.py`:
  `97253dc811414cff934e3f9572f7ec6b3d57165d1256be3a5a4674cb5caa4b4b`;
- `synthetic/valid/Types.cs`:
  `d6410f38049c5d83d4fa6b8ef3e2e365e8e89c4f291573c2939f2cdb00371cb7`.

The manifest itself pins all other helper, project, NuGet and overflow-fixture
bytes.

## Stop boundary

This scope does not authorize a target invocation. The disposable tool has run
only against inert synthetic assemblies. After independent review of this
scope, exact packet, and synthetic result, the coordinator may separately
authorize one exact metadata-only invocation against the pinned image. A
failure ends that invocation without a looser retry. No additional member,
caller, resource, localization, profile/save, Cloud, gameplay, native runtime,
network, reflection, or private-field access is included.
