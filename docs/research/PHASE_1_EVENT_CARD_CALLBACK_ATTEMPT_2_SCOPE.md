# Phase 1 event card-callback static scope

- Date: 2026-09-06
- Status: corrected proposal after one fail-closed attempt; corrected synthetic gates pass, corrected target packet not read
- Baseline: `920ec84`
- Accepted caller result SHA-256: `c6340b67d61bd01f447bd4bad320e3ef26abf323a04b1db51f4a0050dc245f6e`

## Purpose and exact candidates

Inspect five exact positive caller rows needed to design one reusable add,
single removal, multi-removal and event-upgrade increment:

1. `BrainLeech.ShareKnowledge()` for simple-grid reward addition;
2. `Wellspring.Bathe()` for removal;
3. `ZenWeaver.RemoveCardsAndProceed(int,int)` for a possible multi-count removal;
4. `AromaOfChaos.MaintainControl()` for event upgrade; and
5. `SapphireSeed.Eat()` as an independent event-upgrade alternative.

These are selectors for static inspection, not accepted native policies. The
caller census proves only that each exact attributed state-machine body has the
recorded selector and effect calls. It does not prove option identity, counts,
eligibility, preview mode or effect completion.

The exact five-body selection is SHA-256
`cfc57aa9ef8fc35b818e6d2b2ab1fddf384f84904ed6c4c19e30e1e9173e4589`.
It mechanically preserves the event, source method, actual `MoveNext` body,
call offsets, kinds and full callee identities from the accepted result.

## Exact inspected metadata and bodies

For each selected event the tool emits:

- the direct event TypeDef's complete field and method identity inventory;
- the exact selected source-to-state-machine binding and full selected
  `MoveNext` body;
- the sole directly declared `GenerateInitialOptions` body; and
- bounded callback candidates with bodies: every `b__` or `g__` method on a
  nested type of that exact event, plus any same-event method-definition target
  reached by `ldftn` or `ldvirtftn` in the selected or initial-options body.

The nested callback set is deliberately overinclusive and does not claim that
every emitted candidate is bound to the selected option. The full bodies are
needed to trace exact `EventOption` key/delegate construction, selector
preferences and counts, eligibility callbacks, preview/confirmation policy,
and post-await effect witnesses. A production row still requires an exact
key-to-delegate-to-selector trace and independently reviewed completion proof.

For each exact `EventOption` constructor in `GenerateInitialOptions`, the tool
admits one binding only when the preceding constructor segment contains exactly
one same-event `ldftn`/`ldvirtftn` method-definition target and exactly one
following key-like `ldstr`. The key must be 1..96 ASCII letters, digits,
underscores or dot-separated segments. The result records that key, callback,
constructor identity and three offsets. A segment with another string or
callback fails closed. This narrowly exposes option localization keys needed by
the native registry; every other user string remains the fixed marker
`user_string`.

The packet also emits one narrowly named command-helper chain needed by the
selected removal callers. It binds the exact
`CardSelectCmd.FromDeckForRemoval(Player,CardSelectorPrefs,Func<CardModel,bool>)`
wrapper, the exact `CardSelectCmd.FromDeckGeneric(Player,CardSelectorPrefs,
Func<CardModel,bool>,Func<CardModel,int>)` source and its attribute-bound
`<FromDeckGeneric>d__24.MoveNext`, plus only directly referenced
`CardSelectCmd`-owned `ldftn`/`ldvirtftn` callback bodies. The direct member
inventory establishing those two signatures and the generated state-machine
name is SHA-256
`d3daf5216cc1e33cf086a79b907f1196805acb267636ed56dc1bebc8d2b34195`.
This is not a general callee traversal.

Prior retained helper bodies establish a separate production admission limit:
upgrade and simple-grid reward helpers can return an empty result or complete
without opening a selector when the eligible count does not exceed
`MinSelect` and manual confirmation is false. A row backed by the current
required-child protocol must therefore prove a nonzero eligible domain and
that the exact preferences force an actual selector. Selectorless direct
effects remain unsupported by this packet.

For multi-upgrade preview, retained `NDeckUpgradeSelectScreen.OnCardClicked`
evidence shows the preview model is a clone produced from the original. The
public `CardModel.CloneOf` member exists, but its getter and the relevant clone
construction bodies are not in the retained body evidence. Production cannot
map a multi-preview clone back to its original by card key; that mapping needs
a separately reviewed narrow static proof.

The tool validates every selected call offset and callee against the target
body before emitting evidence. It does not follow arbitrary callees, inherited
methods, other event bodies, resources, localization, debug data, profile/save,
history, Cloud or network data. User-string operands outside the exact option
binding above are emitted only as the fixed marker `user_string`.

The first reviewed revision stopped with `ambiguous_metadata` because it
required assembly-wide uniqueness from a method identity that omits generic
arity and return type. That rejects unrelated legal overloads such as `M()` and
`M<T>()`. The corrected tool resolves only the exact selected source/body and
the two exact removal-helper methods, requiring each of those identities to be
unique. Its positive fixture contains an unrelated generic-arity collision;
its negative adds the collision to an exact selected method and requires
`ambiguous_metadata`. It does not weaken selected-method, state-machine or
callsite binding.

## Bounds and sanitized output

The target mode binds the exact selection bytes before opening the target. It
then accepts only physical `sts2.dll` bytes with SHA-256
`e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`,
hashes before `PEReader`, and zeros the bounded image on every post-allocation
path. The assembly is never loaded or executed.

- exactly 5 selected bodies and 5 initial-options bodies;
- at most 64 event callback bodies, 8 removal-helper bodies and 82 bodies total;
- at most 2,500 instructions per body and 100,000 aggregate;
- no truncation; mismatch or overflow stops without a looser rerun.

Output contains only fixed schema/evidence hashes and counts, event field/method
metadata identities, exact option binding rows, body role/event/source/method identities, and decoded
instruction offsets, numeric opcodes, metadata identities, numeric constants,
variable indices and branch targets. Apart from the exact validated option keys
described above, it contains no user-string contents or raw image bytes.

## Disposable tool

The tool is `/private/tmp/event-card-callbacks-b`:

- `Program.cs`: `2e1dabcff216f62fe318c6745a49dcae19f5af55af2dda99b011beba9354f5d2`;
- `IlDecoder.cs`: `58a15d83f6b97916ab5f63b2b765f29cd8d46e380d5a270bf8c91dd333d25933`;
- `MetadataNames.cs`: `f7b481088f436e9ada05fc269101cd98b05326122798ff6043eeab8286517d23`;
- `VerificationException.cs`: `d96d1849ca4990461488dae68f9a972fc4c37afae42d5a31892f03f8bbafa907`;
- project: `c21c689cf0292d7a0c305a1e9bbf4b6465c0450f7c1238fb260a5fe3aac17cf1`;
- selection: `cfc57aa9ef8fc35b818e6d2b2ab1fddf384f84904ed6c4c19e30e1e9173e4589`;
- runner: `179142d17c5bac875cfc84201233b4457e82238a78643955b6bef6a41ab8c399`;
- complete 13-input source manifest: `a3a012d287f73f37ff1865417e0ff30363ea375b319b02906993670b8f6c6851`.

The exact built scanner bundle is:

- DLL, 64,000 bytes: `f1c728be934b5b2e462618634abfed18b613384df7eabd3d01570ce35ac63ac7`;
- deps: `0a059cd277ab0f19ed704a0a0d7ac716e0277fb24219a44650fa11e8c4897558`;
- runtime config: `9b93bb9ae8b1f2d369e6bfd31f183e2db18031236ff1171bb899522aea902297`;
- copied selection: `cfc57aa9ef8fc35b818e6d2b2ab1fddf384f84904ed6c4c19e30e1e9173e4589`.

The inert tool gate passes exact 13 checks covering schema and roles, selected
call binding, the removal wrapper/generic state/callback chain, exact option
key/callback binding, initial-options and callback-body inclusion, user-string
redaction, deterministic output, image pin, call-offset drift, event mismatch,
unrelated identity-collision acceptance, selected identity-collision rejection,
symlink rejection and target-mode selection pin ordering.

## Capture and stop boundary

The capture wrapper in `/private/tmp/event-card-callbacks-capture-b` verifies
the complete tool source and bundle pins, drains at most 4,000,000 stdout bytes
and 4,096 stderr bytes for at most 60 seconds, and creates a private direct
`/private/tmp/event-card-callbacks-capture-<24hex>` directory. It writes exact
stdout/stderr with mode `0600`, exclusive creation and fsync before schema
validation or summary. It validates the exact header, body/role counts and
instruction bounds. Its sources are:

- wrapper: `f7d4eca3aa729ad15f5ef3075ffb26f43ea2866c6fa89870e0588ab9497fa66a`;
- fixture runner: `1852ec326ed2eb68e61274688c113f56e01f1173d7c9357f35cf972b86d91c10`;
- two-input manifest: `cac346c367cea8409033d49aa5bc7267e9e161cf240a042fdb5b1bcf88069d59`.

Its inert capture test passes exact 3 checks for byte-complete persistence,
private modes and output-directory non-reuse.

Independent review must accept the exact scope, tool, selection and capture
wrapper before the root coordinator may authorize one metadata/IL target read.
The result may narrow concrete production rows but does not itself authorize
native implementation or a live action.
