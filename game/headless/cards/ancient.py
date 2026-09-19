"""Cards granted by solo Ancient relics, outside ordinary generation pools."""

from dataclasses import dataclass
from functools import partial
from game.headless.cards.builders import define
from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.effects import GainBlock, DrawCards
from game.headless.cards.operations import Attack, Power, ChoosePileCard


@dataclass(frozen=True, slots=True)
class AncientOperation:
    operation: str

    def apply(self, card, player, target):
        from game.headless.core.resolution import push
        if self.operation == 'apotheosis':
            for other in player.deck.all_cards():
                if other is not card and other not in player.deck.offered and other.upgrade_level + 1 < len(other.definition.levels):
                    other.upgrade()
        elif self.operation == 'quadcast':
            push(player, *[['orb_evoke', False, i == 3] for i in range(4)])
        elif self.operation == 'meteor':
            push(player, *[['status', i, status, 2] for i,e in enumerate(player.combat_enemies) if e.is_alive for status in ('weak','vulnerable')])
        elif self.operation == 'maul':
            for other in player.deck.all_cards():
                if other.definition.definition_id == 'maul' and other not in player.deck.offered:
                    other.combat_state.extra_damage += 2 if card.upgraded else 1
        elif self.operation == 'flame_energy':
            player.gain_energy(3 if card.upgraded else 2)
        elif self.operation == 'flame_hp':
            target_hp = player.max_hp - 1
            if player.hp > target_hp:
                player.lose_hp(player.hp - target_hp)
            previous = player.max_hp
            player.max_hp = max(1, target_hp)
            player.rules.max_hp_gained += player.max_hp - previous
        elif self.operation == 'stun' and target is not None and target.is_alive:
            target.stunned = True
        elif self.operation == 'luminesce':
            player.gain_energy(3 if card.upgraded else 2)


card = partial(define, pool='colorless')
from game.headless.cards.osty_effects import OstyAttack

DEFINITIONS = (
    define('suppress','Suppress',0,'attack','ancient',(Attack(),Power('weak',3,5,target=True)),damage=11,upgraded_damage=17,base_innate=True,pool='silent'),
    define('protector','Protector',1,'attack','ancient',(OstyAttack(expression='protector'),),damage=10,upgraded_damage=15,upgraded_cost=0,pool='necrobinder'),
    define('meteor_shower','Meteor Shower',0,'attack','ancient',(Attack(all_enemies=True),AncientOperation('meteor')),damage=14,upgraded_damage=21,star_cost=2,target=False,pool='regent'),
    define('quadcast','Quadcast',1,'skill','ancient',(AncientOperation('quadcast'),),upgraded_cost=0,pool='defect'),
    card('apotheosis','Apotheosis',2,'skill','ancient',(AncientOperation('apotheosis'),),upgraded_cost=1,base_innate=True,exhaust=True),
    card('maul','Maul',1,'attack','ancient',(Attack(hits=2),AncientOperation('maul')),damage=5,upgraded_damage=6),
    card('relax','Relax',3,'skill','ancient',(GainBlock(),Power('draw_next_turn',2,3),Power('energy_next_turn',2,3)),block=15,upgraded_block=17,exhaust=True),
    card('luminesce','Luminesce',0,'skill','token',(AncientOperation('luminesce'),),exhaust=True,retain=True),
    card('wish','Wish',0,'skill','ancient',(ChoosePileCard('draw_pile','hand'),),exhaust=True,upgraded_retain=True),
    card('brightest_flame','Brightest Flame',0,'skill','ancient',(AncientOperation('flame_energy'),DrawCards(),AncientOperation('flame_hp')),draw=2,upgraded_draw=3),
    card('whistle','Whistle',3,'attack','ancient',(Attack(),AncientOperation('stun')),damage=33,upgraded_damage=44,exhaust=True),
    card('apparition','Apparition',1,'skill','ancient',(Power('intangible'),),ethereal=True,upgraded_ethereal=False,exhaust=True),
    CardDefinition('soot',(CardSpec('Soot',-1,'status',uses_target=False),),(),rarity='status',pool='status',generate_in_combat=False),
)
