# Combined bridge live batch

Status: first event attempt stopped before child admission and was cleaned up.
Generic upgrade, combat-choice and reward/map completion remain unverified in
this batch. The user authorized live testing after feature preparation and
confirmed manual readiness on Profile 3.

## First installation and event attempt

- Source: `72aaaf528200523e93479d7f5100f3482e191151`.
- Accepted release SHA-256:
  `74e3cfee962253f9bab0fbc8b13e1aa80df1e134d20c31e5bbc5cb029afc01a8`.
- DLL: 784896 bytes,
  `3424b5d15191f458faab369de20df151477372a2a129c41b0df78753aa327797`.
- Historical installed state:
  `4b8cea51c2d3e334c888db600a94cc7ff0b7fa972833f4ed22466f3df4d40a9f`.

Preparation verified the stopped game and closed port, the exact pinned 429-file
base and exactly two installed overlay files. Client ownership/configuration
preflight passed. After manual launch, the exact running process, authenticated
health, compatible build manifest and public main menu passed. UI showed Profile 3.

UI continued the existing test run to a treasure room. Controlled console setup
issued eight `card BASH Deck` commands and `event SAPPHIRE_SEED`; the console
reported successful additions and event entry. However, the subsequent UI still
showed a 12-card deck and an 11-card upgrade grid. This did **not** establish the
intended larger-deck/off-screen premise. The reason those additions did not appear
in the event deck was not determined.

The existing shared `BridgeClient` and generic host ran with a bounded custom
provider intended to select advertised slot 15 once, then confirm its exact
preview and verify core map readiness. The provider was never given an admitted
child. Consume was accepted and the UI showed HP 77 → 80 plus the upgrade grid.
The controller stopped with:

- `code: unsupported_state`, 258 reads;
- parent attempted/accepted/reconciled: **1 / 1 / 0**;
- card child attempts/accepted/reconciled: **0 / 0 / 0**;
- admitted child episodes and completed card/item children: **0**;
- latest effect label: `unverified`; map check not attempted.

No card-selection input, confirmation or upgrade was dispatched. There was no
retry or manual completion of the unresolved bridge operation. The exact native
admission diagnostic was not retained, so the observed result does not identify
which native readiness check blocked admission.

Normal application quit succeeded. Runtime checks found the game stopped and
listener closed (three process samples, two port samples). Quarantine state was
`36d7569bbf6e748769380b4e237d876a20fcfbf6ff2950df8e8c6a5742fb23e2`;
purge removed the four owned generated files and returned the campaign to absent.
Post-cleanup base verification passed: 429 files, zero overlays, projection
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
No profile/save/history/Cloud filesystem data was read. Credentials stayed within
the existing authenticated client's read lease and were cleared after use.

## Reproduced compatibility correction

Source inspection found that single-upgrade selection required the hitbox's exact
runtime type to be `NClickableControl`, whereas the multi-upgrade and transform
adapters accept derived controls and retain exact object identity. The single
fixture was changed to use the existing derived-hitbox fixture class. Before the
correction, native admission failed at `generic child FIRST_EVENT` in
`/private/tmp/sts-bridge-mxm6j4_e`.

The correction uses the same native validity predicate as the sibling adapters.
It preserves exact hitbox reference, holder/card/model/highlight/material identity,
visibility, enabled state, native clickability and all preview/effect checks.
A regression rejects replacement with another derived hitbox. The focused native
suite passed **3,897** checks in `/private/tmp/sts-bridge-cd7fegve`; one independent
semantic review found no blockers. This is a reproduced compatibility defect,
not proof of the first live failure's cause. Current release records own the final
combined gate and package identity.

The next live attempt should first retain the bounded native diagnostic if
admission fails, verify the actual advertised domain, and establish any off-screen
target premise from the visible selector. Combat choices, both reward policies
and event-to-core map return still belong to the pending batch. Phase elapsed
times for live setup and review were not captured.
