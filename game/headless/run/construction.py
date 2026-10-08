"""Construct declared combat setups and fork owned hypothetical combats.

These are domain helpers, not a public snapshot sanitizer. A caller declares
fresh card templates and already-owned inventory; acquisition effects have
already happened. Normal combat setup, effects and settlement own all rules.
"""
from game.headless.cards.catalog import DEFAULT_CARDS
from game.headless.core.native_service import NativeRandomService, bind_combat
from game.headless.core.snapshots import card_record, restore_card
from game.headless.potions.base import PotionInstance
from game.headless.relics.base import RelicInstance
from game.headless.run.config import RunConfig
from game.headless.run.engine import RunEngine


def declared_combat_region(encounter_id):
    """Resolve an ordinary Act 1 encounter using the engine's own registries.

    Event encounters need their event/room continuation and cannot use this
    fresh inventory entry point. No private map assignment is consulted.
    """
    from game.headless.encounters.catalog import (NATIVE_OVERGROWTH_ENCOUNTERS,
                                                   NATIVE_UNDERDOCKS_ENCOUNTERS)
    for region, registry in (('overgrowth', NATIVE_OVERGROWTH_ENCOUNTERS),
                             ('underdocks', NATIVE_UNDERDOCKS_ENCOUNTERS)):
        if encounter_id in registry.values():
            return region
    raise ValueError('Declared combat requires a registered ordinary Act 1 encounter.')


def declared_combat(*, deck, relics, potions, hp, max_hp, gold,
                    encounter_id, seed, cards=DEFAULT_CARDS, draw_knowledge=None, hp_knowledge=None):
    """Ironclad A0 setup with fresh (definition, upgrade) card templates.

Relics are (definition, explicit counter) with empty instance data. This is a
complete setup declaration, not an inference that missing counters/data are zero.
No gameplay seed, private continuation, actor or observation object is accepted.
"""
    if type(seed) is not int:
        raise ValueError('A simulation seed is required.')
    region = declared_combat_region(encounter_id)
    run = RunEngine(seed=seed, card_ids=[], hp=hp, max_hp=max_hp, gold=gold,
                    cards=cards, config=RunConfig(act=region), rng_profile='native')
    for definition, upgrade in deck:
        card = cards.create(definition, upgrade_level=upgrade,
                            instance_id=run.state.allocate_card_id())
        # Reuse runtime validation, including content requiring extra state.
        run.state.deck.append(restore_card(card_record(card), cards))
    run.state.relics = [RelicInstance(name, run.state.allocate_item_id(), count)
                        for name, count in relics]
    run.state.potion_capacity = len(potions)
    run.state.potions = [None if name is None else
                         PotionInstance(name, run.state.allocate_item_id()) for name in potions]
    run.state.validate()
    # Optional conditional proposal owners are local to this newly constructed
    # hypothetical world. They are not snapshot fields or global RNG overrides.
    try:
        run.start_combat(encounter_id=encounter_id, draw_knowledge=draw_knowledge, hp_knowledge=hp_knowledge)
        if hp_knowledge is not None:
            hp_knowledge.finish()
    finally:
        if hasattr(run.state.rng.stream('niche'), 'hp_knowledge'):
            del run.state.rng.stream('niche').hp_knowledge
    return run


def fork_combat(run, *, future_seed=None):
    """Independent branch; optionally sample fresh *future* native randomness.

Call only on a hypothetical world at a supported decision. Existing
draw order and resolved effects are retained. Changing future randomness is a
planning approximation, never an operation on the real game or its seed.
"""
    if run.combat is None:
        raise ValueError('A live hypothetical combat is required.')
    if future_seed is not None:
        p = run.combat.player
        selecting = p.pending_play is not None or p.rules.selection is not None
        if (type(future_seed) is not int or not isinstance(run.state.rng, NativeRandomService)
                or (not selecting and (p.rules.tasks or p.rules.enemy_turn is not None or p.rules.turn_ending))):
            raise ValueError('Future RNG requires a supported native decision boundary.')
        if selecting:
            from game.headless.core.actions import ChooseCombatCard, ConfirmCombatSelection
            actions = run.legal_actions()
            if not actions or any(not isinstance(a, (ChooseCombatCard, ConfirmCombatSelection)) for a in actions):
                raise ValueError('Future RNG requires an owned combat selection.')
    from game.headless.run.snapshots import restore_run
    # Restoration validates selector ownership, queued tasks and any captured
    # enemy hit/turn cursor. A suspended engine-owned selection is a decision
    # boundary too; already captured hits/offers remain in this snapshot.
    branch = restore_run(run.snapshot(), cards=run.cards)
    if future_seed is not None:
        old = branch.state.rng
        # Validate the ownership graph before changing streams. Keep every
        # stream object alive so deck/enemy aliases continue to refer to it.
        bind_combat(old, branch.combat)
        fresh = NativeRandomService(future_seed)
        fresh.active_event = old.active_event
        for name in old.stream_names:
            stream = old.stream(name)
            stream.setstate(fresh.stream(name).getstate())
            fresh._streams[name] = stream
        branch.state.seed, branch.state.rng = future_seed, fresh
        bind_combat(fresh, branch.combat)
    return branch


def materialize_combat_draw(run, knowledge):
    """Resample an owned hypothetical pile and its derived selector ordering.

    Call only after normal snapshot validation. Pending choices cache an order
    derived from that pile; resampling changes this cache, never their members,
    selected order, bounds or sampled whitelist. Deferred live choices retain
    their captured membership until the ordinary hook scheduler resumes them.
    """
    p = run.combat.player
    knowledge.materialize(p.deck)
    for selection, deferred in [(p.rules.selection, False),
                               *((h['selection'], True) for h in p.rules.deferred_hooks)]:
        if selection is None:
            continue
        cards = _draw_selection_cards(p, selection)
        if cards is None:
            continue
        identities = [c.instance_id for c in cards]
        if len(identities) != len(selection['candidates']) or set(identities) != set(selection['candidates']):
            if deferred:
                # Live eligibility can have changed while this hook is paused.
                # The scheduler, not hypothetical resampling, owns its refresh.
                continue
            raise ValueError('Hypothetical draw choice changed membership.')
        selection['candidates'] = identities


def _draw_selection_cards(p, selection):
    """Reuse ordinary engine eligibility; no selection effects or RNG calls."""
    from game.headless.core.piles import draw_choice_cards, stratagem_cards
    source, operation = selection['source'], selection['operation']
    if source in p.rules.potion_uses:
        from game.headless.potions.selections import SETTINGS, eligible
        kind = p.rules.potion_uses[source]['definition_id']
        if kind in SETTINGS and SETTINGS[kind][0] == 'draw_pile':
            return eligible(p, kind)
        return None
    if operation in ('nec_cleanse', 'nec_seance'):
        from game.headless.cards.necrobinder_effects import choice_settings
        return choice_settings(p, operation.removeprefix('nec_'))[0]
    if operation in ('regent_charge', 'regent_charge_up'):
        from game.headless.cards.regent_effects import choice_settings
        return choice_settings(p, 'charge')[0]
    if operation == 'regent_foregone_conclusion':
        return stratagem_cards(p)
    if source == 'stratagem':
        return draw_choice_cards(p, source)
    card = next((c for c in p.deck.in_play if c.instance_id == source), None)
    frame = p.rules.plays.get(source)
    if card is None or frame is None:
        return None
    effect = card.definition.effects[frame['effect_index']]
    kind = getattr(effect, 'operation', None)
    if kind in ('secret_technique', 'secret_weapon', 'seeker_strike'):
        return draw_choice_cards(p, kind, selection.get('whitelist'))
    return None


def inventory_combat(*, deck, relics, potions, hp, max_hp, gold, encounter_id,
                     seed, draw_knowledge=None, reveal_journal=None):
    """Fresh ordinary Ironclad inventory, including declared enchantments.

    Inputs are plain template records and already-owned items, never an engine
    snapshot. Acquisition effects have already happened. Combat setup and
    settlement run through the normal engine, with its character potion pool.
    """
    from game.headless.characters import potion_pool
    from game.headless.enchantments.base import restore as restore_enchantment
    run = RunEngine(seed=seed, card_ids=[], hp=hp, max_hp=max_hp, gold=gold,
                    config=RunConfig(act=declared_combat_region(encounter_id),
                                     reward_potions=potion_pool('ironclad')),
                    rng_profile='native')
    for definition, upgrade, enchantment in deck:
        card = run.cards.create(definition, upgrade_level=upgrade,
                                instance_id=run.state.allocate_card_id())
        card.enchantment = restore_enchantment(enchantment)
        run.state.deck.append(restore_card(card_record(card), run.cards))
    run.state.relics = [RelicInstance(name, run.state.allocate_item_id(), count) for name, count in relics]
    run.state.potion_capacity = len(potions)
    run.state.potions = [None if name is None else PotionInstance(name, run.state.allocate_item_id())
                         for name in potions]
    run.state.validate()
    from contextlib import nullcontext
    from game.headless.reveals import run_reveals
    with run_reveals(run, reveal_journal) if reveal_journal is not None else nullcontext():
        run.start_combat(encounter_id=encounter_id, draw_knowledge=draw_knowledge)
    return run
