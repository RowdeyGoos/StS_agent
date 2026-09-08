# Generic event v4 wire

GET `/probe/generic-event-v4/public/decision` has no body. POST
`/probe/generic-event-v4/public/action` is a canonical UTF-8 JSON object with
ordered keys `decision_id`, `action_id`, `child`; the latter is null for parent
choices or exactly `ordinal`, `parent_decision_id`, `parent_action_id` for a child.
Actions are the advertised `choose:0..7` or frozen card actions. No request can
supply operation, preferences, candidates or native identities.

Every response has ordered keys `schema_version` (1), `protocol`
(`generic_event_v4`), `session_nonce` (32 lowercase hex), `kind`, `parent`,
`child`, `payload`. Decision IDs are64 lowercase hex. Duplicate/unknown keys,
wrong types, nonmatching publication or lineage, reused decisions and malformed
requests invalidate the session before further dispatch. Responses are bounded
to65536 bytes, requests4096, JSON depth12 (requests4).

A `decision` response's parent has ordered fields:

- `status`, `phase`, `decision_id`, `candidates`, `legal_actions`, `prior_results`;
- `parent_attempted`, `parent_accepted`, `parent_reconciled`, `child_episodes`;
- `child_attempted`, `child_accepted`, `child_reconciled`, `total_attempted`, `effects`, `completed_card_children`.

Candidates contain `index`, `action_id`, `stable_id`, `rendered_text`, `enabled`,
`is_dangerous`, `is_proceed`, `discovery`. Discovery is `deferred` for an ordinary
choice and `none` for Proceed. Counts are monotonic; parent history is an immutable
prefix of matching accepted receipts, with `option_transition`, `child_completed`
or `map_handoff` results. Ordinary transitions do not certify HP/gold effects.

An admitted child contains `ordinal`, `parent_decision_id`, `parent_action_id`,
`operation`, `min_select`, `max_select`, `commit_mode`, `domain_count`. The current
families require upgrade,1<=min=max<=8,preview_confirm,max<domain<=64; remove,1<=min<=max<=8,
preview_confirm,max<domain<=64; or add,1<=min<=max<=8,auto_at_max/explicit_confirm,
max<domain<=64. Selected slots/cards are duplicate-free sets;
receipt order and candidate order remain distinct. Its payload is the
unchanged `card_selection_v1` public codec value. Parent state is captured before
the child read, so its reconciliation counter can lag that read's child history;
the host reconciles exact received action/history pairs itself. It delivers a
resolved child before the following GET resumes/disposes it through the parent.

An `action` response has null parent, the active child descriptor or null, and
an exact correlated receipt in payload. Parent receipt keys are `version`,
`session_nonce`, `decision_id`, `action_id`, `outcome`. Child receipts preserve
the frozen codec. Any nonaccepted result stops the controller without retry.
An `error` has null parent/child and payload `code`: invalid_request,
internal_failure or unsupported. Attempts remain counted even when a response
is lost; a failure does not assert that the game was unchanged.

The controller has one30-second deadline,2048 reads,12 parent actions,4 children
and52 total actions, preserving each child's10-action bound. No budget reset on
child entry, provider retry, automatic recovery or independent child route exists.

Reward auto mode permits select actions only and resolves at exactly max, with a
final selected receipt and no committed row. Explicit mode allows Confirm in
selecting at min..max and resolves with its committed row; it has no preview.
Preview-based families retain their witnessed preview and final Confirm. Public
mode/count/operation changes or illegal terminal controls stop before dispatch.

`completed_card_children` is 0..4 and counts validated child resolutions only.
The parent snapshot equals the consumer's count before reading this envelope's
child payload. A first fully validated resolved child increments the count once;
the next parent snapshot must reflect it. Parent child_completed history owners
must be distinct completed lineages. Only unsupported cleanup failure may retain
one completed latest-parent lineage not yet present in history. Ready/complete
and new parent dispatch require history equality. Later failure or Proceed does
not erase completion evidence. Existing effects remains last-action reporting.
Fixed multi-upgrades automatically open preview at max; no variable or early
preview capability is admitted. Transform remains unsupported.
