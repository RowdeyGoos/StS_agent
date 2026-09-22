"""Damage modifiers with an explicit pet dealer and source card."""

from game.headless.core.resolution import push


def pet_damage(p, target, amount):
    from game.headless.relics.damage import attack_bonus, attack_multiplier
    from game.headless.relics.combat import has
    from game.headless.potions.powers import attack_multiplier as potion_multiplier
    from game.headless.powers.necrobinder import damage_multiplier
    from game.headless.powers.status import modify_attack_damage_for_statuses
    card = p.current_card
    n, d = target.incoming_attack_multiplier()
    n *= attack_multiplier(p, card) * potion_multiplier(p, card)
    from game.headless.powers.silent import damage_multiplier as silent_multiplier
    n *= silent_multiplier(p, target)
    nn, dd = damage_multiplier(p, card)
    n *= nn
    d *= dd
    if target.statuses.get('vulnerable'):
        # Paper Phrog and Cruelty modify the vulnerable power independently of dealer.
        vulnerable = 150 + p.rules.powers.get('cruelty', 0) + (25 if has(p, 'paper_phrog') else 0)
        if target.statuses.get('debilitate'):
            vulnerable = 100 + (vulnerable - 100) * 2
        n *= vulnerable
        d *= 200 if target.statuses.get('debilitate') else 150
    return modify_attack_damage_for_statuses(amount + p.rules.powers.get('calcify', 0) + attack_bonus(p, card), target.statuses, extra_multiplier=(n, d))


def after_attack_damage(p, target, total, *, pet, damage, sic_em):
    tasks = []
    slot = p.combat_enemies.index(target)
    for key, amount in p.rules.powers.items():
        if key == 'reaper_form' and total > 0:
            tasks.append(['status', slot, 'doom', total * amount])
        elif key == 'envenom' and not pet and damage > 0:
            tasks.append(['status', slot, 'poison', amount])
        elif key == 'monarchs_gaze' and not pet:
            tasks.append(['status', slot, 'monarchs_gaze_strength_down', amount])
    if pet and sic_em:
        tasks.append(['nec_summon', sic_em, p.current_card.instance_id, slot])
    push(p, *tasks)
