# Current unified release

This directory binds the broader native `agent_v2` package to its source and
validation. [Current status](../../../../docs/STATUS.md#release-and-latest-evidence)
owns live support; [bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, review intervals, installation and live status |

Manifest SHA-256: `32d721e8f6f680d6fc0eeccfe90eeb5926dcbe17ac605cab43b89b36561ec314`.
It binds **461 inputs across 52 projects**, source `6c04327`, feature `cc9fa81`.
DLL: **1,682,432 bytes**, SHA-256
`470e6b75f5d57ceefa706c86ca62e5ad264de203f8b3300a3f183c6ffcac3fc8`.

The final release gate passed **85 groups in 319.717 seconds**, including
reproducible builds, native metadata/dependency checks, packaging and disposable
installation/cleanup. It includes **168 client tests**, **1,628 router checks**,
**13,930 native event checks**, **656 rest checks**, **252 campaign checks** and
**179 potion checks**. Independent semantic review passed after corrections;
measured review intervals and focused checks are retained in `validation.json`.
The broad Python suite completed in **1,872.05 seconds**: **8,181 passed**, two
initial failures and two existing Gymnasium warnings. The sandbox socket case
passed outside the sandbox; the outdated release fixture passed after correction.
Both affected suites also passed in the final release gate. The original broad
result and focused reruns remain recorded separately.

The package adds hand/optional combat selections, native potion use/discard and
potion-owned selectors, chest claiming and empty-chest completion, reward
reroll/sacrifice and certified automatic relic effects, shop removal cancellation,
Cauldron/Orrery reward decisions, shared event reward children, and opt-in public
live recording. Parent completion waits for exact native tasks, individual child
receipts and successful cleanup. Legacy versioned controllers retain their scope.

The [bounded live batch](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md)
passed reroll, map potion use/discard, chest claiming, potion-owned hand/optional
offers and the first Sacrifice. Whetstone on the second Sacrifice failed
reconciliation at **36/36/35** actions. No mutation was retried. Normal quit and
exact four-file cleanup finished by **14:09:44 UTC**, with **429 unchanged base
files and zero overlays**. No profile/save/history/Cloud filesystem content was
accessed and no live trajectory corpus was collected. A narrow observer correction
is validated locally; this manifest does not contain that correction.

The [native candidate boundary](../../../../docs/AGENT_CONTRACT.md#native-full-run-v2-candidate)
remains explicit. Neow's Bones needs a compound relic-pickup/curse continuation;
the full producer rejects its actionable parent before input. Arbitrary nested
pickup callbacks and complete native campaign acceptance are not established.

The previous manifest `812c148b…`, source `53e2255`, passed the shared-policy
rest/card-reward/map path on 2026-09-25: **4/4/4 actions**, 27 reads, no pending
action, HP **45/83 → 69/83**, deck **6 → 7**, gold unchanged at 399, and
`truncated/external_stop` at the map. Normal quit and exact four-file cleanup
finished by **11:02:21 UTC**, with 429 unchanged base files and zero overlays.
Its original record is preserved in Git `8a75686` and in the evidence directory;
that live result is not repinned to this package.

Current evidence and the preserved previous package/record are under
`/private/tmp/sts-bridge-d2n3wh6m`. Current install inputs are at
`/private/tmp/sts-unified-bridge-release`.
