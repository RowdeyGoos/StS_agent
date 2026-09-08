# Card selection v1 independent review

Date: 2026-09-06. Review scope: the isolated `card_selection_v1` source,
contract, sanitized static evidence, pure and actual-source fixtures, native
compile boundary, wire/controller contract and final offline result. This was a
read-only review outside the explicitly owned parent and parent-adapter fixture
files. No target assembly was executed and no live, operator, profile, save,
Cloud or remote operation was performed.

## Disposition

Accepted for the implemented offline development boundary. The selected native
surface is limited to Room Full of Cheese Gorge add-two-of-eight and ordinary
single-character SmithCount=1 upgrade-one. Remove, transform and multi-card
upgrade are exercised by the pure core only; their native callers remain
unsupported. The packet has no listener, bootstrap, package, operator tooling
or live client, so this review does not claim release readiness or live card
selection.

The final contract is SHA-256
`af8125ba2dd7bd8d7df85144f5a275d20a347ca7d4fe5bd5e666e53b3f57186c`.
The sanitized static result is
`dd96dbcf77125642685fc133fd61fdb76c9235c9a1e3f6f5b0241742434b012d`
and the exact selection record is
`ec8b8d53858182e8e75d4efebe2a843de7a6d9b74b9de2f5b9c1c2252ad349b9`.
The selection used 47 types and 142 bodies within the frozen 80-type/200-body
ceilings.

## Reviewed boundaries

The core contracts/session are respectively
`e7c221ec1c5390d9a21c6097d3d41b78ee06ee722d5447a7fc5a54146ff9df06`
and `6621da8f4fc9e83d3ffd566005e639a86cf9e531475b982d90718b30c6be353e`.
They bind complete domain and deck projections, including `CompleteDeck`,
reserve before dispatch, reject uncertain retry, require the exact retained
completion task and selected originals, and keep task completion distinct from
the typed parent effect witness.

The child native rules/adapter are respectively
`e85f8017e919b4f484da8f14df32687b68afe2ad4b8759968e02b52876647fa9`
and `bdf25e398b9ff2e589db17eee066a38c7fe347a5e0282d2b0f8a1bddc4158290`.
Admission requires exact selector and grid runtime types, complete authorized
domains and stable candidate mappings. The passive readiness functions share
the same projection validation as child creation and do not call
`CardsSelected`; child creation calls it once only after readiness.

The parent contracts/session are respectively
`60d2e207dc029700a4ea22edc85408740a821ee077e35d7904129c1a902579a7`
and `c26905fb340eabc9b4731063e5cff197df53acbe5ee4db3e55b702687b577cd9`.
The parent constructs and owns the real child session from the accepted context,
checks the exact admitted screen on every available child capture, and keeps
begin, child resolution, typed effect completion, Proceed and final same-map
handoff separate. Full child-phase recapture is validated before invoking the
factory. Initial absence may wait; disappearance after retaining a selector,
foreign or changed overlays, changed bound references and uncertain dispatch
all terminalize without later adoption.

The parent native rules/adapter are respectively
`03894516817f15d64306a7cf315078e19af8d71890ff0d0b6f5596366164e4a6`
and `0111109aaa6841d99b18931dc8b063c401dd2178263491a2a442444e4d9dbe4b`.
The event path binds the exact Gorge option and finished-event singleton
Proceed. The rest path binds one valid visible `NRestSiteCharacter`, its public
`Player`, the exact Smith option, full eligible deck count and exact Proceed
control. The static evidence proves this rendered one-character binding because
`NRestSiteRoom._Ready` creates one character per run-state player; it does not
prove global multiplayer absence or local-player semantics. Multiple or changed
characters reject, and no multiplayer helper body was followed.

The wire protocol/codec/service hashes are
`b31a4f265ee246299683460bb36ea84ffdec458909bec4db5cba049f6aecf716`,
`9f2ccbab2ead265315f06b187854c30f4f3da9b8f173aded6998db22741b5442`
and `8a568d0007fb893518c973ec77eaa08c91bcdb453e9f1131d1c6773f7ed323e1`.
The Python host is
`aa517a36ddab784c629f07b887f077f8f73700314ede821b80fb6ef0c9ee8c80`.
Review confirmed ordered candidates, global decision non-reuse before POST,
exact commit receipt before Smith resolution, bounded monotonic deadlines,
canonical scalar JSON and separate parent/child routes and counters.

## Fixture and aggregate evidence

The actual parent-adapter source fixture links the production parent native
sources against inert stubs and no target DLL or native project reference. Its
project is
`17a6f454df3b0344458861de515b83fbd3ff15afc46384c230915009695f5f43`;
Program, target stubs and child-native stub are respectively
`72d5d4238d65801d14d45fd359503aa2bd1b2ed24f873a5dbda451d56ea99f77`,
`79a038620c9873dda23aeb488e8b9976b412c39613daa22defe4552ee27176fb`
and `be8860adf13b8a3d68760db961114efa1602629aa51d0264b87125eefd30b5d0`.
Its eight scenario groups cover Cheese and Smith bindings, readiness, retained
screen loss/replacement, uncertain and duplicate begin, effect/Proceed/map
handoff, sole-player changes and exact-type canaries.

The final source manifest is
`ca4e18dbb66520481881ea86a91925162593f8496c7abccc061a31f1c319a0ac`
with 40 recorded files plus the manifest and source inventory
`51135dfb6749d58b897bb4670ffa709ca5b756873464c9e045f2ba80f87bfc64`.
The reviewed checker and create-only freeze helper are
`a29f714e15d911ac4f2d056dc2f0521b4aa1809901e2bbeddcf76cc2185e842f`
and `ddb5bad0031bf4cb90c56e8184eb167915c9cd5639c22ab69f602786504b1b44`.

The canonical offline result at
`/private/tmp/sts-card-selection-v1-final-gate-a1/result.json` is
`b0f73ad4b76047e88eafd786b298417a5cf17bf68f0fd0d2ff514c9ab879ac7e`.
It reports exact passed group counts: core 16, child-native rules 28, parent 12,
parent-native rules 5, actual parent-adapter source 8, wire 11, project boundary
15, Python host 13 and cross-language 2. All nine predecessor inventories and
the original 48-file bridge inventory passed unchanged.

Both native projects were compiled twice from separate physical snapshots and
were byte-identical. The child native assembly is 24,064 bytes,
`b7b6cff562a93d4b72de0bd39d418404425d356c231093e53505d36e7196c0ca`;
the parent native assembly is 30,208 bytes,
`a069b1b640f904dc2c9e8a1f937587d2635ff2a27d668eaab396d595587b7403`.
Neither assembly was executed. The repository Python regression separately
passed 1,192 tests in 107.55 seconds after the test-module naming collision was
removed.

## Residual boundary

Offline fixtures establish the bounded state machine and compile the selected
native APIs. They do not establish that the two selected screens will appear in
a live run, that longer event/rest variants work, or that a packaged bridge can
operate them. A successor release must retain the exact source and artifact
identities, default-deny the whole assembly, add protected operator and lifecycle
composition, and pass synthetic package/manager/client gates before any bounded
live campaign.
