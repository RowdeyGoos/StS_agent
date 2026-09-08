# Generic transformation discovery acceptance

2026-09-08. Preparation and frozen-tool review accepted before the single
metadata-only invocation below. Implementation baseline: `ac95b77` in the
23cf integration worktree. All 24 successors remain frozen.

## Accepted scope and tools

The independently accepted [scope](PHASE_1_GENERIC_TRANSFORM_SCOPE.md) remains
byte-exact, SHA256 `ef8cc8607e6f82905891513ab529ea14d3a8ad567f9d61b97657ee7ecb5dcc1d`.
This ledger supplies its appended acceptance record without changing its hash.
Root owns invocation/results; B prepared the inspector; R independently reviewed
the exact final source, bundle, synthetic evidence and invocation command.

Frozen preparation root: `/private/tmp/generic-transform-inspector-a`.

- Source manifest, 31 entries: `04c537590f0de90a7dc31082882bc96673529bd38a06a69d443a3b67fdd8872f`.
- Bundle manifest, 3 entries: `9cf1ceaf2d0d654ab912cc1f50df7d6f133e32a89889760df94fbe483ddff8d9`.
- Synthetic manifest, 12 entries: `221645c1f62552012c6e515dc596eed3fe9b3b1dc0c3b9c9f0b89c63e73c939b`.
- Synthetic result, 1,556 bytes: `50d5e30fd4c772e226ea9d83182bf8aa0ec364d901ac8b9d6744e0c2e2f2e64d`.
- Inspector DLL, 49,664 bytes: `149da5c5a590ff017f57ec41fa6b30ff994dbf00e23247384854c6d38302194a`.

All 43 inert checks pass. These cover exact nine-body/two-type selection,
method signatures and nested generic names, missing/ambiguous/bodyless methods,
instruction/declaration/MethodImpl ceilings, no callee following, string redaction,
malformed images and wrong pins, symlinks, canonical serialization, bounded
stdout/stderr/deadline handling and create-only capture. Review identified the
inherited fixture wrapper checking file shape before lexical fixture-path bounds.
The corrected wrapper rejects outside, relative or noncanonical arguments before
file/output operations; three explicit regressions pass. Prior source and manifest
identities are preserved in scratch and were never used for target invocation.
R and root rehashed every final manifest entry. No target access occurred in prep.

## Single accepted invocation

R accepted this exact root-only command and fresh output directory:

```bash
env -i PATH=/usr/bin:/bin TMPDIR=/private/tmp DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_MULTILEVEL_LOOKUP=0 /Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python -B -I -S /private/tmp/generic-transform-inspector-a/capture.py --dotnet /private/tmp/sts-sdk-resume.6AJGPQ/sdk/dotnet --bundle /private/tmp/generic-transform-inspector-a/bundle --output-root /private/tmp/generic-transform-target-a --target
```

The pre-invocation record above was written before execution. No game launch,
profile/save/Cloud access, installation or live action is included. The target
assembly is parsed as metadata only and never loaded or executed. Successful
capture is evidence for the next implementation contract, not transform support.

## Single invocation result

The exact accepted command ran once and exited zero. Capture status passed:
2 declared types, 9 bodies and 1,395 instructions. `stdout.bin` is 204,926 bytes,
SHA256 `fe6402573e251c2229fe615c38f3d11fbf760ef3fccb5443cee83d6c6adc485e`.
`stderr.bin` is empty. Root verified directory mode0700, both files mode0600,
result hash and counts. No retry, expansion or target execution occurred.

Initial reading establishes that the multi-transform command removes originals
before inserting replacements and awaits per-card hooks during insertion. A hook
can replace the initially generated card. The frozen positional, constant-length
transform validator cannot cover this behavior as-is. Exact native analysis and
remaining mapping/declaration gaps are recorded separately in
[the native evidence](PHASE_1_GENERIC_TRANSFORM_NATIVE_EVIDENCE.md). No native
transform support or live evidence is claimed from this successful discovery.

## Independent result review and checkpoint

R independently rehashed the output and reviewed the exact native findings,
including the request shortcut, getter/factory branches, nullable result caveat,
post-hook assignment and common per-card await. The 12,884-byte native evidence
report has SHA256 `ca2f04373f7f7d2def63b8dc8c09d3cc23e466e2b217245eeb3c4257318ff5ed`.
Review accepted both that report and living documentation with no actionable
finding. Raw pile value6, AddInternal(-1), sorting, result-field visibility and
live hook yielding remain explicitly unresolved. No additional inspector was
prepared or invoked. Root revalidated G4 and all predecessor source identities,
derivations and source closure after these documentation changes.

G4 functional implementation remains committed as `ac95b77`. Transformation is
a separately pending development family; its next implementation must preserve
actual intermediate states, bind final replacements and explicitly version any
changed effect semantics. Existing family behavior and all frozen sources persist.
