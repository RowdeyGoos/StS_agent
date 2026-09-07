# Proposed holder projection and initialization metadata read

The proposal below is preserved from before execution. Its reviewed single
metadata invocation is now complete; see the [result](PHASE_1_GENERIC_CANDIDATE_HOLDER_RESULT.md). No target code was executed.

Purpose: resolve whether NCardHolder reassignment and NGridCardHolder overrides retain the offered CardModel as their public CardModel, and how the native holder initializes its hitbox. This can identify a static incompatibility with candidate admission; it cannot by itself identify the live predicate that emitted prepare_candidates. Do not inspect assets to resolve a remaining concrete scene type.

## Exact proposed selection

See [exact selection](PHASE_1_GENERIC_CANDIDATE_HOLDER_SELECTION.json): seven exact declared signatures, two known types, each signature confirmed unique in hash-verified retained members. Do not follow callees recursively or automatically select generated bodies.

1. NCardHolder.ReassignToCard(CardModel,PileType,Creature,ModelVisibility)
2. NCardHolder._Ready()
3. NCardHolder.ConnectSignals()
4. NGridCardHolder.OnCardReassigned()
5. NGridCardHolder.SetCard(NCard)
6. NGridCardHolder._Ready()
7. NGridCardHolder.Create(NCard)

All are already declared in the retained metadata. The requested NCardHolder.SetCard(NCard) is already available: do not re-read it. Verified retained stdout /private/tmp/generic-removal-preview-v2-target-a/stdout.bin, SHA256 f9404d721c4ba8824938ee0684ccf7fe21a885eda974bc986b825b986a82cf56, role holder_set_card. It retains input CardNode and reparents/adds that exact node. Retained NCard.Create/model getters/setters in the same output can be reused without a target read.

Member evidence: /private/tmp/card-selection-static-qfocay2o/outputs/sts2.members.MegaCrit.Sts2.Core.Nodes.Cards.Holders.NCardHolder.jsonl SHA256 96a9add7650f1602e4fe2607a75e1086072eae55e61240711c3870e49dadb2c7; NGridCardHolder equivalent SHA256 ecbba1b3c73620810bcf7f65e496abf540a7af7ec1af62e20b0db9d17373f8c7. Rehashed against docs/research/PHASE_1_CARD_SELECTION_API_SELECTION.json.

## Target and limits for a new reviewed scanner

Only the fixed pinned sts2.dll at /Users/rowdeygoos/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64/sts2.dll; exactly 9363456 bytes, SHA256 e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18. Hash the bounded image before PEReader. Preserve physical-file/nonsymlink ancestry checks and pre/post file-shape checks. No Assembly.Load, target invocation, app launch, saves/profile/Cloud/network accesses, resources/assets/prefs, catalog, or additional declarations.

Recommend seven exact signature-and-return-type resolutions and seven bodies in a single target invocation, at most2500 decoded instructions per body and17500 total, stdout at most1MiB, stderr4096 bytes, wallclock30 seconds. Redact user-string operands to user_string. Symbolic member operands may be retained. If a selected method is absent/ambiguous/bodyless or any cap is exceeded, stop; do not broaden or retry automatically.

## Existing implementation and invocation requirements

Original inspector in /private/tmp/card-selection-static-qfocay2o is verified in verified_old_inspector.json. All35 frozen_history_hashes in the repo record were rehashed successfully. Its CLI is `dotnet ApiInspect.dll sts2 il TYPE METHOD_NAME`, with frozen.json and selections.json next to its executable. It requires net9.0 SDK/runtime, no external NuGet packages, offline NuGet.Config. It limits80 types/200 bodies/2500 instructions per body and reads pinned bytes before PEReader.

Do NOT run the old inspector directly for this new scope: it reads the target before checking frozen selectors, selects all overloads by method name, emits user-string contents, exposes a catalog mode, permits repeated target reads, and mutates a shared historical ledger. Preserve its sources/history.

Prefer deriving a new disposable exact selector scanner from /private/tmp/generic-removal-preview-v2-a/Program.cs and capture.py. Its exact signature resolver, pin-before-PEReader, string redaction, output bounds, synthetic-only mode, clean capture and frozen bundle checks already meet the required shape. Remove the preview-specific declaration/MethodImpl projection; replace six old body requests with these seven; do not keep any old target selectors. New source/build/capture/bundle must be reviewed and hash-frozen after synthetic no-target validation, before one target invocation. No executable new scanner is supplied by this proposal.

Verified predecessor source manifest: /private/tmp/generic-removal-preview-v2-a/source_manifest.json SHA256 ea39dd301db097943719fc91d7a7cb5854919e34018b026b5b947779216976d0. Program.cs SHA256 9a4abdd310eb228d3fae3f8220bf918bc09a4ce9452ed0c0861ef22517a23559; capture.py SHA256 91a48dfaa1e35b891595b1e57d2d9a92321bcc93885c3e04c07fa16dca97ecfc. The parent should verify these again when copying. Both target and fixture modes must be explicit; no target path fallback.

Pinned available SDK path previously used: /private/tmp/sts-sdk-resume.6AJGPQ/sdk/dotnet (SDK9.0.303). Coordinate exclusive SDK lane before build. Use clean env with PATH=/usr/bin:/bin, task-local CLI_HOME/TMPDIR/packages, telemetry/multilevel disabled, no MSBuild server, and offline NuGet config. For later reviewed capture, invoke Python -B -I -S under env -i and the hash-frozen wrapper with explicit dotnet/bundle/create-only output paths and --target. Exact invocation cannot yet be frozen because the new scanner and bundle do not yet exist.

## Scope review and persistent authority

2026-09-07, authoritative23cf baseline9cf4415. The user asked to proceed with
candidate-stage diagnosis after the failed v3 campaign and complete cleanup.
Independent review accepted the exact seven-body scope for scanner implementation
and inert validation. The original proposal SHA256 is
`5816d1ccb54da2c985a4951b07c074f0cd42910f2f8e3ab8827a51a9a60453c4`;
the selection SHA256 is
`3949be1e65499dbe5c60fd8566fceb726b175b9a0e311fa4e814f653ba042b19`.
This repository copy corrects the selection link and adds review/completion records.
A separate source/bundle/capture validation review still precedes one target read.
The existing generic release21 and every predecessor remain frozen. Game closed;
no active campaign or profile/Cloud work.

## Frozen implementation review and single invocation

Independent reviewer and root verified all16 source entries and3 bundle entries.
Source manifest SHA256: `d7486035a07e373cd98044dd5ebd55a08127103ba60a23a8d0cf778008e2c716`.
Bundle manifest SHA256: `9762dbbfcfd5e81285ea276b4de82ecce38eee0a66655a1fda5ce2fd98c050b0`.
Synthetic result SHA256: `79febec0fe8017eb735a9ce8eb2fbbe9f07f8aa6260c547ddfe3546a3c5c13fb`.
All19 inert checks passed. Exact selection, pin before metadata parsing, string
redaction, bounded capture and no target execution were independently accepted.
The proposal selection JSON remains preserved unchanged; this section records
acceptance of the frozen implementation under the user's continuing request.

The single accepted command is:

```bash
env -i PATH=/usr/bin:/bin TMPDIR=/private/tmp DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_MULTILEVEL_LOOKUP=0 /Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python -B -I -S /private/tmp/generic-candidate-holder-inspector-a/capture.py --dotnet /private/tmp/sts-sdk-resume.6AJGPQ/sdk/dotnet --bundle /private/tmp/generic-candidate-holder-inspector-a/bundle --output-root /private/tmp/generic-candidate-holder-target-a --target
```

No automatic retry, selector broadening or callee/asset inspection is included.
