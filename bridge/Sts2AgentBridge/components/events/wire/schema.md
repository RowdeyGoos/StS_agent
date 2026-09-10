# Generic event v8 wire

GET `/probe/generic-event-v7/public/decision` has no body. POST
`/probe/generic-event-v7/public/action` is a canonical UTF-8 JSON object with
ordered keys `decision_id`, `action_id`, `child`; the latter is null for parent
choices or exactly `ordinal`, `parent_decision_id`, `parent_action_id` for a child.
Actions are the advertised `choose:0..7` or frozen card actions / `collect:i` item actions. No request can
supply operation, preferences, candidates or native identities.

Every response has ordered keys `schema_version` (1), `protocol`
(`generic_event_v8`), `session_nonce` (32 lowercase hex), `kind`, `parent`,
`child`, `payload`. Decision IDs are64 lowercase hex. Duplicate/unknown keys,
wrong types, nonmatching publication or lineage, reused decisions and malformed
requests invalidate the session before further dispatch. Responses are bounded
to65536 bytes, requests4096, JSON depth12 (requests4).

A `decision` response's parent has ordered fields:

- `status`, `phase`, `decision_id`, `candidates`, `legal_actions`, `prior_results`;
- `parent_attempted`, `parent_accepted`, `parent_reconciled`, `child_episodes`;
- `child_attempted`, `child_accepted`, `child_reconciled`, `total_attempted`, `effects`, `completed_card_children`, `completed_item_children`.

Candidates contain `index`, `action_id`, `stable_id`, `rendered_text`, `enabled`,
`is_dangerous`, `is_proceed`, `discovery`. Discovery is `deferred` for an ordinary
choice and `none` for Proceed. Counts are monotonic; parent history is an immutable
prefix of matching accepted receipts, with `option_transition`, `child_completed`
or `map_handoff` / `combat_handoff` results. Ordinary transitions do not certify HP/gold effects.

The routes retain their v7 names; the response protocol and parent receipt version
are v8. A complete parent has phase `map_handoff` after an accepted Proceed, or
`combat_handoff` after an accepted non-Proceed choice without a child. Its final
history row must match that phase and the latest accepted parent receipt, with
all parent actions reconciled. Combat entry certifies only the exact in-progress
non-resuming combat requested by that choice, not victory. Event-supplied extra
rewards and resumed event callbacks are unsupported. The unified core retains
combat ownership until that same combat has a terminal observation.

`stable_id` is a public option key, not a session-wide action reservation. It can
reappear on a later page, including with identical text. A settled page with fresh
native controls receives a fresh decision after the preceding accepted choice
reconciles. Reused decisions remain forbidden. The bundled host reserves decisions
rather than option keys; older hosts may reject these newly admitted repeat pages.

An admitted child begins with `ordinal`, `parent_decision_id`, `parent_action_id`,
`kind`, `contract_version`. Card descriptors (`kind: card_selection`) continue with
`operation`, `min_select`, `max_select`, `commit_mode`, `domain_count`. Item
descriptors (`kind: item`, `contract_version: item_v1`) continue only with
`offer_count`, exactly1. Child ordinal1..4 is shared across both kinds. Requests
supply correlation only; clients cannot choose the family or native semantics.

Card families retain upgrade/transform1<=min=max<=8 with preview_confirm,
remove1<=min<=max<=8 with preview_confirm, or add1<=min<=max<=8 with
extended auto_at_max/explicit_confirm modes; every domain is max<domain<=64.
Transform payloads use the local G7 `card_transform_v2` codec, while the
other card families use the original frozen `card_selection_v1` codec.

Item payloads use the exact frozen `item_probe_v1` envelope, `item_v1` version,
and surface_ordinal1 regardless of outer ordinal. Ready exposes one exact indexed
potion/relic offer, potion slots and `collect:<index>`; accepted and resolved values
must match that sole action and offer index/kind/key. Full potion inventory cannot
be repaired by a controller action. No card count/operation fields are fabricated.
For item decisions only, replay reservations include the full outer child lineage
and version. An identical inner decision ID on a later owned item episode is valid;
replaying a reservation on the same lineage is invalid. Parent/card global replay
rules remain unchanged.

Parent state is captured before the child read, so its reconciliation and completion
counters can lag that envelope's first resolved payload. The next parent snapshot
must reflect the increment. Item-local completion is withheld until the owned
collection, Offer and Chosen tasks succeed and the screen closes, with fresh effect
validation throughout. No task/model/screen identities enter public payloads.

An `action` response has null parent, the active child descriptor or null, and
an exact correlated receipt in payload. Parent receipt keys are `version`,
`session_nonce`, `decision_id`, `action_id`, `outcome`. Child receipts preserve
the frozen codec. Any nonaccepted result stops the controller without retry.
An `error` has null parent/child and payload `code`: invalid_request,
internal_failure or unsupported. Attempts remain counted even when a response
is lost; a failure does not assert that the game was unchanged.

The controller has one30-second deadline,2048 reads,12 parent actions,4 children
and52 total actions, preserving each card child's10-action bound and each item child'sone collection. No budget reset on
child entry, provider retry, automatic recovery or independent child route exists.

Reward auto mode permits select actions only and resolves at exactly max, with a
final selected receipt and no committed row. Explicit mode allows Confirm in
selecting at min..max and resolves with its committed row; it has no preview.
Preview-based families retain their witnessed preview and final Confirm. Public
mode/count/operation changes or illegal terminal controls stop before dispatch.

`completed_card_children` and `completed_item_children` each range0..4 and count fully validated resolutions of their respective kind. Their disjoint lineage union is bounded by the shared four child episodes.
The parent snapshot equals the consumer's count before reading this envelope's
child payload. A first fully validated resolved child increments the count once;
the next parent snapshot must reflect it. Parent child_completed history owners
must be distinct completed lineages. Only unsupported cleanup failure may retain
one completed latest-parent lineage not yet present in history. Ready/complete
and new parent dispatch require history equality. Later failure or Proceed does
not erase completion evidence. Existing effects remains last-action reporting, adding `item_effect_verified` for the latest resolved item action.
Fixed multi-upgrades automatically open preview at max; no variable or early
preview capability is admitted. Transform selection uses its separate card_transform_v2 effect contract.

Transform payloads use `card_transform_v2`; other card families retain `card_selection_v1`, and item children retain `item_v1`. The operation-to-version binding applies to all child observations, resolutions, receipts and failures. Transform admission is 1<=min<=max<=8, preview_confirm, domain>max<=64. Variable transformation additionally requires native manual confirmation. Preview below max requires an accepted explicit preview action; only selection at max may open preview automatically. Native journal witnesses never enter payloads.
