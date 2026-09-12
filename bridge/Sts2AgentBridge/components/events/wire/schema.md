# Generic event v10 wire

GET `/probe/generic-event-v7/public/decision` has no body. POST
`/probe/generic-event-v7/public/action` is a canonical UTF-8 JSON object with
ordered keys `decision_id`, `action_id`, `child`; the latter is null for parent
choices or exactly `ordinal`, `parent_decision_id`, `parent_action_id` for a child.
Actions are the advertised `choose:0..7` or frozen card actions / `collect:i` item actions. No request can
supply operation, preferences, candidates or native identities.

Every response has ordered keys `schema_version` (1), `protocol`
(`generic_event_v10`), `session_nonce` (32 lowercase hex), `kind`, `parent`,
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
choice, `none` for map Proceed, or `abandon_confirmation` for the
explicit popup exception described below. Counts are monotonic; parent history is an immutable
prefix of matching accepted receipts, with `option_transition`, `child_completed`
or `map_handoff` / `combat_handoff` / `combat_resume_handoff` results. Ordinary transitions do not certify HP/gold effects.

The routes retain their v7 names; the response protocol and parent receipt version
are v10. A complete parent has phase `map_handoff` after an accepted Proceed, or
`combat_handoff` or `combat_resume_handoff` after an accepted non-Proceed choice
without a child. Its final
history row must match that phase and the latest accepted parent receipt, with
all parent actions reconciled. Combat entry certifies only the exact in-progress
combat requested by that choice, not victory. The non-resuming path releases
ownership after that same combat’s terminal observation. The resuming path keeps
the event cleanup owner until its exact callback Task and replacement event node
are verified, then disposes that owner before releasing core combat ownership.
Non-resuming entry admits zero to eight exact extra special-card, potion or relic
rewards (at most one special card), including deferred item generation. Core terminal item reward sessions
use ready schema 4 (`item_key`, session-ordinal `reward_index`, `collect:<slot>`,
public `potion_slots` and explicit `discard:<slot>` actions under replacement policy).
Sessions containing a terminal Potion Belt reward use schema 5, adding the declared
`potion_capacity_gain` to reward rows;
see the [reward contract](../../../../../docs/GENERIC_EVENTS.md#extra-potionrelic-rewards-and-mixed-collection).
Resuming entry still admits no extra rewards. Owned potion/relic resume children use the continuation routes below.

The Python resolved event summary includes `destination` and `session_nonce`.
For `combat_resume_handoff`, GET `/probe/event-combat-v2/public/decision` returns
exact fields `schema_version` (1), `protocol` (`event_combat_v2`), `session_nonce`
and `status` (`combat`, `waiting`, `item`, `resumed`). It accepts no action headers or body.
This endpoint is unavailable outside an owned resuming combat. `resumed` requires
a successful callback and cleanup; it is not a victory or an effect certificate.
Status `item` admits the owned continuation `item-decision` and `item-action`
routes under the same v2 prefix, using the existing item child contracts. Other
fields and phases of the parent/child wire retain their existing contracts.

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

## Crystal Sphere child

The new descriptor uses `kind: crystal_sphere`, `contract_version: crystal_sphere_v1`
and `offer_count: 121` after the common lineage fields. The outer protocol remains
`generic_event_v10`; existing child versions retain their semantics.

Payload keys are ordered `version`, `session_nonce`, `status`, `phase`,
`decision_id`, `board`, `legal_actions`, `prior_results`. Ready phases are `board`,
`rewards` and `cards`. Ready `board` has ordered `divinations` (0..20), `tool`
(`small`/`big`), `hidden` (121 booleans, slot y*11+x) and `rewards` (0..8 rows).
Reward rows have `slot`, `kind` (gold/card/potion/relic), `key`, `amount`, `cards`;
card rows have `slot`, `key`, `upgrade_level` (0..5 cards per offer). No hidden item
content or RNG state is published. Board phase has positive divinations and no
reward rows; reward/card phases have zero divinations.

Actions are the advertised `tool:small`, `tool:big`, `reveal:0..120`,
`reward:claim:0..7`, `reward:collect:0..7`, `reward:open:0..7`,
`reward:choose:0..4`, `reward:skip_card` or `dismiss`. There are at most 123 legal
actions per ready payload and 40 accepted child actions. Histories contain the
matching `decision_id`, `action_id`, `result: completed` receipts. Non-ready
payloads have null board, empty decision and no legal actions; waiting/unsupported
phases match status, while resolved uses `complete`.

The host validates each public board transition against the accepted tool/reveal
receipt. Small clears one cell; big clears the bounded 3×3 neighborhood; revealing
decrements divinations exactly once. The sphere episode contributes to child
history and reconciliation, but not `completed_card_children` or
`completed_item_children`; effects remain `unverified`. Its resolved payload is
nonterminal: parent native Leave must still reconcile map handoff and cleanup.

## Abandonment confirmation

`abandon_confirmation_v1` uses kind `abandon_confirmation` and `offer_count: 2`.
The payload keys are `version`, `session_nonce`, `status`, `phase`, `decision_id`,
`consequence`, `legal_actions`, `prior_results`. Consequence is `run_abandoned`.
Ready phase `confirm` advertises exactly `cancel`, `confirm_abandon`, in that order.
Each child accepts at most one action; its correlated result is `cancelled` or
`abandoned`. Waiting and unsupported phases expose no action. Receipts use the
ordinary version/nonce/decision/action/outcome fields.

The narrowly identified native Trial DoubleDown callback publishes discovery
`abandon_confirmation`, retaining its native dangerous and Proceed flags. It
belongs to an unfinished choice page and does not count as map Proceed. Other
dangerous choices remain illegal. Cancellation revalidates the retained parent
presentation and inventory before publishing a fresh decision for those same
controls. The previous decision remains retired. Confirmed abandonment completes
the parent with phase and final history result `run_abandoned`, after child
reconciliation. It does not increment card/item completion counts or certify a map
handoff. Overall effects remain `unverified`. Native cleanup revalidates the
completed outcome; pending or uncertain abandonment cannot release a clean owner.
