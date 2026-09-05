# Room Release V1 acceptance

Date: 2026-09-05. Selected checkout: 23cf, branch
codex/phase1-actor-ready-integration, predecessor commit
4085d2fc44e4470ff0aaa1c2efdd8e39c0b3ee0a.
The [release contract](../PHASE_1_ROOM_RELEASE_V1_CONTRACT.md) and frozen
[functional packet](PHASE_1_ROOM_FLOWS_V1_ACCEPTANCE.md) bind this release.

## Accepted implementation and reviews

The combined runtime, secure operator/bootstrap, native factory, strict Python
transport/client, whole-assembly verifier, canonical package and transactional
campaign tools are implemented and independently accepted. Agent A owned
runtime/tests; B owned operator, lifecycle, native composition and their tests;
R implemented the coordinator-delegated verifier/policy/mutations. The coordinator
owned transport/client, package, operations, aggregate checker and shared docs.
A, B and R cross-reviewed the other lanes; the coordinator reviewed integration.
No model escalation was requested in this release wave.

Production is one explicitly linked Sts2AgentBridgeRoomFlowsV1 1.0.0 DLL.
Protected configuration selects shop or event once and binds the same immutable
selection and exact configuration hash into campaign state. Transport settlement,
owner-frame service disposal and Godot detachment are separate obligations.
No off-thread shutdown reports native disposal as completed. Credential/config
arrays are zeroed even when startup rejects before transferring ownership.

The actual synthetic socket composition caught a rate-limit rejection during an
event plus item child sequence. The new runtime admits burst 16 at 20 requests
per second; the client also spaces parent and child starts by at least 50 ms
within the existing deadlines. A wrong-route terminal classification was tightened
to exact GET/POST status tables. These fixture findings are separate from the
historical room_interaction_timeout; no discarded live response was reconstructed
and no uncertain live action was retried.

## Final aggregate evidence

Both fresh physical gates passed: coordinator
/private/tmp/room-release-final-check-b and independent reviewer
/private/tmp/room-release-independent-final-c. Their complete sanitized
[result files](PHASE_1_ROOM_RELEASE_V1_OFFLINE_RESULT.json) are byte-identical.
Each gate copies verified sources, runs the actual fixtures and builds the
production candidate twice from independent paths; all four DLLs are identical.
The original 51-input manifest at b7fc404 matched these gates; the later
operational correction and replacement freeze are recorded below.

| Gate | Passed evidence |
| --- | --- |
| Secure operator and bootstrap | 5 and 12 fixture groups |
| Runtime and actual C# runtime/Python/frozen-host sockets | 1254 and 87 checks |
| Build-project boundary | 15 mutations/checks; no candidate execution |
| Python transport and installed-state client | 8 and 13 groups |
| Campaign manager and runtime operations | 39 and 17 groups, both selected flows and cleanup faults |
| Whole-assembly verifier | 931 method bodies, 35 verifier checks, 10 shipping CLI negative cases |
| Canonical package | 5 groups containing 9 mutation cases |
| Frozen functional rechecks | broker 575, shop 13, event 36, wire 16, cross-language 192 |

The policy pins 37 production sources, 6938 inventory rows, 931 method bodies
and 13 read-only Darwin imports. It checks source, metadata, IL, exact routes,
initializer binding and exclusions. The shipping verifier cannot extract a
replacement policy. Real PE mutations exercise the relevant denials.
The equivalent compact JSON policy fits the unchanged 1 MiB source limit;
no predecessor checker limit was loosened. The aggregate operator invocation
was corrected to pass its required absent synthetic home directly under
/private/tmp; that fixture creates and removes the home. Earlier failed gate
attempts produced no accepted result or live activity.

The checker verifies all six frozen successor inventories and all 48 old bridge
inputs byte-exact. It executes pure fixtures only; the production candidate,
Godot and game assemblies are never executed. Native references are pinned
sts2.dll and GodotSharp.dll from the selected build. The final Python sources
also pass syntax parsing. No game/ or tests/ source changed; prior committed
regression coverage remains all 1155 tests (1154 sandbox plus the unchanged
single ephemeral-loopback fixture passing with authorized socket access).

## Frozen identities

| Input or artifact | SHA256 |
| --- | --- |
| Contract | f5c0f76a302b78ae30994a96288dd9a70310af908dd63dfc1cef0cf7e566df21 |
| Source manifest, 51 inputs | 20460d277797a5d1e3663729209b601f9ed9565298c51676bde520a7fceac82d |
| Source inventory | f22933487b581a3e0e06ca364d71b0ef3ca5b892f1b50824f08b9a983d68b6b5 |
| Aggregate checker | 8c8baffeb8b359e8f95612499c54dd2c9f2c619a55ed853db75e0f4544c5b28e |
| Both result JSON files | d3f38436462587f1e5d87f5ddc4afe232034ad8a9e3719f78b7e1d193c2baf85 |
| Compact policy, 1040076 bytes | 6cde6aac22dd7a8e73416da9b75209ba44bb18d8c9be1e5d92e1d6b4d32af81f |
| Production source projection | b042b1a91852dd35533df5d7818a0dfd57b7dc857e461df3b9bc5a9136e35a09 |
| Production metadata projection | e34f6970dbd85f1ca370404d7f7390d4b1ad9b7af323b295de8102152c091d7a |
| DLL, 177152 bytes | 60db75fa1c50c46bc2a6426b269a9aa5aebca9211a136de79f801ec1cdfa5a6f |
| Manifest, 344 bytes | 9b361b08e3e99de5322d24811c24497c37662ded1c9e5623a2b4e9cc9ab38812 |
| ZIP, 177900 bytes | ee030cad1bb019b1793f04a6faaf94caa65b821d4c349fecd83ba668f61c4819 |

The coordinator exclusively published and reread all three pinned artifacts at
/private/tmp/sts-room-flows-v1-release after aggregate acceptance. The ZIP has
exactly the DLL and manifest under Sts2AgentBridgeRoomFlowsV1/. No old artifact
or frozen source was modified.

## Live boundary and prepared first campaign

Release acceptance is complete; live shop/event acceptance is still pending.
Standing user authorization covers one bounded campaign at a time, including
installation and normal cleanup. The user confirmed availability with the game
closed. Fresh read-only preflight passed game stopped/port closed (3 process,
2 port samples) and the pinned 429-file base with zero overlay. A fresh conflict
absence and stopped/closed check immediately precede installation.

First select shop, install only while closed, then request Profile 3 and the
continued Ironclad Ascension 0 run at a fresh shop with merchant inventory open
and at least one affordable ordinary card visible. The user must leave purchase,
close and leave untouched. Verify that exact supported screen before invoking
the fixed client once with the installed state hash. Its bounded intended
sequence is one affordable ordinary-card purchase, inventory close and room
leave. No retries or adoption follow uncertainty. The campaign has a 30-minute
outer bound from installation, including cleanup. A later event test uses a
separate clean installation selecting event and a fresh event with untouched
choice buttons, never the historical uncertain event.

After a campaign: normal game quit, stopped/closed, code-first quarantine,
exact four-file purge and final 429-file/zero-overlay/absence checks. The repeated
unmodded game relaunch is user-waived, not claimed as passed. If setup cannot be
completed within the bound, stop and clean up without sending an action.
Record any live invocation and cleanup in a dated subsection below; the offline
result is not live evidence. No campaign had started at this release acceptance.

Steam capture was tested through supported computer use in this fresh session
and still failed with ScreenCaptureKit -3811. This remains separate from the
controller timeout and fixture findings. No profile/save filesystem access,
Cloud change, retained live corpus, remote Git operation or broader capability
change occurred. Shop relic/potion/removal/restock and rest-site upgrades remain
unsupported; existing rest healing evidence is unchanged.

## Prelaunch shop installation closed — 2026-09-05 21:47:07 UTC

Release commit b7fc404 passed fresh stopped/closed, base 429/zero-overlay and
seven fixed conflict-absence checks. Installation selecting shop passed at
21:45:24 UTC with state SHA256
66983dd0a323b84d36ef417bc5a0f5bb1444f9b488064bf2449d4bc51e055ab3.
The read-only post-install overlay check stopped with manifest_not_canonical.
The copied operations/tool_common.py still expected the old item release name
and description, although the accepted package and manager pinned the correct
room release bytes. This exposed a missing aggregate test of the actual overlay
checker. The game was never launched; no live client or game action was
attempted. This is an operational validation defect, not a gameplay result.

The coordinator kept the game closed, reconfirmed stopped/closed, quarantined
code first with state SHA256
95e4fddb578499a432788dd59b0739e285e0f1d9eb1cc6d4c0a7739d5be24622,
and purged exactly four generated files. Final checks passed unchanged base 429,
zero overlay, stopped/closed (3 process and 2 port samples) and seven fixed
absence checks by 21:47:07 UTC. No campaign remains active. No unmodded relaunch
was needed; that check remains waived. Neither historical state may be reused.

The bounded correction aligns only those two manifest literals to the unchanged
canonical package and adds actual synthetic base/overlay checker coverage.
The production DLL, manifest, ZIP, policy, gameplay/runtime behavior, release
contract and all six predecessor trees remain unchanged. Replacement source
acceptance must pass before another installation or live setup request.

## Operational correction accepted — 2026-09-05

B implemented the two-literal correction and a new seven-check fixture. R and
the coordinator independently accepted the diff. The fixture binds the actual
accepted DLL through package.canonical_files, requires the exact public manifest,
and executes the real clean-install operation against disposable base and
overlay trees. It rejects package-manifest, installed-overlay, base-projection
and target-manifest mutations. No real installation is touched by these tests.

The corrected aggregate runs this fixture after the fresh candidate/package.
Coordinator /private/tmp/room-release-corrected-check-a and independent
/private/tmp/room-release-corrected-independent-a both passed; their exact
[corrected result JSON](PHASE_1_ROOM_RELEASE_V1_CORRECTED_OFFLINE_RESULT.json)
is byte-identical. All previous counts remain unchanged, with clean_install 7
added. Both production builds in each run reproduce the unchanged DLL. No
candidate or target assembly was executed. No additional full regression was
necessary for these operational-only changes.

This replaces only the new room_release_v1 source freeze from b7fc404. All six
predecessors, release contract, runtime/production source projection, verifier
policy, DLL, manifest and ZIP retain their recorded identities. The existing
published package was read-only verified; it was not republished or modified.

| Corrected source identity | SHA256 |
| --- | --- |
| Source manifest, 52 inputs | d567c8e91e45fd2bcff2cd446f85d3d7faef3baf2b22b6f7b75ba2490d360957 |
| Source inventory | 1fde216af25f0a94c16e13b869216d7990c862d7ba19d2246060e1f36bfabf4b |
| Aggregate checker | abf81f9b968f3eb1f68e41ffbb3479a0a07d7a98251fe1250f440adf53dd194d |
| Corrected common operations | ff1a284ae1f2e5d84e89ee50dfaed970b903a64d9cf79d03b597401c0ae83fa3 |
| New actual installation-check fixture | 1f23875a68a913b82fbedac30db9d75c4ebe7c39d3e8e3fd8dcaedab1a31bff7 |
| Both corrected result JSON files | d164ef8a3232f7488269adf11a51533c3c440fedb25d5b416e982f089ad12cb0 |

Fresh real base verification still passes 429 files/zero overlay, and the game
remains stopped with the port closed. Release readiness is restored; live shop
and event behavior remains untested by this release. The next installation uses
fresh state/credentials under the user's standing authority and availability.
