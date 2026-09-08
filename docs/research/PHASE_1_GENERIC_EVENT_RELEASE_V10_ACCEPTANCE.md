# Generic release v10: direct card16 test acceptance

2026-09-08. User explicitly directs a card16–20 click without the prior geometry
requirements. The chosen target is the sixteenth native grid holder, slot15.
Contract SHA256 `52b03ae2926c8eba66da0ec93bd43da126850060f2f1558f47667163045bc5cd`
was independently accepted. All31 earlier successors remain frozen.

The adapter removes the complete GridGeometry/ProbeGeometry implementation and
all related reads. TargetCard16 exposes only select:15; Select also checks slot15
before dispatch. Existing model/holder identity, native enabled/tree-visible
state, exact-original preview and transformation journal remain. No clipping,
viewport, layout-size requirement or scrolling is introduced. Off-screen status
comes from the user’s controlled20-card setup, not a new runtime certificate.

Focused actual-adapter tests pass21 assertions, including16/20-card domains,
sole slot15 eligibility, actual holder15 input, exact preview original, final
transformation/map, missing/disabled/replaced target and deferred wrong-original
rejection. Evidence `/private/tmp/generic-release-v10-native-a/result.json`.
These are inert target fixtures, not live success. All six focused socket cases passed in the frozen aggregate. The previous geometry matrix and unrelated frozen G7 regressions are
not rerun; retained regression evidence remains in the v9 ledger.

Production pair `/private/tmp/generic-release-v10-production-candidate-a/result.json`
contains two byte-identical385024-byte DLLs, SHA256
`cf8c0023386609dcf8dcd802ddf4f8ce50e3323575b6455cc3301b2653f14272`.
Independent review rehashed both DLLs and56 current production sources. Source
projection `3055edf7fc7b8a1002ec8c0f675c2c6ee24c059b826e3e87a6b3c56ef5f0614a`.
No game/Godot/production assembly was executed. Verifier now forbids all seven
former geometry APIs from every caller; diagnostic vocabulary115 remains exact.

Package manifest354 bytes SHA256
`306a2737ce330a409847b30b62bf20c4162a2bd6e08b5f657539607f593817a3`;
ZIP385814 bytes SHA256
`14e9d365e2308ca7f8899925739fa64c7b01bfeec426034625a4fe2403dc9e8f`.
The single source-frozen aggregate passed; independent review and operational
preflights passed, and installation is complete as recorded below.


## Frozen acceptance and installed readiness

Single aggregate `/private/tmp/generic-release-v10-root-frozen-a/result.json`,
SHA256 `147ef2c449dac1d3f7af01d7859df1ff32782890d5b192dd3ea5eaa3212e9ec5`,
passed: 21 direct-target native assertions, six socket cases, 386 verifier,
966 runtime, 23 transport and 13 client checks, plus package/operator/bootstrap,
native release, transactional lifecycle/cleanup and source provenance checks.
All 31 predecessor inventories passed. Frozen G7 regressions use the accepted
v9 ledger evidence and were explicitly not rerun. No production/game/Godot
assemblies executed offline; pinned Harmony ran only against inert targets.

Source inventory SHA256
`8f2c017a7acaabd3aa7d9ae1013e844007f22feabc8b9d593dd890fde4d2b2b8`;
manifest SHA256
`e3d541f4be1b550666cc5bc80efcf36c7973a50899ea211e4089cc18260e1431`.
Independent review verified all 73 files plus manifest match both frozen
snapshots and all four production DLLs match the artifact above. Both policy
extractions match SHA256
`e3a49c39d6b1619f684f11c0dcf7b25e29ca0d489e9a82c23f280f7c187360cd`:
2121 method bodies, 14679 metadata rows, zero former geometry API calls or
member references, unchanged 115 diagnostic vocabulary. Final acceptance passed
with no remaining review blocker.

Fresh stopped/closed runtime checks and clean base passed before publication:
429 files, base SHA256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`,
zero overlays. Published exactly three verified artifacts to
`/private/tmp/sts-generic-event-v10-release`. One install passed for
GENERIC-EVENT-V10-SMOKE-V1; fresh installed state SHA256:
`d2c1267bcdc7f4a0754c4e595dee23bb0ccadaa4326f9b78087b876e9ed6f8ad`.
Evidence `/private/tmp/generic-release-v10-install-result.json`.
Overlay verification passed: same 429 base files plus two owned overlay files;
evidence `/private/tmp/generic-release-v10-overlay-verification.json`.
Frozen client and installed metadata validation passed without reading
credential contents. No live invocation or automatic launch occurred.

Await manual start/readiness in the same 20-card Aroma of Chaos setup. The
client directly targets slot15 once; no geometry admission remains. Selection
success requires the preview to identify the exact original card, independently
of any later completion failure. After the test, normal quit and stopped checks,
quarantine using this fresh installed hash, purge using the returned quarantine
hash, and unchanged-base/zero-overlay checks close this owned campaign.
