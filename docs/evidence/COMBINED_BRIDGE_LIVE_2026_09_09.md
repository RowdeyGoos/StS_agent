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


## Eleventh installation: generic event feature batch

The user requested live testing after five offline feature increments. One combined
release passed all **71 groups in 258.357 seconds**, including **6,004 native
assertions**, **311 event integration cases** (249 production native), shared
host/client checks, reproducible packaging and owned installation/cleanup fixtures.
All 302 source/test inputs match commit `7fa8eae89160ee582dc9e66610f6b8f976a98825` byte-for-byte. The existing
feature semantic reviews remain applicable to these unchanged implementations.

- Release manifest SHA-256: `e7126021456c35077fea0996ccdef98f5ea045bdfa4f8333bc124eed80f3ad18`.
- Source inventory: `da579606508e0855e18b6f9d7e0d710a7037cab7ff977076c8211070255183a4`.
- DLL: 868352 bytes, `e2b5b0344f0820a2030b22c2b0617552c5e44e18fa81727da85f32e7a7a00b00`.
- Installed state: `23576968fd70ae15c79efd9081b977ad1a81075ed211d59d8d1259ce612c8942`.
- Gate outputs: `/private/tmp/sts-bridge-4ljtuw2f`.

Canonical publication and installation passed. Fresh pre-install checks found the
exact game process stopped and local bridge port closed; all 429 pinned base files
matched with zero overlays. Post-install verification matched the same base files
and exactly two owned overlay files. The prior accepted package is retained at
`/private/tmp/sts-unified-bridge-release-before-event-batch-20260909`; the new package
occupies `/private/tmp/sts-unified-bridge-release`.

The first bounded policy is prepared at
`/private/tmp/sts-wood-carvings-live-20260909.py`, SHA-256
`59107dcf50e773b5a3e8dae8e5198e8bce7514fb2903bff2b83131d17c17d0cc`. It uses the existing unified release,
installation, credential, transport and host machinery. It chooses only Wood
Carvings' Bird option, selects one advertised eligible card, pauses five seconds
at its exact original preview, confirms once, chooses Proceed and independently
checks a fresh actionable core map. Nine offline policy checks use the actual
host's frozen DecisionView shape. Independent review caught a tuple/list preview
comparison mismatch; the correction passed those checks and narrow re-review.
The result path is exclusively created at
`/private/tmp/sts-wood-carvings-live-20260909-result.json`. PECK is an expected native
result, not an observed replacement-key claim before the test.

Manual Profile 3 launch/setup is pending. Start from a normally entered map room,
open `event WOOD_CARVINGS`, keep at least two eligible basic cards and leave the
initial choices visible with the console closed. The remaining batch queue is
Waterlogged Scriptorium/Prickly Sponge, item reward sets, an ordinary singleton
CardReward menu and Colorful Philosophers' multiple menus. Each later setup will
be checked before acting; this queue is not live evidence.

No live input has been sent. **Installation is active; cleanup is required after
the batch and normal quit.** No profile/save/history/Cloud filesystem content was
accessed. Release-gate time is recorded above; separate review/packaging timing
was not tracked, and manual setup wait begins after this preparation.


### Bird transformation result

After user readiness, the exact running process, installed release/source and
state identity, authenticated health and compatible manifest passed. The bounded
provider chose `WOOD_CARVINGS.pages.INITIAL.options.BIRD`, then upgraded
`STRIKE_IRONCLAD` at slot **0** in a **21-card** domain. Its exact original preview
was held for five seconds, then confirmed once.

The native transformation journal reconciled the selected removal and exact
replacement insertion, successful native tasks and unchanged ordered survivors.
The child resolved, Proceed completed, and an independent core map read reported
**two actionable candidates**. Parent and child counters were each **2 attempted /
2 accepted / 2 reconciled**: four total actions, six event reads and one map read.
One completed card child was retained. Elapsed time was **6.119 seconds** including
the preview pause. The final `effects: unverified` field describes the latest parent
Proceed action; it does not erase the verified child result.

Result: `/private/tmp/sts-wood-carvings-live-20260909-result.json`, SHA-256
`9f9c6f53a0b3dd53d31164ff0e0622a550100274eac71d8cadf1f1699d62a33b`. Native diagnostic sequence:
`parent_ready`, `child_ready`, `parent_ready`, `map_ready`. No mutation was retried.
The policy records PECK as the expected native result. Its public summary does not
expose the replacement key; the user separately confirmed “Yes, Peck is present”
in the deck. This is visual confirmation, not replacement-name telemetry. This is live
acceptance of one generic deck transformation interaction, not Torus/all branches,
all deck sizes or an autonomous full run.

The installation remains active for the next case, Waterlogged Scriptorium's
Prickly Sponge. Its policy at `/private/tmp/sts-scriptorium-live-20260909.py`
(SHA-256 `6e9861219a796665c13e6dfe5ac51ae4af44957455b66e4ed3148ac4288c349e`) passes twelve offline checks with the
actual frozen host views. It requires the exact Prickly Sponge parent, fixed-two
`card_enchant_v2`, Steady amount 1, two distinct eligible cards, exact original
preview, one confirmation, parent completion and fresh map. Independent policy
review passed with no blockers; manual setup is pending. The native branch costs
99 gold. No live input
for this second case has been sent; normal quit and owned cleanup remain required
after the batch.


### Prickly Sponge stopped at the production response boundary

The user prepared the initial event choices and confirmed readiness. The exact
running process and installed release/source/state checks passed. The policy
accepted `WATERLOGGED_SCRIPTORIUM.pages.INITIAL.options.PRICKLY_SPONGE`
(`choose:2`), but the next read failed with `invalid_response`. There were **1
parent attempted / 1 accepted / 0 reconciled**, **zero child actions**, two reads
and no map check. Elapsed time: **0.308 seconds**. The user confirmed a
card-selection screen was visible. Only `parent_ready` reached the controller.
The parent may already have spent its native 99-gold cost; this attempt did not
verify that effect or enchant any cards through the bridge.

Result: `/private/tmp/sts-scriptorium-live-20260909-result.json`, SHA-256
`68c9748e0c1d1f67876ccc62b729f0f10b5b7b5a5ebb27a82c98158eb3120da8`. One subsequent read-only diagnostic GET received
`ConnectionRefusedError`; it sent no mutations. No action was retried.

Source inspection identified a concrete production mismatch: the terminal
classifier called `ContractVersion(operation)` with the default maximum of one,
rejecting the emitted `card_enchant_v2` descriptor. The same classifier lacked the
new item-set/card-reward formats, and the shared request parser lacked new
card-reward verbs. These latter gaps were found offline, not by additional live
attempts. The fix preserves parent ownership and terminal failure semantics.

After the user quit normally, three process samples and two port samples confirmed
the game stopped and listener closed. Exact owned quarantine produced state
`21fcace5e8f27b5dc0ccec9361b1bd7dca20d3481628cb33f030dd9442fbea9a`;
purge removed four generated files. All **429 base files** remained unchanged
with the recorded base hash and **zero overlays**. The eleventh installation is
**cleaned up**. Bird's earlier pass remains bound to its original release. No
profile/save/history/Cloud filesystem content was accessed.


## Twelfth installation: production event boundary correction

Corrected the production classifier's multi-enchantment contract selection and
its item-set / singleton and multiple card-reward payload handling. Added the
canonical card-reward verbs to the existing shared event request grammar. Native
legality/effect checks, parent ownership through child resolution, terminal
failures and no-retry behavior remain intact. One independent semantic review
found no blockers. Focused checks passed: **664 shared checks**, **311 C#/Python
event cases** including **249 native-adapter cases**, and the event Python suite.
Every native integration response now traverses the actual production classifier.

The final release gate passed **71 groups in 257.219 seconds**, including 6,004
native assertions, 125 host tests, 311 integration cases, 664 shared checks,
byte-identical reproducibility, canonical packaging and owned installation/cleanup.
Release outputs: `/private/tmp/sts-bridge-ot98xkue`. Manifest SHA-256:
`748e3172a886a499342810aec43e86fd0987ce003e7989c9f5ffb1594f52c1d3`. Exact input commit: `c531b4c9963b640d52d0bb5fe9ec40d9808f3021`;
all **303 inputs** were independently checked against its Git bytes. Source inventory:
`4cd44456be890b42becf72682d4283ca55e64938d778573f3d80b39146abdd8a`.

DLL: **871424 bytes**, SHA-256
`dd8e8a986808522a2fd80a6bf001eb17921fe79be21e7529dd3ff7ddc18e5ec9`. Package ZIP: **872,118 bytes**, SHA-256
`c9ddf52c7a354fd1b07f60c98a301d62053540702be1e6073f4fdecd89f042d7`.
The prior package is retained unchanged at
`/private/tmp/sts-unified-bridge-release-before-boundary-fix-20260909`.
The corrected package occupies `/private/tmp/sts-unified-bridge-release`.

Fresh pre-install runtime checks confirmed the exact game process stopped and
bridge port closed. All 429 base files passed with the existing base hash.
Installation produced state
`1801571490790c9ec82fc9a8fe1bc8c72ad1cd0e9a5a6a5316e69c7446fc05ec`;
post-install verification found the unchanged 429 base files and exactly two
owned mod files. **Installation is active; no live input has been sent.**

Reuse the unchanged reviewed Prickly Sponge policy at
`/private/tmp/sts-scriptorium-live-20260909.py`, SHA-256
`6e9861219a796665c13e6dfe5ac51ae4af44957455b66e4ed3148ac4288c349e`.
Its twelve actual frozen host-view checks were rerun and passed. The new exclusive
result path is `/private/tmp/sts-scriptorium-live-20260909-retry-result.json`.
Manual Profile 3 setup is pending: enter a room normally, ensure at least 99 gold
and three eligible unenchanted cards, then `event WATERLOGGED_SCRIPTORIUM` and
leave initial choices visible with the console closed. This is a fresh attempt,
not adoption or replay of the stopped selector. Normal quit and owned cleanup
remain required after testing. No profile/save/history/Cloud content was accessed.
Separate implementation, review, packaging and user-wait times were not measured.


### Prickly Sponge fixed-two enchantment passed

After fresh manual setup and user readiness, the exact running game, installed
release/source/state identities, authenticated health and compatible manifest
passed. The unchanged reviewed policy chose Prickly Sponge, selected upgraded
`STRIKE_IRONCLAD` slots **0 and 1** in a **24-card** eligible domain, observed
the exact selected originals in preview for five seconds and confirmed once.
The native journal verified **Steady amount 1 on each selected original**, exact
request results, unchanged survivors, completed native tasks and overlay closure.
Proceed reconciled and one independent core-map read exposed **two actionable
candidates**.

Result: **passed in 6.730 seconds**, including the preview pause. Parent counters:
**2 attempted / 2 accepted / 2 reconciled**. Child counters: **3 / 3 / 3**, one
completed card child, five total actions, 14 event reads and one map read.
Diagnostics: `parent_ready`, `child_ready`, `parent_ready`, `map_ready`.
Final `effects: unverified` describes the last parent Proceed; it does not erase
verified cumulative child completion. No action was retried.

Result: `/private/tmp/sts-scriptorium-live-20260909-retry-result.json`, SHA-256
`63ffcf38f5b4f1a4ebe385e670e9d6230aeeed2099af86d1b4ef78adb35b43ea`. Release and installation remain the twelfth bindings
recorded above. This demonstrates one fixed-two caller/domain, not every count,
selector or enchantment. The successful event released its native module and the
shared core map was independently available. The installation stays **active** for
the remaining reward cases; normal quit and owned cleanup are still required.
No profile/save/history/Cloud filesystem content was accessed.


The next reviewed policy is Potion Courier/Grab Potions at `/private/tmp/sts-courier-set-live-20260909.py`, SHA-256
`e64bd456ab0b1dc603ad1db4b5a9954119d4280dd3295b1b91f52ccea8e7ba22`. Eighteen offline checks using actual frozen host views passed.
Independent semantic review found no blockers. The policy requires the exact
`POTION_COURIER.pages.INITIAL.options.GRAB_POTIONS` option and one `item_set_v1`
child containing three sequential `FOUL_POTION` entries. The host presents each
next inner `item_v1` view after validating the set history; the policy checks
remaining free potion capacity before collection. Each effect reconciles through
the existing host before another input. Success requires three reconciled item
actions, one completed item child, two reconciled parent actions and fresh map.
The bounded native source inspection confirmed canonical `FoulPotions = 3`,
mutable PotionReward creation followed by OfferCustom and SetEventFinished.

Result path `/private/tmp/sts-courier-set-live-20260909-result.json` is exclusive and unused. Setup is pending on the same
installation: enter a room normally, leave at least three empty potion slots,
run `event POTION_COURIER`, and leave initial choices visible with console closed.
No new package or install is needed, and no input for this next case has been sent.


### Potion Courier three-item reward set passed

After manual setup and user readiness, the exact running process, installed
release/source/state, authenticated health and manifest checks passed. The reviewed
provider chose `POTION_COURIER.pages.INITIAL.options.GRAB_POTIONS`, then collected
`FOUL_POTION` at generated list indexes **0, 1 and 2** in order. Each native claim,
collection task and exact inventory insertion reconciled before the next action.
The set, Offer/Chosen tasks and overlay completion reconciled, Proceed completed,
and a separate core-map read exposed **two actionable candidates**.

Result: **passed in 0.944 seconds**. Parent counters: **2 attempted / 2 accepted /
2 reconciled**. Child counters: **3 / 3 / 3**, one completed item child, zero card
children, five total actions, seven event reads and one map read. Diagnostics:
`parent_ready`, `child_ready`, `parent_ready`, `map_ready`. No action was retried.
Final `effects: unverified` refers to the last parent Proceed; cumulative child
completion retains the verified collections.

Result: `/private/tmp/sts-courier-set-live-20260909-result.json`, SHA-256
`93a8b5d60bd18e92bb0d48a1074469fa2c6f04bec1d7a01dd4fd5408680cf19b`. This demonstrates the three-potion caller with
sufficient empty slots, not full-inventory replacement or arbitrary relic pickup
composition. Release and installation remain the twelfth bindings above. The
installation is **active** for the remaining card-reward cases; normal quit and
owned cleanup are still required. No profile/save/history/Cloud content was read.


The next policy is Brain Leech/Rip at `/private/tmp/sts-brain-reward-live-20260909.py`, SHA-256
`6f116005c341c5e8cbd8a2f536f64657deb1177df3fd96a97122436309ca4f10`. Eighteen offline checks using actual frozen host views passed.
Independent semantic review found no blockers. It requires exact
`BRAIN_LEECH.pages.INITIAL.options.RIP`, one `card_reward_v1` child, `open` once,
then advertised slot 0 from a 1–5 card menu once, followed by Proceed only after
native/host reconciliation. Success requires two parent and two child actions
all reconciled, one completed card child, no item child and fresh core map.
The existing credential, bounded host/transport and no-retry paths are unchanged.

Pinned source confirms canonical `RipHpLoss = 5`, `RewardCount = 1`, damage before
one ordinary colorless CardReward/OfferCustom and final SetEventFinished.
The card child does not independently verify the preceding damage. Manual setup
must establish more than 5 HP; that premise is not new bridge HP telemetry.
Result path `/private/tmp/sts-brain-reward-live-20260909-result.json` is exclusive and unused. Setup is pending on the same
installation: enter a room normally, have more than 5 HP, run `event BRAIN_LEECH`,
and leave initial choices visible with console closed. No input for this next
case has been sent. Existing release and completed evidence are reused unchanged.


### Brain Leech singleton card reward passed

The user reported Brain Leech ready after the setup instruction requiring more
than 5 HP. That HP premise came from manual setup; no HP preflight telemetry was
added. Exact running-process, release/source/state, authenticated health and
compatible manifest checks passed. The reviewed provider chose
`BRAIN_LEECH.pages.INITIAL.options.RIP`, opened the ordinary reward, and selected
**EQUILIBRIUM**, upgrade level **0**, slot **0 of 3** advertised cards.
The native/host checks verified exact offered-card insertion and task completion.
Proceed reconciled and an independent map read showed **two actionable candidates**.
The child does not independently verify Rip's preceding automatic damage.

Result: **passed in 1.232 seconds**. Parent counters: **2 attempted / 2 accepted /
2 reconciled**. Child counters: **2 / 2 / 2**, one completed card child, no item
child, four total actions, 12 event reads and one map read. Diagnostics:
`parent_ready`, `pending_chosen_completion`, `pending_offers`, `parent_ready`,
`map_ready`. Waiting during native completion did not cause a retry or early
handoff. Final `effects: unverified` describes the last parent Proceed, not the
verified card-child completion.

Result: `/private/tmp/sts-brain-reward-live-20260909-result.json`, SHA-256
`f04edd4668c664ca38163caa9c763ab71999507f819155040fc60cceedeb643a`. This demonstrates the singleton choose path, not
singleton Skip/dismiss or every caller/card modification. Release and installation
remain the twelfth bindings above. The installation is **active** for the final
multiple-menu feature case; normal quit and owned cleanup remain required.
No profile/save/history/Cloud content was accessed.


### Colorful Philosophers multiple menus and Skip passed

The policy at `/private/tmp/sts-philosophers-set-live-20260909.py`, SHA-256
`bb384d2f2669c23d65a754309579ef38315f2a2c2c8b70e4bd10ee47e01d6ef8`, passed 25 actual frozen-view checks and independent
semantic review before execution. It admits an advertised generated color option
with the pinned `COLORFUL_PHILOSOPHERS.pages.INITIAL.options.` prefix, exactly
three ordinary card-reward entries, sequential open/choose or Skip, then final
dismissal. Existing release/state/credential, host, map and no-retry paths are
unchanged. The user reported the Colorful event ready. Exact running-process,
installed release/source/state, authenticated health and manifest checks passed.

The provider chose **NECROBINDER**, opened menu 0 and chose **FEAR**, upgrade
level **1**, slot **0 of 3**. It opened menu 1 and used the advertised native
**skip:1**. It opened menu 2 and chose **NECRO_MASTERY**, level **0**, slot **0 of 3**.
Each original-card insertion or unchanged-deck Skip reconciled before advancing.
After all three menus settled, the exact root **dismiss** action completed the
reward set. Parent Proceed reconciled and an independent core-map read exposed
**two actionable candidates**.

Result: **passed in 2.768 seconds**. Parent counters: **2 attempted / 2 accepted /
2 reconciled**. Child counters: **7 / 7 / 7**, one completed card child, no item
child, nine total actions, 25 event reads and one map read. Diagnostics:
`parent_ready`, `pending_offers`, `parent_ready`, `map_ready`. No action was retried.
Final `effects: unverified` refers to parent Proceed; cumulative child completion
retains all three verified menu outcomes and final dismissal.

Result: `/private/tmp/sts-philosophers-set-live-20260909-result.json`, SHA-256
`f31bae713734293589e09865300ddda5b539baf665a46165812dd7baceafb76e`. This demonstrates one three-menu mixed outcome,
not every count, all-collected/all-skipped or singleton Skip/dismiss. Together
with Bird on its original release and the other three cases on this package,
all five planned feature representatives passed. Release and installation remain
the twelfth bindings above. Normal quit was requested; **cleanup is pending**.
No profile/save/history/Cloud content was accessed.


### Twelfth installation cleanup

The user confirmed the game closed normally. Three exact-process samples and two
listener samples verified stopped/closed state. Quarantine from installed state
`1801571490790c9ec82fc9a8fe1bc8c72ad1cd0e9a5a6a5316e69c7446fc05ec`
produced `6a5d4fef1db86dd1e9269717f1d00b03ca941d31cfced47fd4966d58de75cc15`.
Exact owned purge removed four generated files and reported the campaign absent.
Base verification passed **429 files**, hash
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`, with
**zero overlays**. The twelfth installation and this five-feature live batch are
**closed and cleaned up**. Current package, manifest and source identity remain
retained; no profile/save/history/Cloud content was accessed. No new build or
broad test rerun was required for these evidence-only updates.


## Thirteenth installation: ancient and event feature batch

The user requested live testing after the optional-offer increment. Release
`1512ea86fa2b6b445fcae7023379257c13f94b4b180507c3e6afa337f41e555d` packages the
combined offline increments: mixed rewards, ancient dialogue, optional grids and
transforms, direct card offers/bundles, inactive combat-layout options, results
acknowledgment, and optional offers with one extra grant. All 313 accepted inputs
match source commit `691cb31ad088140d4fd7c5878ffb9830442d3b8e`. Production DLL SHA-256:
`06602e6ba4865887985e94317bfab84d51fe87243dfd1711ad8cdf1eb2fc0433`.
The previous accepted package is preserved at
`/private/tmp/sts-unified-bridge-release-before-ancient-batch-20260909`.

Final release validation passed all **71 groups in 370.564 seconds**, including
7,788 native assertions, 125 host tests, 450 C#/Python cases (388 through native
adapters), 809 shared checks, reproducible production builds, package rejection
fixtures and owned installation/cleanup checks. Output:
`/private/tmp/sts-bridge-0j2oddyi`. Existing implementation semantic reviews were
reused; this is one final combined release gate, not live acceptance.

Three process samples and two port samples verified the exact game stopped and
listener closed. The canonical installer rechecked the pinned build and ownership,
installed the accepted package, and created the mods parent. Installed state:
`2645fc0353e50095acd66fedcd789dc9d266a1dd20a527df4c2f4ca0f58a8013`.
Read-only post-install metadata/content verification passed without reading the
credential. The installation is **active**, awaiting manual Profile 3 launch and
setup. Normal quit and exact owned cleanup remain pending.

The first planned cases are HeftyTablet choose and Skip. A narrow inspection of
the same pinned game PE establishes `AncientConsoleCmd` syntax
`ancient <id> <choice>`: it creates an ancient event and sets `DebugOption` from the
matching option key. Use `ancient NEOW HEFTY_TABLET` after normal map-room entry;
leave the ancient dialogue/options visible with the console closed. This user
setup establishes the ancient identity before its generic dialogue is advanced.
The policy then requires the exact `NEOW.pages.INITIAL.options.HEFTY_TABLET` option.
Direct console relic acquisition would bypass the owned event callback and is
not this test's setup. Inspection output: `/private/tmp/sts-live-ancient-il.json`.

Policy `/private/tmp/sts-hefty-live-20260909.py`, SHA-256
`906bfff7db565c74ddcb1caef8c2f852ab42e8de585c378379cc23150a381a07`, passed **32
frozen-view checks** and independent semantic review. It uses the existing unified
release/state/credential checks, client, host and map verifier. Each invocation
chooses once or skips once, requires one `card_offer_v2` completion and the observed
Injury suffix, and verifies a fresh actionable map. It retains `unverified` effect
semantics and never retries uncertain input. No live input has been sent yet.
No profile/save/history/Cloud filesystem content was accessed. Separate preparation,
review and user-wait elapsed times were not measured.


### HeftyTablet first observation stopped; thirteenth installation cleaned

The user confirmed readiness with the Hefty Tablet relic option visible. Fresh
exact-process, accepted source/package/state and authenticated health/manifest
checks passed. The reviewed choose policy then stopped on the first event read:
`invalid_response`, **zero parent/child actions attempted, accepted or reconciled**,
no child admission and no map check. Elapsed policy time: **0.227 seconds**.
No dialogue or relic option was selected. Console setup may skip initial dialogue;
the policy already permits the relic option directly, so missing dialogue is not
the cause. Result: `/private/tmp/sts-hefty-choose-live-20260909-result.json`, SHA-256
`4c98d007e8bf0568b28331d6b903f078644abbab2f4f5607d9b2ce0830c8fa79`. A subsequent read-only diagnostic received connection refused,
confirming the listener had stopped; no action was retried.

Pinned PE metadata inspection found the concrete initialization defect:
`NSimpleCardsViewScreen.ShowScreen(List<CardPileAddResult>, LocString)` declares
return type **NCardsViewScreen**, although it creates a NSimpleCardsViewScreen.
The hook guard, postfix signature and inert stubs had incorrectly used the concrete
return type, rejecting event-hook initialization. Earlier IL callsite inventories
omitted declared return types and therefore did not establish that signature.
The correction uses the base declaration and retains the exact concrete runtime
screen/capstone identity. A release verifier check now compares the production
postfix and inert target declaration against pinned game metadata without loading
the game. Inspection: `/private/tmp/sts-hooks-signature-inspect/il.json`.

The user quit normally. Owned quarantine moved installed state
`2645fc0353e50095acd66fedcd789dc9d266a1dd20a527df4c2f4ca0f58a8013` to
`1c4c2b979e8a8203bf40bf5a2e52ea0ecf7dd90e469efc87d68d1a37d4efdfa2`;
exact purge removed four generated files and left the campaign absent. Base
verification passed **429 unchanged files**, SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`, with **zero
overlays**. The thirteenth installation is **closed and cleaned up**. No
profile/save/history/Cloud filesystem content was accessed.

### Fourteenth installation: results-return correction

Corrected release `c73fde6c7877b4bba71fdab3a11e2d9b05a5e64e49ffbbd470b38e27b3e31d57`
is bound to source commit `b7d474070b89978747d64f30dae5f76668cbf084`:
all **314 source/test inputs** match the accepted manifest byte-for-byte. DLL
SHA-256: `356f0e18d6b5f2db99fdd8351cab533a69441ee34216b9dd62985c61671454c3`.
All **71 release groups passed in 370.071 seconds**, including 450 C#/Python cases
(388 native), 809 shared checks, reproducibility, the mandatory pinned-PE signature
comparison, and package/owned installation-cleanup fixtures. Integration took
225.883 seconds; production and reproducibility builds took 1.437 and 1.460 seconds.
Evidence: `/private/tmp/sts-bridge-_el21wpf`.

Focused surface checks passed 174 assertions. The metadata regression accepted
the corrected production/fixture pair and rejected each prior incorrect production
postfix or fixture against pinned game metadata. Evidence:
`/private/tmp/sts-results-return-metadata-evidence.json`, SHA-256
`3bf214e7dca5b91dd432bebc4c9fcc39d410254572ea79d4713cb0a6ab074757`.
Independent semantic review found no blockers. An initial release invocation
stopped before checks because its metadata-helper link lay outside the maintained
source boundary; a local metadata-only provider corrected that prerequisite.
The final gate used the stable corrected sources. The previous package was verified
and preserved at
`/private/tmp/sts-unified-bridge-release-before-results-return-fix-20260909`.

Fresh stopped-process/closed-port checks passed. Installation succeeded with state
`265480ccd6e8029ff097518a4412a236373316a22eeb4a5e0f2b6fb8129b9ed1`.
Read-only installed package/configuration verification passed without reading the
credential. The **fourteenth installation is active**, awaiting manual Profile 3
launch and `ancient NEOW HEFTY_TABLET` after normal map-room entry. Direct relic
options are allowed; initial dialogue is not required. The policy remains unchanged
at SHA-256 `906bfff7db565c74ddcb1caef8c2f852ab42e8de585c378379cc23150a381a07`;
its 32 completed frozen-view checks and semantic review are reused.
No live input has been sent on this installation. Cleanup is pending after testing.
No profile/save/history/Cloud filesystem content was accessed. Separate
implementation, review, preparation and user-wait times were not measured.

### HeftyTablet choose passed

On the fourteenth installation and corrected release recorded above, the user
confirmed the prepared event was ready. Fresh exact running-process verification,
release/source/owned installation checks and authenticated health/manifest passed.
The unchanged reviewed policy chose the exact HeftyTablet relic option, selected
**Cruelty (upgrade level 0)**, and selected Proceed. No initial dialogue was needed.
The native child verified the selected original and one appended **Injury**;
`card_offer_v2` resolved with selected index 0 and `collected` history.

All **three actions reconciled**: two parent and one child attempted/accepted/
reconciled, one completed card child, no item child, 11 event reads. A separate
fresh core-map observation passed with two candidates. Elapsed policy time:
**1.436 seconds**. Parent effects remain `unverified`; this demonstrates the
observed selected/extra-card outcome, not automatic-grant provenance or every
optional-offer branch. No uncertain input was retried.

Result: `/private/tmp/sts-hefty-choose-live-corrected-20260909-result.json`, SHA-256
`bdbe657ebf4db7ba213dfd22fd8f2dbe4e7674b70d9f08cea5e60489136bc7a7`.
The diagnostic sequence included `pending_task_failed` before successful completion.
Source inspection shows that label is assigned before checking task failure and
can remain on a pending-child capture; this was not a terminal host failure.
The successful resolved receipts and map check establish this case's outcome.

The same installation remains active for a fresh HeftyTablet **Skip** setup;
normal quit and cleanup remain pending after the live batch. The unchanged policy
already contains the reviewed Skip branch, so its completed checks/review are
reused. No profile/save/history/Cloud filesystem content was accessed.

### HeftyTablet Skip passed

The user confirmed a fresh HeftyTablet setup on the same fourteenth installation.
Fresh exact running-process, release/source/owned installation and authenticated
health/manifest checks passed. The unchanged reviewed policy chose the exact relic
option, dispatched native **Skip once**, then Proceed. The child resolved as
`card_offer_v2`, selected index null, with `skipped` history and exactly one
additional **Injury (upgrade level 0)**. No offered card was added.

All **three actions reconciled**: two parent and one child attempted/accepted/
reconciled, one completed card child, zero item children, ten event reads. A fresh
core-map read passed with three candidates. Policy time: **1.006 seconds**.
Parent effects remain `unverified`; both observed HeftyTablet branches now have
representative live acceptance. The transient diagnostic sequence matches the
previous choose case and its documented nonterminal label behavior.

Result: `/private/tmp/sts-hefty-skip-live-20260909-result.json`, SHA-256
`94986e6a39f42c7683e1845b34246664055fc80b35c1d9d46bc4dc6795e18257`.
The bridge remains installed for the remaining batch; cleanup is pending after
live testing. No profile/save/history/Cloud filesystem content was accessed.

The next bounded policy is prepared at `/private/tmp/sts-seaglass-live-20260909.py`,
SHA-256 `6351761f495671d8f388205fe0c32047d239e8e858935188af5b359d27422de3`. Its **96 frozen-view
checks passed** and independent semantic review found no blockers. It reuses the
existing unified client, source/state/authentication validation, generic event host
and fresh core-map verifier. It requires exact
`OROBAS.pages.INITIAL.options.SEA_GLASS`, `card_add_v2`, min zero/max fifteen,
exactly fifteen offers and explicit confirmation. Counts zero, three and fifteen
are supported by the policy; **zero is the next live case**. Selection uses lowest
advertised unselected slots and requires exact selected-card identities in the
resolved child, plus matching action counts and one completed child. Zero requires
an explicitly confirmed empty result. No uncertain input is retried.

Pinned Orobas metadata and the shared option-key builder establish this key and
`ancient OROBAS SEA_GLASS` setup. Sea Glass has character-specific pool variants;
this test makes no pool/color claim. Enter a room from the map normally, invoke
the console command, close the console and leave the relic option untouched.
No further build/install is needed; the accepted release is unchanged. This policy
has not yet run live. Separate policy preparation/review times were not measured.

### Sea Glass zero stopped before child admission

The user confirmed readiness, and fresh running-process, release/source/owned
installation and authenticated health/manifest checks passed. The reviewed policy
accepted `OROBAS.pages.INITIAL.options.SEA_GLASS` once. The selector could not be
admitted: diagnostic `prepare_geometry`, followed by bounded `unsupported_state`
after **17.358 seconds / 258 event reads**. Parent attempted/accepted/reconciled
**1/1/0**; child episodes and actions **zero**. No card selection or Confirm was
sent, no child outcome was verified and no map check ran. The user confirmed a
card-selection grid with **15 cards**. No uncertain input was retried.

Source inspection identifies the admission boundary in
`GenericEventV7RewardAdapter.TryPrepareSurface`: exact offered models, native
holder/control identities, initial visibility/enabled state and foreground checks
pass before `GridGeometry.TryBind`. That remaining geometry helper demands computed
whole-grid fit and bit-identical inferred dimensions. This is an unnecessary
prerequisite for native holder input or zero-selection Confirm, analogous to the
previously removed deck-removal layout prerequisite. The result does not identify
which individual dimension failed. Correction should retain exact grid/holder/card
identity, native legality, bounded input, task/deck outcome checks and cleanup.

Result: `/private/tmp/sts-seaglass-zero-live-20260909-result.json`, SHA-256
`94fc6792fc1584068b0830ed104199fbb90287a8f2a2285520d1ef60b05076cd`.
The fourteenth installation is stopped for this test and remains installed,
awaiting user-confirmed normal quit and exact owned cleanup before source changes.
The earlier HeftyTablet passes retain their original release evidence. No
profile/save/history/Cloud filesystem content was accessed.

The user then quit normally. Exact owned quarantine moved installation state
`265480ccd6e8029ff097518a4412a236373316a22eeb4a5e0f2b6fb8129b9ed1` to
`a3f7500c77db6cd4f98b4e3dcf80002327145fbd9c201a864f6dcbee7a42476f`.
Purge removed four generated files and left the campaign absent. Base verification
passed **429 unchanged files**, SHA-256
`d111d988aca63d8933b8b88968f4e3ecd8006e877eb2990e60b8a40511c50be0`, with zero overlays.
The fourteenth installation is **closed and cleaned up** before source edits.

### Fifteenth installation: native add-card input without inferred layout

The correction removes `GridGeometry` from the generic reward/add-card adapter.
Exact allocated grid/holder/card/hitbox/Confirm identities remain required;
native holder `_isClickable` now mirrors the removal adapter. Visibility/enabled
state, animation/transient behavior, bounded input, exact tasks and deck outcomes
remain checked. Zero selection no longer requires a computed layout certificate.
The audit found no other actual whole-grid-fit check in generic event adapters;
the separate older standalone Cheese adapter retains its historical geometry.

Focused reward surface checks passed **283 assertions**, including zero/three/
fifteen selections under overflowing and changing layouts, and stale grid, holder,
model, hitbox, domain, clickability and Confirm failures without dispatch. Existing
optional-event checks passed **379 assertions**. Independent semantic review found
no blockers. An initial release run stopped because the new tests had been invoked
before fixed historical assertion-count boundaries. Moving only the invocation
after the preserved predecessor boundary corrected test ordering; no production
change was required. The final gate used stable sources.

All **71 release groups passed in 371.191 seconds**: 7,896 native event assertions,
125 host tests, 450 C#/Python cases (388 native), 809 shared checks, pinned-signature
comparison, reproducible production binary and package/owned cleanup fixtures.
Integration took 225.461 seconds; production/reproducibility builds took
1.490/1.469 seconds. Evidence: `/private/tmp/sts-bridge-n2fi2egq`; initial stopped
gate: `/private/tmp/sts-bridge-88z165dz`.

Release SHA-256: `c6670ae435c0d1ba33af202d89b693fa7bfd469da988a2b3462d09e1cdfd0eb5`.
Source commit: `23cbff0d38a18b866c94531f8b23a57b3bb030e0`, with all 314
accepted inputs verified byte-for-byte. DLL SHA-256:
`95d3bd970682cef1d13b07eaebfdfbde0c762e43c06ef83d9631fbaa99148e5a`.
The previous package was verified and preserved at
`/private/tmp/sts-unified-bridge-release-before-reward-layout-fix-20260909`.

Fresh stopped-process/closed-port checks passed. Installation succeeded with state
`1af40d941099a2dc21ef6964a2943b136d05cac580fbac5764c5a09782cd0dd9`.
Read-only installed package/configuration verification passed without reading the
credential. The **fifteenth installation is active**, awaiting manual fresh
Profile 3 setup, normal map-room entry, `ancient OROBAS SEA_GLASS`, console closed,
relic option untouched. The next case is explicitly **zero cards**, not cancellation.
The unchanged Sea Glass policy remains at
`/private/tmp/sts-seaglass-live-20260909.py`, SHA-256
`6351761f495671d8f388205fe0c32047d239e8e858935188af5b359d27422de3`;
its 96 completed checks and independent review are reused. No live input has been
sent on this installation; normal quit/cleanup remain pending after testing.
No profile/save/history/Cloud filesystem content was accessed. Separate
implementation/review/preparation/user-wait elapsed times were not measured.

### Corrected Sea Glass startup stopped with zero actions

On release `c6670ae435c0d1ba33af202d89b693fa7bfd469da988a2b3462d09e1cdfd0eb5`
and the fifteenth installation, the user confirmed readiness. Fresh exact running
process, accepted source/state/owned package and authenticated health/manifest
checks passed. The unchanged zero-card policy stopped on its **first event read**
with `invalid_response`, **zero parent/child actions attempted, accepted or
reconciled**, no child admission and no map read. Elapsed policy time: **0.694
seconds**. The user confirmed the **Sea Glass relic option** remained visible.
Result: `/private/tmp/sts-seaglass-zero-live-corrected-20260909-result.json`, SHA-256
`45e64b1315c521450bd3b09e48c450d2ae15adc09bd16277f2830085a30fa6a8`.

One read-only diagnostic request received `ConnectionRefusedError`, establishing
that the listener had stopped; it sent no game actions. The first raw HTTP frame
was not retained, so this evidence does not distinguish a router/module exception
from an empty response after the existing **500 ms** frame-work result budget.
The elapsed total includes preflight and is not a measurement of native hook
initialization. Neither hypothesis is established; the geometry correction itself
was not exercised. No source/package change or timeout relaxation follows from
this observation alone.

The user quit normally. Fresh stopped-process/closed-port checks passed (three
process samples, two port samples); read-only owned installation verification
passed without credential access. The **same fifteenth installation is retained**
for one fresh-process read-only startup experiment, with cleanup pending afterward.
This is not a handoff within the failed native host: the old game process ended.
No uncertain game mutation is being retried.

Diagnostic `/private/tmp/sts-seaglass-startup-diagnostic-20260909.py`, SHA-256
`afee7ce3282c4a2dc69d02a31691706f0ebfcec1dfde0fcda38238d721bf731c`, is prepared and syntax-checked without a
live request. It uses the existing release/state/credential/client checks and
health/manifest checks, then makes **one event GET with no POST**. It records only
response length, a bounded HTTP/error category, exact Sea Glass option readiness
and timing, and clears credential/response buffers. It will distinguish absent
bytes from a structured bridge-stopped response if the failure repeats. A ready
result can precede the already reviewed zero-selection policy; no new build,
installation or release gate is needed. No profile/save/history/Cloud filesystem
content was accessed.

### Sea Glass zero passed after read-only startup

The user relaunched and prepared the Sea Glass option on the unchanged fifteenth
installation. Fresh exact running-process verification passed. The prepared
read-only diagnostic revalidated release/source/owned installation and authenticated
health/manifest, then made one event GET: **HTTP 200, 1,692 response bytes**, exact
Sea Glass option ready, no bridge error, **0.528 seconds** for the event exchange
(**0.629 seconds** total). No POST or game input occurred in that check.
Result: `/private/tmp/sts-seaglass-startup-read-live-20260909-result.json`, SHA-256
`7ee235349e7bb9a1747be83acb02ee5ae397b4264d98a09cd9e80fc60ddd7e23`.
This demonstrates successful startup on the same binary in a fresh process. It
does not identify the previous failure: exchange timing includes client pacing,
so native initialization duration and a frame-work timeout remain unproven.

With the exact option freshly verified, the unchanged reviewed zero-card policy
then selected `OROBAS.pages.INITIAL.options.SEA_GLASS`, explicitly **confirmed zero
cards**, and selected Proceed. `card_add_v2` resolved with `operation: add`, empty
`selected_cards` and a `committed` Confirm receipt. Native task/deck checks verified
the empty selection and unchanged baseline deck. All **three actions reconciled**:
two parent and one child attempted/accepted/reconciled, one completed card child,
zero item children, five event reads. A separate fresh map read passed with one
candidate. Diagnostics: `parent_ready`, `child_ready`, `parent_ready`, `map_ready`.
Policy time: **0.712 seconds**. Parent effects remain `unverified`.
Result: `/private/tmp/sts-seaglass-zero-live-after-startup-20260909-result.json`, SHA-256
`fc20941a3ab3108fd1d17e39b32cd35e99f72ae3bb1eaab8bcf659c3d4abea59`.

This gives representative live acceptance to zero-selection confirmation after
removing inferred grid-fit admission. It does not yet demonstrate nonzero native
holder selection or every layout. **Three-card selection is next**, using the same
reviewed policy with `--count 3`; its 96 completed checks/review remain applicable.
A fresh Profile 3 test run avoids re-obtaining the already owned Sea Glass relic;
enter a room from the map normally, run `ancient OROBAS SEA_GLASS`, close the console
and leave the option untouched. The same installed release remains active; cleanup
is pending after the batch. No profile/save/history/Cloud filesystem content was
accessed, and no uncertain mutation was retried.

### Sea Glass three-card selection passed

The user prepared a fresh Sea Glass option. Fresh exact running-process,
release/source/owned installation and authenticated health/manifest checks passed
on the unchanged fifteenth installation and release. The reviewed `--count 3`
policy selected slots **0 Twin Strike**, **1 Sword Boomerang**, **2 Tremble**, each
at upgrade level **0**, then Confirm and Proceed. `card_add_v2` resolved with
exactly those selected original cards; baseline deck and exact additions passed
native effect checks. Three `selected` receipts and one `committed` receipt were
reconciled in the child.

All **six actions reconciled**: parent attempted/accepted/reconciled 2/2/2, child
4/4/4, one completed card child, zero item children, 29 event reads. A fresh core
map read passed with two candidates. Policy time: **2.517 seconds**. Parent effects
remain `unverified`. This demonstrates partial selection and native card input on
the offered grid; it does not establish off-screen selection or every layout.
Result: `/private/tmp/sts-seaglass-three-live-20260909-result.json`, SHA-256
`b52252ae9b8d1a3ebeefac1f2df12724205784e69eafd0785f08ff785967ea53`.

Full **fifteen-card selection** is next using the same unchanged reviewed policy
with `--count 15`. Its 96 completed checks/review are reused. Prepare a fresh
Profile 3 run, enter a room from the map normally, run `ancient OROBAS SEA_GLASS`,
close the console and leave the relic option untouched. The same release remains
installed; cleanup is pending after the batch. No uncertain mutation was retried
and no profile/save/history/Cloud filesystem content was accessed.

### Sea Glass fifteen-card selection passed

The user prepared a fresh Sea Glass option on the unchanged release and fifteenth
installation. Fresh exact running-process, release/source/owned package and
authenticated health/manifest checks passed. The unchanged reviewed policy ran
with `--count 15`, selected every advertised slot **0 through 14** once, then
explicitly Confirmed and selected Proceed. All fifteen cards were unupgraded.
`card_add_v2` resolved with exactly those selected originals and fifteen selected
receipts followed by one committed Confirm receipt. Native effect checks preserved
the baseline and verified every appended card. Exact card keys are retained in the
bound result below.

All **18 actions reconciled**: parent attempted/accepted/reconciled **2/2/2** and
child **16/16/16**, one completed card child, zero item children, **125 event reads**.
A fresh core-map read passed with two candidates. Policy time: **9.617 seconds**.
Diagnostics remained parent-ready/child-ready/parent-ready/map-ready; parent effects
remain `unverified`. The test establishes a full selection on this allocated grid,
not universal layout/viewport coverage or grant provenance.
Result: `/private/tmp/sts-seaglass-fifteen-live-20260909-result.json`, SHA-256
`35f614c88241cf9c005b3745d3b88e3674a9e96542df79d8b1a2680e0a283aed`.

Sea Glass now has **zero, partial (three) and full (fifteen)** live acceptance.
The same bridge remains installed for the next family, **Tanx/Claws**, starting
with zero transformations. Cleanup remains pending after the live batch. No
uncertain mutation was retried and no profile/save/history/Cloud filesystem content
was accessed.

Claws policy `/private/tmp/sts-claws-live-20260909.py`, SHA-256
`f3017dddcefb463b45ca896b09ac748a6628027e8b4bf4b8677f7b42f5783750`, passed **105 frozen-view checks** and
independent semantic review with no blockers. It reuses the existing unified
client/source/state/authentication checks, generic event host and map verifier.
The exact parent key is `TANX.pages.INITIAL.options.CLAWS`, established by pinned
Tanx `RelicOption<Claws>(INITIAL)` metadata. It requires `card_transform_v3`, min
zero/max six, preview-confirm mode and a complete eligible domain sufficient for
the requested count. Counts zero/three/six are supported. Below six it sends one
explicit preview request; at six it requires the native preview. It confirms once,
requires exact selected-original identities and matching action reconciliation,
one completed child and a fresh map. Public result payloads do not expose replacement
names, so none are claimed by the policy. Native preview/task/effect checks remain
responsible for exact replacement verification.

**Zero transformations is the next live case**: explicit Preview then Confirm,
empty selected result and unchanged deck, with the native empty transform command
required by the implemented contract. Use a fresh Profile 3 run, normal map-room
entry, `ancient TANX CLAWS`, console closed and relic option untouched. The policy
has not yet run live. No source/build/install change is needed; current release
and installed state remain unchanged. Separate policy preparation/review times
were not measured.

### Claws zero-transformation passed

The user prepared Claws on the unchanged fifteenth installation and release.
Fresh exact running-process, release/source/owned installation and authenticated
health/manifest checks passed. The unchanged reviewed `--count 0` policy selected
`TANX.pages.INITIAL.options.CLAWS`, explicitly requested an **empty Preview**, then
**Confirm** and Proceed. `card_transform_v3` resolved with `operation: transform`,
empty selected originals and reconciled `previewed`/`committed` receipts. Native
completion verified the unchanged deck, empty request/selector results and required
single successful empty transform command. This is confirmation, not cancellation.

All **four actions reconciled**: parent attempted/accepted/reconciled **2/2/2**,
child **2/2/2**, one completed card child, zero item children, six event reads. A
fresh core-map read passed with three candidates. Policy time: **0.832 seconds**.
Diagnostics: parent-ready/child-ready/parent-ready/map-ready. Parent effects remain
`unverified`. No replacement-name claim is needed for the empty outcome.
Result: `/private/tmp/sts-claws-zero-live-20260909-result.json`, SHA-256
`843cd255bb5d26a654661061641ccdd0da36ba88abb052b775e1b2744b1a5e5c`.

**Three-card transformation** is next with the same reviewed policy and `--count 3`:
select three exact originals, explicitly preview below the native maximum of six,
confirm and verify native replacements and map return. Its 105 completed checks
and independent review are reused. Prepare a fresh Profile 3 run with at least
three eligible cards, normal map-room entry, `ancient TANX CLAWS`, console closed
and relic option untouched. The same release remains installed; cleanup is pending
after the batch. No uncertain mutation was retried and no profile/save/history/
Cloud filesystem content was accessed.

### Claws three-card transformation passed

The user prepared a fresh Claws option. Fresh exact running-process,
release/source/owned package and authenticated health/manifest checks passed on
the unchanged fifteenth installation. The unchanged reviewed `--count 3` policy
selected **unupgraded Strike originals at slots 0, 1 and 2**, explicitly requested
Preview below the maximum, Confirmed and selected Proceed. `card_transform_v3`
resolved with exactly those selected originals and selected/previewed/committed
history. Native preview, transformation journal and deck checks verified the
replacement effects. Replacement names are not exposed by this public payload,
so no particular output-card name is asserted from the result.

All **seven actions reconciled**: parent attempted/accepted/reconciled **2/2/2**,
child **5/5/5**, one completed card child, zero item children, 30 event reads.
A fresh core-map read passed with two candidates. Policy time: **2.637 seconds**.
Diagnostics: parent-ready/child-ready/parent-ready/map-ready. Parent effects remain
`unverified`. This demonstrates partial optional transformation with explicit
preview; it does not establish every deck size or preview layout.
Result: `/private/tmp/sts-claws-three-live-20260909-result.json`, SHA-256
`fc65a1237214fd69d03ad6e1b6f80ec58a4093032e73b595179a8384f011a710`.

The **six-card maximum** is next, using the unchanged reviewed policy with
`--count 6`. It selects six originals, requires automatic native preview at max,
then Confirms once and verifies completion/map. Its 105 completed checks and
independent review are reused. Prepare a fresh Profile 3 run with at least six
eligible cards, normal map-room entry, `ancient TANX CLAWS`, console closed and
relic option untouched. The same release remains installed; cleanup is pending
after the batch. No uncertain mutation was retried and no profile/save/history/
Cloud filesystem content was accessed.

### Claws six-card maximum passed

The user prepared a fresh Claws option on the unchanged fifteenth installation.
Fresh exact running-process, release/source/owned package and authenticated
health/manifest checks passed. The unchanged reviewed `--count 6` policy selected
**five unupgraded Strikes at slots 0–4 and one unupgraded Defend at slot 5**. The
native selector automatically opened preview at the maximum; **no explicit Preview
action was sent**. The policy then Confirmed once and selected Proceed.
`card_transform_v3` resolved with exactly those original identities. Native preview,
transformation journal and deck checks verified the replacement effects; public
payloads do not expose replacement names, and none are asserted from this result.

All **nine actions reconciled**: parent attempted/accepted/reconciled **2/2/2**,
child **7/7/7**, one completed card child, zero item children, 46 event reads.
A fresh core-map read passed with three candidates. Policy time: **3.808 seconds**.
Diagnostics: parent-ready/child-ready/parent-ready/map-ready. Parent effects remain
`unverified`. This demonstrates the maximum-count automatic-preview path on this
deck; it does not establish every deck size or layout.
Result: `/private/tmp/sts-claws-six-live-20260909-result.json`, SHA-256
`8a3c6e2f1014b26857095f64c6dc9c61e0da4db27f93a313f799881b76c90eb7`.

Claws now has **zero, partial (three), and full (six)** live acceptance. The next
family is **Neow/ScrollBoxes bundle selection**. The same release remains installed,
and cleanup is pending after the batch. No uncertain mutation was retried and no
profile/save/history/Cloud filesystem content was accessed.

Scroll Boxes policy `/private/tmp/sts-scrollboxes-live-20260909.py`, SHA-256
`e9abf4280bcfcc03877989a0b54276255973fb32f66bf22b341d24d7272ab147`, passed **89 frozen-view checks** and
independent semantic review with no blockers. It reuses the existing unified
source/state/authentication checks, client, event host and map verifier. Pinned
metadata supports exact `NEOW.pages.INITIAL.options.SCROLL_BOXES` and the native
bundle caller. The policy requires `bundle_offer_v1`, one to five offers and one
to eight cards per bundle, chooses bundle zero once, requires the same exact ordered
cards and selected index in native preview, then Confirms once. Completion requires
two reconciled child actions, one completed card child, exact chosen-bundle cards
in the resolved payload and a fresh actionable map. Native task/deck checks verify
all selected additions; no uncertain input is retried.

Prepare a fresh Profile 3 run, enter a room from the map normally, run
`ancient NEOW SCROLL_BOXES`, close the console and leave the relic option untouched.
The policy has not run live yet. No source/build/install change is needed; the
same accepted release and installation remain active. Separate policy preparation/
review times were not measured.

### Scroll Boxes bundle selection passed

The user prepared Scroll Boxes on the unchanged fifteenth installation and release.
Fresh exact running-process, release/source/owned package and authenticated
health/manifest checks passed. The unchanged reviewed policy selected
`NEOW.pages.INITIAL.options.SCROLL_BOXES`, then bundle zero of two three-card offers:
**unupgraded Havoc, Cinder and Feel No Pain**. It required the same exact ordered
cards in native preview, Confirmed once and selected Proceed. `bundle_offer_v1`
resolved with selected index zero and previewed/collected history. Native task/deck
checks verified all three additions.

All **four actions reconciled**: parent attempted/accepted/reconciled **2/2/2**,
child **2/2/2**, one completed card child, zero item children, six event reads.
A fresh core-map read passed with two candidates. Policy time: **0.841 seconds**.
The transient `pending_task_failed` diagnostic also appeared in this successful
run; it is not a terminal result (the earlier Hefty evidence explains its pending
placement). Parent effects remain `unverified`. This demonstrates one selected
three-card bundle, not every bundle size or alternative branch.
Result: `/private/tmp/sts-scrollboxes-live-20260909-result.json`, SHA-256
`419c84b7c370aa22b5d8513a85b55c6be2b784e9861af103a1667c92dff5f7fc`.

The next case is **Neow/LeadPaperweight optional single-card choice without an
extra grant**. The same
release remains installed; cleanup is pending after the batch. No uncertain mutation
was retried and no profile/save/history/Cloud filesystem content was accessed.

Lead Paperweight policy `/private/tmp/sts-leadpaperweight-live-20260909.py`, SHA-256
`3c013be775e7af2217c44ac0bc372ec561abd15a6038ec8f2bdadfc9db87a43d`, passed **35 frozen-view checks** and
independent semantic review with no remaining blockers. Review caught the initial
incorrect required-offer assumption before live input. Retained pinned metadata
`/private/tmp/sts-event-research-20260909/retained-il.json`, SHA-256
`87a8f2847f841403d7963c929e34bcef1eb24a8ec51c592c8db3881c942d8390`, shows
LeadPaperweight `AfterObtained.MoveNext` passing `canSkip=true` at IL123–124,
with its sole chosen-card `CardPileCmd.Add` at IL243 (null choice bypasses addition).
MassiveScroll also passes true at IL250–251. These callers therefore use
`card_offer_v2`; the current guides' v1 classification is corrected. The bounded
retained-caller inspection identified no required v1 caller. Original research
artifacts and accepted build evidence are unchanged.

The corrected policy requires exact `NEOW.pages.INITIAL.options.LEAD_PAPERWEIGHT`,
a v2 menu of one to three single-card offers with advertised Skip, chooses card
zero once, and requires that exact selected card, no additional cards, one
reconciled child action and a fresh actionable map. Native ownership/task/deck
checks remain in force. No Lead Paperweight live input has been sent.
Prepare a fresh Profile 3 run, enter a room from the map normally, run
`ancient NEOW LEAD_PAPERWEIGHT`, close the console and leave the relic option
untouched. No source/build/install change is needed. Separate policy preparation/
review times were not measured.

### Lead Paperweight choice passed

The user prepared Lead Paperweight on the unchanged fifteenth installation and
release. Fresh exact running-process, release/source/owned package and authenticated
health/manifest checks passed. The unchanged reviewed policy selected
`NEOW.pages.INITIAL.options.LEAD_PAPERWEIGHT`, then the first of two offered cards:
**unupgraded Dramatic Entrance** (the other offer was Jack of All Trades). It then
selected Proceed. `card_offer_v2` resolved with selected index zero, the exact
chosen card, an empty `additional_cards` list and one collected receipt. Native
task/deck checks verified the sole chosen-card addition.

All **three actions reconciled**: parent attempted/accepted/reconciled **2/2/2**,
child **1/1/1**, one completed card child, zero item children, ten event reads.
A fresh core-map read passed with three candidates. Policy time: **1.054 seconds**.
The previously explained transient `pending_task_failed` diagnostic appeared;
no terminal failure occurred. Parent effects remain `unverified`.
Result: `/private/tmp/sts-leadpaperweight-live-20260909-result.json`, SHA-256
`f7ce7cca140938176d5773dba560e5618466eab11772507a1ba342fef89f31f7`.

The next case is **Lead Paperweight Skip without an additional grant**. The same
release remains installed; cleanup is pending after the batch. No uncertain mutation
was retried and no profile/save/history/Cloud filesystem content was accessed.

Skip policy `/private/tmp/sts-leadpaperweight-skip-live-20260909.py`, SHA-256
`9e40218fafff0d5bf5df4fe9a49fe7f09dedc62684589602cedb81d87f6ee016`, passed **35 frozen-view checks** and
independent semantic review with no blockers. It retains the reviewed exact parent
and v2 menu admission, sends Skip once and requires a null selected index, empty
additional cards, a single skipped result, one reconciled child action and a fresh
map. Native completion requires empty selector/null request results, successful
tasks, overlay closure and unchanged deck identity/order/metadata from child
admission. Parent effects remain unverified.
Prepare a fresh Profile 3 run, enter a room from the map normally, run
`ancient NEOW LEAD_PAPERWEIGHT`, close the console and leave the relic option
untouched. This Skip policy has not run live. No source/build/install change is
needed. Separate policy preparation/review times were not measured.

### Lead Paperweight Skip admission stopped (2026-09-10)

Fresh exact running-process and the unchanged reviewed policy hash passed, as did
release/source/owned installation and authenticated health/manifest checks. The
first event read returned `unsupported_state` with diagnostic `parent_unavailable`.
**Zero parent or child actions were attempted, accepted or reconciled**; no child
was admitted and map handoff was not attempted. Effects are `none_attempted`.
Policy time: **0.561 seconds**. The user confirmed the relic option is visible.

The diagnostic covers multiple parent admission checks (world/map/overlay,
layout and binding identity); it does not identify which prerequisite failed.
This is not the earlier `invalid_response` startup failure and does not exercise
Skip or its deck outcome. No retry or source/build change was made. The fifteenth
installation remains active; setup context is being clarified and cleanup is
pending. No profile/save/history/Cloud filesystem content was accessed.
Result: `/private/tmp/sts-leadpaperweight-skip-live-20260910-result.json`, SHA-256
`3b9ae96533b9d40e03ba6005045b82c5dafe92d5be8403bb341bce0748916a89`.

The user subsequently confirmed they had forgotten to start a fresh run and will
correct the setup. This establishes the setup mismatch, not the exact native
predicate behind the diagnostic. The same reviewed Skip policy and unchanged
release will be used only after fresh readiness; no mutation was sent in this
stopped attempt.

### Corrected-setup attempt found listener unavailable

After the user requested another attempt, fresh running-process and unchanged
policy hash checks passed. The same policy verified release/source/installed state
but hit `ConnectionRefusedError` before obtaining a bridge response. No decisions,
native diagnostics or live actions were recorded. Time: **0.035 seconds**.
The running game therefore did not have an accepting bridge listener at the
connection attempt; this did not exercise the corrected event setup or Skip.
Normal quit was requested so stopped state can be verified before a same-build
relaunch. No rebuild, source edit or uncertain mutation retry was performed.
The fifteenth installation remains installed; cleanup is pending.
Result: `/private/tmp/sts-leadpaperweight-skip-fresh-live-20260910-result.json`, SHA-256
`827b4da42b78a4d61aa09425260f2f1b8311f129a5af9eb34f135c28db0063bf`.

The user confirmed normal quit. `require-stopped` passed with **three stopped-process
samples and two closed-port samples**. The same accepted package and installed
state are retained for relaunch; this is not removal/cleanup. Prepare a fresh
Profile 3 run after manual relaunch, enter a room normally from the map, run
`ancient NEOW LEAD_PAPERWEIGHT`, close the console and leave the relic option
untouched. The unchanged reviewed Skip policy remains ready.

### Lead Paperweight Skip passed after relaunch (2026-09-10)

After manual relaunch and fresh user setup, the exact running-process check and
unchanged reviewed policy hash passed. Release/source/owned installation and
authenticated health/manifest checks passed on the unchanged fifteenth installation.
The policy selected Lead Paperweight, Skipped the Dark Shackles/Prolong menu, then
selected Proceed. `card_offer_v2` resolved with null selected index, no additional
cards and one skipped receipt. Native selector/request/task and retained deck
checks verified the unchanged deck from child admission.

All **three actions reconciled**: parent attempted/accepted/reconciled **2/2/2**,
child **1/1/1**, one completed card child, zero item children and eleven event reads.
One fresh core-map read passed with three candidates. Policy time: **1.443 seconds**.
The previously explained transient `pending_task_failed` diagnostic appeared;
no terminal failure occurred. Parent effects remain `unverified`. Lead Paperweight
now has choose and Skip live acceptance without an extra grant. The earlier
zero-action admission and connection failures remain recorded above.
Result: `/private/tmp/sts-leadpaperweight-skip-relaunch-live-20260910-result.json`, SHA-256
`c8511f8a491d344323ee6729fed11c76a5ba1565bee39ad92c6404d4512ccc27`.

The same accepted package remains installed for Lost Coffer's mixed card/potion
reward case. Cleanup remains pending after the batch. No uncertain mutation was
retried and no profile/save/history/Cloud filesystem content was accessed.

Lost Coffer policy `/private/tmp/sts-lostcoffer-live-20260910.py`, SHA-256
`df424ceea970c1c0b31beb9b7527b28022d9d035109e6dd5302aee23c8997f3b`, passed **37 frozen-view checks** and
independent semantic review with no blockers. Pinned metadata confirms exact
`NEOW.pages.INITIAL.options.LOST_COFFER` and ordered three-card CardReward (IL66),
PotionReward (IL83), then OfferCustom (IL100). The policy requires
`mixed_reward_set_v1` with exactly card then potion, opens the card menu, chooses
slot zero once, collects the potion once, and requires exact typed settlements,
three reconciled child actions, one completed mixed child and a fresh map. Native
admission checks potion capacity and retains card/potion/task ownership throughout.

Prepare a fresh Profile 3 run with **at least one free potion slot**, enter a room
normally from the map, run `ancient NEOW LOST_COFFER`, close the console and leave
the relic option untouched. The policy has not run live yet. No source/build/install
change is needed; separate policy preparation/review times were not measured.
