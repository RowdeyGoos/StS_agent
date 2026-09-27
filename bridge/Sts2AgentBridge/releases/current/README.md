# Current unified release

Reward claims now carry potion capacity validated by the exact pickup effect
owner. Previously settled items accept this capacity while the native callback
is pending, then store it only after successful settlement. This fixes Phial
Holster after another reward and capacity granted through Large Capsule, while
preserving exact earlier potion slots and identities.

[Current status](../../../../docs/STATUS.md#release-and-latest-evidence) owns support;
[bridge usage](../../README.md#client-modes) owns commands.

| Record | Meaning |
| --- | --- |
| [bridge.json](bridge.json) | Exact source/test, toolchain, reference, binary and package identities |
| [validation.json](validation.json) | Release checks, independent review and separately bound live evidence |

Manifest SHA-256: `69bfd021968f2ea8e3879fe09901cdaf53f3cfa90fbae5f8bc69fe16f3f2e639`. Source: `0fb2972acf5475de36908beac2b89c4d50a60a93`.
The final gate passed **85 groups in 379.888 seconds**, including reproducible
production builds, package metadata, integration and operational fixtures.
Focused checks passed **3,487 full-event reward checks** and **216 reward
alternative checks** in 61.067 seconds. Independent semantic review found no blocker.

Installation and metadata verification passed by **15:07:20 UTC**: the exact two
overlay files are installed and all **429** base files are unchanged. The game
was stopped for installation. Manual Profile 3 launch and a fresh `TEST91`
Shears/full-belt Holster retest are pending.

The [previous live failure](../../../../docs/evidence/FULL_AGENT_BRIDGE_LIVE_2026_09_25.md#neow-phial-holster-pickup-stopped)
remains **6/5/4**, with one uncertain action, under manifest `14772d59…`.
Its package, original record and cleanup evidence are retained separately.
The earlier bundle/removal **8/8/8** and offer/upgrade **7/7/7** passes retain that
same original artifact. Other compound branches and capacity-first rewards remain
separate live cases.
