# Generic event release v6

Installable composition of the frozen generic_event_v6 engine: generic card
upgrade/removal/addition, fixed multi-upgrade, transformation and singleton direct
potion/relic rewards. Gameplay source files and their frozen child engines are
linked unchanged. Eighteen owned native hooks connect the original event request,
UI selection, asynchronous completion and verified child effect. Event names do
not determine handler admission.

The release adds protected operator configuration, authenticated loopback transport
on127.0.0.1:43117 and Godot owner-frame execution. Routes use generic-event-v6;
child requests retain complete parent correlation. Item and transformation child
completion returns to the parent; explicit Proceed/map handoff ends the run.
Uncertain POSTs are never retried. Failed hook installation and cleanup retain
owner-frame ownership until cleanup succeeds, after transport stops.

The source-linked releasev5 diagnostic enum and codec retain all78 values. The
header describes the last native parent capture; it is not a precise diagnostic
for every item or transform continuation failure. The sanitized host result keeps
completed_card_children and completed_item_children across later Proceed/failure.
Its effects field describes only the latest parent action.

Production uses only the exact pinned game-owned Harmony library. Build/path,
hash,MVID,assembly identity and load context checks precede native construction.
Offline tests execute inert target stubs, never sts2.dll,GodotSharp.dll or the
production bridge assembly. All26 previous successor components remain frozen.

See the [contract](../../../../docs/PHASE_1_GENERIC_EVENT_RELEASE_V6_CONTRACT.md)
and [acceptance ledger](../../../../docs/research/PHASE_1_GENERIC_EVENT_RELEASE_V6_ACCEPTANCE.md)
for current evidence, identities and live disposition.

## Offline gate

Run Python3.10+ and SDK9.0.303, using a nonexistent scratch directory:

```sh
python -B bridge/Sts2AgentBridge/successors/generic_event_release_v6/check.py \
  --dotnet /absolute/path/to/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-generic-release-v6-gate
```

The gate validates frozen/source closure, complete G6 regressions, release
bootstrap/native/runtime/socket/client tests, metadata/IL policy, verifier
mutations, canonical packaging and transactional operations. Production must be
byte-identical across two fresh builds. It installs and downloads nothing.

## Bounded live test

Do not launch until offline acceptance, fresh stopped/closed/clean-base checks
and installation finish. The initial campaign is GENERIC-EVENT-V6-SMOKE-V1,
artifact root/private/tmp/sts-generic-event-v6-release, operator leaf
generic_event_v6, overlay Sts2AgentBridgeGenericEventV6.

Manual setup: Profile3,single-player,fresh Room Full of Cheese initial options.
Keep HP above Search's displayed damage cost and leave a potion slot empty. Leave
both choices untouched and close the console,selectors and other popups. The
fixed campaign policy requires two initial options and legal choose:1 (Search),
then chooses the first legal child/later-parent action. It does not adopt an open
reward screen. Search is a candidate for singleton relic testing; its actual
request shape and generic compatibility are not asserted before the live result.

Exactly one client invocation:
`client/run_live.py --expected-state-sha256 <fresh-installed-state-sha256>`.
It validates source, package, installed state and protected metadata before one
credential transfer. Output contains fixed summary counts and finite diagnostic,
never credentials or raw observations. Afterward quit normally and complete
stopped/closed,code-first quarantine,exact owned purge and clean-base checks.
No profile/save filesystem or Steam Cloud changes are included.
