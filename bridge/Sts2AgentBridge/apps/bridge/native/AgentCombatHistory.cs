using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;

namespace Sts2AgentBridge.Unified;

// Observe public plays from combat setup, never reconstruct them from the game's
// private history. Late attachment explicitly lacks the virtual power-card pile.
internal sealed class AgentCombatHistory : IDisposable
{
    private CombatState? _combat;
    private readonly List<CardPile> _piles = new();
    private readonly Dictionary<CardModel, Action> _listeners = new(ReferenceEqualityComparer.Instance);
    private readonly List<(CardModel Card, JsonObject View)> _powers = new();
    private readonly Func<CardModel, JsonObject> _freeze;
    private readonly Dictionary<CardModel, JsonObject> _entering = new(ReferenceEqualityComparer.Instance);
    private CardPile? _play;
    private bool _overflow;
    internal AgentCombatHistory(Func<CardModel, JsonObject> freeze) { _freeze = freeze; CombatManager.Instance.CombatSetUp += Setup; }
    private void Setup(CombatState combat)
    {
        Clear();
        if (combat.Players.Count != 1 || combat.Players[0].PlayerCombatState is not {} player) return;
        _combat = combat;
        _play = player.PlayPile; _play.CardAdded += EnterPlay;
        foreach (var pile in player.AllPiles)
        {
            _piles.Add(pile); pile.CardAdded += Watch;
            foreach (var card in pile.Cards) Watch(card);
        }
    }
    private void Watch(CardModel card)
    {
        if (_listeners.ContainsKey(card)) return;
        if (_listeners.Count >= 512) { _overflow = true; return; }
        Action listener = () => {
            if (card.Type == CardType.Power && !_powers.Any(p => ReferenceEquals(p.Card, card)))
            {
                if (_powers.Count >= 64) _overflow = true;
                else if (_entering.Remove(card, out var view)) _powers.Add((card, view));
                else _overflow = true;
            }
        };
        card.Played += listener; _listeners.Add(card, listener);
    }
    private void EnterPlay(CardModel card)
    {
        // Played fires after cost cleanup. The play-pile entry is the last
        // physical public descriptor, before temporary costs reset.
        try { if (card.Type == CardType.Power) _entering[card] = _freeze(card); }
        catch { _overflow = true; }
    }
    internal (CardModel Card, JsonObject View)[] Powers(CombatState combat)
    {
        if (_overflow || !ReferenceEquals(combat, _combat)) throw new AgentUnsupported();
        return _powers.ToArray();
    }
    private void Clear()
    {
        foreach (var pair in _listeners) pair.Key.Played -= pair.Value;
        foreach (var pile in _piles) pile.CardAdded -= Watch;
        if (_play is not null) _play.CardAdded -= EnterPlay;
        _play = null; _entering.Clear();
        _listeners.Clear(); _piles.Clear(); _powers.Clear(); _combat = null; _overflow = false;
    }
    public void Dispose() { CombatManager.Instance.CombatSetUp -= Setup; Clear(); }
}
