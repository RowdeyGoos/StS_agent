# Generic event v2 acceptance ledger

2026-09-07. Active integration worktree `/Users/rowdeygoos/.codex/worktrees/23cf/StS_agent`,
branch `codex/phase1-actor-ready-integration`, starting commit `aa178ee` (clean).
User request: continue working on the generic handler.

## Scope and ownership

The reviewed [v2 contract](../PHASE_1_GENERIC_EVENT_V2_CONTRACT.md) preserves
upgrade-one and adds shared standard removal with counts1..8 and variable limits,
without event-name registrations. It preserves all fifteen frozen predecessors
and the original bridge. The new tree is `successors/generic_event_v2`.

- Root: contract, core admission, wire, checker, provenance and living docs.
- Native lane: bounded public preview mapping evidence; native adapter/hooks and
  focused native fixtures after that evidence is accepted.
- Host/review lane: strict Python controller/tests and independent source review.
- Integration lane: wire tests and C#-to-Python fixtures, including actual native.

Independent design review accepted explicit equality between preview originals
and reconciled selections, plus full context checks at both removal creation
entry and returned-screen binding. The parent now receives an immutable admitted
operation/count/mode/domain description and passes its opaque identity into child
creation. Host and wire preserve receipt order but compare selection membership
as sets, avoiding the predecessor's one-card ordering assumption.

## Evidence and final review

The removal command wrapper and selector lifecycle are retained hash-bound static
evidence. A new independently reviewed six-body metadata-only inspection passed
in a clean environment, proving the public preview-holder/card-original mapping.
See its [scope](PHASE_1_GENERIC_EVENT_V2_PREVIEW_SCOPE.md) and
[result](PHASE_1_GENERIC_EVENT_V2_PREVIEW_RESULT.md). The target was read as
metadata only and never loaded or executed. This was a new scope, not a rerun of
any historical inspection command.

Independent tests and source review identified and corrected confirmation before
preview publication, below-min preview/duplicate select advertisements, candidate
flag mismatch, parent control/UTF8 bounds, missing required removal-test inventory,
admitted max+1 result bounds and owner-thread hook access. Partial preview creation
waits for exact selected-original membership before binding preview holders.
The final reviewer found no remaining actionable issues and independently matched
the source/contract to the passed candidate result. Staged `git diff --check`
passed before source freeze.

## Candidate aggregate

`/private/tmp/generic-event-v2-root-candidate-a/result.json` passed:

- 375 native assertions with real Harmony and production code against inert stubs.
- 73 wire checks, including rejection before POST dispatch.
- 52 Python host tests (33 preserved,19 removal/variable-count tests).
- 45 C#-to-Python integration cases:34 pure, including a mixed upgrade→removal
  event parent;11 production-native flows (four upgrades,seven removals).
- Removal fixtures use three unrelated/held-out actual event subclasses and cover
  reverse order, explicit preview below max, automatic preview at max, eight-card
  selection, delayed creation/effects and lost-response accounting without retry.
- All15 predecessor source identities and original48 bridge files unchanged.
- Seven explicit project closures built; source derivations and required tests
  verified. Two pinned compile-only native builds matched exactly:54,272 bytes,
  SHA-256 `784f7623ffad1221ceff56d9c29f80558ec541a9c2887ffbbd13cba26b345502`.
  No target assemblies were executed or copied into output directories.

The545 focused checks are the new component aggregate; this increment did not
change simulator/training sources or rerun their unrelated full regression suite.
The source/component contract remained unchanged after this passed aggregate.

## Frozen identity

The32-file component identity is frozen:

- Manifest SHA-256:
  `dbbd8cb5d80f54040967b4b2dc27c70a2b031e5bb1077ae86362c80182e59db1`.
- Source inventory SHA-256:
  `9edaac1a72a61d86ff6c9d38cebcd28117f1825c033f2cccd63c8919cc5947ab`.
- Contract SHA-256:
  `7e651227deef02dbec967c84ce95eddc4ac75008ba18d5749bdb6944ac4bcea2`.

The fresh frozen aggregate passed at
`/private/tmp/generic-event-v2-root-frozen-a/result.json`; its exact bytes are
[retained in the repository](PHASE_1_GENERIC_EVENT_V2_FROZEN_RESULT.json).
Result SHA-256: `676331c75ddaf363c7650643bf0278d1b5d7d76dfd3639c33d8054bf001b6f20`.

It verified the frozen identity and repeated all545 checks successfully. Both
native builds again matched candidate A: four identical builds across the two
aggregate runs. Functional acceptance is complete for the stated two families.
Python3.10 parsing and staged whitespace validation also passed.

## Remaining boundaries

There are16 frozen successors including v2. Functional support covers generic
upgrade-one and removal1..8 with variable limits, ordinary choices and Proceed.
Generated adds, transformation, multi-upgrade, optional zero, scrolling, repeated
keys, item children, custom screens and event combat remain open in this successor.
No named-event complete-branch or runtime eligibility claim follows from fixtures.

Release composition, installable packaging and actual EventSynchronizer context
preservation remain untested live gates. Lost asynchronous ownership fails closed.
No live campaign, installation, profile/save, Cloud or remote Git operation occurred.
