# Card selection v1 wire schema

The in-process service exposes four exact routes:

- `GET /card-selection-v1/parent`
- `POST /card-selection-v1/parent/action`
- `GET /card-selection-v1/child`
- `POST /card-selection-v1/child/action`

A GET has an empty body. A POST body is the canonical UTF-8 object
`{"decision_id":"<64 lower hex>","action_id":"<canonical action>"}` with
properties in that order, no duplicate or additional properties, and no trailing
byte. Parent actions are `begin` and `proceed`. Child actions are `select:<slot>`
for decimal slots 0 through 63 without leading zeroes, `preview`, or `confirm`.
The maximum request body is 256 bytes. Responses are canonical UTF-8 JSON objects
without a trailing newline and are at most 65536 bytes.

`CardSelectionV1WireResponse.StatusCode` is 200 for a validated module value, 400
for `invalid_request`, and 500 for `internal_failure`. Error bodies have exactly:

`schema_version,kind,status,code`, where `kind=error`, `status=error`, and `code`
is `invalid_request` or `internal_failure`.

All successful bodies begin with `schema_version=1` and one exact `kind` below.
Property order is the listed order.

- `parent_observation`: `schema_version,kind,version,session_nonce,parent_ordinal,status,phase,parent_kind,policy,decision_id,legal_actions`
- `parent_resolved`: `schema_version,kind,version,session_nonce,parent_ordinal,status,result,begin_decision_id,begin_action_id,proceed_decision_id,proceed_action_id`
- `parent_receipt`: `schema_version,kind,version,session_nonce,parent_ordinal,decision_id,action_id,outcome`
- `parent_failure`: `schema_version,kind,version,session_nonce,parent_ordinal,outcome`
- `child_observation`: `schema_version,kind,version,session_nonce,parent_ordinal,status,phase,operation,commit_mode,min_select,max_select,decision_id,candidates,selected_slots,legal_actions,prior_results`
- `child_resolved`: `schema_version,kind,version,session_nonce,parent_ordinal,status,phase,operation,selected_cards,prior_results`
- `child_receipt`: `schema_version,kind,version,session_nonce,parent_ordinal,decision_id,action_id,outcome`
- `child_failure`: `schema_version,kind,version,session_nonce,parent_ordinal,outcome`

A candidate or selected-card object has exactly
`slot,key,upgrade_level,visible,enabled,selected`. An action-result object has
exactly `decision_id,action_id,result`. Arrays preserve the immutable module
order. Opaque parent, screen, task, model, holder, control, and replacement
identities are never encoded.

Fixed parent waiting/unsupported observations retain only version/session/ordinal,
status and phase; their parent kind, policy, decision and action arrays are empty.
Parent `waiting/transient` remains on the parent route; only
`waiting/card_child` authorizes the first child GET.
Fixed child waiting/unsupported observations retain prior action results and set
operation/commit/decision and candidate/selected/action arrays empty with both
cardinalities zero. Parent-owned child-unavailable values use this same fixed
child observation shape. Parent-owned child apply failures use the fixed child
failure shape.

The service validates route-specific result types, scalar domains, exact nonce and
ordinal, every accepted receipt against the immediately published decision, each
child result history as a monotonic exact prefix of accepted receipts, selection
cardinality, and final parent begin/proceed correlation before encoding. Any
unknown object type, malformed public value, impossible phase/status combination,
oversized output, reentry, off-owner call, or cleanup failure becomes the fixed
`internal_failure` response and permanently fails the service.
