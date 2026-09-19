"""Content-owned pages using the same deck/reward continuation as Act 1 events.

Only page names, offered values, chosen options and operation receipts are saved.
Executable plans are always rebuilt from the immutable event definition.
"""
from copy import deepcopy
from dataclasses import dataclass
from game.headless.events.steps import StepEvent, complete, drain, select, reward
from game.headless.events.checkpoint import capture, refresh
from game.headless.core.snapshots import card_record


@dataclass(frozen=True)
class FlowEvent(StepEvent):
    branches: tuple = ()

    @property
    def combat_encounter_ids(self):
        from game.headless.events.fights import ENCOUNTERS
        return ENCOUNTERS.get(self.definition_id, ())

    def generate(self, rng, *, state, cards):
        from game.headless.events.roster import page, ANCIENTS
        if self.definition_id in ANCIENTS:
            from game.headless.relics.run_rules import heal
            heal(state, state.max_hp)
        context = page(self.definition_id, 'initial', state, cards, rng, [])
        data = dict(choice=None, cursor=0, active=None, receipts=[], eligible=[],
                    variables={}, options=context['options'], originals=[card_record(c) for c in state.deck],
                    pages=[dict(name='initial', context=context, choice=None)])
        data['checkpoint'] = capture(state, data)
        return data

    def plan(self, data):
        from game.headless.events.roster import branch
        result = []
        for index, row in enumerate(data['pages']):
            if row['choice'] is None:
                break
            operations, next_page = branch(self.definition_id, row['name'], row['choice'], row['context'])
            result.extend([list(op) for op in operations])
            if next_page is not None:
                result.append(['page', next_page, index + 1])
        return result

    def open_page(self, state, pending, cards, name, index):
        from game.headless.events.roster import page
        data = pending['data']
        if index != len(data['pages']):
            raise ValueError('Event page was already entered.')
        context = page(self.definition_id, name, state, cards, state.rng, data['pages'])
        data['pages'].append(dict(name=name, context=context, choice=None))
        data['active'] = {'page': index}
        pending['stage'] = 'page'

    def options(self, pending):
        if pending['stage'] == 'page':
            return tuple(pending['data']['pages'][-1]['context']['options'])
        return super().options(pending)

    def choose(self, state, pending, option_id, *, cards):
        self._atomic(state, cards, option=option_id)
        if state.pending and state.pending["stage"] == "fight":
            from game.headless.events.combat import EventCombatRequest
            return EventCombatRequest(state.pending["data"]["active"]["encounter_id"])

    def select_card(self, state, pending, identity, *, cards):
        return self._atomic(state, cards, identity=identity)

    def _atomic(self, state, cards, *, option=None, identity=None):
        trial = deepcopy(state)
        pending = trial.pending
        data = pending['data']
        if identity is not None:
            select(trial, pending, cards, identity)
        elif pending['stage'] in ('options', 'page'):
            if option not in self.options(pending):
                raise ValueError('Unavailable event option.')
            if pending['stage'] == 'page':
                complete(data, self.plan(data)[data['cursor']], option)
            data['pages'][-1]['choice'] = option
            data['choice'] = data['pages'][0]['choice']
        else:
            reward(trial, pending, cards, option)
        drain(trial, cards)
        refresh(trial)
        state.__dict__.clear()
        state.__dict__.update(trial.__dict__)

    def validate(self, pending, *, state, cards, defeated=False):
        from game.headless.events.step_snapshots import restore_records, validate_active
        from game.headless.events.roster import branch, validate_context
        data = pending['data']
        if not isinstance(data, dict) or set(data) != {'choice','cursor','active','receipts','eligible','variables','options','originals','pages','checkpoint'}:
            raise ValueError('Invalid paged event fields.')
        if data['checkpoint'] != capture(state, data):
            raise ValueError('Event state differs from its last successful command.')
        restore_records(data['originals'], state, cards)
        if data['variables'] or not isinstance(data['pages'], list) or not data['pages']:
            raise ValueError('Invalid event pages.')
        expected = 'initial'
        for index, row in enumerate(data['pages']):
            if not isinstance(row, dict) or set(row) != {'name','context','choice'} or row['name'] != expected:
                raise ValueError('Event page differs from its branch.')
            validate_context(self.definition_id, row['name'], row['context'], cards)
            if row['choice'] is None:
                if index != len(data['pages']) - 1:
                    raise ValueError('Unanswered event page has successors.')
            elif row['choice'] not in row['context']['options']:
                raise ValueError('Unknown event page option.')
            else:
                _, expected = branch(self.definition_id, row['name'], row['choice'], row['context'])
        if data['choice'] != data['pages'][0]['choice'] or data['options'] != data['pages'][0]['context']['options']:
            raise ValueError('Event initial choice changed.')
        plan = self.plan(data)
        cursor = data['cursor']
        if type(cursor) is not int or not 0 <= cursor <= len(plan) or not isinstance(data['receipts'], list) or len(data['receipts']) != cursor:
            raise ValueError('Invalid event cursor.')
        for op, receipt in zip(plan, data['receipts']):
            if not isinstance(receipt, dict) or set(receipt) != {'operation','result'} or receipt['operation'] != op:
                raise ValueError('Event receipt differs from content.')
            if op[0] == 'page' and receipt['result'] != data['pages'][op[2]]['choice']:
                raise ValueError('Event page receipt differs from choice.')
        if pending['stage'] == 'fight':
            if defeated or state.relic_work or cursor >= len(plan) or plan[cursor][0] != 'combat' or data['active'] != {'encounter_id': plan[cursor][1]} or plan[cursor][1] not in self.combat_encounter_ids:
                raise ValueError('Invalid pending event combat.')
        elif pending['stage'] == 'page':
            if defeated or state.relic_work or cursor >= len(plan) or plan[cursor][0] != 'page' or data['active'] != {'page': len(data['pages']) - 1} or data['pages'][-1]['choice'] is not None or data['eligible']:
                raise ValueError('Invalid pending event page.')
        else:
            validate_active(self, pending, state, cards, plan, defeated=defeated)

    def is_allowed(self, conditions):
        from game.headless.events.roster import allowed
        return allowed(self.definition_id, conditions)
