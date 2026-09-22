# Generic event v10 wire

This reference describes the current envelope and version routing.
[Event contracts](../../../../../docs/GENERIC_EVENTS.md) own native/effect semantics;
[current status](../../../../../docs/STATUS.md) owns support and live evidence.

## Requests and parent envelope

GET `/probe/generic-event-v7/public/decision` has no body. POST
`/probe/generic-event-v7/public/action` is a canonical UTF-8 JSON object with
ordered keys `decision_id`, `action_id`, `child`; the latter is null for parent
choices or exactly `ordinal`, `parent_decision_id`, `parent_action_id` for a child.
Actions must be advertised by the current parent or versioned child. Parent
choices use `choose:0..7`; child action grammars are family-specific below. No request can
supply operation, preferences, candidates or native identities.

Every response has ordered keys `schema_version` (1), `protocol`
(`generic_event_v10`), `session_nonce` (32 lowercase hex), `kind`, `parent`,
`child`, `payload`. Decision IDs are 64 lowercase hex. Duplicate/unknown keys,
wrong types, nonmatching publication or lineage, reused decisions and malformed
requests invalidate the session before further dispatch. Responses are bounded
to 65,536 bytes, requests 4,096, JSON depth 12 (requests 4).

A `decision` response's parent has ordered fields:

- `status`, `phase`, `decision_id`, `candidates`, `legal_actions`, `prior_results`;
- `parent_attempted`, `parent_accepted`, `parent_reconciled`, `child_episodes`;
- `child_attempted`, `child_accepted`, `child_reconciled`, `total_attempted`, `effects`, `completed_card_children`, `completed_item_children`.

Candidates contain `index`, `action_id`, `stable_id`, `rendered_text`, `enabled`,
`is_dangerous`, `is_proceed`, `discovery`. Discovery is `deferred` for an ordinary
choice, `none` for map Proceed, or `abandon_confirmation` for the
explicit popup exception described below. Counts are monotonic; parent history is an immutable
prefix of matching accepted receipts, with `option_transition`, `child_completed`
or `map_handoff` / `combat_handoff` / `combat_resume_handoff` / `run_won` /
`run_abandoned` results. Ordinary transitions do not certify HP/gold effects.

The routes retain their v7 names; the response protocol and parent receipt version
are v10. A complete parent has phase `map_handoff` after an accepted Proceed, or
`combat_handoff` or `combat_resume_handoff` after an accepted non-Proceed choice
without a child. Terminal completion may instead report `run_won` after the exact
Architect task chain, or `run_abandoned` after the confirmed popup below. Its final
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
`potion_capacity_gain` to reward rows. A terminal Fake Lee’s Waffle session uses
schema 6, adding bound `heal_amount` for exact capped healing;
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

## Child versions

Every descriptor starts with `ordinal`, `parent_decision_id`, `parent_action_id`,
`kind`, `contract_version`. Ordinals 1..4 are shared across all child kinds. A
`card_selection` descriptor appends `operation`, `min_select`, `max_select`,
`commit_mode`, `domain_count`; other kinds append `offer_count`. Requests carry
correlation only and cannot choose native semantics. Reject an unfamiliar version
before input; a newer child does not silently widen an older contract.

| Kind | Contract version | Payload/semantic reference |
| --- | --- | --- |
| `card_selection` | `card_selection_v1` | Positive add grids and fixed upgrade; inherited selection codec |
| `card_selection` | `card_remove_v2` | Selected removal plus zero/one unverified appended grant |
| `card_selection` | `card_transform_v2`, `card_transform_v3` | Positive fixed/variable transformation; v3 permits optional zero |
| `card_selection` | `card_add_v2` | Optional 0..15 grid selection |
| `card_selection` | `card_enchant_v1`, `card_enchant_v2` | Single/fixed multi-card enchantment descriptor and effects |
| `item` | `item_v1`, `item_set_v1` | One item or 2–8 ordered items with retained collected prefix |
| `card_reward` | `card_reward_v1`, `card_reward_set_v1`, `mixed_reward_set_v1` | One/multiple ordinary menus or mixed card/item entries |
| `item_policy` | `item_policy_v1` | Full-inventory/reordered policy surface below; 1–8 offers |
| `card_offer` | `card_offer_v1`, `card_offer_v2`, `bundle_offer_v1` | Required/optional direct card or bundle; native direct menus max 3 |
| `card_results` | `card_results_v1` | Acknowledge 1–64 results without certifying prior transformations |
| `crystal_sphere` | `crystal_sphere_v1` | Board/rewards, `offer_count: 121` |
| `abandon_confirmation` | `abandon_confirmation_v1` | Cancel/Confirm, `offer_count: 2` |

[Card contracts](../../../../../docs/GENERIC_EVENTS.md#card-selectors-and-deck-effects)
and [reward/offer contracts](../../../../../docs/GENERIC_EVENTS.md#event-rewards-and-offers)
define exact fields, bounds, legal transitions and version-specific exceptions.
There is no universal `domain > max` rule: optional versions admit specified
smaller/equal domains. Single-card/multi-card preview semantics remain distinct.

Singleton `item_v1` retains the `item_probe_v1` envelope and `surface_ordinal: 1`
regardless of outer ordinal. Its accepted/resolved payload binds the sole offered
index/kind/key. It has no discard action; `item_policy_v1` provides that separate
contract. An item set keeps exact list positions and per-entry identities, even
when native reward indices or model keys repeat.

Replay reservations for item, reward, offer, results, custom-screen and policy
children bind their outer lineage/version as well as the inner decision. An
identical inner ID in a later owned episode cannot replay a prior episode's
reservation. Card-selection and parent decision rules remain strict.

Parent state is captured before the child read, so its reconciliation and completion
counters can lag that envelope's first resolved payload. The next parent snapshot
must reflect the increment. Item-local completion is withheld until the owned
collection, Offer and Chosen tasks succeed and the screen closes, with fresh effect
validation throughout. No task/model/screen identities enter public payloads.

An `action` response has null parent, the active child descriptor or null, and
an exact correlated receipt in payload. Parent receipt keys are `version`,
`session_nonce`, `decision_id`, `action_id`, `outcome`. Child receipts preserve
their versioned codec. Any nonaccepted result stops the controller without retry.
An `error` has null parent/child and payload `code`: invalid_request,
internal_failure or unsupported. Attempts remain counted even when a response
is lost; a failure does not assert that the game was unchanged.

The controller has one 30-second deadline, 2,048 reads, 12 parent actions, four
children and 52 total actions. Local accepted-action caps are family-specific:
selection 10 (optional add 16), item-set one per entry, card-reward set `2*n+1`,
offer/bundle 2, results 1, sphere 40, abandon 1 and item-policy 25. These caps do not
increase global limits. No budget reset on
child entry, provider retry, automatic recovery or independent child route exists.

Reward auto mode permits select actions only and resolves at exactly max, with a
final selected receipt and no committed row. Explicit mode allows Confirm in
selecting at min..max and resolves with its committed row; it has no preview.
Preview-based families retain their witnessed preview and final Confirm. Public
mode/count/operation changes or illegal terminal controls stop before dispatch.

`completed_card_children` and `completed_item_children` each range 0..4 and count fully validated resolutions of their respective kind. Their disjoint lineage union is bounded by the shared four child episodes.
The parent snapshot equals the consumer's count before reading this envelope's
child payload. A first fully validated resolved child increments the count once;
the next parent snapshot must reflect it. Parent child_completed history owners
must be distinct completed lineages. Only unsupported cleanup failure may retain
one completed latest-parent lineage not yet present in history. Ready/complete
and new parent dispatch require history equality. Later failure or Proceed does
not erase completion evidence. Existing effects remains last-action reporting, adding `item_effect_verified` for the latest resolved item action.
Fixed multi-upgrades automatically open preview at max; no variable or early
preview capability is admitted. Transform selection uses its separate versioned effect contract.

## Full-inventory item policy child

`item_policy_v1` uses `kind: item_policy` and `offer_count: 1..8`.
Payload fields are ordered `version`, `session_nonce`, `status`, `phase`,
`decision_id`, `offers`, `card_options`, `potion_slots`, `can_skip`, `legal_actions`,
`prior_results`. Each offer has `index`, `kind`, `key`, `capacity_gain`, `settled`;
card options have `slot`, `key`, `upgrade_level`; potion slots contain public keys
or nulls. Native identities never enter the payload.

Advertised actions are `collect:N`, `discard:N`, `choose:N`, `skip_card` and
`skip_remaining`. Collecting a card entry opens its native menu; choosing/skipping
that menu is separate. Original-potion removal, collection and native dismissal
have separate correlated receipts and reconciled history. Newly collected potions
are protected. Native skip legality is required; no synthetic dismissal is allowed.
Receipts use the ordinary version/nonce/decision/action/outcome fields. The same
codec services owned resume-item policy screens, without admitting resume cards
or nested selectors. See [policy semantics](../../../../../docs/GENERIC_EVENTS.md#full-inventory-item-policies).

## Crystal Sphere child

The descriptor uses `kind: crystal_sphere`, `contract_version: crystal_sphere_v1`
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
