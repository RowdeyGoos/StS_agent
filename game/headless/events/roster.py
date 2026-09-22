"""Pinned solo event pages outside the original Overgrowth catalog."""
from game.headless.events.flow import FlowEvent
from game.headless.events.steps import eligible


def selection(mode, count=1, argument='', amount=0):
    return ('select', mode, count, argument, amount)


BRANCHES = {
    'amalgamator': {
        'combine_strikes': (selection('remove_strike', 2), ('card','ultimate_strike')),
        'combine_defends': (selection('remove_defend', 2), ('card','ultimate_defend'))},
    'bugslayer': {'extermination': (('card','exterminate'),), 'squash': (('card','squash'),)},
    'doors_of_light_and_dark': {'light': (('random_upgrades',2,'event.upgrade'),), 'dark': (selection('remove'),)},
    'drowning_beacon': {'bottle': (('fixed_potion','glowwater_potion'),), 'climb': (('max_hp',-13),('relic','fresnel_lens'))},
    'field_of_man_sized_holes': {'resist': (selection('remove',2),('card','normality')), 'enter_your_hole': (selection('enchant',1,'perfect_fit',1),)},
    'grave_of_the_forgotten': {'confront': (('card','decay'),selection('enchant',1,'souls_power',1)), 'accept': (('relic','forgotten_soul'),)},
    'hungry_for_mushrooms': {'big_mushroom': (('relic','big_mushroom'),), 'fragrant_mushroom': (('relic','fragrant_mushroom'),)},
    'infested_automaton': {'study': (('generated_card','power',False),), 'touch_core': (('generated_card','zero_cost',True),)},
    'lost_wisp': {'claim': (('card','decay'),('relic','lost_wisp')), 'search': (('gold','$gold'),)},
    'potion_courier': {'grab_potions': (('fixed_potion','foul_potion'),)*3, 'ransack': (('event_potion','uncommon','rewards'),)},
    'reflections': {'touch_a_mirror': (('reflections',),), 'shatter': (('clone_deck',),('card','bad_luck'))},
    'spiraling_whirlpool': {'observe': (selection('enchant',1,'spiral',1),), 'drink': (('heal','$heal'),)},
    'spirit_grafter': {'let_it_in': (('heal',25),('card','metamorphosis')), 'rejection': (selection('upgrade'),('damage',10))},
    'sunken_treasury': {'first_chest': (('gold','$small'),), 'second_chest': (('gold','$large'),('card','greed'))},
    'symbiote': {'approach': (selection('enchant',1,'corrupted',1),), 'kill_with_fire': (selection('transform'),)},
    'waterlogged_scriptorium': {'bloody_ink': (('max_hp',6),), 'tentacle_quill': (('spend',55),selection('enchant',1,'steady',1)), 'prickly_sponge': (('spend',99),selection('enchant',2,'steady',1))},
    'zen_weaver': {'breathing_techniques': (('spend','$breathing_cost'),('card','enlightenment'),('card','enlightenment')), 'emotional_awareness': (selection('remove'),('spend',125)), 'arachnid_acupuncture': (selection('remove',2),('spend',250))},
    'stone_of_all_time': {'lift': (('discard_potion','$potion'),('max_hp',10),('rng_int',100)), 'push': (('damage',6),selection('enchant',1,'vigorous',8),('rng_int',100))},
}
PAGED = ('battleworn_dummy','punch_off','the_lantern_key','fake_merchant','crystal_sphere','endless_conveyor','tinker_time','trash_heap','war_historian_repy','the_architect','abyssal_baths','colossal_flower','doll_room','round_tea_party','trial','colorful_philosophers',
         'ranwid_the_elder','relic_trader','welcome_to_wongos')
from game.headless.events.ancients import NAMES as ANCIENTS
DEFINITIONS = tuple(FlowEvent(n) for n in (*BRANCHES, *PAGED, *ANCIENTS))


def page(name, page_name, state, cards, rng, previous):
    if name in ('battleworn_dummy','punch_off','the_lantern_key','fake_merchant'):
        from game.headless.events.fights import page as fight_page
        return fight_page(name, page_name, state, cards, rng, previous)
    if name in ('crystal_sphere','endless_conveyor'):
        from game.headless.events.minigames import page as minigame_page
        return minigame_page(name, page_name, state, cards, rng, previous)
    if name in ('tinker_time','trash_heap','war_historian_repy','the_architect'):
        from game.headless.events.special import page as special_page
        return special_page(name, page_name, state, cards, rng, previous)
    if name in ANCIENTS:
        from game.headless.events.ancients import page as ancient_page
        return ancient_page(name, state, rng)
    c = {'options': []}
    if page_name == 'initial' and name in BRANCHES:
        c['options'] = list(BRANCHES[name])
        if name == 'zen_weaver': c['breathing_cost'] = min(50, state.gold)
        if name == 'lost_wisp': c['gold'] = rng.randint('event.variables',45,75)
        if name == 'sunken_treasury':
            c.update(small=rng.randint('event.variables',52,67), large=rng.randint('event.variables',303,363))
        if name == 'spiraling_whirlpool': c['heal'] = state.max_hp * 33 // 100
        if name == 'stone_of_all_time':
            potions = [p.instance_id for p in state.potions if p is not None]
            c['potion'] = rng.choice('event.potion',potions) if potions else None
            if not c['potion']: c['options'].remove('lift')
        for option, operations in BRANCHES[name].items():
            if option not in c['options']: continue
            for op in operations:
                if op[0] == 'select' and op[1] == 'enchant' and not eligible(state,op[1],op[3]):
                    c['options'].remove(option); break
                if op[0] == 'spend' and option != 'breathing_techniques' and state.gold < op[1]:
                    c['options'].remove(option); break
        return c
    from game.headless.events.social import page as social_page
    return social_page(name, page_name, state, cards, rng, previous)


def branch(name, page_name, option, c):
    if name in ("battleworn_dummy","punch_off","the_lantern_key","fake_merchant"):
        from game.headless.events.fights import branch as fight_branch
        return fight_branch(name, page_name, option, c)
    if name in ("crystal_sphere","endless_conveyor"):
        from game.headless.events.minigames import branch as minigame_branch
        return minigame_branch(name, page_name, option, c)
    if name in ("tinker_time","trash_heap","war_historian_repy","the_architect"):
        from game.headless.events.special import branch as special_branch
        return special_branch(name, page_name, option, c)
    if name in ANCIENTS:
        from game.headless.events.ancients import branch as ancient_branch
        return ancient_branch(name, option, c)
    if name in BRANCHES and page_name == 'initial':
        return tuple(tuple(c[x[1:]] if isinstance(x,str) and x.startswith('$') else x for x in op) for op in BRANCHES[name][option]), None
    from game.headless.events.social import branch as social_branch
    return social_branch(name, page_name, option, c)


def validate_context(name, page_name, context, cards):
    if not isinstance(context, dict) or not isinstance(context.get('options'),list) or len(context['options']) != len(set(context['options'])) or any(not isinstance(v,str) for v in context['options']):
        raise ValueError('Invalid event page options.')
    if name == "crystal_sphere":
        from game.headless.events.crystal_validation import validate_context as validate_crystal
        validate_crystal(page_name, context)
        return
    # Check each saved option against the authored branch, never deserialize code.
    for option in context['options']:
        branch(name, page_name, option, context)


def allowed(name, c):
    if name in ANCIENTS or name in ('war_historian_repy','the_architect'): return False
    act = c.get('act_index',0)
    if name in ('potion_courier','symbiote','ranwid_the_elder','relic_trader') and act == 0: return False
    if name in ('doll_room','stone_of_all_time','welcome_to_wongos') and act != 1: return False
    if name == 'crystal_sphere': return act > 0 and c['gold'] >= 100
    if name == 'fake_merchant': return act > 0 and (c['gold'] >= 100 or c.get('foul_potions',0) > 0)
    if name == 'endless_conveyor': return c['gold'] >= 120
    if name == 'punch_off': return c.get('floor',0) >= 6
    if name == 'ranwid_the_elder': return c.get('tradable_relics',0) > 0 and c['gold'] >= 100 and c['potion_count'] > 0
    if name == 'relic_trader': return c.get('tradable_relics',0) >= 5
    if name == 'trash_heap': return c['hp'] > 5
    if name in ('field_of_man_sized_holes','grave_of_the_forgotten','spiraling_whirlpool'):
        return c.get('enchant_'+{'field_of_man_sized_holes':'perfect_fit','grave_of_the_forgotten':'souls_power','spiraling_whirlpool':'spiral'}[name],0) > 0
    if name == 'colossal_flower': return c['hp'] >= 19
    if name == 'round_tea_party': return c['hp'] >= 12
    if name == 'zen_weaver': return c['gold'] >= 125
    if name == 'waterlogged_scriptorium': return c['gold'] >= 55
    if name == 'welcome_to_wongos': return c['gold'] >= 100
    if name == 'stone_of_all_time': return c['potion_count'] > 0
    if name == 'amalgamator': return c.get('basic_strikes',0) >= 2 and c.get('basic_defends',0) >= 2
    return True
