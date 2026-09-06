# Event card operations v1

This functional component adds exact event card-operation bindings to the shared
event controller. Independent source review and the candidate offline aggregate
pass, including actual native/controller composition and two matching production
builds. The living ledger records the final source-freeze disposition. There is
no installable release or live campaign for this component.

The accepted structural contract is
[`PHASE_1_EVENT_CARD_OPERATIONS_V1_CONTRACT.md`](../../../../docs/PHASE_1_EVENT_CARD_OPERATIONS_V1_CONTRACT.md).
The [living acceptance ledger](../../../../docs/research/PHASE_1_EVENT_CARD_OPERATIONS_V1_ACCEPTANCE.md)
records exact source checkpoints, static evidence and remaining gates.

## Flow

The event parent binds a closed policy and expected candidate count before
choosing a supported card option. The actual frozen card-selection controller
then selects the required number of cards, handles preview/confirmation, checks
the exact returned cards and deck effect, and returns control to the same event.
A supported card option cannot resume as an ordinary option transition without
completing its child. Known unsupported card options are observed but never legal.

The public parent version is `event_card_operations_v1`, with routes:

- `GET /probe/event-card-operations-v1/public/decision`
- `POST /probe/event-card-operations-v1/public/action`

The candidate's `child_domain_count` is part of structural and decision identity.
The existing child payload versions remain unchanged. Limits remain 12 parent
actions, four child episodes, 52 total actions, 2,048 reads and one 30-second
budget across the entire event. An uncertain action is never retried.

## Evidence boundaries

The closed production catalog contains three exact rows:

- Room Full of Cheese/Gorge: the preserved add-two-of-eight path.
- Aroma of Chaos/Maintain Control: upgrade one from 2..64 eligible originals.
- Sapphire Seed/Eat: upgrade one from 2..64 eligible originals after its healing step.

Both new upgrade rows retain the complete deck and eligible original cards
before choosing the event option. Selection and confirmation must return the
reserved original; the exact upgrade effect and the same event's finished state
must be visible before parent continuation. Replaced screens, changed keys,
stale domains and unrelated deck changes stop without another action.

Synthetic descriptors exercise add-three, remove-two, upgrade-two and
transform-two without enabling additional game callers. Ordinary Smith remains
its separately accepted exactly-one rest-site upgrade path. Brain Leech,
Zen Weaver, transformations and multiple-card native upgrades remain open.
Shared multi-card support does not prove an arbitrary event's eligibility rules,
selector controls or completion.

The aggregate verifies the exact project and authority inventory, 19 suite
summaries, actual C# service-to-Python integration, and two matching native builds
against the pinned game references. Target assemblies are never executed by
offline checks. The separate derivation gate verifies explicit changes from
frozen predecessors; all thirteen accepted components and the original bridge
remain byte-exact. Functional acceptance does not provide release packaging or
live evidence.
