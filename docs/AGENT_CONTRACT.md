# Public agent contracts

Implemented by [`game.agent.contracts`](../game/agent/contracts/__init__.py).
The contract is milestone 1 of the [agent environment plan](AGENT_ENVIRONMENT.md);
the [headless producer](#headless-producer) and public-only chooser implement
milestone 2. The [native producer](#native-producer) and existing bridge client
implement milestone 3 through new `agent_v1` routes; existing routes retain their
semantics. The controlled native slice is accepted. The milestone 4
[encoding and Gymnasium consumer](AGENT_ENCODING.md) is implemented over this
contract. Milestone 5 adds the opt-in [full-run v2 profile](#full-run-v2-profile)
for the headless engine. The accepted native `agent_v1` profile is unchanged.

## Scope and wire boundary

`PublicDecision` has schema `sts_public_decision_v1` and profile
`combat_reward_map_v1`. Its contexts are ordinary combat, nested discard/exhaust
card selection, ordinary combat rewards and map choice. The first integrated
scenario is an Ironclad combat with Neow's Fury, rewards and map handoff. Five
character resource shapes are defined, including resources acquired through
off-character cards/items. Additional room, potion, event and ending decisions
use the separate v2 profile below; never silently drop unsupported legal commands
to make a state fit v1.

The [dataclasses](../game/agent/contracts/models.py) are the authoritative field
schema. They are immutable and use tuples internally; JSON uses arrays. Every
declared field must be present, including explicit null arguments. The
[codec](../game/agent/contracts/codec.py) rejects extra/missing fields, duplicate
JSON keys, non-finite numbers, bools/floats masquerading as integers, unknown
versions/profiles and invalid discriminators. Only these named message types may
be deserialized; input cannot import a class. There are no arbitrary data bags.

Use `loads`/`from_dict` and `dumps`/`to_dict` at every boundary. Dataclass
construction alone does not validate. Semantic checks reject duplicate identities,
inconsistent bounds/piles, dangling action references and contradictory execution
reports. They do not prove that an action is legal in a backend: producers must
enumerate native/engine legal actions and dispatch through their existing owners.

```python
from game.agent.contracts import loads, require_ready

decision = require_ready(loads(json_text))
# Only this public object reaches a chooser. Dispatch stays outside this package.
```

[`neows_fury_v1.json`](../tests/agent/fixtures/neows_fury_v1.json) is an authored
valid wire example. [`invalid_v1.json`](../tests/agent/fixtures/invalid_v1.json)
lists independent path replacements that must each be rejected, including
private fields, duplicate physical cards and invalid selection bounds. These are
synthetic contract fixtures, not bridge captures. [Tests](../tests/agent/test_contracts.py)
also round-trip all five resource shapes, both selection branches, duplicate
reward offers, map decisions, outcomes and execution failures.

## Availability, information and identity

`Observed[T]` always has `status` and `value`:

| Meaning | Example |
| --- | --- |
| Known zero/empty | `known(0)`, `known(())` |
| Not applicable | `not_applicable()`; its value is null |
| Unavailable to this producer | `unknown()`; its value is null |
| Known absent entity | Empty potion slot; `known(OstyState(None))` |

Required inventory/pile/history fields cannot use not-applicable. `missing_fields`
reports unavailable applicable fields; `require_ready` raises
`UnsupportedDecision` before policy use. The sole optional unknown is a card's
deck-origin link: at live attachment, identical copies may not have a publicly
distinguishable original. Never expose a private origin link to fill that field.
Publicly identified generated cards and permanent originals have not-applicable
origin. When provenance cannot be established from the producer's public history,
the origin stays unknown, including at attachment. Required
information cannot be replaced with zero, an empty list or an unrelated old read.

`History.coverage` explicitly distinguishes observations from `run_start` from
those since `attachment`. A known empty attachment history makes no claim about
earlier actions. It is an ordered public decision/event history, not the native
private combat history. Full trajectory records are separate future work.

References use a public namespace and nonnegative ordinal, e.g. `card:4`,
`enemy:0`, `power:1`, `orb:0`, `reward:0`, `node:1`, `action:0`. Entity references
are unique in a decision. Keep them stable for an observable object's lifetime
within an episode; never reassign an enemy reference after a death. Deck originals
and combat copies have separate refs, with an optional publicly justified origin
link. Repeated equal card definitions remain separate options. Selection order,
hand order and orb queue order are meaningful.

Reference allocation must use public observation history and canonical public
content, not private snapshot sequence numbers or hidden draw position. Sort draw
contents by public content/established public identity; the wire marks that pile
`canonical`. The validator rejects a draw pile marked `visible`; it cannot detect
a producer falsely claiming canonical order. Hidden-state invariance and stable
reference tests are mandatory in milestone 2. Map `unknown` means the visible
question mark; it must not disclose the room/encounter assigned behind it.

Indistinguishable copies in an unordered pile cannot establish a private physical
correspondence. The headless producer rebinds those equal copies in public
destination order when they become visible, retaining the remaining public names
in the draw multiset. It preserves exact hand/selection identities and their
command bindings; a public name must not reveal which identical hidden copy was
next in the stack.

IDs and counter labels use lower snake case. Normalize native content IDs through
the pinned vocabulary (`NEOWS_FURY` → `neows_fury`; `STRIKE_IRONCLAD` → `strike`),
not blindly by lowercasing. Card `values` are the current displayed numeric
variables, and `modifiers` are public modifiers/keywords and their displayed
amounts; empty means none. Power instances have separate refs and public counters
so repeated timers do not collapse into one stack. Cost amounts are current
displayed/spend values, with separate X flags; an inapplicable currency is not zero.
Non-attack/hidden intent damage and hit count are not-applicable, not invented zero.

Exclude seeds, RNG counters/state, hidden draw order, future reward/encounter
generation, unrevealed map assignments, native object addresses, protocol tokens,
private resolution frames and dispatch hashes. This allowlist must be projected
directly; do not serialize a private snapshot and subtract a blacklist.

## Producer field mapping and explicit gaps

This table records the milestone 1 audit of the original bridge DTOs. Their gaps
are addressed for the bounded [native producer](#native-producer) below; it does
not make every native card, power or room supported.

Native inspection uses the pinned `sts2.dll` SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
Native class/member names below are source references from that assembly, not
permission to read game profiles. Native member availability alone does not prove
public visibility; the UI/public rule basis is listed separately.

| Contract fields | Headless source | Native public source / visibility | Current bridge agreement or gap |
| --- | --- | --- | --- |
| `run.character`, `ascension`, `act`, `floor` | `RunState.config.character/ascension`, `act_index`, visited route in [run state](../game/headless/run/state.py) and [config](../game/headless/run/config.py) | `Player.Character`, run difficulty/act and displayed route/top-bar progress | No coherent combined decision projection; normalize act to one-based, floor to visited-room count |
| HP/max HP, gold | `RunState`, active [Player](../game/headless/core/player.py) during combat | `Player.Creature.CurrentHp/MaxHp`, `Player.Gold`; displayed HUD | Core combat supplies HP; reward/room supplies gold; must join only within the same owned decision |
| Deck cards, upgrades, costs, modifiers, origins | `RunState.deck`, [Card](../game/headless/cards/base.py) spec, upgrade level, enchantment/combat state | `Player.Deck`, `CardModel.CurrentUpgradeLevel`, `EnergyCost.GetAmountToSpend`, `GetStarCostWithModifiers`, `DynamicVars`, `Enchantment`, `Affliction`; deck/pile/card previews. `DeckVersion` alone is not proof of observable origin | Ordinary combat DTO only has card ID/type/energy-cost text/playability/target type. Full instances, numeric values, Stars, modifiers and public origin mapping are gaps |
| Relics and public counters | `RunState.relics`; combat relic values/owned public counters in [rules](../game/headless/core/card_state.py) | `Player.Relics`, relic descriptions/counter UI; only displayed or independently knowable counters | Room inventory is partial; no full per-decision counters or public relic refs |
| Potion slots, including holes | `RunState.potions` and capacity | `Player.PotionSlots`, visible belt slots; preserve empty indexes | Existing reward/item routes expose slot keys; shared coherent inventory and refs still needed |
| Map nodes, edges/current node, reachability | [map travel](../game/headless/run/map_travel.py) and `RunEngine.graph`; project displayed node kind only | `NMapScreen`/`NMapPoint.Point`, visible edges and point state | [Map reader](../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicMapDecisionReader.cs) exposes travelable nodes only; full visible graph/current context is a gap. `monster`→`combat`, `rest_site`→`rest` |
| Public history and coverage | Adapter records observed commands and public results from run start/attachment | Same adapter-owned observation/accepted-action history | Not currently maintained for this contract; native private history is not a substitute |
| Combat round, energy, block | `CombatEngine.player`, `rules.round_number` | `CombatState` round and `PlayerCombatState.Energy`, creature block; HUD | Present in [combat DTO/reader](../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicCombatDecisionReader.cs); bridge round is already a public read |
| Player/enemy power instances, amounts/counters | Player statuses/powers/auxiliary counters and [monster public statuses](../game/headless/monsters/base.py); explicit public projection only | `Creature.Powers`, `PowerModel.DisplayAmount` and visible description; `NPower` displays counter-stack amounts | Missing from ordinary combat DTO; expose public display semantics, not every private power member |
| Enemy refs, IDs, HP/block | Stable slots and live/dead state in [CombatEngine](../game/headless/core/combat.py) | `combat.Enemies`, native creature identity maintained privately, public creature display | Reader compacts living-enemy indexes. Need persistent public refs and a current native target binding; index equality across backends is invalid |
| Intent categories, numeric damage/hits | [Intent](../game/headless/monsters/base.py) plus public damage modifiers, using displayed values rather than execution-only values | `NIntent.UpdateVisuals`; `AttackIntent.GetSingleDamage`, single/multi `GetIntentLabel` and `Repeats` match displayed labels | Reader currently emits intent categories only. Numeric label-equivalent projection is missing; no future move/state-machine access |
| Hand, draw/discard/exhaust, in-play/power cards | Player [piles](../game/headless/core/piles.py) and deck; preserve physical copies | `PlayerCombatState` piles and `NCardPileScreen.OnPileContentsChanged`: draw display sorts by rarity/ID, not draw position; discard/exhaust are inspectable | Hand is thin; full piles/cards absent. Native has five physical piles and no power-card pile: `powers` must be derived from public played-card history, or this profile is unsupported at attachment. Public sorting/identity must be independent of hidden order |
| Stars and Sovereign Blades | `rules.stars`, [Forge](../game/headless/cards/regent_effects.py) and each blade's public damage value | `PlayerCombatState.Stars`; `ForgeCmd` creates/updates multiple `SovereignBlade` cards and their displayed damage | Both absent. `sovereign_blades` lists card refs; there is no single shared Forge damage counter. Known empty before Forge |
| Osty presence/HP/block/powers | `rules.osty`, [Osty rules](../game/headless/core/osty.py). Current engine stores HP/max HP; its pet damage uses player block | `Player.Osty` creature/UI; known absence differs from an unavailable read | No existing bridge DTO. Headless has no independent pet block/power state; first profile may only claim its supported plain Osty shape, otherwise explicitly unsupported |
| Orb capacity, ordered orb identities and passive/evoke values | `rules.orb_slots`, `orb_order`, `orbs`, [orb effects](../game/headless/core/orbs.py) | `PlayerCombatState.OrbQueue`, `OrbModel` displayed amounts and `NOrb` | Absent. Preserve queue order, public Focus-adjusted values and per-orb Dark accumulation |
| Selection source/pile/options/selected/bounds/confirmation/cancel | [serializable choices](../game/headless/core/choices.py); map private source/effect metadata to visible cards only | `NCombatPileCardSelectScreen`, prefs, enabled card holders and accepted parent card | [Existing adapter](../bridge/Sts2AgentBridge/components/cards/combat_native/PinnedCombatCardChoiceAdapter.cs) supports discard/exhaust holders, bounds and toggles. Host must retain combat context, bind the public source and enrich option cards. Unsupported selectors are not this profile |
| Reward entries, values, duplicate card offers, resolved flags | [rewards](../game/headless/run/rewards.py), pending offers/modifiers and legal commands | Reward buttons and visible card-reward selector; existing [reward reader](../bridge/Sts2AgentBridge/src/Sts2AgentBridge/Adapters/Public/PinnedPublicRewardDecisionReader.cs) | Gold/item kinds and offer IDs exist. Card instance/modifier details and shared refs are missing. The current parent DTO already includes precomputed offer IDs; the new projection must withhold them until the actual child screen. Resolved entries have no payload; acquired items live in inventory |

All scalar fields are required where their containing object exists. Complex
fields use `Observed` to name missing producer support. Ironclad/Silent start
with no special resources; Regent requires Stars and blade references,
Necrobinder requires Osty state, Defect requires orb capacity/queue. Any character
can acquire the other resources. For a native-character baseline an unavailable
resource is unknown, never not-applicable. Attached history coverage and optional
unobservable origins remain explicit even in a ready decision.

## Candidate and dispatch mapping

A candidate contains only its `ref`, semantic `kind`, `subject` and `target`.
Each play/target pair is separate. The chooser returns a candidate ref from the
advertised decision. No commands are reconstructed from a card's definition ID.
Keep an opaque backend decision binding alongside the public value; dispatch must
receive that binding as well as the selected ref. Reusing `action:0` in another
decision cannot authorize a stale action. Reset/restore/attachment and a changed
decision invalidate old bindings. The headless dispatcher is implemented;
the native dispatcher is implemented by the owned `agent_v1` session.

| Candidate | Headless command through `RunEngine.apply` | Existing native route / integration requirement |
| --- | --- | --- |
| `play_card(card, enemy?)` | `PlayCard(instance_id, stable_target_slot)` | Core public combat applier with current hand/target indexes and decision ID; revalidate against exact bound entities |
| `end_turn` | `EndTurn()` | Existing core end-turn route |
| `select_card` / `deselect_card` | Both map to `ChooseCombatCard(instance_id)` after checking current selected membership | Combat-choice host `select:N` / `deselect:N`; preserve physical holder identity and parent session |
| `confirm_selection` | `ConfirmCombatSelection()` | Existing `confirm`; zero selection is legal when minimum is zero |
| `cancel_selection` | No current direct command for this first headless selector; do not advertise | Only advertise if the native capability owns and supports cancellation; current first case is not cancelable |
| `claim_reward(reward)` | `ClaimGold`, `ClaimPotion`, `ClaimRelic` as actually legal | Existing gold/item claim routes; nested item decisions require another supported context |
| `open_card_reward(reward)` | Adapter-owned presentation step over precomputed private offers; no claim, game command or RNG consumption | Existing `open:N` action; await/reconcile the real child screen before exposing offers |
| `choose_reward_card(reward, card)` | `ChooseRewardCard(definition_id, offer_index)`; preserve duplicate offer index | Existing card reward session and exact option; acquire policy choice at its real visibility/decision boundary |
| `skip_reward(reward)` | Ordinary card: `ChooseRewardCard(None)` | Actual card selector skip only when available; individual gold/item skip is not fabricated |
| `leave_rewards` | `LeaveRewards()` | Existing proceed/leave route with its native reconciliation |
| `choose_map_node(node)` | `ChooseNode(node_id)` | Existing map action applier; the agent client can opt into one map dispatch and stops after its native completion |

A card reward starts as `presentation="summary"` with all payload fields
not-applicable. `open_card_reward` identifies which reward to reveal; the child
changes to `presentation="choice"` with public cards. Only one child may be active,
and only its choose/skip actions are legal while it owns the decision. Parent
claims, leave and opening another reward cannot pass through that child. Multiple
unopened entries retain distinct reward refs, so the chooser controls their order.
Claim/skip resolves the child and returns to the parent. Resolved entries are
payload-free summaries; inventory/history own the acquired entity and result.

The headless adapter implements this explicit presentation state over its
already-generated private reward offers. Opening changes the public presentation
and decision binding without consuming RNG or applying a reward. Choosing then
uses the existing game command. This preserves native information timing and
does not create a second reward rule implementation. The chooser acts again
after the child becomes visible.

The engine's [legal command enumeration](../game/headless/run/flow.py) remains the
authority. The current [combat host](../bridge/Sts2AgentBridge/apps/bridge/client/combat_host.py)
has a nested `choice_provider`, but main combat follows its recommendation and
other controllers may mechanically choose follow-ups. The new agent session
exposes the same public-only policy at each supported decision, with owner-frame
reads, parent/child ownership, bounded execution and cleanup. Precommitted selections are equivalent
only when their information and decision timing match the interactive choice.

## Outcomes and execution reports

`sts_run_outcome_v1` describes the game/episode, independently of transport:

| Kind | Reason | Meaning for later Gym integration |
| --- | --- | --- |
| `victory` | `none` | Actual full-game victory; terminate, reward 1 |
| `defeat` / `abandoned` | `none` | Actual game ending; terminate, reward 0 |
| `truncated` | `decision_budget`, `time_budget`, `slice_complete`, `act_complete`, `external_stop` | External/authored cutoff; truncate, reward 0 |

Combat victory is an ordinary transition within a run, not a `RunOutcome` victory.
Use the engine's explicit [RunPhase](../game/headless/run/state.py) and native
ending evidence; errors never become fabricated losses or victories.

`sts_execution_report_v1` separates lifecycle from outcome. `pending/queued`
means accepted but unresolved; `reconciled/applied` means completion verified.
`rejected/none` covers invalid or confirmed stale actions, and
`unsupported/none` covers missing public fields/version/capability.
`uncertain/unknown` covers timeout/transport ambiguity and stops execution without
retry. `faulted` covers transport/deadline/cleanup failure with explicit mutation
knowledge; cleanup failure is never a successful handoff. Reasons and permitted
mutation states are enforced by the validator. A confirmed stale no-mutation
rejection may permit bounded re-observation; timeout alone does not prove that no
mutation occurred. Native wire, public schema, encoding and future trajectory
versions remain independent.

## Native producer

[`AgentPublicReader`](../bridge/Sts2AgentBridge/apps/bridge/native/AgentPublicReader.cs)
builds the same public contract directly from the pinned game's public fields in
the router's owner frame. Native objects, legacy action strings and opaque tokens
stay in private bindings. [`AgentSession`](../bridge/Sts2AgentBridge/apps/bridge/runtime/AgentSession.cs)
re-observes the rich state and exact bound objects before delegating to the existing
combat, choice, reward or map owner. A confirmed stale/no-mutation rejection permits
bounded re-observation. Uncertain dispatch, failed reconciliation or failed cleanup
stops the host without retry.

The new routes are GET `/probe/agent-v1/public/decision` and POST
`/probe/agent-v1/public/action`, on the existing authenticated transport. The
envelope has `schema_version: 1`, `protocol: agent_v1`, status, opaque decision/action
IDs, public observation, code/outcome, attempted/accepted/reconciled counts and
parent/child pending flags. A stale rejection instead carries
`mutation_state: none` and `reason: stale_decision`. These control fields never
enter the policy input. The existing bridge manifest version remains `1.0.0`.

The producer covers one single-player A0–A10 combat/reward/map slice, with at most
128 deck/combat cards, six living enemies, 64 powers per creature and 256 map
nodes. It publishes stable enemy identities, canonical hidden draw contents,
displayed numeric intents, visible map types/edges, public resource shapes and
attachment history. It withholds unopened reward offers. Public power-card
descriptors are frozen when cards enter the play area and retained after a public
play; the observer must therefore start before combat setup. It cannot reconstruct
earlier plays from private combat history. Global damage/block previews apply in
hand/play, following native preview behavior, rather than in draw/discard piles.

Coverage is deliberately explicit:

- Cards: five characters' Strike/Defend; Ironclad Bash, Neow's Fury, Anger, Cleave,
  Headbutt, Iron Wave, Pommel Strike, Shrug It Off, Twin Strike, Thunderclap and
  Inflame; Zap, Dualcast and Defy. Other cards, enchantments and afflictions stop
  this profile, including an unsupported card in a visible reward offer. This is
  not a claim of complete starter decks or arbitrary reward-pool support.
- Relics: the five starter relics, Strawberry, Pear, Mango, Golden Pearl and
  Nutritious Oyster. Their projected counters are empty; other relics stop the
  profile until their public semantics are mapped.
- Powers: Strength, Dexterity, Focus, Vigor, Vulnerable, Weak, Frail, Artifact,
  Poison, Doom, Ritual, Plating and Thorns. Amounts use native displayed values.
- Health: numeric native displays only, including invincibility displays that
  still show numbers. Hidden-number infinity and unknown display modes stop this
  profile before projection or pending-action reconciliation. The separate
  campaign combat schema 2 does not widen `agent_v1`.
- Owned potions, additional room/event decisions, unsupported selectors and
  item follow-ups stop explicitly. No legal candidate is silently removed to
  manufacture support. The reference chooser leaves optional potion drops.
- Expanded terminal reward schemas 9–10 remain outside this v1 profile and is
  rejected before pending-action reconciliation. Its larger native screen limit
  does not silently expand the shared slice.

[`LiveAdapter`](../bridge/Sts2AgentBridge/apps/bridge/client/agent_host.py) validates
the envelope and shared contract, passes only immutable `PublicDecision` values
to the same chooser, and retains dispatch uncertainty across lost/malformed
receipts and interrupts. The default run stops at an actionable map; explicit
map dispatch stops after one native transition. Limits are 180 seconds, 256
decisions, 4,096 reads and three confirmed stale re-observations, in addition to
the stricter existing native/session budgets. Slice completion is truncation,
not a run victory. A reported native defeat remains defeat on repeated reads.

Combat readiness and terminal observations remain gated by the exact accepted
native action's successful execution. A state change during an animation is not
reconciliation. Nested selection actions reconcile separately while their parent
remains pending; even after the selector closes, its parent must finish. Faults,
cancellation and unresolved cleanup stop the owner without a clean handoff.

The five-row [paired fixture](../bridge/Sts2AgentBridge/apps/bridge/client_tests/agent_pair.json)
compares full normalized public observations/candidate sets and deterministic
Neow's Fury transitions against both producers. It uses authored matching setups
and inert native API objects, not a game capture or matched-RNG proof. Native
projection, socket transport and failure-path fixtures are separate checks.
The [controlled live acceptance](evidence/AGENT_BRIDGE_M3_2026_09_23.md) passed
combat, Neow's Fury's two-card selection, gold collection/reward leave and a
separate map transition, followed by owned cleanup. The identical callback passed
headless first, using the shared chooser with a gold-then-leave reward override.
Live card-offer selection and wider content coverage remain unverified.

## Headless producer

[`HeadlessAdapter`](../game/agent/headless/adapter.py) owns synchronous public
observation and exact dispatch over an existing `RunEngine`. See the
[README example](../README.md#playing-and-implementing-the-game) for usage.

- `observe()` returns `DecisionFrame(decision, binding)` or a `RunOutcome` for
  an actual terminal engine phase. The frozen public decision is the only input
  to [`choose_action`](../game/agent/policy.py), which returns an advertised
  `Candidate`. The chooser is deterministic and makes no strength/win-rate claim.
- `step(binding, candidate.ref)` returns a validated execution-report shape.
  All gameplay commands go through `RunEngine.apply`; the single exception is
  the presentation-only open described above. Every accepted action consumes its
  binding, including open. Invalid/stale actions leave both gameplay and adapter
  history unchanged.
- Bindings are in-process opaque capabilities, separate from the public codec.
  The private snapshot digest and retained owned-root identities only guard
  dispatch. The [projection](../game/agent/headless/projection.py) directly reads
  allowlisted fields; it never filters a private snapshot into an observation.
- Use the adapter as the engine's sole command owner. `reset(engine)` creates a
  new attachment, clearing identities, presentation and history. An externally
  restored/replaced engine root invalidates outstanding bindings and starts a
  fresh attachment on observation. No adapter checkpoint/restore API is exposed;
  an engine checkpoint alone cannot restore its public history or bindings.
- History coverage is `attachment`. It records accepted public actions, exact
  selection toggles, observed combat endings and reward forfeitures. Leaving an
  already resolved reward list invents no skip event. This is not the future
  trajectory recorder. Combat-copy origins remain unknown unless public
  provenance is established; private `original_ids` mappings are not consulted.
- The virtual `powers` card pile contains frozen last-observed descriptions of
  cards played since attachment. Preexisting retained power cards at attachment
  raise `power_card_history`; later private changes to detached cards are not
  public previews. Live production must establish equivalent history.

The producer is deliberately bounded to the first integration slice. It does
not advertise a reduced subset when the backend also has an unsupported legal
command. It raises `UnsupportedProfile(capability)`, with an
`unsupported/none/unsupported_capability` report, before policy use. An unexpected
execution exception raises `AdapterFault` and stops the adapter: mutation may
have happened and the command must not be retried. This local failure is not
mislabelled as a v1 transport error or a game loss.

| Area | Implemented boundary / named remaining gap |
| --- | --- |
| Contexts | Ordinary combat; discard/exhaust selectors with toggles/manual confirmation or immediate single selection; base combat rewards; map choice. Potion commands, rest/shop/event/Ancient/act-transition commands, other selectors and extra reward batches raise `legal_action_family`, `selection_family` or `reward_family` |
| Cards | Explicit previews for simple attacks/fixed hits, block, draw, status/power amounts, pile choice, Neow's Fury, Silent discard, Stars/Forge/Blade, Summon/Unleash, fixed channel and evoke. [Preview allowlist](../game/agent/headless/cards.py) is authoritative. Enchantments, event variables, curse hooks, other operations/expressions and X costs outside combat are named unsupported gaps |
| Values | `damage`, `hits`, `block`, `draw`, named status/power amounts, `select`/`select_maximum`, `stars`, `forge`, `summon`, `channel_KIND`, `evoke`, fatal `max_hp`, end-turn damage/loss. Combat previews include supported Strength/Weak/Frail/Dexterity effects; Blade uses its own accumulated damage, Unleash includes Osty HP. Active keywords/afflictions are separate modifiers |
| Resources | Five starter shapes; off-character applicability, known zero/empty values, each Sovereign Blade, plain Osty presence/HP, and ordered Focus-adjusted orb values. Independent Osty block/power extensions raise `osty_public_powers` |
| Powers / enemies | Public status stacks and effective Strength, plus player Dexterity/Focus/Vigor. Enemy layouts: SimpleEnemy, Nibbit and ShrinkerBeetle, with stable slots and target-adjusted displayed intents. Other power displays or monster-specific powers raise `power_display` / `enemy_public_powers` |
| Inventory | All permanent card instances within preview coverage; physical potion slots; five starter relics and Strawberry/Pear/Mango/Golden Pearl/Nutritious Oyster with no dynamic counters. Other relic counters raise `relic_counters` / `combat_relic_counters`. Acquired reward cards/items retain their public refs |
| Map | Public room kinds, edges and native coordinates; authored coordinate-free fixture DAGs use depth and authored sibling order. Internal edge order and future encounter/event assignments are excluded. Non-room fixture termination markers are omitted; choosing such a marker is `fixture_terminal_command`. A missing map raises `run_map` |

[`test_headless_adapter.py`](../tests/agent/test_headless_adapter.py) executes the
Neow's Fury → nested selection → rewards → map slice through the same public-only
chooser and dispatches a subsequent map node. It also tests all five resource
shapes, duplicate card/offer identity, optional-zero selection, stale/illegal
rejection, reset/restore, read-only observation, hidden-state invariance, public
display modifiers and unsupported/fault boundaries. This is headless fixture
evidence, not live bridge execution or exhaustive native equivalence. The v1
schema and its declared limits remain unchanged.

## Full-run v2 profile

[`game.agent.contracts.full`](../game/agent/contracts/full.py) defines
`sts_public_decision_v2` / `full_run_v2`. Select it explicitly:

```python
from game.agent.headless import HeadlessAdapter
from game.agent.full_policy import choose_action
from game.headless.run.engine import RunEngine

adapter = HeadlessAdapter(RunEngine.campaign(character="defect", seed=2),
                          decision_profile="full_run_v2")
frame = adapter.observe()
choice = choose_action(frame.decision)
adapter.step(frame.binding, choice.ref)
```

This profile covers the current solo engine's command and pending-decision
families for all five characters, A0–A10, both Act 1 regions, Hive, Glory and
Architect. It is a public decision interface, not an exhaustive native-equivalence
claim or a guarantee that the demonstration policy wins. Rules remain entirely in
`game/headless/`. The full chooser imports only the public contract.

V2 uses immutable `Node`, `Field` and `Link` records for `run` and `context`.
Nodes have a mechanic kind, content identifier, optional entity reference, typed
scalar fields, entity links and ordered children. This accommodates existing
mechanics across card content without a per-card encoder registration. Fields
are explicitly projected by the producer; private snapshots, pending dictionaries,
continuation plans and arbitrary engine objects are never serialized into nodes.
The JSON codec requires exact record fields and validates versions, depth,
duplicate identities/keys, link resolution and candidate arguments. Entity refs
belong in links, not scalar fields. The ready graph permits 24 levels of child
nesting; outcomes retain the shared `sts_run_outcome_v1` schema.

Cards include the current resolved spec, immutable effect parameters, energy/star
costs, upgrades, enchantments and public modifiers. Draw piles and draw-backed
selectors use canonical public content order. Void Form's hand/play cost display
does not alter off-table previews. Detached played powers contain only retained
pre-play descriptions, labelled `observed_plays`; attachment cannot inspect an
unobserved power pile. Deck originals and combat copies remain distinct.

Relics expose `show_counter`, nullable `display_counter`, visible `status` and
specific tooltip values. Hook bookkeeping and undisplayed cumulative totals are
excluded. Powers expose their displayed amounts/counters; historical play/draw/HP
totals are not inferred at attachment. Enemy slots survive death and revival;
current intent icons and attack values remain visible, but future move damage
does not. An infinite HP display uses `infinite_hp=true` with null HP/max HP.
Stars, blade card values, Osty HP/max HP and ordered Focus-adjusted orbs use the
engine's current resource shapes; Osty shares player block in this engine.

Availability is explicit at each applicable boundary: null means no displayed
counter/value, empty children mean known empty, and unavailable attachment source
or transient status uses `unavailable_on_attachment`. History contains only
actions observed since attachment. The adapter retains Regal Pillow's rest status
through its own observed room actions; a late attachment after the rest result was
discarded reports that status unavailable rather than guessing.

Rewards have a presentation boundary. Parent rows show their kind and resolved
state; unopened card offers and removal options remain hidden. `open_reward` and
`close_reward` change only adapter presentation, consume the old binding and count
as reconciled decisions. They do not advance engine state or RNG. An open child
owns its candidates until choice, skip or close; parent commands are suspended.
The union of reachable presentation states maps exactly to the engine's legal
commands. Later relic-pickup queues, unopened chest contents, unchosen event plans
and unrevealed Crystal Sphere cells stay private. Repeated equal offers use new
surface identities. Parent identities survive nested pickup children, sibling
rerolls do not rename unaffected offers, and shop price changes do not replace
stock identities. Acquired items retain their public offer identity when the
chosen offer and visible inventory change establish the correspondence; generated
replacements for consumed potions receive new identities.

### Command and pending-surface coverage

Every command class in `core.actions` and `run.actions` is bound by
[`COMMANDS`](../game/agent/headless/full_projection.py); the fixture census fails
if either engine module adds a command without integration. Optional choices,
deselection, skipping and abandonment receive distinct public action kinds.

The native column distinguishes the accepted shared adapter from older feature
controllers. Those controllers are **not v2 observation/dispatch support**.
All v2 rows have headless projection, exact dispatch and lossless encoding within
the [finite profile](AGENT_ENCODING.md#full-run-profile-and-environment).

| Headless commands / pending surface | Fixture evidence | Native observation/action coverage | Live evidence |
| --- | --- | --- | --- |
| `PlayCard`, `EndTurn`; combat, Stars/Forge, Osty, orbs | Five-character selectors/resources and ordinary-HP campaigns; 1,075 card-level previews | `agent_v1` bounded content only | Controlled Ironclad slice only |
| `ChooseCombatCard`, `ConfirmCombatSelection`; manual/automatic selectors, toggles and zero confirmation | Exact-instance dispatch, draw-order invariance, source/operation/bounds and suspended potion choices | `agent_v1` discard/exhaust profile; broader selectors outside it | Neow's Fury zero/two choices |
| `UsePotion`, `DiscardPotion`; combat/anytime/automatic items | All 63 potion definitions, targeted use and child selectors; automatic-only items expose discard | No potion-use candidate in `agent_v1`; older replacement controllers do not establish general use control | Foul Potion event entry and replacement cases only |
| `ClaimGold`, `ChooseRewardCard`, `ClaimPotion`, `ClaimRelic`, `ChooseExtraReward`, `LeaveRewards`; main/extra/stolen/special rows | Modal visibility, exact upgrades, acquisition identity, skip/leave and nested pickups | `agent_v1` ordinary supported rewards; legacy extra/item controllers have separate bounds | Gold/leave in shared slice; legacy card/item/extra cases in [status](STATUS.md) |
| `RerollCardReward`, `SacrificeCardReward` | Driftwood reroll and Pael's Wing sacrifice | Outside `agent_v1` | No shared-profile evidence |
| `ChooseRelicCard`, `ConfirmRelicSelection`, `ChooseRelicReward`; select/card reward/card grid/potion/relic/bundle queues | Dolly's Mirror, Orrery repeated offers, Sea Glass, Scroll Boxes, Lost Coffer, scissors/Claws/Pael's Tooth/Toy Box | Legacy generic pickup surfaces partially supported; full v2 outside profile | Representative legacy selectors/grid/bundle paths only |
| `OpenChest`, `ClaimTreasureRelic`, `LeaveTreasure`; closed/open/resolved chest | Hidden pre-open contents and exact pickup continuation | Outside `agent_v1` | No v2 live evidence |
| `ChooseNode`; generated/authored maps, visible marks | Exact node dispatch, Fur Coat marks, both regions and multi-act transitions | `agent_v1` bounded map projection/action | Separate native map transition accepted |
| `Rest`, `Smith`, `Hatch`, `Lift`, `Dig`, `UseRestRelic`, `ChooseUpgrade`, `ChooseCookCard`, `ConfirmCook`, `LeaveRest`; options/smith/cook/hatched/resolved | All commands, Smith/Cook cancel, Cook pair and nested follow-up | Legacy `rest_v2`; Smith/Cook cancel and broader reward children excluded; outside `agent_v1` | Heal/Smith only; other six options offline |
| `BuyShopItem`, `BeginShopRemoval`, `ChooseShopRemoval`, `LeaveShop`; stock/removal | Prices, modifiers, exact purchase/removal/cancel; engine restocking | Legacy bounded shop controllers; outside `agent_v1` | Purchase/removal and selected restock cases only |
| `ChooseAncientRelic`; Neow offers | Exact offered relic and pickup continuation | Outside `agent_v1`; legacy event/Ancient path is separate | Console-selected legacy Ancient routes only |
| `ChooseEventOption`, `ChooseEventCard`, `LeaveEvent`; options/page/select_card/resolved/fight | All 65 events' initial branches plus bounded nested continuations, selected card operations and event combat resumption | Legacy generic event families; outside `agent_v1` | Representative pages/selectors/combat/resumption; no all-branch claim |
| Same event commands; event_rewards/card_rewards/potion_rewards/relic_reward/gold_reward/special_card_reward | Mixed rewards, multi-pick identity, current offers, duplicate items and terminal effects | Legacy bounded child controllers; outside `agent_v1` | Representative mixed/item/card results only |
| Same event commands; Crystal Sphere board and Trial confirmation | Uncovered fragments only, legal cell choices, explicit `abandon_run` outcome | Legacy specialized controllers; outside `agent_v1` | Representative Sphere and Trial cancel/confirm accepted |
| `ContinueAct`, final Architect option; act_complete/epilogue/terminal | Controlled three-act A0/A10 routes, second Glory boss and Gym reward 1 only after Architect | Outside `agent_v1`; legacy ending code exists | Architect admission has a known unresolved live failure |

[`test_full_profile.py`](../tests/agent/test_full_profile.py) checks the command
census against real legal commands, differential dispatch, serialization/tensor
roundtrips, non-mutating observations, stale bindings and rare/hidden-information
cases. [`test_full_gym.py`](../tests/agent/test_full_gym.py) covers all five characters
on both Act 1 regions at A0/A10 with normal HP, reproducible independent environments,
the Gym checker and separate controlled victory fixtures. These tests establish
the stated interface coverage; they do not enumerate every content permutation.

The full v2 policy cannot attach to `agent_v1`. Complete v2 native observations,
potion control, cancellation, wider reward limits and full-run orchestration
remain outside the current live profile. The native release and its original
live evidence are retained unchanged.
