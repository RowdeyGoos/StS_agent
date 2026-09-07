# Generic event v2 wire

GET `/probe/generic-event-v2/public/decision` has no body. POST
`/probe/generic-event-v2/public/action` is a canonical UTF-8 JSON object with
ordered keys `decision_id`, `action_id`, `child`; the latter is null for parent
choices or exactly `ordinal`, `parent_decision_id`, `parent_action_id` for a child.
Actions are the advertised `choose:0..7` or frozen card actions. No request can
supply operation, preferences, candidates or native identities.

Every response has ordered keys `schema_version` (1), `protocol`
(`generic_event_v2`), `session_nonce` (32 lowercase hex), `kind`, `parent`,
`child`, `payload`. Decision IDs are64 lowercase hex. Duplicate/unknown keys,
wrong types, nonmatching publication or lineage, reused decisions and malformed
requests invalidate the session before further dispatch. Responses are bounded
to65536 bytes, requests4096, JSON depth12 (requests4).

A `decision` response's parent has ordered fields:

- `status`, `phase`, `decision_id`, `candidates`, `legal_actions`, `prior_results`;
- `parent_attempted`, `parent_accepted`, `parent_reconciled`, `child_episodes`;
- `child_attempted`, `child_accepted`, `child_reconciled`, `total_attempted`, `effects`.

Candidates contain `index`, `action_id`, `stable_id`, `rendered_text`, `enabled`,
`is_dangerous`, `is_proceed`, `discovery`. Discovery is `deferred` for an ordinary
choice and `none` for Proceed. Counts are monotonic; parent history is an immutable
prefix of matching accepted receipts, with `option_transition`, `child_completed`
or `map_handoff` results. Ordinary transitions do not certify HP/gold effects.

An admitted child contains `ordinal`, `parent_decision_id`, `parent_action_id`,
`operation`, `min_select`, `max_select`, `commit_mode`, `domain_count`. The current
families require upgrade,1,1,preview_confirm,2..64 or remove,1<=min<=max<=8,
preview_confirm,max<domain<=64. Selected slots/cards are duplicate-free sets;
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
