"""Hive-only status cards and choice previews; excluded from random generation."""
from dataclasses import dataclass
from game.headless.cards.base import CardDefinition, CardSpec


@dataclass(frozen=True)
class FranticEscape:
    def apply(self, card, player, target):
        from game.headless.monsters.hive_bosses import TheInsatiable
        for enemy in player.combat_enemies or ():
            if isinstance(enemy, TheInsatiable) and enemy.is_alive and enemy.sandpit:
                enemy.sandpit += 1
                break
        card.combat_state.combat_cost_change += 1


DEFINITIONS = (CardDefinition('frantic_escape', (CardSpec('Frantic Escape', 1, 'status', uses_target=False),),
                              (FranticEscape(),), rarity='status', pool='status', generate_in_combat=False),) + tuple(
    CardDefinition(name, (CardSpec(name.replace('_', ' ').title(), -1, 'status', uses_target=False),), (),
                   rarity='status', pool='status', generate_in_combat=False)
    for name in ('disintegration', 'mind_rot', 'sloth', 'waste_away'))
