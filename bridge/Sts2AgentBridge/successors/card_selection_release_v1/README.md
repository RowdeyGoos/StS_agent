# Card selection release v1

This isolated release connects the frozen `card_selection_v1` component to the
pinned game through one authenticated loopback listener and the game frame.
Protected configuration selects one supported flow for one campaign:

- Cheese: Room Full of Cheese's initial Gorge choice, then exactly two of eight
  cards, automatic commitment, restored Proceed, and map return.
- Smith: an ordinary rest site's untouched Smith choice, then exactly one
  eligible card, upgrade confirmation, restored Proceed, and map return.

The functional core models variable-cardinality add/remove/upgrade/transform;
this release's native coverage is the two flows above. Other native event
callers, scrolling and partial visible domains remain unsupported. The controller
chooses the first legal cards for conformance testing; it has no strategic policy.

Every action is bound to its observed decision. Child completion does not end
the controller: the parent must separately reconcile Proceed and map return.
Uncertain actions are never retried. Temporary credentials and owned message
buffers are cleared, and service disposal happens on the game frame after the
transport has settled.

The [accepted contract](../../../../docs/PHASE_1_CARD_SELECTION_RELEASE_V1_CONTRACT.md)
and [acceptance ledger](../../../../docs/research/PHASE_1_CARD_SELECTION_RELEASE_V1_ACCEPTANCE.md)
define exact scope, source and artifact identities, gates, and evidence levels.
Development fixtures are not live evidence. The package pins the exact reviewed
production DLL, canonical manifest and deterministic archive; installation still
requires a completed aggregate gate and the final acceptance disposition.

The offline gate verifies all ten frozen predecessor inventories and old bridge
sources, isolates every build, runs pure and actual socket composition fixtures,
reproduces the production DLL, verifies complete metadata, and checks packaging
and transactional operations. It never executes the candidate or game assemblies,
installs an overlay, reads a live credential, or starts a campaign.

```sh
python3 -B -I -S bridge/Sts2AgentBridge/successors/card_selection_release_v1/check.py \
  --dotnet /absolute/path/to/pinned/dotnet \
  --game-data-dir /absolute/path/to/pinned/game/data \
  --scratch /private/tmp/a-new-card-release-gate
```

SDK 9.0.303 and the exact two pinned game references are required. The scratch
root must not exist. Installation is separate, requires the game closed and a
clean verified base, and publishes code last. All previous campaign states,
operator units and overlays are preserved and block a conflicting installation.

For a later live test, the user must leave the selected initial parent choice
untouched; an already-open card selector cannot be adopted. Cleanup quits
normally, quarantines code first, purges exactly owned objects and verifies the
base installation. The user's waiver of repetitive unmodded relaunch checks
remains in effect. No profile/save filesystem, Steam Cloud, retained live corpus,
remote Git, or unrelated gameplay capability is included.
