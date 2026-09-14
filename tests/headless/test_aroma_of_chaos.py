"""Event-owned selectors and permanent upgrade/transformation continuation."""

from copy import deepcopy
import json

import pytest

from game.cli.headless_play import play_slice
from game.headless.cards.catalog import DEFAULT_CARDS, CardCatalog
from game.headless.events.aroma_of_chaos import AromaOfChaos
from game.headless.map.graph import MapGraph, MapNode
from game.headless.run.actions import ChooseNode, ChooseEventOption, ChooseEventCard, LeaveEvent, DiscardPotion
from game.headless.run.deck import transform_card
from game.headless.run.engine import RunEngine
from game.headless.run.inventory import add_potion
from game.headless.run.state import RunPhase


def aroma(*, card_ids=("strike","strike","bash"), enter=True, seed=2, cards=DEFAULT_CARDS):
    graph = MapGraph((MapNode("aroma1","event",("aroma2",),event_id="aroma_of_chaos"),
                      MapNode("aroma2","event",("fight",),event_id="aroma_of_chaos"),
                      MapNode("fight","combat",(),"overgrowth_nibbit")),"aroma1")
    run = RunEngine(seed=seed,card_ids=card_ids,cards=cards,graph=graph)
    if enter: run.apply(ChooseNode("aroma1"))
    return run


def snap(run): return json.loads(json.dumps(run.snapshot()))


def step(run,action):
    clone = RunEngine(cards=run.cards,card_ids=()); clone.restore(snap(run))
    assert clone.legal_actions() == run.legal_actions()
    clone.apply(action); result = run.apply(action)
    assert snap(run) == snap(clone)
    return result


def option(run,choice): return ChooseEventOption(run.state.pending["event_instance_id"],choice)


def select(run,card): return ChooseEventCard(run.state.pending["event_instance_id"],card)


def leave(run): return LeaveEvent(run.state.pending["event_instance_id"])


def reject(run,action):
    before = snap(run)
    with pytest.raises(ValueError): run.apply(action)
    assert snap(run) == before


@pytest.mark.parametrize("choice",["maintain_control","let_go"])
def test_selector_locks_other_commands_and_has_no_cancel(choice):
    run = aroma(); add_potion(run.state,"fire_potion")
    reject(run,leave(run))
    step(run,option(run,choice))
    assert run.state.pending["stage"] == "select_card"
    assert all(isinstance(a,ChooseEventCard) for a in run.legal_actions())
    assert len(run.legal_actions()) == 3
    reject(run,select(run,None)); reject(run,select(run,"missing"))
    reject(run,leave(run)); reject(run,option(run,choice))
    reject(run,DiscardPotion(run.state.potions[0].instance_id))
    step(run,select(run,run.state.deck[1].instance_id))
    assert run.state.pending["stage"] == "resolved"
    assert any(isinstance(a,LeaveEvent) for a in run.legal_actions())


def test_exact_permanent_upgrade_excludes_maxed_cards_and_uses_no_rng():
    run = aroma(); first,second,bash=run.state.deck; bash.upgrade()
    before_rng=run.state.rng.snapshot(); allocator=run.state.next_card_id
    step(run,option(run,"maintain_control"))
    assert select(run,bash.instance_id) not in run.legal_actions()
    step(run,select(run,second.instance_id))
    assert second.upgrade_level == 1 and first.upgrade_level == 0
    assert run.state.next_card_id == allocator and run.state.rng.snapshot() == before_rng
    reject(run,select(run,first.instance_id))
    step(run,leave(run))
    step(run,ChooseNode("aroma2")); step(run,option(run,"maintain_control"))
    # The sole remaining eligible card upgrades automatically.
    assert first.upgrade_level == 1 and run.state.pending["stage"] == "resolved"
    step(run,leave(run)); step(run,ChooseNode("fight"))
    combat_cards=[*run.combat.player.hand,*run.combat.player.deck.draw_pile]
    assert all(c.upgrade_level == 1 for c in combat_cards)


def test_transform_preserves_position_and_other_duplicates_but_not_upgrade_or_identity():
    run=aroma(); original=run.state.deck[1]; original.upgrade()
    keep=run.state.deck[0]; last=run.state.deck[2]; next_id=run.state.next_card_id
    step(run,option(run,"let_go")); step(run,select(run,original.instance_id))
    replacement=run.state.deck[1]
    assert run.state.deck[0] is keep and run.state.deck[2] is last
    assert replacement.instance_id == f"run.card.{next_id}" and replacement.upgrade_level == 0
    assert replacement.definition.definition_id in AromaOfChaos().transform_pool
    assert all(c.instance_id != original.instance_id for c in run.state.deck)
    assert run.state.rng.request_count("event.aroma_transform") == 1
    step(run,leave(run)); step(run,ChooseNode("aroma2"))
    step(run,option(run,"maintain_control")); step(run,select(run,keep.instance_id)); step(run,leave(run))
    step(run,ChooseNode("fight"))
    combat_ids={c.instance_id for c in [*run.combat.player.hand,*run.combat.player.deck.draw_pile]}
    assert replacement.instance_id in combat_ids and original.instance_id not in combat_ids


@pytest.mark.parametrize("choice",["maintain_control","let_go"])
def test_one_and_zero_card_auto_resolution(choice):
    run=aroma(card_ids=("strike",)); old=run.state.deck[0]
    step(run,option(run,choice))
    assert run.state.pending["stage"] == "resolved"
    if choice == "maintain_control": assert old.upgrade_level == 1
    else: assert run.state.deck[0].instance_id != old.instance_id
    empty=aroma(card_ids=()); before=empty.state.rng.snapshot()
    step(empty,option(empty,choice))
    assert empty.state.pending["stage"] == "resolved" and empty.state.pending["data"]["result"] is None
    assert empty.state.rng.snapshot() == before
    step(empty,leave(empty))


def test_no_upgrade_candidates_finishes_without_mutation():
    run=aroma()
    for card in run.state.deck: card.upgrade()
    before=[(c.instance_id,c.upgrade_level) for c in run.state.deck]
    step(run,option(run,"maintain_control"))
    assert run.state.pending["stage"] == "resolved"
    assert before == [(c.instance_id,c.upgrade_level) for c in run.state.deck]
    step(run,leave(run))


def test_exact_rng_continuation_and_excluding_original_definition():
    for seed in range(15):
        a,b=aroma(seed=seed,card_ids=("pommel_strike",)),aroma(seed=seed,card_ids=("pommel_strike",))
        before=snap(a)
        for _ in range(3): a.legal_actions();snap(a)
        assert snap(a)==before
        b.state.rng.randint("shop.stock",0,10)
        step(a,option(a,"let_go"));b.apply(option(b,"let_go"))
        assert a.state.deck[0].definition.definition_id != "pommel_strike"
        assert a.state.deck[0].definition == b.state.deck[0].definition
        assert a.state.pending == b.state.pending


def test_stale_selector_and_choice_cannot_mutate_next_event():
    run=aroma(); choice=option(run,"let_go");selection=select(run,run.state.deck[0].instance_id)
    step(run,choice);step(run,selection);step(run,leave(run));step(run,ChooseNode("aroma2"))
    reject(run,choice);step(run,option(run,"let_go"));reject(run,selection)


@pytest.mark.parametrize("pool",[("strike",),("strike","strike"),("missing",),()])
def test_transform_failure_preserves_deck_ids_and_rng(pool):
    run=aroma();before=snap(run)
    with pytest.raises(ValueError): transform_card(run.state,run.cards,run.state.deck[0].instance_id,pool)
    assert snap(run)==before


def test_missing_catalog_or_unsupported_source_rejects_entry_atomically():
    cases=[aroma(card_ids=("wound",),enter=False),aroma(enter=False,cards=CardCatalog((DEFAULT_CARDS.definition("strike"),DEFAULT_CARDS.definition("bash"))))]
    for run in cases:
        before=snap(run)
        with pytest.raises(ValueError):run.apply(ChooseNode("aroma1"))
        assert snap(run)==before


def test_transform_failure_during_selection_preserves_parent(monkeypatch):
    run=aroma();step(run,option(run,"let_go"));before=snap(run)
    from game.headless.core.rng import GameRandomService
    def fail(self,stream,values): raise ValueError("failed draw")
    monkeypatch.setattr(GameRandomService,"choice",fail)
    with pytest.raises(ValueError):run.apply(select(run,run.state.deck[0].instance_id))
    assert snap(run)==before


@pytest.mark.parametrize("mutation",["eligible","duplicate","one_card","choice","result","selected","stage","schema","content","dead"])
def test_malformed_selector_snapshot_is_atomic(mutation):
    run=aroma();step(run,option(run,"let_go"));before=snap(run);broken=deepcopy(before)
    pending=broken["state"]["pending"];data=pending["data"]
    if mutation=="eligible":data["eligible"]=["missing","unknown"]
    elif mutation=="duplicate":data["eligible"][1]=data["eligible"][0]
    elif mutation=="one_card":data["eligible"]=data["eligible"][:1]
    elif mutation=="choice":data["choice"]="join_forces"
    elif mutation=="result":data["result"]={}
    elif mutation=="selected":data["selected_card_id"]=data["eligible"][0]
    elif mutation=="stage":pending["stage"]="resolved"
    elif mutation=="schema":broken["schema"]="headless_run_state_v7"
    elif mutation=="content":next(e for e in broken["events"] if e["definition_id"]=="aroma_of_chaos")["transform_pool"].append("strike")
    elif mutation=="dead":broken["state"]["phase"]="defeat";broken["state"]["hp"]=0
    with pytest.raises(ValueError):run.restore(broken)
    assert snap(run)==before


@pytest.mark.parametrize("choice",["let_go","maintain_control"])
@pytest.mark.parametrize("field,value",[("instance_id","missing"),("definition_id","strike"),("upgrade_level",True),("upgrade_level",9)])
def test_resolved_result_snapshot_binds_actual_card(choice,field,value):
    run=aroma(card_ids=("bash",));step(run,option(run,choice));before=snap(run);broken=deepcopy(before)
    broken["state"]["pending"]["data"]["result"][field]=value
    with pytest.raises(ValueError):run.restore(broken)
    assert snap(run)==before


def test_installed_route_consumer_picks_aroma_and_upgrades(original_slice_rewards):
    run,trace=play_slice(seed=2,route="overgrowth-act1",path="right",rest_choice="rest",verify_restore=True)
    assert "aroma" in run.state.visited_nodes and "jungle_maze" not in run.state.visited_nodes
    assert any(t["action"]=="ChooseEventCard" for t in trace)
    assert next(c for c in run.state.deck if c.definition.definition_id=="bash").upgrade_level==1
    assert run.state.phase is RunPhase.ACT_COMPLETE
