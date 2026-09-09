# Combined bridge live batch

Status: representative batch completed, including allocated off-screen
single-upgrade. Generic event/map, both combat/choice/reward/map policies and
Sapphire Seed off-screen Defend slot 20 of 23 passed. A sixth installation
also passed Plant and Nourish single-card enchantment on the new artifact.
All six installations were cleaned up. The user authorized live testing after feature preparation and
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


## Sixth installation: single-card enchantment

The user requested the prepared test and confirmed readiness after manual launch
and Sapphire Seed setup on the established Profile 3 workflow. UI showed the
initial Consume and Plant and Nourish options untouched. No profile/save/history/
Cloud filesystem data was accessed. The same installed bridge, transport and
generic controller were used with a bounded test provider.

Artifact and ownership:

- Source commit: `50add7d2d5516c23166f80be91dbb54ed94400e3`.
- Release manifest SHA-256:
  `19142148f81ab5363aa3a131c9ff28ca8f9745af29b322a2ef2e1fb25099ccf0`.
- DLL: 797184 bytes,
  `9f0021f98a269214e02a99a9c834c27472276dd28703343f37cdae7383926303`.
- Installed state:
  `95d1580479666caeea76dabb82150d0d9d07a6f21eef54c35c00da201d0d7358`.
- Release/source/package and owned installation validation passed. Authenticated
  health was running and the manifest reported a compatible build before input.

The provider selected advertised `choose:1`,
`SAPPHIRE_SEED.pages.INITIAL.options.PLANT`. The bridge admitted a
`card_enchant_v1` child with **24 eligible candidates**, requesting **SOWN,
amount 1**. It selected `DEFEND_IRONCLAD`, **slot 5**, upgrade level **0**,
then received the exact-original enchantment preview. The provider allowed an
eight-second observation window and sent `confirm` once. No preview screenshot
was retained; preview identity and effect verification were performed by the
native adapter. A subsequent screenshot showed the returned map.

The child resolved only after the selected original gained the requested
enchantment, the unselected deck remained unchanged, the native tasks completed
and the selector closed. The parent resumed through advertised Proceed
(`choose:0`). The existing core map checker independently accepted a fresh
actionable map with two candidates; no map node was selected.

| Result | Observed value |
| --- | --- |
| Event status | resolved |
| Parent attempted / accepted / reconciled | 2 / 2 / 2 |
| Child attempted / accepted / reconciled | 2 / 2 / 2 |
| Child episodes / completed card children | 1 / 1 |
| Event reads | 13 |
| Map reads / candidates | 1 / 2 |
| Final latest-parent effect label | unverified (Proceed); one verified card child retained |
| Elapsed client flow | 9.540 seconds, including eight-second preview window |
| Native diagnostics | parent_ready → child_ready → parent_ready → map_ready |

There was no UI card selection, manual confirmation, mutation retry or gameplay
source correction during this test. The provider and sanitized result remain at
`/private/tmp/sts-enchant-live-20260909.py` and
`/private/tmp/sts-enchant-live-20260909-result.json`. Credentials were cleared by
the shared client and not recorded.

Normal application quit was followed by successful owned quarantine:
`8dcecc449ba73d8266c403d98306e3f2a8d695dce578eecaf2fb24d90abfbee7`.
The manager verified the stopped process/closed listener and exact ownership;
purge returned the campaign to absent and removed four generated files.
Post-cleanup base verification passed: **429 unchanged files, zero overlays**,
projection `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.

This demonstrates one fixed-single Sown enchantment and event-to-core map
handoff on this release. Stacking/replacement, other enchantments/callers,
multiple/optional selection and full runs are not established.

## Seventh installation: repeated pages and pre-selector additions

The user requested live testing before further implementation. The accepted
combined package was reused without rebuilding or repeating unchanged release
checks. Installation passed through the existing manager, including stopped
process/closed listener, pinned base build and owned artifact/configuration checks.

- Source commit: `baeaf5c3ac4420fdc6927c8bd357389cf116d6fc`.
- Release manifest SHA-256:
  `65c4e3d526b799f53795ab77131ba8947ad42be1db7f8261c1cacb064fe52dc9`.
- DLL: 798208 bytes,
  `e2906241d61ca70456257de5de214ad1f2a899e15b3c47ae800b3b5323ee339a`.
- Installed state:
  `1ca975ba8d0ecd4d043afb8443550c2c263d400002c7ba78dd61fd7aaa6e6a4a`.

The user confirmed readiness after manual Profile 3 launch and initial Abyssal
Baths setup. The ephemeral
provider `/private/tmp/sts-baths-live-20260909.py` uses the existing client and
generic host for exactly Immerse, Linger, Linger, Exit Baths and Proceed, then
the existing read-only core map check. Its local sequence and wrong/extra-page
rejection checks passed without credentials or live transport.

Authenticated health/manifest and exact installed release validation passed before
input. The live sequence selected the advertised IMMERSE key, the same LINGER key
on two successive fresh decisions, EXIT_BATHS and PROCEED. All **5 attempted,
accepted and reconciled parent actions** completed; there were **0 children**.
The event resolved in **8 reads**, followed by a successful independent core map
check in **1 read with 2 candidates**. No map node was selected. Elapsed client
flow was **1.349 seconds**. Native diagnostics included `parent_ready`,
`pending_chosen_completion` and `map_ready`. No mutation was retried.

The sanitized result is `/private/tmp/sts-baths-live-20260909-result.json`.
Credentials were cleared and not recorded. The effect label remains `unverified`:
this establishes completed option callbacks and page/map transitions, not an
independent HP-effect oracle. Other repeat-page callers remain untested.

Grave of the Forgotten/Confront is prepared next with the same client/host in
`/private/tmp/sts-grave-live-20260909.py`: exact Confront, first native-eligible
slot, SoulsPower amount 1, an eight-second preview, confirmation and Proceed/map.
The first Grave attempt, after user readiness, passed installed-release and
authenticated health/manifest checks but stopped on its first event read:
`unsupported_state`, native diagnostic `parent_unavailable`. All attempted,
accepted and reconciled action counts were **0**; effects were `none_attempted`.
No option or card was selected, and no map handoff was attempted. Elapsed flow
was **0.218 seconds**. The sanitized result is
`/private/tmp/sts-grave-live-20260909-result.json`. The initial native context or
presentation must be established before another attempt; this did not exercise
pre-selector additions. The user confirmed that initial Confront/Accept choices
were visible with the console closed. The diagnostic does not identify which
native context predicate failed. Retained map travel state from console creation
is a possible explanation, consistent with the fourth installation's earlier
admission failure, not a proven cause. The terminal response stops the bridge
session; no retry was issued.

The user confirmed fresh setup after instructions to quit normally, manually
relaunch Profile 3, enter a normal room through the map, then create Grave with
the console. The unchanged provider ran from
`/private/tmp/sts-grave-live-20260909-fresh-room.py`, with a separate result path.
The same installed package was used; no source correction, guard change or
rebuild was made.

Authenticated health/manifest and exact installation validation passed. The
provider selected advertised Confront (`choose:0`), then received a fixed-single
`card_enchant_v1` child with **3 eligible candidates**, requesting **SOULS_POWER,
amount 1**. It selected **NEOWS_FURY, slot 0, upgrade level 0** once. The exact
preview was admitted, held for eight seconds, then confirmed once. Native effect
verification required the selected original to gain the requested enchantment,
the rest of the request-time deck to remain unchanged, completed native tasks
and a closed selector. Proceed (`choose:0`) returned to a fresh core map.

| Result | Observed value |
| --- | --- |
| Event status | resolved |
| Parent attempted / accepted / reconciled | 2 / 2 / 2 |
| Child attempted / accepted / reconciled | 2 / 2 / 2 |
| Child episodes / completed card children | 1 / 1 |
| Event reads | 13 |
| Map reads / candidates | 1 / 2 |
| Elapsed client flow | 9.526 seconds, including eight-second preview window |
| Native diagnostics | parent_ready → child_ready → parent_ready → map_ready |

The sanitized result is
`/private/tmp/sts-grave-live-20260909-fresh-room-result.json`. Credentials were
cleared and not recorded. No UI card selection, mutation retry or map-node action
was used. The final parent effect label is `unverified` for Proceed; the completed
verified card child remains counted. This demonstrates Grave's native
curse-before-selector composition and SoulsPower effect, not independent
verification of automatic Decay addition provenance. Trial verdicts and
post-selector additions are not established. The successful fresh setup does not
identify the exact predicate behind the first admission failure.

The user confirmed normal game quit. Owned quarantine verified stopped process,
closed listener and ownership, returning state
`e9015c5b0f83f7d20c6eb9005f974fe7260b8fd0319b7b2054a3ed7214a35bd5`.
Purge returned the campaign to **absent**, removing four generated files.
Post-cleanup base verification passed: **429 unchanged files, zero overlays**,
projection `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
All seven installations are now cleaned up. No profile/save/history/Cloud
filesystem data was accessed. Live flows were timed above; documentation and
user setup/quit wait were not separately timed.

## Eighth installation: removal followed by one appended grant

The user requested testing of the new removal-parent-grant feature. The accepted
package was reused without rebuilding or repeating its 71 passed release groups.
The canonical manager verified stopped process/closed listener, the pinned base
build and owned artifacts/configuration; installation passed.

- Source commit: `3a354b0a65d6a96b16eacf340eee56e3e1370229`.
- Release manifest SHA-256:
  `f1563b68b94fa62b64d387205b1e35a002085b7cefcc1016ca15ce5821ee32b9`.
- DLL: 802816 bytes,
  `e15a31cb8c397a061f92b1e655e73ef839effc5dda62f91378b84c8a367f3978`.
- Installed state:
  `92ae69702afc34acb85c7da9af9dd043c4309685e471c9c8f14335ebb8fb5cf6`.

The ephemeral provider `/private/tmp/sts-amalgamator-live-20260909.py` reuses the
existing authenticated client, generic host and read-only core map check. It
chooses Amalgamator's exact Combine Strikes option, the first two native-eligible
slots, pauses eight seconds on the exact preview, confirms once and proceeds to
the map. It additionally checks for one separately reported Ultimate Strike
parent addition; the public metadata remains explicitly unverified for provenance.
Native upgrades caused by relics are recorded without assuming level zero.

Provider compilation, exact five-action sequence, wrong event/preview rejection
and duplicate-confirm rejection passed locally without credentials or transport.
The pinned native `GenerateInitialOptions`/`EventModel.OptionKey` methods confirmed
the stable option key. The live case requires at least three eligible Strikes and
normal room entry through the map before console event creation, following the
previous setup evidence. Manual Profile 3 setup is pending. No live input has been
sent; installation remains active and cleanup is pending the test and normal quit.

After the user confirmed readiness, installed-release identity and authenticated
health/manifest preflight passed. Combine Strikes (`choose:0`) was attempted and
accepted, but the parent never reconciled: diagnostics changed from `parent_ready`
to `prepare_candidates`. The bounded host stopped with `unsupported_state` after
**258 reads and 17.801 seconds**. Parent attempted/accepted/reconciled counts were
**1/1/0**; all child counts were **0**, with no completed child or map handoff.
No card selection or removal confirmation was dispatched, and no mutation was
retried. Effects remain `unverified`.

The user reported **five selectable Strikes** visible after the stop. This confirms
the reported setup had enough targets; it does not isolate which holder/model,
highlight, visibility or enabled-state check failed within `TryCreateBindings`.
The failure preceded the new removal-plus-grant behavior and provides no live
acceptance of it. No runtime safeguard was changed. The sanitized result is
`/private/tmp/sts-amalgamator-live-20260909-result.json`; credentials were cleared
and not recorded. Normal quit has been requested for owned cleanup.

The user confirmed normal quit. Owned quarantine verified stopped process,
closed listener and exact ownership, returning state
`b937fe89febdfb7ae35913fc1a0f0569290ccbfdfc492b206c66596002e74ec7`.
Purge returned the campaign to **absent**, removing four generated files.
Post-cleanup base verification passed: **429 unchanged files, zero overlays**,
projection `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
All eight installations are cleaned up. No profile/save/history/Cloud filesystem
data was accessed. The next correction should isolate the failing candidate
admission predicate before another removal-parent-grant live attempt.

### Reproduced removal-hitbox compatibility correction

Removal still required the hitbox's exact runtime type to be
`NClickableControl`, unlike the corrected single/multi-upgrade, transformation
and reward adapters. Reusing `MultiDerivedHitbox` throughout `RemovalFixture`
reproduced the defect before correction: the native executable stopped at
`removal admitted` in `/private/tmp/sts-removal-hitbox-before`.

The correction replaces only the two exact-hitbox-type predicates with the
existing instance-validity predicate. Static `NClickableControl` typing, exact
holder-to-hitbox identity, holder/card/model/highlight/material identity,
visibility, enabled state, preview membership, task completion and exact
deck-effect reconciliation remain enforced. New stale-decision cases prove that
replacement, disabled, hidden and destroyed hitboxes dispatch no selection or
confirmation and leave the deck unchanged. The complete native executable passed
**4,638 checks** in `/private/tmp/sts-removal-hitbox-after`. The new cases run after
the retained legacy groups; their original assertion-count checks are unchanged.
One independent semantic review found no blockers.

A narrow read-only scan of the same pinned `sts2.dll` confirmed that
`NCardHolder.ConnectSignals` retrieves `%Hitbox` as `NClickableControl`, and that
`NDeckCardSelectScreen` still uses the inspected shared grid, selection highlights
and original-card preview. This establishes the compatibility defect, not the
exact cause of the eighth installation's coarse `prepare_candidates` failure.
The planned broader diagnostic expansion was unnecessary for this reproduced
correction. A fresh Amalgamator live attempt remains necessary.

## Ninth installation: corrected removal hitboxes

The corrected combined release passed all **71 groups in 161.809 seconds**,
including **4,638 native checks**, **221 event integration cases** (159 production
native), reproducibility, packaging and owned installation/cleanup fixtures.
All 294 source/test inputs match source commit
`93ffbb9c441fa05a71d3f666f109c1313f995623` byte-for-byte.

- Release manifest SHA-256:
  `5869376503308299efe15cddec8b237848967314b0ae6f5a0cc9eb7fa55ec25d`.
- Source inventory:
  `b2cc26cb8ccfe4076328cb817fb45be77b64a68c33686682addb86bb946baeee`.
- DLL: 802816 bytes,
  `4e38a6121adf1a57e6eca5d34ae71f28dcf4f767c3c76a6487f2cf4c2fc78319`.
- Installed state:
  `d492bdf9406a4f23fe1d13b4b3fa794e64c50c1f198152e44f76afafd8e9de03`.

The old package was retained at
`/private/tmp/sts-unified-bridge-release-before-removal-hitbox-20260909`.
Canonical publication and installation passed, including exact package/source
identity, stopped process/closed listener, pinned base build and owned files.
The new package occupies `/private/tmp/sts-unified-bridge-release`.

The existing bounded Amalgamator provider is prepared at
`/private/tmp/sts-amalgamator-live-20260909-hitbox.py` with the new release/state
identities and a fresh exclusive result path. Selection policy is unchanged.
Compilation, exact sequence and wrong-event/preview/duplicate-confirm rejection
checks passed without credentials or live transport. Manual Profile 3 setup is
pending; no live input has been sent on this release. Installation remains active
and cleanup follows the live attempt and normal quit. Native and integration
checks took 20.332 and 77.185 seconds respectively; implementation, review,
packaging and user wait were not separately timed.

After the user confirmed readiness, installed-source identity and authenticated
health/manifest preflight passed. Combine Strikes (`choose:0`) was attempted and
accepted. Candidate binding passed; the next diagnostic was `prepare_geometry`.
The host stopped with `unsupported_state` after **258 reads and 17.704 seconds**.
Parent attempted/accepted/reconciled counts were **1/1/0**. All child counts were
**0**; no card selection, removal confirmation, completed child or map handoff
occurred. No mutation was retried. Effects remain `unverified`.

The sanitized result is
`/private/tmp/sts-amalgamator-live-20260909-hitbox-result.json`. Credentials were
cleared and not recorded. This demonstrates progress beyond candidate binding on
the corrected package, but does not establish removal-parent-grant behavior.
The failure is within the existing `GridGeometry.TryBind` layout checks, which
include exact computed dimensions and complete-grid containment; the diagnostic
does not distinguish their individual predicates. Normal quit was requested for
owned cleanup, together with confirmation of whether all five cards were visible.

The user confirmed all five Strikes were visible without scrolling and then
explicitly confirmed the game was closed. The manager independently verified
stopped process/closed listener and exact ownership. Quarantine returned state
`e813c87ea2c73dba2b53a21d146010c4313898b00c8738a9150cc680e9a06953`;
purge returned the campaign to **absent**, removing four generated files.
Post-cleanup base verification passed: **429 unchanged files, zero overlays**,
projection `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
All nine installations are cleaned up. No profile/save/history/Cloud filesystem
data was accessed.

The user questioned the retained geometry restriction. Removal dispatch uses the
exact bound holder's native input method, while the geometry policy additionally
requires computed whole-grid dimensions and complete containment. The next
correction should align removal with existing holder-based sibling adapters,
preserving target identity, native legality and exact preview/effect verification.
No geometry predicate has yet been changed or live-tested in this record.

### Removal layout correction

At the user's request, removal now follows the sibling adapters' native holder
input policy. The obsolete `GridGeometry` capture, computed full-grid fit and
size/position retention checks are removed. The exact grid must remain valid and
not animating out; the complete allocated holder domain and retained
holder/model/card/hitbox/highlight/material identities still govern admission and
commit. Candidate legality now explicitly checks the native `_isClickable` field
using the existing sibling mechanism, in addition to hitbox enabled state and
node visibility. Pinned `NCardHolder._GuiInput` IL checks this field before
deferring `EmitPressed`; input uses the holder object, not screen coordinates.

Native fixtures cover five and twenty allocated cards in layouts that fail the
old computed fit, then change grid size and scroll position after the first
selection. Both cases verify exact two-original preview, selected-only removal,
ordered survivors and parent/map completion. Additional stale-decision cases
reject an unclickable holder, replaced or destroyed grid, outgoing animation and
changed holder domain with zero card dispatch and unchanged deck. Existing
replacement/disabled/hidden/destroyed hitbox tests remain. The full focused native
executable passed **4,687 checks** in `/private/tmp/sts-removal-layout-tests`.
An initial fixture compile used a set method on its list; the assertion was
corrected to exact sequence equality before the passing run.

Independent semantic review found no blockers. Ownership, action bounds,
preview, native-task completion, full-deck removal/grant reconciliation, wire
contracts and cleanup behavior remain unchanged. Fixtures are inert and do not
prove live off-screen removal. The upcoming live target remains the user's
ordinary five-Strike Amalgamator setup, previously confirmed visible without
scrolling. No extra viewport certificate or diagnostic system was introduced.

## Tenth installation: native removal without whole-grid geometry

The corrected combined release passed all **71 groups in 161.665 seconds**,
including **4,687 native checks**, **221 event integration cases** (159 production
native), reproducibility, packaging and owned installation/cleanup fixtures.
All 294 source/test inputs match source commit
`bd45e1bbd3a7c007a3acf3d1dac12182c1582d79` byte-for-byte.

- Release manifest SHA-256:
  `fcfdd9e9deb162a5ca1f0b0756505048b48cdb83e18255520fcc788081a526dd`.
- Source inventory:
  `058cf81db3b713373268e0a4574bcb6ed3e6e17f10d0fe692f8593a7bc0d479a`.
- DLL: 801280 bytes,
  `a7e62b229a5e103c8802b599f705da908551ffa3087c5470c7a089b04ef11c50`.
- Installed state:
  `a8b6ba4456681d5a8c824f0c84826a21446c0aeddee5207b0be1de85fee1d496`.

The previous package is retained at
`/private/tmp/sts-unified-bridge-release-before-removal-layout-20260909`.
Canonical publication and installation passed, including exact package/source
identity, stopped process/closed listener, pinned base build and owned files.
The current package occupies `/private/tmp/sts-unified-bridge-release`.

The bounded Amalgamator provider is prepared at
`/private/tmp/sts-amalgamator-live-20260909-layout.py` with the new release/state
identities and a fresh exclusive result path. Selection policy remains unchanged:
Combine Strikes, first two eligible slots, eight-second exact preview, confirmation,
Proceed and independent fresh core map check, with separate Ultimate Strike grant
metadata. Compilation and exact sequence plus wrong-event/preview/duplicate-confirm
rejection checks passed without credentials or live transport.

Manual Profile 3 setup is pending; no live input has been sent on this release.
Installation remains active and cleanup follows the attempt and normal quit.
Native and integration checks took 19.399 and 78.143 seconds respectively;
implementation, review, packaging and user wait were not separately timed.

After the user confirmed readiness, exact installed-release validation and
authenticated health/manifest checks passed. The bridge selected advertised
Combine Strikes (`choose:0`) and admitted a fixed-two `card_remove_v2` child with
**five eligible candidates**. It selected **STRIKE_IRONCLAD, upgrade level 1,
slots 0 and 1**, paused for eight seconds on their exact preview, then confirmed
once. The native child verified both selected originals absent, unchanged ordered
survivors, closed selector and successful native task/option completion.

The resolved child reported exactly one separate parent addition:
`ULTIMATE_STRIKE`, upgrade level **1**, no enchantment, status **unverified**.
This records the actual appended descriptor; it does not independently certify
automatic grant provenance. Proceed returned to an independently checked
fresh actionable core map. No map node was selected.

| Result | Observed value |
| --- | --- |
| Event status | resolved |
| Parent attempted / accepted / reconciled | 2 / 2 / 2 |
| Child attempted / accepted / reconciled | 3 / 3 / 3 |
| Child episodes / completed card children | 1 / 1 |
| Event reads | 18 |
| Map reads / candidates | 1 / 2 |
| Elapsed client flow | 10.078 seconds, including eight-second preview pause |
| Native diagnostics | parent_ready → child_ready → parent_ready → map_ready |

The sanitized result is
`/private/tmp/sts-amalgamator-live-20260909-layout-result.json`. Credentials were
cleared and not recorded. No UI card selection or mutation retry was used. The
final parent effect label remains `unverified` for Proceed; the completed
verified removal child remains counted. This demonstrates one fixed-two
Amalgamator/CombineStrikes removal-plus-grant path, not CombineDefends, arbitrary
counts, other callers, off-screen removal or a full run. Normal quit was requested
for owned cleanup.

The user confirmed normal quit. The manager independently verified stopped
process/closed listener and exact ownership. Quarantine returned state
`b1e8b8807acab62773612764a416b6bcc9a54de755e8d8ea4dac825d653ace20`;
purge returned the campaign to **absent**, removing four generated files.
Post-cleanup base verification passed: **429 unchanged files, zero overlays**,
projection `d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`.
All ten installations are cleaned up. No profile/save/history/Cloud filesystem
data was accessed. The live flow took 10.078 seconds; user setup/quit wait and
documentation were not separately timed.
