"""Common public combat belief, independent of the receipt's producer.

Historical fresh-inventory prefixes and campaign entry receipts normalize to
one contract. Setup timing is explicit: room-entry effects run exactly once.
The legacy validators retain their original admission semantics; a bridge can
produce this contract when it has equivalent public evidence, not a snapshot.
"""
from copy import deepcopy

from game.agent.contracts import full as f
from game.headless.draw_knowledge import DrawKnowledge, HPKnowledge, InconsistentKnowledge
from game.headless.planning import UnsupportedSearch
from game.headless.reveals import CombatReveals, validate_reveals
from game.headless.run.construction import campaign_combat, revealed_encounter
from .belief import _boundary
from . import campaign, observed

MODEL = 'combat_belief_v1'
ANCHOR = 'sts_combat_anchor_v1'


def normalize_anchor(anchor):
    if not isinstance(anchor, dict):
        raise ValueError('Invalid public combat anchor')
    schema = anchor.get('schema')
    if schema == observed.ANCHOR:
        value = observed.validate_anchor(anchor)
        value.update(schema=ANCHOR, setup_stage='fresh_before_room_entry', facts={}, ruleset='ironclad_campaign_v1')
    elif schema == campaign.ANCHOR:
        value = campaign.validate_anchor(anchor)
        value.update(schema=ANCHOR, setup_stage='after_room_entry', ruleset='ironclad_campaign_v1')
    elif schema == ANCHOR:
        value = deepcopy(anchor)
    else:
        raise ValueError('Unknown public combat anchor schema')
    if (set(value) != {'schema', 'setup_stage', 'ruleset', 'initial', 'opening', 'opening_reveals', 'transitions', 'facts'}
            or not isinstance(value['transitions'], list) or len(value['transitions']) > 512):
        raise ValueError('Invalid public combat anchor fields')
    initial, opening = f.from_dict(value['initial']), f.from_dict(value['opening'])
    expected_ruleset = ('declared_combat_v1' if initial.context.get('entry_action_kind') == 'declared_combat'
                        else 'ironclad_campaign_v1')
    if value['ruleset'] != expected_ruleset:
        raise ValueError('Combat producer ruleset mismatch')
    if value['setup_stage'] == 'fresh_before_room_entry':
        # This legacy producer explicitly certifies fresh templates and empty
        # instance data. It is not an inference about an arbitrary campaign.
        if value['facts'] != {}:
            raise ValueError('Unexpected fresh inventory facts')
        legacy = {k: v for k, v in value.items() if k not in ('setup_stage', 'facts', 'ruleset')}
        legacy['schema'] = observed.ANCHOR
        observed.validate_anchor(legacy)
    elif value['setup_stage'] == 'after_room_entry':
        if initial.context.get('entry_action_kind') not in ('choose_map_node', 'declared_combat'):
            raise UnsupportedSearch('campaign_event_or_missing_entry_context')
        facts = value['facts']
        if (not isinstance(facts, dict) or set(facts) != {'card_combats'} or not isinstance(facts['card_combats'], dict)
                or any(type(k) is not str or type(v) is not int or v < 0 for k, v in facts['card_combats'].items())):
            raise ValueError('Invalid public combat facts')
        campaign.inventory(initial, facts)
    else:
        raise ValueError('Unknown combat setup stage')
    validate_reveals(value['opening_reveals'])
    _boundary(opening)
    enemies = [n.definition_id for n in f.walk(opening.context) if n.kind == 'enemy']
    try:
        revealed_encounter(enemies)
    except ValueError as error:
        raise UnsupportedSearch('campaign_event_or_unknown_encounter') from error
    if opening.context.get('round') != 1:
        raise UnsupportedSearch('campaign_missing_opening')
    current = opening
    for row in value['transitions']:
        if not isinstance(row, dict) or set(row) != {'action_ref', 'successor', 'reveals'}:
            raise ValueError('Invalid public combat prefix')
        if row['action_ref'] not in {a.ref for a in current.candidates}:
            raise ValueError('Prefix action is not advertised')
        validate_reveals(row['reveals'])
        current = f.from_dict(row['successor'])
        _boundary(current)
    return value


def inventory(anchor):
    initial = f.from_dict(anchor['initial'])
    if anchor['setup_stage'] == 'after_room_entry':
        return campaign.inventory(initial, anchor['facts'])
    old = observed.inventory(initial)
    old.pop('encounter_id')
    return dict(old,
        deck=[dict(definition_id=name, upgrade_level=upgrade, enchantment=enchantment,
                   combats_seen=0, permanent_damage=0, permanent_block=0)
              for name, upgrade, enchantment in old['deck']],
        relics=[(name, count, {}) for name, count in old['relics']], fur_coat_active=False)


class CombatBelief(observed.ObservedCombatBelief):
    validate_anchor = staticmethod(normalize_anchor)

    def _fresh_opening(self):
        events = self.anchor['opening_reveals']
        knowledge = DrawKnowledge()
        knowledge.condition([tuple(e['value']) for e in events if e['kind'] in ('draw', 'autoplay_top')], self._seed())
        journal = CombatReveals(events, seed=self._seed())
        enemies = [n for n in f.walk(self.opening.context) if n.kind == 'enemy']
        hp = HPKnowledge(tuple(n.get('max_hp') for n in enemies))
        from game.headless.characters import potion_pool
        from game.headless.run.config import RunConfig
        potions = (RunConfig().reward_potions if self.anchor['ruleset'] == 'declared_combat_v1'
                   else potion_pool('ironclad'))
        try:
            run = campaign_combat(**inventory(self.anchor),
                encounter_id=revealed_encounter([n.definition_id for n in enemies]),
                seed=self._seed(), draw_knowledge=knowledge, hp_knowledge=hp, reveal_journal=journal,
                room_entered=self.anchor['setup_stage'] == 'after_room_entry', reward_potions=potions)
            knowledge.finish()
            journal.finish()
            world = campaign.CampaignWorld(run, knowledge, self.opening)
            world.log_weight = knowledge.log_likelihood + journal.log_likelihood + hp.log_likelihood
            return world, self._key(world.project()) == self._opening_key
        except InconsistentKnowledge:
            return None, False
        except (ValueError, KeyError) as error:
            raise UnsupportedSearch('combat_setup_unsupported') from error
