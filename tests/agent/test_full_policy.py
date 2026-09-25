"""The common chooser consumes both native display values and headless specs."""
from game.agent.contracts import full as f
from game.agent.full_policy import choose_action


def node(kind, *, ref=None, fields=(), children=(), links=()):
    return f.Node(kind, kind, ref, tuple(f.Field(*v) for v in fields),
                  tuple(f.Link(k, tuple(v)) for k, v in links), tuple(children))


def decision(context, actions, deck=()):
    return f.PublicDecision(f.SCHEMA, f.PROFILE,
        node('run', fields=(('hp', 80), ('max_hp', 80)), children=deck), context, tuple(actions))


def test_native_previews_are_consumed_without_inventing_a_static_spec():
    attack = node('card', ref='card:0', children=(node('preview', fields=(('damage', 9),)),))
    block = node('card', ref='card:1', children=(node('preview', fields=(('block', 12),)),))
    enemy = node('enemy', ref='enemy:0', fields=(('hp', 20),))
    plays = (f.Candidate('action:0', 'play_card', 'card:0', 'enemy:0'),
             f.Candidate('action:1', 'play_card', 'card:1'), f.Candidate('action:2', 'end_turn'))
    view = decision(node('combat', children=(attack, block, enemy)), plays)
    assert choose_action(f.loads(f.dumps(view))) == plays[0]


def test_headless_static_spec_remains_supported():
    attack = node('card', ref='card:0', children=(node('spec', fields=(('base_damage', 10),)),))
    block = node('card', ref='card:1', children=(node('spec', fields=(('block_gain', 15),)),))
    plays = (f.Candidate('action:0', 'play_card', 'card:0'), f.Candidate('action:1', 'play_card', 'card:1'))
    assert choose_action(decision(node('combat', children=(attack, block)), plays)) == plays[0]


def test_native_smith_preview_confirms_instead_of_selecting_another_card():
    cards = (node('card', ref='card:0'), node('card', ref='card:1'))
    selection = node('selection', fields=(('minimum', 1), ('maximum', 1)),
                     links=(('options', ('card:0', 'card:1')), ('selected', ('card:0',))))
    actions = (f.Candidate('action:0', 'deselect_card', 'card:0'),
               f.Candidate('action:1', 'choose_upgrade', 'card:1'),
               f.Candidate('action:2', 'confirm_selection'), f.Candidate('action:3', 'cancel_selection'))
    assert choose_action(decision(node('rest', children=(selection,)), actions, cards)) == actions[2]
