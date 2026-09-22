# Card-Record Representation Kernel

> Archived 2026-09-22: this pipeline is retired. Commands and source descriptions
> apply to the original revision, not the current engine.

The card-record kernel is an opt-in foundation for a future scalable RL card
representation. It does **not** change `CombatEnv`, `ObservationEncoder`, action
features, policies, trainers, checkpoints, commands, or any current default.

The pure-Python record API is in `game.simulation.card_records`. The optional
Torch component is in `game.agents.card_encoder`. These canonical subpackage
paths are intentional; the kernel is not exported from the root `game` facade
until it is integrated into an end-to-end policy path.

## Format v1

`CARD_RECORD_FORMAT_VERSION` is `1`. Card IDs retain the existing assignments:

| ID | Card |
| ---: | --- |
| 0 | `<PAD>` |
| 1 | Strike |
| 2 | Defend |
| 3 | Bash |
| 4 | Slimed |
| 5 | Pommel Strike |
| 6 | Shrug It Off |
| 7 | Iron Wave |
| 8 | Body Slam |

IDs are append-only and must remain contiguous. They cannot be renamed,
renumbered, reused, or removed. The format reserves 256 card IDs, ten ordered
hand records, and 32 distinct records per hidden pile. Capacity overflow fails
instead of truncating information.

Each card has fixed-width semantics for kind, cost, per-hit damage, hit count,
block, draw, status application, exhaust, targeting, and dynamic damage. The
existing card metadata has no multi-hit field yet, so format v1 reserves the
field and infers one hit for current damaging cards. Body Slam uses the
`player_block` dynamic-damage rule. Card identity remains separate so unique
behavior is distinguishable even when two cards have similar semantics.

`extract_card_zone_records()` preserves the ordered hand and converts draw,
discard, and exhaust composition into canonical `(card ID, count)` records.
The records are exact for the information already visible in the structured
observation. They deliberately do not expose hidden draw order.

The schema can be serialized with `card_record_schema_dict()` and identified by
the deterministic SHA-256 value from `card_record_schema_fingerprint()`.

## Learned encoder

`tensorize_card_zone_records()` pads a batch while keeping IDs and counts as
integer tensors and masks as booleans. `SharedCardEncoder` uses:

- one `256 x 16` learned card-ID embedding with padding ID zero
- a fixed semantic lookup table
- one shared MLP that produces 32-value card embeddings
- ordered per-hand embeddings and a pooled hand embedding
- count-weighted, record-order-invariant pooling for each hidden pile
- exact total card counts beside the three pooled pile embeddings

The same `encode_card_ids()` method is intended for future action-card IDs, so
hand, pile, and action identity will share weights. Padded records are masked
after the MLP, preventing layer biases from producing padding features.

## Future checkpoint contract

No current checkpoint contains or consumes this representation. End-to-end
integration must keep representation and policy architecture as separate
choices; for example, a future `card_records_v1` representation must be able to
compose with a `shared_enemy` policy architecture.

A future card-aware checkpoint must record:

- representation name and `CARD_RECORD_FORMAT_VERSION`
- schema fingerprint and registry names in ID order
- greatest card ID observed during training
- hand, pile, and ID capacities
- card-ID and output embedding dimensions

Existing one-hot checkpoints are a retraining boundary and must not be silently
converted. Changing semantics or an ID assignment for an existing card requires
a new format version. Appending a card below the reserved capacity keeps tensor
and parameter shapes stable, but a checkpoint should reject unseen card IDs by
default because those embedding rows were not trained. A later explicit
fine-tuning or diagnostic override may opt into unseen IDs.

Trainer, replay/rollout, environment-factory, CLI, and checkpoint integration is
intentionally deferred until the named-deck and shared-enemy DQN work has landed.
