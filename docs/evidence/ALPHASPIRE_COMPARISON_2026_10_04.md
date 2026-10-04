# AlphaSpire comparison with StS Agent

Research recorded on 2026-10-04 to preserve the comparison with AlphaSpire and
identify useful experiments for this project. This is a dated research reference;
the [roadmap](../../ROADMAP.md) remains the source of current priorities.

**The main architectural difference is combat search and the training data it
produces.** AlphaSpire uses a neural network to guide simulations before choosing
a combat action, and its combat training interface supports learning from the
search's action preferences. Our current learned policies score legal actions
directly, with imitation followed by PPO. AlphaSpire also has a separate learned
policy for decisions outside combat.

Search, the separation of combat and macro learning, and training exposure are
plausible explanations for its reported strength. This inspection does not isolate
their contributions experimentally. The released Ironclad networks are small,
which makes network size alone a weak explanation of the apparent performance gap.

## Evidence and scope

The comparison used these sources:

- AlphaSpire **v0.2.1**, source commit
  [`9774eca833588cae88dea01f34422a8b0758cf14`](https://github.com/AlphaSpire2/alphaspire/tree/9774eca833588cae88dea01f34422a8b0758cf14).
  The release was published on 2026-10-03. Source links below are pinned to this
  revision rather than the changing default branch.
- The JSON metadata and ONNX graphs in the release asset `ckpts-v0.2.1.zip`,
  available from the [release page](https://github.com/AlphaSpire2/alphaspire/releases/tag/v0.2.1).
- The author's [release announcement](https://www.reddit.com/r/slaythespire/comments/1wx0okp/releasing_my_sts2_engine_alphaspire_ironclad_wr/).
  Its text was available through search retrieval; the attached benchmark charts
  were not inspected. Exact per-setting chart values are therefore not recorded.
- Our working checkout based on `c9f1802cac23b97641c5dd2cad7e64c701cf1907`, including
  uncommitted representation, catalog, and experiment documentation changes
  present on 2026-10-04. The base commit alone does not reproduce that working
  tree. Local links below point to the files that owned those findings.

Both projects target Slay the Spire 2 **v0.107.1** in the inspected material.
AlphaSpire's stated product goal is retrospective run analysis, similar to
reviewing a chess game. Our [target](../TARGET.md) is an autonomous player that
optimizes complete-run victory probability. They share the central gameplay
problem, while their immediate product goals differ.

We inspected source and released model structure, but did not run AlphaSpire or
reproduce its benchmark. The separate trainer was not included in the inspected
repository, and the author described the simulator as closed source. The public
code establishes the intended search and data interfaces; it does not provide a
complete independent audit of simulator fidelity, belief sampling, or training.

## Reported performance and our baseline

| Result | Population and endpoint | Evidence |
| --- | --- | --- |
| AlphaSpire approximately 90% at A1 | Ironclad complete runs | Author-reported headline |
| AlphaSpire approximately 15% at A10 | Ironclad complete runs | Author-reported headline |
| Our 250k checkpoint 56/256, or 21.88% | Ironclad A0 Act 1 completion, 128 starts per region | Recorded held-out evaluation |
| Our initializer 23/256, or 8.98% | Same paired Act 1 starts | Recorded held-out evaluation |
| Our heuristic 14/256, or 5.47% | Same paired Act 1 starts | Recorded held-out evaluation |

The author reports 100 runs at each ascension from A0 through A10 for the tested
resolver settings, except that the expensive 512-iteration/32-candidate setting
was run at only three ascensions. The headline percentages should not be assigned
to a specific search setting without reading the charts. These are estimates
from finite samples, not established population win probabilities.
[Announcement](https://www.reddit.com/r/slaythespire/comments/1wx0okp/releasing_my_sts2_engine_alphaspire_ironclad_wr/).

Our September 30 test was a full-run-policy checkpoint evaluated only through
the Act 1 boundary. It is not a result for the newer combat specialist. Its
observed improvement over the initializer was 12.89 percentage points; the
predeclared conservative interval was -4.09 to +29.87 points, retaining the
protocol's formal `inconclusive` conclusion. These figures must not be substituted
for complete-run win rates or pooled with reused development cases.
[Test description](../AGENT_TRAINING.md#held-out-act-1-test-2026-09-30),
[retained evidence](act1_heldout_250k_2026_09_30.json).

If reproduced under the reported conditions, AlphaSpire's results would represent
a substantial advance over our current demonstrated playing strength. A numerical
head-to-head comparison still needs matched endpoints, game settings, cases,
information access, and inference budgets.

## Architecture comparison

| Component | AlphaSpire | Our system at the inspection date |
| --- | --- | --- |
| Combat action selection | Neural-guided belief Monte Carlo tree search | Direct masked policy scoring, with greedy or sampled selection |
| Combat learning | Search-generated policy targets and fight-value targets for expert iteration | Imitation warm-up followed by PPO; teacher and reward experiments |
| Decisions outside combat | Separate macro policy trained with PPO over a frozen combat resolver | Full-run PPO is available; current combat studies use a fixed noncombat heuristic for hybrid Act 1 checks |
| Ironclad model | Embeddings, pooled token features, and feed-forward layers | Graph actor-critic; richer combat features and alternative pooled/attention models have been tested |
| Simulator | Rust `sts2sim` dependency | Independent Python `game/headless` engine |
| Practice distribution | Fight library with resampled setups and explicit class mixes | Campaign-derived frozen openings and later-turn starts, split by source campaign |
| Integration emphasis | Generate and analyze recorded runs | Headless training plus the existing live-game observation/control bridge |

Our implementation and current scope are described in the
[training guide](../AGENT_TRAINING.md), [model source](../../game/agent/training/model.py),
[project overview](../../README.md), and [target](../TARGET.md).

## Combat search

AlphaSpire's combat network provides a prior distribution over candidate actions
and a value estimate for the position. Search applies actions in simulated worlds,
uses network values at newly expanded leaves, and propagates those evaluations
back to compare the actions available now. Actual fight endings are scored by
the combat objective. It does not need to finish every simulated fight before
getting an estimate.

The default learned resolver uses Gumbel selection. It draws a shortlist of root
actions using the policy prior, allocates simulations among them, and repeatedly
eliminates weaker candidates so the remaining budget concentrates on survivors.
The repository also implements a UCT selection alternative.
[Search](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/search.rs),
[combat resolver](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/actor.rs).

The README suggests 16 iterations for fast macro-training rollouts and 64 for
benchmarking, with 16 root candidates by default. Larger budgets support deeper
analysis. Iterations count simulated searches; they are not a fixed number of
moves or turns of lookahead. More search consumes more inference-time compute,
and neither finite search nor a learned value function guarantees a better real
outcome on every decision.
[Usage and budgets](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/README.md).

For Vantom, search can compare card orders, simulate their effects on Slippery,
and evaluate the resulting positions. Our direct policy must learn to prefer
useful sequences through its weights. Our
[action-preview experiment](../AGENT_TRAINING.md#vantom-action-preview-experiment)
supplies some immediate damage and stack consequences for supported attacks, but
does not compare multi-action continuations. This example explains a mechanism;
it is not evidence from a paired AlphaSpire-versus-our-agent Vantom test.

## Hidden information

AlphaSpire's public search wrapper constructs a belief state from visible
information, samples a possible hidden world for each rollout, and keys search
nodes by observations. Its combat search stops at the fight boundary, beyond
which that combat belief model does not claim to sample fairly. A separate
`TrueState` mode is explicitly privileged and used for coverage/debugging; it is
not the belief-based training path.
[Environment boundary](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/env.rs),
[training boundary](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/training.rs).

The design is consistent with our public-information requirement. Its actual
erasure and sampling are implemented in the simulator dependency, which was not
audited here. For our own search experiment, cloning the true private engine
snapshot and searching its future would violate [our target](../TARGET.md), even
if the neural network itself only received public observations. The entire
planner must operate on appropriately sampled or reconstructed public states.

## Learning from search

The public combat data interface records the observation, legal actions, the
search's improved action distribution, and the fight's eventual value. It can
also record a root-value estimate and the spread between action values. Together
these support the expert-iteration loop:

1. Use the current network to guide search.
2. Record search-informed action preferences and outcomes.
3. Train a network to imitate those preferences and predict value.
4. Use the updated network to guide subsequent search.

This gives a possible source of better supervision than the current policy's
own action samples. Our PPO primarily updates from actions actually selected and
the rewards that followed; comparing alternatives at the same position is not
part of its present decision process. Search can therefore help both action
selection and training data quality, although the benefit depends on search
quality and value calibration.
[Sample format and semantics](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/training.rs).

The repository also supports optional counterfactual branches, including testing
low-prior alternatives and ending a turn while a useful attack remains available.
These can expose positions ordinary self-play avoids. Their presence in the
code does not establish how much they contributed to the released checkpoints.
[Counterfactual implementation](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/search.rs).

## Separate macro learning

The macro actor handles routes, card choices, shops, rests, events, and other
noncombat decisions. It samples its actions during PPO data collection and hands
combat to a frozen resolver. Keeping that resolver fixed within a generation
gives the macro learner a stable combat policy to plan around and removes card
plays from the macro actor's decision sequence.
[Macro actor](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/actor.rs).

The announced deployment uses direct macro-policy decisions without macro
search. The repository additionally contains optional act-level search; that
capability should not be attributed to the reported benchmark setup. Our project
already supports separate combat checkpoints in hybrid evaluation, but its
current noncombat controller is fixed. Our existing full-run learner is not the
same as a dedicated macro-only learner over a frozen searched resolver.
[Run command](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/cli/run.rs),
[our combat workflow](../AGENT_TRAINING.md#campaign-derived-combat-training).

AlphaSpire's released Ironclad macro checkpoint names `run-return-v1`: the current
implementation pays 0.1 per floor of progress, +10 for victory, and -5 for defeat.
Optional additional reward components are supported but are not implied by that
checkpoint's reward identity.
[Run rewards](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/reward.rs).

## Model size and training exposure

Inspection of the released Ironclad ONNX graphs found pooled token features and
feed-forward layers, without self-attention. Each of the inspected combat and
macro models has **263,746 stored parameter elements**, counted by summing the
ONNX initializer dimensions. Metadata specifies embedding width 64 and hidden
width 128. Some other character models include attention, so this observation
should not be generalized to every AlphaSpire checkpoint.

| Inspected model or experiment | Parameters |
| --- | ---: |
| AlphaSpire `ironclad-combat-a5-gen15` | 263,746 |
| AlphaSpire `ironclad-macro-a1-u1688` | 263,746 |
| Our legacy rich-combat graph in the catalog pilot | 97,058 |
| Our graph with expanded catalog vocabulary in that pilot | 222,866 |

The comparison is per network, not total compute: AlphaSpire has two separately
trained models and repeatedly evaluates the combat model during search. Our
counts come from the [catalog representation pilot](../AGENT_TRAINING.md#vantom-catalog-representation-pilot-2026-10-04).
Similar parameter counts do not imply equivalent representations or training.

The released Ironclad combat metadata records **2,198,810 samples**, **25 epochs**,
and 219,637 held-out samples. Its macro metadata records **23,032 cumulative
episodes** for the recorded training chain, with an earlier warm start. These
fields do not establish lifetime totals across all earlier generations or
independent games. They also cannot be compared one-for-one with our PPO decision
budgets: samples, episodes, epochs, and search simulations are different units.
[Released model bundle](https://github.com/AlphaSpire2/alphaspire/releases/tag/v0.2.1).

The supported inference is that substantial training exposure accompanies a
modest model. This is not an ablation proving that architecture changes are
irrelevant, nor a basis for assuming a larger Transformer is required.

## Other useful design choices

- **Action features:** the encoder includes target-specific damage previews,
  fraction of target HP removed, kill indicators, event effects, and summaries
  of reachable room types for map choices. This supplies useful distinctions
  directly to the scorer. Our richer features and previews move in a related
  direction, but their current scopes differ.
  [Encoding](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/encoding.rs).
- **Fight libraries:** training can reuse a combat setup with different hands
  and an explicit mix of ordinary fights, elites, bosses, and later acts. Exact
  states are also supported for paired evaluation. An optional forced-win
  harvesting mode creates later-game practice setups and labels their origin;
  this is training-data machinery, not evidence that scored benchmark wins were
  forced. Its use in the released training history was not established.
  [Library](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/library.rs),
  [harvesting options](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/cli/run.rs).
- **Action abstraction:** plans combine operations such as freeing a potion
  slot and taking a replacement, or opening a selection screen and choosing an
  answer. Certain free rewards are collected before consulting the policy.
  These reduce navigation decisions and avoidable loops. Our commit-selection
  and reward-navigation policies address related issues.
  [Plans](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/plan.rs),
  [our policy actions](../AGENT_TRAINING.md#shared-policy-actions-and-selection-order).
- **Combat resource pricing:** the default combat objective scores a surviving
  exit as `(1 + remaining_HP_fraction + 0.1 * held_potions) / (1 + 0.02 * turns)`;
  defeat scores zero. This values HP and potions and discourages stalling. Our
  campaign-derived combat objective defaults to `1 + 0.1 * remaining_HP_fraction`
  on victory. Neither objective is itself complete-run victory probability.
  [Combat objective](https://github.com/AlphaSpire2/alphaspire/blob/9774eca833588cae88dea01f34422a8b0758cf14/src/objective.rs).

Rust and CPU ONNX inference make a different engineering tradeoff from our
Python/PyTorch stack. No matched throughput measurement was performed, so this
comparison makes no numerical speedup claim and does not establish that a
simulator rewrite is necessary.

## Proposed experiment for this project

The most informative next architectural test is **combat search around a frozen
existing model**, followed by learning from its decisions if search helps. This
is a recommendation, not an accepted roadmap change or an implemented feature.

1. Establish a small combat search path that respects public information and
   uses existing engine rules. Sample hidden uncertainty without reading the
   authoritative future. Check this boundary before interpreting performance.
2. Compare direct policy play with fixed search budgets such as 16 and 64
   iterations on the same frozen development fights, using identical objectives
   and noncombat control. Record wins, remaining HP, potion use, latency, and
   simulation counts; report policy-only and searched results separately.
3. If search produces reliable gains, collect search targets only from training
   fights and fit a student policy. Evaluate the student with and without search.
   Keep a fresh test population for the selected comparison.
4. Once combat improves consistently, test a dedicated macro PPO policy with
   that combat resolver held fixed. Measure integrated Act 1 progress before
   making a complete-run strength claim.

Our current critic predicts performance under its training objective and policy;
using it at searched positions may expose extrapolation errors. Search latency,
belief quality, and value calibration therefore need measurement. A failed small
pilot would not by itself distinguish those causes, and a successful pilot would
not establish AlphaSpire-level full-run performance.

## Artifact reference

The inspected release bundle was `ckpts-v0.2.1.zip` from
[AlphaSpire v0.2.1](https://github.com/AlphaSpire2/alphaspire/releases/tag/v0.2.1).
Its SHA-256 was
`ee93bcb056fa137cf4e6e3c4a4ade4990b8b3fdec009f6dd0baf774b29b16cfc`.
The exact Ironclad files inspected were the `.json` and `.onnx` pairs named
`ironclad-combat-a5-gen15` and `ironclad-macro-a1-u1688` inside that archive.
Weights were inspected as data; no downloaded model or executable was run.

No implementation, training, benchmark rerun, or roadmap change was performed
for this comparison. Future results should be recorded separately and linked
from the relevant current guide rather than silently updating these dated claims.
