# Current unified release

[bridge.json](bridge.json) binds accepted release `0dd12fd10f84125eb5e8b32ea7bde6da91809358b2d85b8261d5458d2696737c` to the exact
source, toolchain, tests and package of the single production bridge.

This release adds Trial’s owned abandonment popup: Cancel returns to the same
verified event choices; explicit confirmation ends the run only after the exact
native task, abandoned flag, HP zero and modal closure are verified. Default
policy is cancellation. The parent protocol is `generic_event_v10`, with unchanged
routes. Unresolved or changed outcomes cannot release a clean owner.

Independent semantic review found no remaining blocker. All 71 release groups
passed in 212.643 seconds: 10,358 native assertions, 1,233 shared
checks, 485 C#/Python integration cases (423 native), 69 client tests,
128 event-host tests, real socket actions, reproducible packaging and owned
installation/cleanup fixtures. This package has not been installed or live-tested.

The preceding release `6cc54f193c98028f1bfe94d8f65558fc3d513ef2793125b692969c1c83c68319`
passed Lantern Key and Punch Off combat/rewards/map in one live process, including
special-card and deferred potion/relic rewards. Normal quit and exact cleanup
passed with 429 unchanged base files and zero overlays. Those results retain
their original identities in [validation.json](validation.json) and the
[multi-case evidence](../../../../docs/evidence/MULTICASE_BRIDGE_LIVE_2026_09_12.md).
They are not live evidence for this popup increment.

Current capability and limits are in [status](../../../../docs/STATUS.md).
See the [bridge guide](../../README.md) for usage.
