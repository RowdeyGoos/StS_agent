# Room release v1

One installable release for the frozen room_flows_v1 shop and event modules.
Production assembly: Sts2AgentBridgeRoomFlowsV1, version 1.0.0. The event module
uses the real frozen item collector for one causally bound item reward.

The supported shop sequence is one affordable ordinary-card purchase (or no
purchase when none is available), inventory close, then room leave. Relics,
potions, card removal, restocking and other shop services remain unsupported.
The event sequence selects eligible ordinary options, observes continuation,
optionally collects one supported event item reward, and reconciles the final
PROCEED map handoff. Card-selection overlays and other unimplemented event
results fail closed. Rest-site card upgrading is outside this release.

## Build and acceptance

Follow docs/PHASE_1_ROOM_RELEASE_V1_CONTRACT.md and the release acceptance
ledger. check.py accepts only --dotnet, --game-data-dir and a new --scratch
directory directly under /private/tmp. It verifies all six frozen predecessor
inventories and old 48-source projection, copies verified sources and two pinned
compile references to new physical snapshots, runs pure fixtures, builds the
candidate twice, requires identical bytes, runs the metadata-only verifier and
mutations, and validates the canonical package. The candidate and game
assemblies are never executed by the offline gate. No installation or live
connection is performed by check.py.

The shipping verifier accepts only --assembly, --source-root and --policy.
Only the separate verifier test harness can extract a candidate policy; release
policy identity is frozen before acceptance. Production contains no test-only
endpoint or operator seam.

## Live operation

The installed protected configuration selects exactly shop or event for one
activation. The fixed operator directory is
~/Library/Application Support/Sts2AgentBridge/room_flows_v1. The endpoint remains
127.0.0.1:43117 with one fresh credential, one session nonce and one active
exchange. Parent bodies are capped at 65536 bytes; event item bodies at 4096.
The client spaces request starts by at least 50 ms within the frozen 30-second
controller deadline. No uncertain action is retried.

Use operations/manage_live_campaign.py with the fixed campaign and artifact
identities. Install alone adds --flow-kind shop|event; quarantine and purge use
the latest --expected-state-sha256. The client accepts only that state hash and
derives its flow from the validated installation. Never choose a flow by
inspecting the current screen. Existing operator, predecessor overlay or
campaign units are rejected and preserved.

For a shop test, install while the game is closed, then manually enter Profile 3
and navigate to a fresh shop. Open the merchant inventory and stop with at least
one affordable ordinary card visible. Do not buy, close or leave. For an event
test, install the event selection while closed, then stop at a fresh question-mark
event with untouched choice buttons visible. A combat, chest or already-resolved
event is not the requested setup. The coordinator verifies the exact screen
before invoking the one-shot client.

After a campaign: quit through supported UI, verify stopped/closed, quarantine
the code before the operator unit, purge only the exact generated entries, and
verify the pinned base installation. The user has waived repeated unmodded game
relaunches. No profile/save filesystem reads, Steam Cloud changes, retained live
corpus, remote Git operations or unrelated capability changes are authorized.
