"""Five native Overgrowth Ruby Raider variants, at A0."""

from game.headless.monsters.base import Intent
from game.headless.monsters.scripted import ScriptedEnemy


class AssassinRubyRaider(ScriptedEnemy):
    NAME, HP = "Assassin Ruby Raider", (18, 23)
    MOVES = (Intent("attack", 10, "Killshot", attack_damage=10, attack_count=1),)


class AxeRubyRaider(ScriptedEnemy):
    NAME, HP = "Axe Ruby Raider", (20, 22)
    SWING = Intent("attack_defend", 5, "Swing", attack_damage=5, attack_count=1, block_gain=5)
    MOVES = (SWING, SWING, Intent("attack", 12, "Big Swing", attack_damage=12, attack_count=1))


class BruteRubyRaider(ScriptedEnemy):
    NAME, HP = "Brute Ruby Raider", (30, 33)
    MOVES = (Intent("attack", 7, "Beat", attack_damage=7, attack_count=1),
             Intent("buff", 3, "Roar", strength_gain=3))


class CrossbowRubyRaider(ScriptedEnemy):
    NAME, HP = "Crossbow Ruby Raider", (18, 21)
    MOVES = (Intent("defend", 3, "Reload", block_gain=3),
             Intent("attack", 14, "Fire", attack_damage=14, attack_count=1))


class TrackerRubyRaider(ScriptedEnemy):
    NAME, HP = "Tracker Ruby Raider", (21, 25)
    LOOP_START = 1
    MOVES = (Intent("debuff", 2, "Track", status_name="frail", status_stacks=2),
             Intent("attack", 1, "Hounds", attack_damage=1, attack_count=8))
