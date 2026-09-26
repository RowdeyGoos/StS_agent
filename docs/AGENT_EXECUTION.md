# Public trajectories and agent execution

The installed `sts-agent-play` command runs the full headless public-only chooser
and records its decisions. It uses the existing engine and `full_run_v2` adapter;
it adds no game rules. The runner, recorder, public loader and worker supervisor
use only the standard library. NumPy/Gymnasium remain optional consumers.

## Commands and outcomes

```bash
python -m pip install -e .
sts-agent-play --output-dir runs/train --split train --seed 30 \
  --character ironclad --first-act overgrowth --ascension 0 \
  --episodes 2 --workers 2 --max-decisions 600 --time-limit 120

# The checkout entry point has the same interface.
python -m game.cli.agent_play --help
```

All five characters, both Act 1 regions and A0–A10 are supported, with the engine's
declared all-unlocked Ancient profile. The reference chooser is deliberately weak
and can lose. Normal transitions and actual defeat/abandonment have reward zero;
only genuine full-run victory earns one. Decision/time budgets produce explicit
truncations retaining the last ready public decision. Backend/observation/policy
failures stop execution and do not become game outcomes or retries.

The JSON command summary contains artifact paths, actual outcomes and per-episode
reset, observation/candidate creation, policy, step, recording and total timings.
Episode total measures engine construction through publication; batch elapsed
also includes provenance/audit preparation and process startup. These timings are
diagnostics and are not included in model inputs. Return codes are 0 for completed
episodes (including defeat/cutoff), 1 for failure and 130 for cancellation.

## Public format and private replay separation

[`recording.py`](../game/agent/recording.py) owns `sts_public_trajectory_v1` JSONL
files ending in `.trajectory.jsonl`. Each artifact contains:

1. A header with its first complete public decision/outcome and strict metadata:
   opaque episode ID, pinned target, build/rules/policy identities, public scenario
   reference, dataset split, evidence label and `sts_public_json_v2` encoding.
2. Ordered transitions containing the selected advertised candidate reference,
   reconciled execution report, complete successor decision/outcome and sparse
   reward. Every decision retains all candidates and public entity distinctions.
3. A completion record with the actual final outcome/cutoff, step count and SHA-256
   of the exact preceding bytes. No records may follow completion.

Build identity hashes the shipped `game/**/*.py` sources; rules identity hashes
`game/headless/**/*.py`; the policy identity names and hashes the reference chooser.
Paths are normalized relative to the package, so checkout and installed-wheel
identities agree. The final wheel itself has a separate package SHA-256 recorded
with validation below. Unsupported envelope, public-contract and structured-encoding
versions reject. Callers may additionally pin metadata identities when loading.

`headless_rollout` means ordinary generated engine execution, not a native/live
demonstration or a trained policy result. Custom engine factories must use
`controlled_fixture`; custom policies require an explicit caller-supplied policy
identity. Scenario/split identifiers are public metadata and must not contain
private replay information. Retained live corpora are outside this delivery.

Private base seeds, per-episode seeds and replay configuration are written only
to `sts_private_replay_v1` audit files. By default, `runs/train-private` is a sibling
of `runs/train`; `--audit-dir` can select another disjoint directory. Parent/child
overlap and aliases resolving to the same tree reject. Audit directories require
mode 0700, and newly created audit files use 0600. Public artifacts contain no
audit paths, seeds, snapshots, native tokens or dispatch capabilities.

The public loader accepts only published trajectory filenames, never follows a
path from file content and does not import/read the audit format. The policy
callback receives only the immutable public decision. This is a data/API boundary,
not an operating-system sandbox for arbitrary Python policy code. Replaying an
audit seed is an explicit trusted caller operation, not a policy-loader feature.

## Publication and workers

Writes start in an exclusively created `.trajectory.jsonl.partial` file. Completed
bytes are flushed/fsynced and published with an atomic, no-clobber hard link in the
same directory. A finished artifact is never replaced, including concurrent-name
races. Interrupted/failed files remain partial and the loader rejects them. A
partial file may contain a complete footer if interruption occurred immediately
before publication; its filename still prevents loading it as completed evidence.
This protocol requires a filesystem supporting same-directory hard links.

Workers use fresh `spawn` processes and independent engines/RNGs. Episode `i` uses
private seed `base_seed + i`, independent of scheduling; returned summaries retain
episode order. The defaults are one episode/worker, 4,096 decisions and 300 seconds.
Limits are 1–10,000 episodes and 1–32 workers. Each child has a parent-enforced hard
deadline five seconds beyond its configured episode budget, including startup.
Exceeding that deadline is an operational failure, not a fabricated time cutoff.

Ctrl-C/SIGTERM requests cooperative cancellation. No new work is scheduled;
unfinished writers remain partial. The parent gives active children three seconds
to stop, then terminates/kills and joins unresponsive children. Startup signals are
deferred until the process handle can be cleaned up. A failed worker stops its
peers; no uncertain action is retried. Already completed artifacts remain valid.

## Loading public datasets and model samples

```python
from pathlib import Path
from game.agent.dataset import load_dataset
from game.agent.provenance import implementation

paths = sorted(Path("runs/train").glob("*.trajectory.jsonl"))
for episode in load_dataset(paths, split="train",
                            expected={"rules": implementation().rules}):
    for transition in episode.transitions:
        public_decision = transition.observation
        chosen_candidate = transition.action
```

The loader validates a whole artifact before exposing its samples, rejects split
mismatches and preserves evidence/provenance in the episode metadata. It loads one
episode into memory at a time; very long episodes with repeated public history
can be large. No incomplete prefix is silently accepted as a training episode.

After installing `'.[gym]'`, the training loader accepts the existing encoder:

```python
from game.agent.dataset import training_examples
from game.agent.encoding.full import FullRunEncoder

encoder = FullRunEncoder()
for sample in training_examples(paths, split="train", encoder=encoder,
                                expected={"rules": implementation().rules}):
    observation, action = sample.observation, sample.action
    assert observation["action_mask"][action]
```

Samples contain the tensor layout identity, current/next observations, exact
candidate-index action, reward and termination/truncation flags. Metadata/private
audit inputs are excluded. Nonterminal cutoffs retain the successor mask for
bootstrapping; capacity errors propagate without clipping or skipping samples.
See [encoding and capacity limits](AGENT_ENCODING.md). This delivers data loading,
not a training algorithm or training-library performance claim.

## Live boundary

The bridge client selects the shared v1 policy using `--capability agent`, with
optional `--agent-dispatch-map`, or the newer shared v2 chooser using
`--capability full-agent`. Use its
[established entry point and preparation rules](../bridge/Sts2AgentBridge/README.md#client-modes).
The headless execution command does not install/launch the game or collect a live
corpus. The v1 shared-policy slice retains its bounded live acceptance. Milestone 7's
separate [native traversal policy](../bridge/Sts2AgentBridge/README.md#campaign-traversal)
has accepted assisted-campaign evidence. The
[native v2 producer](AGENT_CONTRACT.md#native-full-run-v2-candidate) is implemented
with representative interaction results; complete shared-interface campaign and
remaining path acceptance are still open. Optional live recording uses its own
format and explicit retention authorization, separately from the headless artifacts
described here. [Current status](STATUS.md) owns those evidence boundaries.

## Validation and timing

Focused tests cover malformed/version-mismatched artifacts, candidate/action and
reward consistency, split isolation, private audit separation, atomic publication,
real defeat, explicit cutoffs and a controlled A10 multi-act Architect victory.
The latter round-trips every public decision/candidate through recording and the
training loader; synthetic combat defeats and boosted HP remain labelled fixtures.
Serial/two-worker comparisons, CLI cancellation, a stalled worker and the exact
process-start interruption window exercise ownership and cleanup.

The September 26 delivery refresh includes the subsequent shared-contract and
native-preview chooser changes plus the opt-in live recorder. These are the only
three shipped Python files changed since the milestone 6 wheel; engine rules are
unchanged. The refreshed wheel is
`/private/tmp/sts-agent-delivery-20260926/wheel/sts_agent-0.1.0-py3-none-any.whl`,
SHA-256 `fc86fe7f22b66de58249e3db7ed3b0506daf9611ad5df9ad67ddedebb9b02afd`.
All **282** shipped Python files match the current checkout byte for byte. Its
build identity is `a4513feb98c9e6d446b2a10d46757746c34b29053d6e69587e61e79bd212be22`;
rules identity remains `2eecfffc8f57e27cc25a0092e254c6abea94d9acc08565ded8108077d263e60c`.
The current agent suite passed **406 tests in 586.31 seconds**, including the
20-case normal-HP Gym campaign matrix and controlled endings. Its two warnings
are the existing Gym checker advisory about constant layout metadata bounds.
All game Python sources parsed, and diff/link/source-binding checks passed.

Fresh core and optional-Gym Python 3.11 environments installed this wheel offline.
The core environment had neither NumPy nor Gymnasium. Its installed headless
command completed 38 commands, checking JSON restoration before every command;
its installed agent command recorded two twelve-decision episodes with two workers
in **0.948 seconds**, both explicitly truncated at the decision budget. The public
loader and optional encoder validated all **24** samples against the new build,
with legal candidate indexes and retained successor masks. Audit directory/file
modes were checked without reading their contents. A separate installed
Defect/Underdocks/A10 Gym run completed twelve reconciled decisions and an explicit
cutoff, retaining its successor mask. These are delivery checks, not trained-policy
or native campaign evidence. No live corpus was collected. The build command,
including metadata preparation, took **0.571 seconds**; separate environment
creation/install durations were not measured.

On 2026-09-24 (local date), the final affected agent/package integration passed
**383 tests in 123.12 seconds**. Compilation and diff/link checks passed. The
unchanged 20-case Gym campaign matrix and repository-wide engine/bridge evidence
from [milestone 5](AGENT_ENCODING.md#validation) were reused; they were not rerun
for unrelated runner/data additions. The Gym checker retains its existing advisory
about constant layout metadata bounds.

Independent semantic review ran **22:08:53–22:15:44 UTC on September 23 (6m51s)**,
including correction/recheck. It found the process-start signal window described
above; the fix and exact interruption/cancellation regressions passed, with no
remaining blocker. Implementation/checking/review overlapped, so their elapsed
times are not additive; implementation time was not separately isolated.

The original milestone 6 wheel SHA-256 was
`b79559e8b6ea546f282e593556a611dc6a5da68433634680d2e9ee9e75e97e24`.
All **281** shipped Python source files matched that checkout exactly. Its Python
source build identity is `5215b1a1321140dca0a9eab97b0ec555a935921585cf603a15cb46bc4d1825a7`;
rules identity is `2eecfffc8f57e27cc25a0092e254c6abea94d9acc08565ded8108077d263e60c`.
The wheel built in **0.46 seconds** and installed into a fresh core Python 3.11
environment in **0.30 seconds**. That installation exercised both installed
commands, two-worker recorded execution and public loading with no optional
dependencies. A second fresh environment installed Gymnasium 1.0.0/NumPy 2.4.6,
loaded ten exact training samples and executed twelve reconciled Defect/A10 Gym
decisions through an explicit cutoff with its successor mask preserved. The
workspace's editable install was refreshed to expose the new command.

Matched installed-core runs used two ordinary-HP Ironclad/A0/Overgrowth campaigns
with identical private seed schedules and a 600-decision/120-second budget.
Both runs ended in actual defeat at **150 and 136 decisions**. Entire public
decision/action/successor traces matched across worker counts, excluding opaque
episode IDs. Each batch recorded 21,119,700 public JSONL bytes.

| Measurement | One worker | Two workers |
| --- | ---: | ---: |
| Two-episode batch elapsed | 21.02 s | 11.52 s |
| Reconciled decisions/second, including recording/startup | 13.61 | 24.82 |
| Episodes/second | 0.095 | 0.174 |
| Mean reset | 67.14 ms | 67.39 ms |
| Mean observation/candidate projection | 21.73 ms | 22.31 ms |
| Mean command dispatch | 3.89 ms | 4.05 ms |
| Sum of per-episode policy time | 4.53 s | 4.65 s |
| Sum of per-episode recording/validation time | 8.74 s | 8.99 s |

These are two matched local samples, not general throughput or win-rate claims;
parallel per-episode times overlap. Public projection/validation/recording dominate
raw command dispatch here. This baseline precedes any optimization or training
workload selection.

All **393** accepted bridge source inputs and their inventory digest still match
the milestone 3 release. No native rebuild, installation, game launch, retained
live recording or user setup wait was needed.
