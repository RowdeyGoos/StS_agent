# Generic event development

[Current status](PHASE_1_CURRENT_STATUS.md) owns supported capabilities and latest
evidence. [AGENTS.md](../AGENTS.md) owns the streamlined workflow.
This document describes the architecture and next acceptance case, not campaign history.

## Implemented architecture

Handle shared interactions using the rules the game supplies. A new event using
a supported interaction does not need an event-name registration. Event names
identify ownership and representative/held-out cases; custom surfaces may need
separate adapters.

The parent reserves the chosen option and pre-action deck. Owned native request
and screen-creation hooks supply operation, counts, candidate originals and task
identity. The child advertises legal actions; a replaceable host provider chooses
one. The adapter rechecks identity before native input, verifies preview/effect
completion, then resumes the parent through Proceed.

This two-stage admission is implemented. Do not restart discovery design from
the old proposals. G7 and inherited child contracts describe exact semantics;
a parent action may already have effects before an unsupported child appears.
Preserve cumulative child completion independently of the latest parent's effect label.

## Next change: all eligible transform holders

The successful v10 experiment directly selected an allocated off-screen card.
Its card16-only mask and dispatch guard are test restrictions. Generalize this
working path in `bridge/Sts2AgentBridge/apps/events/gameplay`, retaining historical
release evidence in Git. Shared generic code is in `components/events`.

- Remove both fixed-slot restrictions and expose all legal allocated holders in
  native order. Preserve complete candidate/domain binding.
- Retain exact holder/model/run/screen/task ownership, native enabled state,
  deferred-callback identity, exact-original preview membership and selected-only
  transformation reconciliation. Matching card names do not establish identity.
- Keep viewport, clipping-parent and complete-layout-fit checks out of this
  direct transformation input path. The earlier ten-card suggestion is obsolete.
- Keep fixed/variable preview semantics and host decision-provider behavior.
  Do not change strategy or add event-name admission rules.

Acceptance exercises actual adapter-to-client selection of different targets,
including visible and allocated off-screen holders. It rejects missing, disabled
or reassigned targets without choosing a substitute or retrying uncertainty, and
checks existing preview/completion modes. Reuse matching accepted dependency
evidence; one independent review addresses the changed action semantics.

A further live test must answer a remaining behavior question, such as selecting
another advertised target through the generalized path. Use the minimal known
setup and one precise expected outcome. Do not repeat the same card16 question
with another visibility-proof implementation.

This generalization is planned; the documentation change does not implement it.

## Separate remaining questions

An allocated off-screen holder can accept direct input. A card without an
allocated holder cannot use that path yet. Incomplete coverage may require
scrolling/rebinding or another supported native mechanism; inspect that specific
case before designing infrastructure. Other selector families may still impose
layout restrictions and need their own evidence.

Further work includes optional/zero selection and cancellation, variable-count
upgrading, multiple-item reward sets, custom/repeated choices and event combat.
Choose the next family from a real representative caller or observed play blocker.
Positive variable transformation already works offline; the inspected live caller
used a fixed count. Do not invent a live test from the selector API alone.

For semantic detail use [G7](PHASE_1_GENERIC_EVENT_V7_CONTRACT.md), the
[v10 input experiment](PHASE_1_GENERIC_EVENT_RELEASE_V10_CONTRACT.md) and the
[coverage matrix](research/PHASE_1_EVENT_COVERAGE_MATRIX.md).
For preparation, evidence reuse and cleanup use the [live guide](LIVE_DEVELOPMENT.md).
