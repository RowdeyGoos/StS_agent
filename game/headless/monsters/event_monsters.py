"""Solo event encounters at ascension zero."""
from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy
from game.headless.encounters.randomness import branch


class BattleFriendV1(ScriptedEnemy):
    NAME,HP='Battle Friend V1',(75,75)
    MOVES=(Intent('buff',0,'Nothing'),)

    def __init__(self,rng):
        super().__init__(rng)
        self.remaining_turns=3
        self.timed_out=False

    def advance_intent(self):
        self.remaining_turns=max(0,self.remaining_turns-1)
        if not self.remaining_turns:
            self.timed_out=True
            self.hp=0

    def validate_combat_context(self,player):
        if type(self.remaining_turns) is not int or not 0<=self.remaining_turns<=3 or type(self.timed_out) is not bool or self.timed_out != (self.remaining_turns==0):
            raise ValueError('Invalid dummy time limit.')


class BattleFriendV2(BattleFriendV1):
    NAME,HP='Battle Friend V2',(150,150)


class BattleFriendV3(BattleFriendV1):
    NAME,HP='Battle Friend V3',(300,300)


class PunchConstruct(ScriptedEnemy):
    NAME,HP='Punch Construct',(55,55)
    MOVES=(Intent('defend',10,'Ready',block_gain=10),
           Intent('attack',5,'Fast Punch',attack_damage=5,attack_count=2,status_name='frail',status_stacks=1),
           Intent('attack',14,'Strong Punch',attack_damage=14,attack_count=1))

    def __init__(self,rng,*,fast=False,reduction=0):
        super().__init__(rng)
        self._intent_index=int(fast)
        self.hp=max(1,self.hp-reduction)
        self.statuses.add('artifact',1)


class MysteriousKnight(ScriptedEnemy):
    NAME,HP='Mysterious Knight',(101,101)
    MOVES=(Intent('buff',3,'War Chant',strength_gain=3),
           Intent('attack',9,'Flail',attack_damage=9,attack_count=2),
           Intent('attack',15,'Ram',attack_damage=15,attack_count=1))

    def __init__(self,rng):
        super().__init__(rng)
        self._intent_index=2
        self.strength=6
        self.plating=6
        self.block=6
        self.turns_started=0

    def advance_intent(self):
        self._intent_index=branch(self.rng,((0,) if self._intent_index!=0 else ())+(1,1,2,2))

    def after_move(self,player,intent):
        self.gain_block(self.plating)

    def start_turn(self):
        super().start_turn()
        if self.turns_started:
            self.plating=max(0,self.plating-1)
        self.turns_started+=1

    def _possible_next_templates(self):
        return self.MOVES[1:] if self._intent_index==0 else self.MOVES


class FakeMerchantMonster(ScriptedEnemy):
    NAME,HP='Fake Merchant',(165,165)
    MOVES=(Intent('attack',13,'Swipe',attack_damage=13,attack_count=1),
           Intent('attack',2,'Spew Coins',attack_damage=2,attack_count=8),
           Intent('attack',9,'Throw Relic',attack_damage=9,attack_count=1,status_name='frail',status_stacks=1),
           Intent('buff',2,'Enrage',strength_gain=2))

    def advance_intent(self):
        pool=[0,1,2] if self._intent_index==2 else [0,1,2,3,3,3]
        self._intent_index=branch(self.rng,[i for i in pool if i!=self._intent_index])

    def _possible_next_templates(self):
        return tuple(v for i,v in enumerate(self.MOVES) if i!=self._intent_index and not(self._intent_index==2 and i==3))
