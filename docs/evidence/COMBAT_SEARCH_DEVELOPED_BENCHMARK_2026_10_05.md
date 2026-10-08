# Developed-deck combat search benchmark

Date: 2026-10-05 (Europe/Amsterdam). **Development evidence; search remains experimental.**
On 32 predeclared harder starts, greedy won **22**, root-only search **24**, and
Gumbel search **23**. Gumbel rescued two greedy losses and lost one greedy win.
The 16 easier controls were won by every controller. This population reveals
changed outcomes and a concrete ordering dependency, but does not establish a
reliable search improvement or an Act 1 win rate.

The [public benchmark definition](../../configs/training/search_developed_decks.json)
owns inventories; the [training guide](../AGENT_TRAINING.md#experimental-combat-search)
owns usage. The [evidence extract](combat_search_developed_benchmark_2026_10_05.json)
binds the protocol, declared inventories, checkpoint, public trajectories, targets,
calibration and results. Local raw artifacts and reproduction scripts are under
`runs/search-developed-benchmark-20261005/`.

## Why replace the starter benchmark?

The [previous 128-start test](COMBAT_SEARCH_BENEFIT_2026_10_04.md) used five Strikes,
four Defends and Bash, without potions. It established search coverage and latency,
but mostly separated straightforward wins from difficult losses. Its unchanged
win outcomes were weak evidence about the usefulness of strategic planning.

This benchmark uses developed decks with upgrades, draw, targeted exhaustion,
discard placement, block conversion, persistent strength, multi-hit attacks and
potions. It reuses `declared_combat` and ordinary engine transitions; no card,
enemy, damage or turn rules were implemented in benchmark code. The evaluator
creates the actual fight from the declared inventory. Search receives that same
public declaration and reconciled observations, with its own simulation randomness.
Neither the actual engine nor its private RNG/order is given to the planner.

## Inventories and calibration

Every start is Ironclad A0 at 80/80 HP, with Burning Blood, 99 gold, one additional
relic and one potion in three slots. Relic counters are explicitly zero. Cards
are fresh templates; `+` means one upgrade. Inventories are authored, not recovered
from a campaign, and do not assert a typical late-Act-1 deck distribution.

| Profile | Deck | Additional relic | Potion |
| --- | --- | --- | --- |
| draw_order (15 cards) | 5× Strike, 4× Defend, Bash+, Pommel Strike+, Shrug It Off, Headbutt, Iron Wave, Thunderclap | Bag Of Preparation | Swift Potion |
| block_conversion (14 cards) | 4× Strike, 4× Defend, Bash+, Shrug It Off, Body Slam+, Flame Barrier, Impervious, Iron Wave | Anchor | Block Potion |
| strength (15 cards) | 5× Strike, 4× Defend, Bash+, Inflame, Twin Strike+, Pommel Strike, Shrug It Off, Uppercut | Nunchaku | Strength Potion |
| exhaust_draw (15 cards) | 4× Strike, 4× Defend, Bash+, Burning Pact, True Grit+, Pommel Strike+, Hemokinesis, Shrug It Off, Headbutt | Anchor | Energy Potion |

Calibration used all four decks against Slimes, Bygone Effigy, Vantom and
Lagavulin Matriarch: 32 starts, two seeds per family, with the frozen greedy
network, existing heuristic and random-legal reference. No search was used to
screen families. Keep a family if either greedy or heuristic completed a win.
This retained 12 families and excluded draw/order–Vantom, draw/order–Matriarch,
block–Matriarch and exhaust–Matriarch. These exclusions indicate no demonstrated
win in two calibration seeds, not proven impossibility. No inventory was tuned
after those calibration outcomes.

The strength deck won both calibration Vantom and Matriarch starts with the
network. The block deck won one Vantom start. The exhaust deck had a Vantom
heuristic win at 7 HP where the network lost. This provides examples of
recoverable fights while keeping the comparison independent of search outcomes.
Calibration and benchmark seeds are disjoint. The selected population is a
capability diagnostic, not an unbiased sample of all campaigns.

The preliminary diagnostic harness labeled trajectory policy metadata with the
generic demonstration identity. Calibration was replayed with correct policy
identities; all 96 public transition sequences and outcomes matched exactly.
Original exploratory files are retained; the verified recordings supply this
evidence. The production paired evaluator already recorded the correct policies.

## A concrete ordering witness

In the block-deck Vantom calibration fight, round 5 begins this decision with
71 HP, three energy and zero block. The frozen greedy policy plays **Impervious**
before **Body Slam+** and eventually wins at **12 HP**. Replay the identical
public prefix, choose the advertised Body Slam+ action first at decision 16,
then resume the same frozen greedy policy: the fight ends in defeat. The public
position and prefix equality were checked, and the intervention has a distinct
recorded policy identity. Both fights ended on turn 14 through ordinary rules.

The witness was found in a separate exploratory ordering diagnostic and then
reproduced. It is not a search win or a held-out example. A separate bounded
40-alternative probe on the exhaust/Vantom loss found no single-action recovery;
its heuristic whole-fight win should not be presented as a one-action fix.

## Frozen comparison

Before search gameplay, freeze checkpoint SHA-256
`e22bd23bc0783d67e081816c4066f04a65f2eb1d22be96b19677e0634dbc4862`, the unchanged-weight
normalized initializer at `runs/direct-search-learning-student-20261004/initial.sts-model`.
Its input view is `detached_combat_history_cards_v1`, its action restriction is
`commit_decisions_v1`, and the objective remains victory plus 0.1 times final
winning HP fraction after combat cleanup; defeat is zero. No training occurred.

Use validation indices 21,000–21,047: four fresh starts for each declared family,
cycling the 12 scenarios in manifest order. Each triplet shares the exact same
public opening and actual game seed; planner randomness remains separate. All
pairs are retained. Deck profiles have different totals because the number of
calibration-qualified encounters differs. The 32 `challenge` starts are the
primary comparison; 16 Slimes `control` starts and overall results are descriptive.

Both searched controllers use `direct_belief_v1`, 64 simulations, depth 16,
two particles, 1,024 proposals, 2,048 recovery proposals, 16,384 replay steps,
five-second search/belief ceilings and planner seed zero. Exploration is off.
A separate fight limit is 160 decisions / 600 seconds. Four CPU workers each
own one game and use one Torch thread. There is no outcome-adaptive extension,
search retuning, training, campaign evaluation, held-out opening or promotion.

| Controller | Harder starts | Easier controls | Overall | HP on harder wins | Harder mean return |
| --- | ---: | ---: | ---: | ---: | ---: |
| Greedy network | 22 / 32 | 16 / 16 | 38 / 48 | 38.59 | 0.72066 |
| Root-only search, 64 | 24 / 32 | 16 / 16 | 40 / 48 | 36.79 | 0.78449 |
| Gumbel tree search, 64 | 23 / 32 | 16 / 16 | 39 / 48 | 38.22 | 0.75309 |

Every planned fight terminated: zero episode cutoffs, failures or omissions.
Gumbel's paired challenge difference is **+3.125 percentage points** with the
existing conservative source-fight Hoeffding 95% interval **[−44.89, +51.14] pp**.
Root-only has **+6.25 pp**, interval **[−41.77, +54.27] pp**, with two rescued
losses and no lost greedy wins. These wide intervals do not establish improvement
or establish that root-only is better than Gumbel. HP on wins is conditional and
descriptive. All controllers consumed the potion on every challenge start;
this combat objective does not charge for losing that potion's future campaign value.

| Deck profile | Encounter | Greedy | Root-only | Gumbel |
| --- | --- | ---: | ---: | ---: |
| draw_order | Slimes | 4/4 | 4/4 | 4/4 |
| draw_order | Bygone Effigy | 4/4 | 4/4 | 4/4 |
| block_conversion | Slimes | 4/4 | 4/4 | 4/4 |
| block_conversion | Bygone Effigy | 3/4 | 4/4 | 4/4 |
| block_conversion | Vantom | 1/4 | 1/4 | 1/4 |
| strength | Slimes | 4/4 | 4/4 | 4/4 |
| strength | Bygone Effigy | 4/4 | 4/4 | 4/4 |
| strength | Vantom | 2/4 | 3/4 | 3/4 |
| strength | Lagavulin Matriarch | 4/4 | 4/4 | 3/4 |
| exhaust_draw | Slimes | 4/4 | 4/4 | 4/4 |
| exhaust_draw | Bygone Effigy | 4/4 | 4/4 | 4/4 |
| exhaust_draw | Vantom | 0/4 | 0/4 | 0/4 |

The Gumbel gains were one block/Effigy and one strength/Vantom fight. Its
regression was a strength/Matriarch fight. Exhaust/Vantom had a calibration
witness but no win on these four fresh starts; it remains included in the frozen
denominator. These differing outcomes are useful cases for inspecting critic
estimates and tactical choices before changing the search algorithm.

## Coverage, latency and validation

Gumbel searched **877/877 eligible decisions**, plus 271 forced actions;
root-only searched **882/882**, plus 264 forced actions. Every eligible decision
completed all 64 simulations. There were no belief fallbacks or search cutoffs.
Four-worker Gumbel latency including public belief updates was mean
1.380s, p95 1.733s, maximum 2.018s. Root-only was mean
0.782s, p95 0.956s, maximum 1.114s.

The four preregistered serial Gumbel repeats used the first scenario of each
profile (Slimes controls). Their full public trajectories matched the original
runs. Across 41 eligible actions, serial latency was mean 1.166s,
p95 1.363s, maximum 1.484s. These timing repeats are not
additional efficacy cases and do not by themselves characterize boss latency.
The measured per-action times met the five-second target in this panel.

Validation covered all **144 main episodes**, **3432 transitions**,
**2294 search targets**, all 48 paired openings, the four serial
repeats and all 96 verified calibration trajectories. Legal target support,
probability normalization, chosen-action mapping, declared anchors, completion
records, teacher/objective identity and source groups were checked.
The focused regression suite passed **122 tests in 36.12 seconds**. One independent
semantic review found no blockers; its distinct cancellation check confirmed
planned denominators and separate benchmark tracking identities.

Measured elapsed times: initial calibration 36.81s,
verified calibration 42.83s, paired comparison
522.56s, serial repeats 48.81s,
and evidence validation/extraction 20.36s.
Implementation and review were not separately timed. No release or native launch
was performed. Source build `97fec423ce0a860b6da1d9483455b003382f63f093d13cf4816f0d0fff08afdf`; engine rules `8eaf44ce4600e6b25a1675aa41e181027aed519f1bebfbeb5089b74406b77e8a`.

## Follow-up decision diagnosis

A follow-up diagnostic kept the checkpoint, engine, belief implementation and
search configuration frozen. It selected all three outcome-discordant development
fights and all eight meaningful Gumbel-versus-actor disagreements on their Gumbel
trajectories; four changes between interchangeable card references were excluded.
The [diagnosis supplement](combat_search_developed_diagnosis_2026_10_05.json) binds
its frozen protocol, all positions, artifact hashes and validation. Raw scripts,
public recordings and owner-only evaluator audits are retained under
`runs/search-developed-benchmark-20261005/diagnosis/`.

The public-only audit reproduced all **92 original Gumbel decisions**, including
action, probabilities, values, visits and simulation counts. At each selected
position, it compared the actor's action, recorded Gumbel action and a fresh
root-only recommendation using **32 paired sampled worlds**, followed by the
same frozen greedy policy. Identical first-action recommendations shared their
continuation: there are 768 arm records but **544 distinct sampled action
continuations**, all completed. These are samples from the existing approximate
public belief, not reads of the true hidden order or an exact-posterior guarantee.
The diagnostic left the maintained belief and its RNG unchanged.

A separate evaluator used the original private replay seeds to run three exact
Gumbel controls, eight one-action actor substitutions followed by unchanged
Gumbel, and sixteen paired first-action variants followed by the greedy policy.
Only the evaluator read those seed records; every chooser received the ordinary
public declaration, observation and history. All **27 fights completed**. The
controls reproduced the original public trajectories exactly, and every
intervention preserved the identical public prefix. Recorded search
recommendations remain separate from the one deliberately executed actor action;
these are diagnostic validation trajectories, not teacher targets or PPO data.

### What changed the outcomes?

**Effigy: build block before Body Slam+.** At decision 28 (round 8), the player
has 3 HP and no block; the vulnerable enemy has 11 HP. Search plays Shrug It Off,
then Body Slam+ ends the fight, followed by Burning Blood healing to 9 HP.
Replacing just Shrug with the actor's Body Slam+ loses, even when search resumes.
The same contrast holds with greedy continuation. The public sampled-world
continuations win 32/32 after Shrug versus 11/32 after Body Slam. Reversing the
earlier potion/Shrug order at decision 0 leaves the searched outcome unchanged.

**Vantom: spend an attack to remove Slippery.** At decision 15 (round 5), the
player has 62 HP, one energy and four strength; Vantom has two Slippery stacks.
Search chooses Strike over the actor's Defend. Strike deals only one immediate
damage but removes a Slippery stack and advances Nunchaku. In the paired actual
continuations, this costs five HP at the next enemy turn but lets the next
Twin Strike+ deal 17 damage instead of two. Vantom has 134 HP after that turn
instead of 150, and Nunchaku's later energy trigger occurs earlier. Strike wins
at 13 HP; substituting Defend loses under both tested continuation policies.
The public sampled-world result is a smaller 28/32 versus 26/32 advantage, with
four samples won only after Strike and two won only after Defend. The later
Shrug/Strike ordering disagreement at decision 27 changes neither actual outcome.
This identifies a useful sequence in this fight, not a general rule to attack
instead of block or evidence of knowledge of the actual draw order.

**Matriarch: play Inflame instead of taking immediate damage and draw.** The
opening divergence alone does not explain the regression. At decision 5
(round 2), after Bash+, the player still has 80 HP, one energy and two strength.
The actor and root-only baseline prefer Inflame, but Gumbel chooses Pommel
Strike. Substituting only Inflame and resuming search turns the defeat into a
**22-HP win**. With greedy continuation, Inflame wins at 27 HP and Pommel loses.
Public sampled worlds produce 30/32 wins for Inflame versus 21/32 for Pommel:
nine wins occur only after Inflame and none only after Pommel.

At that Matriarch position, the tree gives Pommel an estimated return of 1.0091
versus Inflame's 0.9780. Root-only estimates favor Inflame, 0.9610 versus 0.9414;
the actor gives it about 73% prior probability. The completed greedy-continuation
means are 0.9584 for Inflame and 0.6712 for Pommel. This isolates a costly reversal
introduced by deeper search and motivates checking continuation evaluation and
optimistic leaf estimates. It does **not** prove a backup-rule bug or isolate the
critic as the sole cause: tree values and greedy-continuation returns have
different continuation policies. No search internals were changed by this audit.

All selected positions are retained below. Decision indices are zero-based;
win HP includes combat cleanup. The middle columns use the same original
Gumbel prefix and actual seed, with a frozen greedy continuation after the named
first action. Each final-column substitution instead resumes unchanged search.

| Fight / decision | Gumbel action / actor action | Gumbel action then greedy | Actor action then greedy | Actor once, then Gumbel |
| --- | --- | --- | --- | --- |
| Matriarch / 0 | Uppercut / Shrug It Off | Win, 8 HP | Win, 8 HP | Defeat |
| Matriarch / 1 | Twin Strike+ / Shrug It Off | Win, 27 HP | Win, 8 HP | Defeat |
| Matriarch / 5 | Pommel Strike / Inflame | Defeat | Win, 27 HP | Win, 22 HP |
| Matriarch / 22 | Pommel Strike / Bash+ | Defeat | Defeat | Defeat |
| Effigy / 0 | Block Potion / Shrug It Off | Defeat | Defeat | Win, 9 HP |
| Effigy / 28 | Shrug It Off / Body Slam+ | Win, 9 HP | Defeat | Defeat |
| Vantom / 15 | Strike / Defend | Win, 13 HP | Defeat | Defeat |
| Vantom / 27 | Shrug It Off / Strike | Win, 13 HP | Win, 13 HP | Win, 13 HP |

### Diagnostic validation and limits

Validation checked all 27 identities/reward sidecars and **810 transitions**.
Across the 11 searched controls/variants, 245 eligible decisions completed all
64 simulations and 87 actions were forced; none fell back or hit a search limit.
There were exactly eight declared differences between recommended and executed
actions. One independent semantic review found no remaining information-boundary,
RNG, ownership or provenance blocker.

The first diagnostic harness returned decoded recorded candidates for replay
prefixes. The existing environment correctly rejected those objects before any
game action. Fourteen jobs produced only a header and no transitions. The harness
was corrected to resolve the action to a currently advertised candidate after
checking public-prefix equality. Only those fourteen jobs were rerun, in separate
artifact directories; all failed partials and thirteen successful first attempts
were preserved. No production ownership safeguard was changed or bypassed.

Measured elapsed times: public audit 184.84s, corrected greedy retries 5.46s,
and final artifact validation 3.70s. The independent final artifact check took
1.62s. Initial intervention wall time and total implementation/review time were
not separately captured; the recorded per-episode durations sum to 327.17s and
are not wall time. No training, release, native launch or held-out evaluation
was performed. Production source and checkpoint identities remain unchanged.

These are selected development examples and fixed-seed causal comparisons under
specified continuations. They explain particular wins/losses, not a new win-rate
estimate or a reliable population benefit. The sampled-world statistics are
model diagnostics, not additional independent fights. The original benchmark
results and confidence intervals above remain unchanged.

## Next decision

Keep this developed-deck panel as a strategic development diagnostic and the
starter panel as infrastructure evidence. The next useful experiment is **bounded
policy rollouts for leaf evaluation**, tested under a fixed total thinking budget
against the frozen greedy, root-only and current Gumbel controls. Use these three
positions to inspect regressions, but tune on broader development data and require
a larger fresh, frozen paired confirmation before claiming combat improvement or
scaling search training. More depth or simulations alone is not yet justified.
Search remains opt-in; the positive paired Act 1 confidence gate is unchanged.
Campaign and bridge attachment still require compatible public history anchors.
