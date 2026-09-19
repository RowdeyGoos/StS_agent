"""Event-only cards, including the owned configuration of Mad Science."""
from dataclasses import dataclass
from functools import partial
from game.headless.cards.base import CardDefinition, CardSpec
from game.headless.cards.builders import define
from game.headless.cards.effects import GainBlock, RandomEnemyAttack
from game.headless.cards.operations import Attack, Power, CardOperation

RIDERS = {'attack': ('sapping','violence','choking'), 'skill': ('energized','wisdom','chaos'), 'power': ('expertise','curious','improvement')}


@dataclass(frozen=True)
class EventOperation:
    operation: str

    def apply(self, card, p, target):
        from game.headless.core.resolution import push
        from game.headless.powers.ironclad import apply_power, card_cost
        from game.headless.cards.colorless_effects import create, pool
        from game.headless.generation.combat import select_cards
        if self.operation == 'dual_wield':
            from game.headless.core.choices import begin
            begin(p, card.instance_id, [c for c in p.hand if c.spec.kind in ('attack','power')], operation='dual_wield_up' if card.upgraded else 'dual_wield')
        elif self.operation == 'distraction':
            from game.headless.core.card_costs import free_this_turn
            options = select_cards(pool(p,'ironclad','skill'),p.deck.generation_rng,1,distinct=True)
            if options: free_this_turn(create(p,options[0]))
        elif self.operation == 'entrench':
            p.gain_block(p.block)
        elif self.operation == 'stack':
            p.gain_block(len(p.deck.discard_pile)+(3 if card.upgraded else 0),powered=True)
        elif self.operation == 'metamorphosis':
            for definition in select_cards(pool(p,'ironclad','attack'),p.deck.generation_rng,5 if card.upgraded else 3,distinct=False):
                from game.headless.cards.colorless_effects import catalog
                from game.headless.core.piles import after_generated_entry
                result=catalog(p).create(definition.definition_id)
                result.combat_state.free_this_combat=True
                p.deck._ensure_identity(result)
                p.deck.draw_pile.insert(p.deck.rng.randrange(len(p.deck.draw_pile)+1),result)
                after_generated_entry(p,result)
        elif self.operation == 'enlightenment':
            from game.headless.core.card_costs import mark_setter
            for c in p.hand:
                if c.spec.x_cost or card_cost(p,c)<=1: continue
                v=c.combat_state
                if card.upgraded:
                    v.combat_cost_override=1;v.combat_override_baseline=v.combat_cost_change
                    mark_setter(v,'combat')
                else:
                    v.turn_cost_override=1;v.turn_cost_until_played=True
                    v.override_turn_baseline=v.cost_change+v.turn_cost_change;v.override_combat_baseline=v.combat_cost_change
                    mark_setter(v,'turn')
        elif self.operation == 'mad_science':
            kind,rider=card.event_data['kind'],card.event_data['rider']
            if kind=='attack':
                if rider=='sapping':
                    Power('vulnerable',2,target=True).apply(card,p,target)
                    Power('weak',2,target=True).apply(card,p,target)
                elif rider=='choking': Power('strangle',6,target=True).apply(card,p,target)
                Attack(hits=3 if rider=='violence' else 1).apply(card,p,target)
            elif kind=='skill':
                p.gain_block(8,powered=True)
                if rider=='energized': p.gain_energy(2)
                elif rider=='wisdom': push(p,['draw',3,False])
                elif rider=='chaos':
                    d=select_cards(pool(p),p.deck.generation_rng,1,distinct=True)[0]
                    from game.headless.core.card_costs import free_this_turn
                    free_this_turn(create(p,d))
            elif rider=='expertise':
                p.gain_strength(2);apply_power(p,'dexterity',2)
            elif rider in ('curious','improvement'): apply_power(p,rider,1)


card=partial(define,pool='event',generate=False)
DEFINITIONS=(
    card("caltrops","Caltrops",1,"power","event",(Power("thorns",3,5),)),
    card("clash","Clash",0,"attack","event",(Attack(),),damage=14,upgraded_damage=18),
    card("distraction","Distraction",1,"skill","event",(EventOperation("distraction"),),upgraded_cost=0,exhaust=True),
    card("dual_wield","Dual Wield",1,"skill","event",(EventOperation("dual_wield"),)),
    card("entrench","Entrench",2,"skill","event",(EventOperation("entrench"),),upgraded_cost=1),
    card("hello_world","Hello World",1,"power","event",(Power("hello_world"),),innate=True),
    card("outmaneuver","Outmaneuver",1,"skill","event",(Power("energy_next_turn",2,3),)),
    card("rebound","Rebound",1,"attack","event",(Attack(),Power("rebound")),damage=9,upgraded_damage=12),
    card("rip_and_tear","Rip and Tear",1,"attack","event",(RandomEnemyAttack(hits=2, upgraded_hits=2),),damage=7,upgraded_damage=9,target=False),
    card("stack","Stack",1,"skill","event",(EventOperation("stack"),)),
    card('exterminate','Exterminate',1,'attack','event',(Attack(hits=4,all_enemies=True),),damage=3,upgraded_damage=4,target=False),
    card('squash','Squash',1,'attack','event',(Attack(),Power('vulnerable',2,3,target=True)),damage=10,upgraded_damage=12),
    card('metamorphosis','Metamorphosis',2,'skill','event',(EventOperation('metamorphosis'),),exhaust=True),
    card('enlightenment','Enlightenment',0,'skill','event',(EventOperation('enlightenment'),),exhaust=True),
    card('feeding_frenzy','Feeding Frenzy',0,'skill','event',(Power('strength',5,7),Power('temporary_strength',5,7))),
    card('mad_science','Mad Science',1,'attack','event',(EventOperation('mad_science'),),damage=12,block=8,innate=True),
    CardDefinition('lantern_key',(CardSpec('Lantern Key',-1,'quest',uses_target=False),),(),rarity='quest',pool='event',generate_in_combat=False),
)
