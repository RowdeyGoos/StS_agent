# Combined bridge live batch

Status: representative batch completed, including allocated off-screen
single-upgrade. Generic event/map, both combat/choice/reward/map policies and
Sapphire Seed off-screen Defend slot 20 of 23 passed. All five installations were
cleaned up. The user authorized live testing after feature preparation and
confirmed manual readiness on Profile 3. Earlier unsuccessful attempts below
retain their original evidence limits.

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

## Corrected release prepared

The final combined gate passed 71 check groups in **148.735 seconds** at
`/private/tmp/sts-bridge-70buv13o`, including production reproducibility, actual
native-to-host integration and owned package/install/cleanup fixtures. Source
commit is `a57cb98`; accepted release SHA-256 is
`731a8cf1c51ecdb5cfa4ef574085122c70606c62eea4a896312fb05506f6c755`.
The preceding package and release records were preserved under
`/private/tmp/sts-bridge-retained-release-km0yyy77` before publishing the correction.

The game was rechecked stopped with its listener closed. Corrected installation
passed with a fresh owned state:
`050f6a250dd2f4241bff666922dee80ce77ff2f97fdb0d7687177c25b67e626b`.
Post-install verification found 429 unchanged base files plus exactly two overlay
files. Client release/ownership/configuration preflight passed without reading
credential contents. At preparation this installation awaited manual relaunch;
its subsequent live result and completed cleanup are recorded below.

## Second live attempt: generic upgrade and core map passed

Manual readiness, exact running process, authenticated health, compatible manifest
and public main menu passed for release
`731a8cf1c51ecdb5cfa4ef574085122c70606c62eea4a896312fb05506f6c755`,
installed state `050f6a250dd2f4241bff666922dee80ce77ff2f97fdb0d7687177c25b67e626b`.
UI confirmed Profile 3 and continued its existing test run. Console setup issued
only `event SAPPHIRE_SEED`, with success visibly verified before bridge control.

The actual shared client/generic host selected the first advertised card,
confirmed its exact upgrade preview, completed the card effect and chose Proceed.
The original response parser still validated each response; a test wrapper
retained only its bounded native diagnostic code after validation. Diagnostics
were `parent_ready`, `child_ready`, `parent_ready`, `map_ready`.

- Parent attempted/accepted/reconciled: **2 / 2 / 2**.
- Card child attempted/accepted/reconciled: **2 / 2 / 2**.
- One admitted and completed card child, no completed item children.
- Four total actions, 14 event reads; resolved with no error.
- A fresh core map decision passed after one read, with one actionable candidate.
- Combined event and map elapsed time: **1.506 seconds**.

The latest parent effect label remained `unverified` after Proceed, as specified;
one completed card child retains the verified upgrade. UI showed the map. This
establishes ordinary single-upgrade and event-to-core map return, not off-screen
upgrade behavior, all event branches or a full run. The result summary is retained
at `/private/tmp/sts-upgrade-retest-result.json`.

## Second live attempt: combat transition stopped

A fresh core map read advertised `select:0` for monster column 4, row 7. Its one
accepted action was reconciled by a complete map observation for the same
destination; UI showed combat at 80/80 HP. The shared `combat-map` controller ran
with `first-select` chooser and `first-card` reward policies.

It stopped at stage `combat` with `unexpected_combat_round`:

- Combat attempted/accepted/reconciled: **9 / 7 / 6**.
- Two confirmed no-mutation stale rejections, 30 combat reads, 19 chooser probes.
- No admitted/completed chooser summaries; rewards and map check not attempted.
- UI showed Neow's Fury's discard selector in turn 2, allowing up to two cards.
  No selector input was sent. Enemy HP was visibly 16/40; player HP remained 80/80.
- A single read-only diagnostic combat observation returned `waiting`.

The pending combat action was not retried or manually completed. No exact pending
versus observed round pair was retained, so the live result alone does not prove
which round transition triggered the check. The predecessor's tested
`apply_combat_live._poll_after_action` waits through changed original-round
observations after end-turn; the newer host immediately rejected them. Focused
regressions reproduced that missing wait before the correction.

Normal quit, stopped process and closed port passed (three process/two port
samples). Quarantine state was
`9160526d7ee99de0e5544812b80dbdb78a0a411f4d4d44f6911ced5b66fb9eff`.
Purge removed the four generated files. Post-cleanup verification found the same
429-file pinned base and zero overlays.

## Combat host correction

Only an accepted pending `end_turn` in its original round enters the existing
bounded wait/chooser path. It retains the reservation and counts; no combat
redispatch or early reconciliation is allowed. Exact next round or terminal
combat still reconciles; backward/skipped rounds and a card action advancing the
round still fail. All deadlines and read/action bounds remain.

Nine focused combat-host tests pass, including optional zero and multiple chooser
selections during this wait, unchanged round timing out without redispatch, and
invalid round changes. The two new waiting scenarios failed before the correction.
The focused host gate passed all ten groups in **9.776 seconds**, including the
existing shared-client socket integration (`/private/tmp/sts-bridge-qy139kvm`).
One independent semantic review found no blockers. Current release records own
the final combined gate and package identity. No native bridge change is needed.

## Combat host retest prepared

Source `370bd77` passed the final 71-group release gate in **146.105 seconds**
(`/private/tmp/sts-bridge-tx2i28t8`). Accepted manifest SHA-256:
`fcf7e2999df081cfdd07e8364c48c5646c6dc34fa7198bf911be816d489a1bdb`.
Its native DLL and canonical package exactly match the preceding accepted
release. The already published, validated package was reused; the changed host
is covered by the new source inventory and executed checks.

Stopped-game/closed-listener checks passed before installing with fresh state
`3599640917195929280b307348fd83cd7a7d3e9d9602821d11a25be45feb6b00`.
Post-install verification found the pinned 429 base files plus exactly two
overlay files. Release and client ownership/configuration preflight passed
without reading credential contents. At preparation this third installation
awaited manual relaunch. Its completed live retest and cleanup follow; the same
native binary's generic upgrade/map result remains valid.

## Third live attempt: both combat/choice/reward/map paths passed

The user manually relaunched. Exact running process, authenticated health,
compatible manifest and public main-menu checks passed for the release and fresh
installed state above. UI confirmed Profile 3. Continue resumed the start of the
native monster encounter at 80/80 HP, gold 161 and deck count 12. This was a fresh
process/combat, with no adoption of the preceding failed operation.

Both runs used the existing authenticated `BridgeClient`, combat and reward
hosts, original public response validation and `run_combat_map`. A bounded test
wrapper retained sanitized action/round/chooser summaries, without raw responses
or credentials. No UI or console input assisted either combat/chooser/reward flow.

| Observation | Two-card / first-card | Zero-card / skip-card |
| --- | --- | --- |
| Combat attempted / accepted / reconciled | 21 / 14 / 14 | 24 / 17 / 17 |
| Combat reads / choice probes | 91 / 67 | 121 / 92 |
| Confirmed no-mutation stale rejections | 7 | 7 |
| Neow's Fury min / max / available cards | 0 / 2 / 6 | 0 / 2 / 7 |
| Choice attempted / accepted / reconciled | 3 / 3 / 3 | 1 / 1 / 1 |
| Choice reads / selected count | 4 / 2 | 2 / 0 |
| Native choice result | selection_verified | selection_verified |
| Combat result / terminal round / HP | victory / 4 / 76 of 80 | victory / 5 / 75 of 80 |
| Reward attempted / accepted / reconciled | 4 / 4 / 4 | 4 / 4 / 4 |
| Reward reads / stale rejections | 11 / 0 | 11 / 0 |
| Verified gold change | 161 → 175 (+14) | 175 → 193 (+18) |
| Verified card reward / deck change | RAMPAGE / 12 → 13 | one skipped / 13 → 13 |
| Fresh map reads / actionable candidates | 1 / 2 | 1 / 1 |
| Complete flow elapsed seconds | 12.881 | 16.518 |

The positive choice selected slots 0 and 1, then confirmed the exact set. The
zero choice confirmed the empty set despite seven available candidates. Each
choice completed before combat resumed. The trace also retained accepted
end-turn followed by an original-round ready observation and subsequent exact
next-round progression, exercising the corrected wait without early
reconciliation or redispatch. Known stale receipts were rejected without mutation
and handled by the existing bounded controller.

Between flows, a fresh map decision advertised monster column 3, row 8 and a rest
site. The bridge selected the monster once, then read a complete map observation
for that exact destination before starting the second combat. Both complete
flows resolved at stage `map` with no error. The bounded summaries were read from
`/private/tmp/sts-combat-map-live-result.json` and
`/private/tmp/sts-combat-map-zero-live-result.json`; this table retains the durable
result without introducing a live corpus.

This demonstrates positive/multiple and optional-zero **discard** selection for
one caller, combat continuation and both supported reward policies. It does not
establish exhaust or fixed-count callers, generic optional selection, off-screen
upgrade, every event branch, strategic quality or a complete autonomous run.
Unchanged module evidence from September 8 was reused. No new code or build was
needed for this retest; the accepted source/package bindings remain unchanged.

## Final cleanup

Normal application quit succeeded. Runtime checks confirmed a stopped game and
closed listener with three process and two port samples. The exact installed
state was quarantined to
`cba1467a54bf9c17d56188b7c11e4b60adfdada73de9e1fa4142d06dc393db0b`.
Purge removed four owned generated files and returned the campaign to `absent`.
Post-cleanup verification passed: 429 unchanged base files, zero overlays,
projection `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
No profile/save/history/Cloud filesystem data was read. Credentials stayed within
the existing client's read lease and were cleared after each invocation. The
user-waived unmodded relaunch was not repeated. Setup, user-wait, documentation
and cleanup phase totals were not captured; measured flow/gate times are above.

## Fourth installation: user-prepared off-screen upgrade setup

The user requested console card additions and offered to prepare the deck. They
reported that removing one card after additions can refresh a stale visual deck
count. This is a setup hypothesis, not yet a verified explanation of the first
attempt. The actual upgrade selector domain and an allocated off-screen target
will be verified before selection.

The existing accepted release/package was reused without source changes or
another build. Fresh stopped-game/closed-listener checks passed (three process,
two port samples). Installation created the owned mods parent and state
`57e94a0b2bb1a7095657c59eae4636ee9a1b4892aa1a7b2c9e9a319ec31f924d`.
Overlay verification passed: 429 unchanged pinned base files plus exactly two
overlay files. Release/client ownership and configuration preflight passed
without reading credential contents. Manual launch and user deck preparation on
Profile 3 are pending; this fourth installation requires cleanup after its test.

### Fourth installation: read-only event admission stopped

After manual readiness, exact running process, authenticated health and compatible
manifest checks passed. UI showed Sapphire Seed's initial Consume/Plant options,
a 24-card deck, HP 75/80 and gold 193. The user supplied this setup; the assistant
did not add/remove cards or open this event. No selector had yet been opened.

The existing generic host stopped after one read with `unsupported_state` and
native diagnostic `parent_unavailable`. Parent and child attempted/accepted/
reconciled counts were all zero, with no child episodes, no actions, no map check
and `effects: none_attempted`. Elapsed controller time was 0.377 seconds. The
bounded result is `/private/tmp/sts-offscreen-upgrade-live-result.json`.

The parent adapter checks map travel state among several readiness predicates.
The initial UI also showed a Proceed control beside the event choices. Console
room creation retaining map state is a possible setup explanation, not a proven
cause; this diagnostic does not identify the exact predicate. No runtime guard
was removed, no failed session was retried and no input was dispatched.

Normal quit succeeded; stopped-game/closed-listener checks passed with three
process and two port samples. The same unchanged validated installation remains
on disk for a fresh manual process. Its exact installed state above remains the
cleanup identity; final quarantine/purge is still pending. Next setup is manual
launch at the main menu, then a verified fresh native room before console event
entry. The 24-card counter alone does not establish the upgrade selector domain.

### Fourth installation: fresh room, counter refresh and two test-wrapper results

Manual relaunch showed Profile 3. Runtime and authenticated compatible-build
checks passed. Continue resumed the previous reward screen at HP 75/80, gold 175
and deck count 13; the user's console setup had not survived the quit. The existing
reward host used `skip-card`: four attempted/accepted/reconciled actions, five
reads, gold +18, one skipped card reward and unchanged deck count 13. A native
map action entered treasure column 2, row 9 and was separately reconciled.

Controlled console setup issued twelve `card BASH Deck` commands, all visibly
reported successful. The displayed counter stayed at 13. One
`remove_card BASH Deck` reported success and refreshed the counter to 24. Then
`event SAPPHIRE_SEED` opened initial event choices without the extra Proceed
control seen in the preceding unsupported setup. This demonstrates the user's
counter-refresh workaround; it does not establish the added cards' eligibility.

The first wrapper incorrectly checked for child kind `card` instead of the actual
`card_selection`. It therefore used the default first-legal policy and selected
slot 0, confirmed and returned to an actionable map. Parent and child counts each
were 2 / 2 / 2, with one completed card child, 13 event reads, one map read and one
candidate, no error, 1.446 seconds. Result:
`/private/tmp/sts-offscreen-upgrade-retest-result.json`. This was an ordinary
upgrade, not the intended off-screen test. The production host was unchanged.

The wrapper child-kind check was corrected and locally exercised with a later
selection and exact preview confirmation. Native map entry to monster column 2,
row 10 was accepted and reconciled, then a fresh console Sapphire Seed was opened.
Consume was accepted and its selector admitted. The actual domain contained eight
unupgraded cards: two Strikes, four Defends, Neow's Fury and Twin Strike. No Bash
was present. UI showed the same eight-card, two-row grid while the top counter
still showed 24. Thus no off-screen target was available in this admitted domain.

The test-only provider's 20-second inspection-input timeout expired before any
card dispatch. It returned `provider_failed`: parent 1 / 1 / 0, one child episode,
child 0 / 0 / 0, two reads, zero completed children, latest effect unverified and
no map check, 20.160 seconds. A subsequent input reached an already-finished
process and caused no game action. Result:
`/private/tmp/sts-offscreen-upgrade-target-result.json`. The pending event was not
retried, adopted or manually completed.

Normal quit and stopped/closed-listener checks passed (three process/two port
samples). Quarantine state:
`52c19e85ed49f1f9ca2cf553b9adf3b8857d71f4c8b7e043d1fbea268df01770`.
Purge removed four owned files and returned the campaign to absent. Base
verification passed: 429 unchanged files, zero overlays, the same pinned
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`
projection. No profile/save/history/Cloud filesystem data was read.

The user then suggested that an automatic attack-upgrade relic had upgraded the
added Bashes. This is a plausible eligibility explanation to verify through
visible relic/card state; neither the displayed counter nor this attempt proves
it. Narrow metadata-only inspection confirmed `IsUpgradable` compares current
and maximum upgrade levels, and that deck `remove_card` returns after its first
matching removal. It did not execute game code or inspect user files.

## Fifth installation: skill-card setup prepared

The same accepted package was reused without a production change or new release
gate. Fresh installed state:
`ed59694f0015caa4c07309af8e9eab3fe459aa95d249efc555cfc6961b8e3537`.
Overlay verification passed: 429 unchanged base files and exactly two overlays.
Release and client ownership/configuration preflight passed without credential
content access. The installer created the mods parent. Manual launch is pending;
cleanup remains required for this installation.

The revised ephemeral provider uses actual kind `card_selection`, requires at
least 21 eligible candidates and chooses slot 20 only if it is an unupgraded
`DEFEND_IRONCLAD`. It verifies selected slot 20 before confirmation and uses the
unchanged host's native preview/effect checks. The timed inspection-input pause
was removed. Local provider checks cover the actual child kind, later target,
preview confirmation and rejection of an eight-card domain. Planned setup adds
Defend skills after opening the event, checks visible upgrade states and the
allocated off-screen premise, then runs the bounded controller. This remains a
prepared experiment, not a successful off-screen result.

## Fifth live attempt: off-screen Defend upgrade passed

Manual readiness, Profile 3 main menu, exact running process and authenticated
compatible-build checks passed for the fifth installation above. Continue resumed
a fresh native combat at HP 80/80, gold 193 and deck count 24. Public UI showed
Bash+ cards. Opening the relic detail confirmed **Molten Egg**, whose displayed
behavior upgrades attacks added to the deck. This supports the user's explanation
for the added Bashes being absent from upgrade choices; they had not established
an eligible off-screen domain. The earlier stale-counter observation also remains
valid, but was a separate issue.

Controlled console setup opened `event SAPPHIRE_SEED` from that native room,
then added sixteen `card DEFEND_IRONCLAD Deck` and removed one with
`remove_card DEFEND_IRONCLAD Deck` to refresh the displayed counter to 39.
The public deck view showed the added Defends unupgraded, with 5 Block. Setup
scrolled that deck viewer only; it was closed before bridge control. The initial
event choices were visible with no other overlay or extra Proceed control.

The existing shared client and generic host ran the prepared exact-target
provider. After Consume, the native child advertised **23 eligible candidates**,
including slot **20**, `DEFEND_IRONCLAD`, upgrade level **0**. An 18-second fixed
observation window before selection remained inside the unmodified 30-second host
deadline and required no operator input. During it, a CUA screenshot showed the
selector at its initial top scroll position with five columns, the first two
rows fully visible and the third partially visible. Slot 20 is in the fifth row,
below that viewport. No selector scroll or other UI input was performed during
the bridge-owned flow.

The provider sent `select:20` once, received a preview observation with exact
selected slots `[20]`, then sent `confirm`. The unchanged native adapter checked
the exact original preview, selected-only upgrade effect and child completion.
The host then chose Proceed and independently verified core map readiness:

- Status resolved, no error, diagnostics `parent_ready`, `child_ready`,
  `parent_ready`, `map_ready`.
- Parent attempted / accepted / reconciled: **2 / 2 / 2**.
- Card child attempted / accepted / reconciled: **2 / 2 / 2**.
- One admitted and completed card child; no completed item children.
- Four total actions, 13 event reads.
- Fresh core map check: one read, two actionable candidates; UI also showed map.
- Elapsed controller time **19.362 seconds**, including the 18-second observation
  window. No new production build or repeated release gate was needed.
- The final parent `effects: unverified` follows Proceed semantics; the completed
  card-child count retains the verified upgrade.

The bounded summary is `/private/tmp/sts-upgrade-after-event-result.json`; the
counts and target above are the durable evidence. This proves one allocated
off-screen **single-upgrade** target in this controlled Sapphire Seed setup. It
does not establish multi-upgrade, arbitrary deck sizes, unallocated cards, other
event branches, strategic quality or complete autonomous runs.

### Fifth installation cleanup

Normal quit succeeded. Runtime checks confirmed the game stopped and the listener
closed using three process and two port samples. Exact quarantine state:
`822b77bea2309fa7b0700372c8efdea5c09f8af44bf64a779a39019bfcda91e9`.
Purge removed four owned generated files and returned the campaign to absent.
Base verification passed: 429 unchanged files, zero overlays, projection
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
No profile/save/history/Cloud filesystem contents were read; credentials remained
inside the existing client's read lease and were cleared after use. The waived
unmodded relaunch was not repeated. User-wait, setup and documentation phase totals
were not captured; measured controller and release-gate times are retained above.
