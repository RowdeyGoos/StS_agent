# Phase 1 event card-caller discovery scope

- Date: 2026-09-06
- Status: proposed; synthetic scanner gate passes, but no pinned target invocation is authorized or performed by this packet
- Baseline: `920ec84`
- Evidence boundary: repository evidence, previously accepted disposable static outputs, and inert synthetic assemblies only

## Purpose

Identify which of the accepted 68 concrete event-model types directly call a
known card-selection or card-effect API. This is a selector for later bounded
method-body review. A callsite row does not establish option identity,
cardinality, optionality, candidate-domain completeness, effect completion, or
native eligibility. An event with no emitted row is not proved free of card
interaction because this pass deliberately excludes unbound compiler lambdas,
callee bodies, inherited bodies, reflection and dynamic dispatch.

The exact event denominator comes from
`PHASE_1_EVENT_COVERAGE_CENSUS_GENERIC_RESULT.md` SHA-256
`a38b05e2f16843befe8f4217aa10c5738ccd8d64c3045f6f04cd5fccd0eb54b6`.
The 68-name configuration SHA-256 is
`5cae9ace6df7bf2de5b4d479d279368fcd45225a2bfc9e53400a84c1b56952f7`.

## Known API allowlist

The scanner accepts exactly 28 method identities: 16 `CardSelectCmd.From*`
selector overloads and 12 effect overloads consisting only of
`CardPileCmd.Add`, `CardPileCmd.RemoveFromDeck`, `CardCmd.Upgrade`, and
`CardCmd.Transform*`. The identities are mechanically copied from these three
previously accepted, hash-bound member outputs:

- `CardSelectCmd`: `d3daf5216cc1e33cf086a79b907f1196805acb267636ed56dc1bebc8d2b34195`;
- `CardPileCmd`: `23f29930b6e7b5e2641e18f4cffd0af38316d2ff6112618252d6d566bb2c892d`;
- `CardCmd`: `f9a9e7b3421adf47315b56fef3070205393754d867972a6a996d298bc9fa2644`.

Those hashes are recorded in
`PHASE_1_CARD_SELECTION_API_SELECTION.json` SHA-256
`ec8b8d53858182e8e75d4efebe2a843de7a6d9b74b9de2f5b9c1c2252ad349b9`.
The canonical 28-row configuration SHA-256 is
`705c405e0a68c2dd37e3998218dc2d8bf1b5f475f8e9e8a840c08d570edd727f`.
No prefix or owner-only match is permitted at scan time; the decoded callee
identity must equal one configured full signature.

## Exact scanned body set

For each exact configured event TypeDef, scan:

1. every method body declared directly by that event type; and
2. the sole `MoveNext` body of the exact type named by a directly declared
   method's `AsyncStateMachineAttribute` or `IteratorStateMachineAttribute`.

The state-machine attribute blob must have the standard prolog, one serialized
type name and zero named arguments. Missing, repeated, ambiguous or malformed
bindings fail closed. Every physical MethodDef body may be scanned once; a
reused binding fails `ambiguous_generated`.

The pass does not scan display-class methods, `<>c` lambdas, arbitrary nested
types, callees, inherited methods, fields, resources, localization, user
strings, sequence points, exception values or locals. Those omissions make the
result an intentionally incomplete positive caller census. A later reviewed
follow-up may select exact emitted source/body methods and their directly bound
lambda delegates where needed.

## Bounds and output

Before opening the target image, target mode requires the exact event and API
configuration byte hashes stated above and exact counts 68 and 28. It then
accepts only a physical file named `sts2.dll`, size 1..100,000,000 bytes, with
pinned SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
It verifies the hash before `PEReader`, reads one bounded byte image and zeros it
on every post-allocation path. It never loads or executes the inspected
assembly.

- exactly 68 configured event types in target mode;
- at most 2,048 scanned bodies;
- at most 2,500 decoded instructions per body and 1,000,000 aggregate;
- at most 512 emitted callsites;
- no truncation; each overflow is a fixed failure.

Canonical output contains only schema/evidence/input hash, event/body and
selector/effect counts, and sorted rows with event type, attributed source
method, actual body method, IL offset, `selector|effect`, and exact allowlisted
callee. It contains no raw IL, constants, branches, strings, field references,
paths or exception text.

## Disposable implementation

The scanner is in `/private/tmp/event-card-callers-b` and uses the accepted
metadata-name and IL-decoder pattern. It builds offline with SDK 9.0.303 and a
NuGet configuration containing `<packageSources><clear/></packageSources>`.

- `Program.cs`: `beb1a92c9d65523673a1cfb556d79609d839741ec2a30e318edca49dfc6a55fb`
- `IlDecoder.cs`: `58a15d83f6b97916ab5f63b2b765f29cd8d46e380d5a270bf8c91dd333d25933`
- `MetadataNames.cs`: `f7b481088f436e9ada05fc269101cd98b05326122798ff6043eeab8286517d23`
- `VerificationException.cs`: `d96d1849ca4990461488dae68f9a972fc4c37afae42d5a31892f03f8bbafa907`
- `EventCardCallers.csproj`: `b5e76aa9c90dc164a1d27d7a3901e3bd0b2b720a3152ef01de7fa122239eb648`
- `NuGet.Config`: `7d59a339f0f6022f0710d690fe52e2a0f868519847651f6c10f6c9ff1bd7213a`
- `run_fixtures.py`: `c7ada32c3006a60040f9a74a74b47c747c55c37f07af2e14fae89b754a5ddf51`
- complete 21-input source manifest: `d8c5a1026dfeabbe5458a8d95b6bf6ac7f72ff96d4db43fb6946cd669370365c`

## Synthetic acceptance and stop boundary

The inert gate requires 14 checks: exact direct selector/effect rows and schema;
async source-to-`MoveNext` attribution; unrelated-call omission; byte-identical
repeat; pin-before-PE; malformed-image fixed failure; missing event; duplicate
API configuration; independent target-mode event-configuration and API-configuration byte drift; callsite overflow; instruction overflow; and symlink
rejection. Its fixed success is:

```json
{"schema_version":1,"status":"passed","suite":"event_card_callers","check_count":14}
```

Independent review must accept this exact source/config/scope before one target
invocation. A failure or overflow stops without a looser rerun. The target result
may select exact follow-up bodies, but cannot by itself authorize native callers
or classify cardinality/effect semantics. No profile, save, history, Cloud,
network, live game, package, operator or runtime work is included.
