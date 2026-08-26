# Ironclad Card Sources

This project implements a deliberately small subset of base, non-upgraded
Ironclad cards for combat-sequencing experiments. The simulator does not yet
model card acquisition, upgrades, rarity, or character progression.

Source data was checked on 2026-08-26 against the Slay the Spire wiki:

| Card | Implemented base effect | Source |
| --- | --- | --- |
| Pommel Strike | Costs 1; deals 9 attack damage; draws 1 card | [Slay the Spire 2: Pommel Strike](https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2%3APommel_Strike) |
| Shrug It Off | Costs 1; gains 8 Block; draws 1 card | [Slay the Spire 2: Shrug It Off](https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2%3AShrug_It_Off) |
| Iron Wave | Costs 1; gains 5 Block, then deals 5 attack damage | [Slay the Spire 2: Iron Wave](https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2%3AIron_Wave) |
| Body Slam | Costs 1; deals attack damage equal to current Block | [Slay the Spire 2: Body Slam](https://slaythespire.wiki.gg/wiki/Slay_the_Spire_2%3ABody_Slam) |

`create_ironclad_sequencing_deck()` is a non-canonical ten-card research preset.
It keeps two Strikes, three Defends, and Bash, then adds one copy of each card
above. The canonical starter deck and the default environment remain unchanged.

Adding these card identities expands the default observation and action-feature
schemas. Checkpoints trained against the earlier card schema must be retrained;
the fixed discrete action space itself is unchanged.
