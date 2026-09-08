# Single holder-model projection inspection

2026-09-07. Follow-up to the reviewed [seven-body result](PHASE_1_GENERIC_CANDIDATE_HOLDER_RESULT.md).

The user continues the generic-handler diagnosis. Retained metadata search found
no `UpdateCardModel` body. Rehashed NGridCardHolder member output SHA256
`ecbba1b3c73620810bcf7f65e496abf540a7af7ec1af62e20b0db9d17373f8c7`
declares exactly one private void method:

`MegaCrit.Sts2.Core.Nodes.Cards.Holders.NGridCardHolder.UpdateCardModel()`

Inspect only that exact signature with return `System.Void`. The reviewed seven
bodies call it while refreshing the public CardModel projection; this separate
scope resolves that missing link. Independent review accepted its relevance and
minimality conditional on the now-completed retained-body search.

Only the fixed pinned sts2.dll at
`/Users/rowdeygoos/Library/Application Support/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.app/Contents/Resources/data_sts2_macos_arm64/sts2.dll`,
9363456bytes, SHA256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
One body,2500instructions total/per-body. Preserve physical ancestry and bounded
pre/post file-shape checks, hash before PEReader, string redaction,1MiB stdout,
4096byte stderr,30second capture and create-only private output. No declarations,
MethodImpl projection, assets, recursive callees, generated methods, target
execution, saves/profile/Cloud, launch or network. Missing/ambiguous/bodyless or
over-limit selection fails closed; no automatic retry or broadening.

A separate inspector under `/private/tmp/generic-holder-model-inspector-a` derives
from the frozen exact-seven sources, preserving that predecessor untouched.
Explicit target/fixture modes; offline inert tests precede source/bundle freeze
and independent review. The target invocation is gated on that review. Planned
create-only target root `/private/tmp/generic-holder-model-target-a`.

## Frozen implementation acceptance

Root and independent reviewer verified all16 source and3 bundle entries.
Source manifest: `bf4c40e0eb3a4a42425bbfb2206017bb4c99f40ff8cbc85b22198008fc1d471a`.
Bundle manifest: `fff460be065d3cede0e06e746b4d5b2bd6e153822c7c042b981137d7807bccf4`.
Synthetic result: `ad395f66c4c1ae55ca84f65e4eff9c07b745b8886b561d399f7ad24a37685c7a`.
All19 inert checks passed. The frozen one-method/private-instance selector,
bounded capture and unchanged guards were accepted before the single invocation.

```bash
env -i PATH=/usr/bin:/bin TMPDIR=/private/tmp DOTNET_CLI_TELEMETRY_OPTOUT=1 DOTNET_MULTILEVEL_LOOKUP=0 /Users/rowdeygoos/code/github/RowdeyGoos/StS_agent/.venv/bin/python -B -I -S /private/tmp/generic-holder-model-inspector-a/capture.py --dotnet /private/tmp/sts-sdk-resume.6AJGPQ/sdk/dotnet --bundle /private/tmp/generic-holder-model-inspector-a/bundle --output-root /private/tmp/generic-holder-model-target-a --target
```
