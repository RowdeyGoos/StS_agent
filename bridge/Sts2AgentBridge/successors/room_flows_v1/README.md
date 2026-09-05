# Room Flows V1 functional packet

This successor implements bounded shop and event control independently of the
unchanged 0.8.0 bridge and five frozen item components. It currently has no live
listener, bootstrap, installable package or game-launch command.

- Shop: enter an already-open ordinary inventory, buy zero or one supported
  affordable card, close inventory, then leave through a verified map handoff.
  Potion/relic purchases, removal and restock purchase remain unsupported.
- Event: expose bounded current option text, reserve stable option keys,
  continue only after a structural change, optionally collect one reward
  through the actual frozen item service, then explicitly exit through Proceed.
  Ordinary option effects are not reported as reconciled.
- Rest-site upgrades are outside this packet. The accepted old rest path
  supports healing and map return.

Common interfaces and the real item broker are shared. The wire exposes one
selected parent flow and gates the existing item routes to its active child.
The Python host uses one 30-second outer deadline and exact action/result
correlation. Responses and event text are transient; summaries contain fixed
codes and validated counts.

## Offline verification

The checker requires Python 3.10+, offline SDK 9.0.303, the exact pinned game
reference directory and a new direct child of /private/tmp. Pass the SHA256 of
docs/PHASE_1_ROOM_FLOWS_V1_CONTRACT.md as --contract-sha256.

Arguments: --dotnet ABSOLUTE_SDK_PATH --game-data-dir ABSOLUTE_PINNED_REFERENCE_DIR
--scratch /private/tmp/NEW_DIRECTORY --contract-sha256 EXACT_CONTRACT_SHA256.

It verifies the frozen source manifests and all 48 old bridge inputs, snapshots
the exact sources, builds/runs only pure fixture assemblies and the real
C#-to-Python integration, then compiles both native adapters without executing
them. It does not read operator files or contact a game endpoint.

The implementation plan, functional contract, sanitized static result and
acceptance ledger are under docs/PHASE_1_SHOP_EVENT_IMPLEMENTATION_PLAN.md,
docs/PHASE_1_ROOM_FLOWS_V1_CONTRACT.md,
docs/research/PHASE_1_SHOP_EVENT_STATIC_RESULT.md and
docs/research/PHASE_1_ROOM_FLOWS_V1_ACCEPTANCE.md.
