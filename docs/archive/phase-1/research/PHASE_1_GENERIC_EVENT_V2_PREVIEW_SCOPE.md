# Generic event v2 removal preview mapping — bounded static scope

2026-09-07. Prepared for independent review before one new metadata-only
invocation. This is a new scope for the current generic-handler development;
no historical inspection command is rerun. No target read has occurred under
this scope as of preparation.

## Question and existing evidence

The retained removal command diagnostic is
`/private/tmp/event-card-callbacks-capture-08be47c191934886a0103cd5/result.json`,
246733 bytes, SHA256
`e8c6f9aad5035daa21e7329b89669c652c9845ae07049d9f1274b1cd26c762ca`.
It proves the shared `FromDeckForRemoval(Player,CardSelectorPrefs,Func<CardModel,bool>)`
request enters `FromDeckGeneric`, whose native path supplies the actual ordered
original domain to `NDeckCardSelectScreen.Create` and awaits `CardsSelected`.
The request returns selected originals; it does not remove cards itself.

Removal always opens preview at max selection, including when
`RequireManualConfirmation` is false. For variable counts the main Confirm
opens preview once min is reached. Only preview Confirm completes selection.
The retained removal `PreviewSelection` body creates an `NCard` from each
selected original, then an `NPreviewCardHolder`; it clears grid highlights.
Therefore a public holder-to-original mapping is necessary before advertising
preview confirmation. Counts and identity must never come from rendered text.

The retained preview diagnostic stdout is
`/private/tmp/event-card-preview-capture-235342f6df5b4c1ba424a6aa/stdout.bin`,
14163 bytes, SHA256
`587b2ee8484f2e372fb317416c94f048e47833d2e35f984e6a75dc62850e0857`.
Its original capture failed only canonical JSON escape comparison, and it remains
explicitly diagnostic evidence. It proves PreviewHolder directly inherits
NCardHolder and its Create calls Initialize; inherited CardModel reads CardNode.Model.
The separately retained CardNode getter is a direct backing-field read:
`sts2.il.MegaCrit.Sts2.Core.Nodes.Cards.Holders.NCardHolder.get_CardNode.jsonl`,
SHA256 `557f19dc40e8d3e0afe3578c47e916a3ab54309ce60cddcc1c7b54f741a8c33d`.
These artifacts were rehashed against their repository reports/selection manifest.

## Exact target and read boundary

One read of the exact physical pinned assembly:
`/Users/rowdeygoos/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64/sts2.dll`.
Expected size9363456 bytes and SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The scanner checks regular-file shape and nonsymlink ancestry before reading,
checks unchanged size/time and exact hash, and uses PEReader/MetadataReader only.
It does not load or execute the assembly or invoke any target API.
Target mode has no caller-selectable path; synthetic fixture mode is confined
to canonical absolute paths under `/private/tmp/` and rejects symlink ancestors.

Exactly six method bodies, exact signatures and return types, with no recursive
body following (prefix `MegaCrit.Sts2.Core` below):

- `Nodes.Cards.NCard.Create(Models.CardModel,Entities.UI.ModelVisibility)` → NCard.
- `Nodes.Cards.NCard.get_Model()` → CardModel.
- `Nodes.Cards.NCard.set_Model(Models.CardModel)` → void.
- `Nodes.Cards.Holders.NPreviewCardHolder.Initialize(Nodes.Cards.NCard,bool,bool)` → void.
- `Nodes.Cards.Holders.NCardHolder.SetCard(Nodes.Cards.NCard)` → void.
- `Nodes.Cards.Holders.NCardHolder.set_CardNode(Nodes.Cards.NCard)` → void.

Additionally emit only `NPreviewCardHolder`'s immediate base identity, declared
method signatures/attributes/returns/body-presence (at most256), and its explicit
MethodImpl mappings (at most64). This detects overridden/new property or SetCard
methods. Do not follow an unexpected override body under this scope. Fixed
method resolution may enumerate metadata type names but emits no type catalog,
interfaces, unrelated method declarations or unrelated bodies. No field values,
resources, source text, localization, asset content, saves, profiles, Cloud,
network, registry, launch, package or live-operation access.

Per body at most2500 IL instructions, total15000. User strings are replaced by
`user_string`; metadata operands remain symbolic identities. At most1MiB stdout,
4096 bytes stderr and30 seconds subprocess time. Output is a fresh `/private/tmp/`
directory with mode0700 and create-only0600 `stdout.bin`/`stderr.bin`. Errors and
bounded partial output are retained; an unsuccessful or incomplete projection
is not silently reused as a successful result.

## Frozen prepared tooling and synthetic validation

New scratch root `/private/tmp/generic-removal-preview-v2-a`, derived from
`/private/tmp/event-card-preview-a` without modifying it. Retained source manifest
SHA256 `57a66b5d69c19c2c01aadff7c71dcca1fd3b9972a9f14687c6a9ca0aab93972e`.
New source manifest `source_manifest.json`:1533 bytes, SHA256
`ea39dd301db097943719fc91d7a7cb5854919e34018b026b5b947779216976d0`,
covering all12 source/project/fixture files.

- Program.cs14057 bytes: `9a4abdd310eb228d3fae3f8220bf918bc09a4ce9452ed0c0861ef22517a23559`.
- capture.py13637 bytes: `91a48dfaa1e35b891595b1e57d2d9a92321bcc93885c3e04c07fa16dca97ecfc`.
- bundle/GenericRemovalPreviewV2.dll48128 bytes: `0daaa9d8be19bdabe045b4d99ceab37f15bf9fffe31bf47a6c297bce3e0dc479`.
- bundle/GenericRemovalPreviewV2.deps.json439 bytes: `685ce2b2356ecca7612ae72a105513d13bca6e09b8e04cb1ba0f90050746af4f`.
- bundle/GenericRemovalPreviewV2.runtimeconfig.json328 bytes: `4719954ee973dde9617a64d30002c1df89df2f75ab40e6b01db8b3126388ce5f`.

.NET9.0.303 Release build passed with zero warnings/errors and no packages.
`synthetic-result.json`:649 bytes, SHA256
`ce962829022768d7f0df03f0f0fe5aee8c2d5e005ec433efc8c46d2e33116178`:
17 passing synthetic checks, target_accessed=false. These cover exact six-body
selection, redaction/no body following, implicit override declarations, nested
`+` metadata canonical serialization, determinism, pin failure, instruction
ceiling, image/ancestor symlinks, malformed image, relative input/target path
override rejection, bounded create-only capture, output limit, failed subprocess
persistence, malformed output and linked bundle rejection. No target was read
by build or synthetic validation.

After independent review, the one invocation uses the frozen capture script,
`/private/tmp/sts-sdk-resume.6AJGPQ/sdk/dotnet`, its exact three-file bundle,
`--target`, and one fresh output root. Record exact invocation, hashes and
mapping assessment in the paired result document. A mismatch, missing body or
unexpected override stops mapping acceptance; it does not authorize recursive
inspection or a live operation.
