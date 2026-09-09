using System;
using System.Collections.Generic;
using System.Linq;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Runs;

namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// One dispatch ticket survives native CallDeferred. Only its matching synchronous
// callback may observe original-to-clone pairs; observation never issues a ticket.
internal sealed class GenericEventV7MultiUpgradeState
{
    private readonly GenericEventV7Binding _binding;
    private NGridCardHolder? _ticketHolder;
    private CardModel? _ticketOriginal;
    private Func<bool>? _ticketValid;
    private bool _active, _closed;
    private int _cloneCalls;
    private readonly List<CardModel> _selected = new();
    private readonly Dictionary<CardModel,CardModel> _pairs = new(ReferenceEqualityComparer.Instance);
    internal GenericEventV7MultiUpgradeState(GenericEventV7Binding binding) => _binding=binding;
    internal IReadOnlyList<CardModel> Selected => _selected;
    internal bool Pending => _ticketOriginal is not null || _active;
    internal bool Complete => !_closed && !_binding.Failed && !Pending && _selected.Count==_binding.Prefs.MaxSelect && _pairs.Count==_selected.Count;
    internal bool TryOriginal(CardModel clone,out CardModel original)
    {
        original=null!;
        foreach(var pair in _pairs) if(ReferenceEquals(pair.Value,clone)){original=pair.Key;return true;}
        return false;
    }
    internal void Reserve(NGridCardHolder holder,CardModel original,Func<bool> ticketValid)
    {
        if(_closed||_binding.Failed||Pending||!GenericEventV7Hooks.Owns(_binding)||!_binding.MatchesChildBinding()||
            !_binding.MatchesCurrentDeck()||_selected.Count>=_binding.Prefs.MaxSelect||_selected.Contains(original,ReferenceEqualityComparer.Instance)||
            !_binding.Originals.Contains(original,ReferenceEqualityComparer.Instance)||!GodotObject.IsInstanceValid(holder)||!ReferenceEquals(holder.CardModel,original))
        {_binding.Failed=true;throw new InvalidOperationException("Multi-upgrade dispatch ticket unavailable.");}
        _ticketHolder=holder;_ticketOriginal=original;_ticketValid=ticketValid;
    }
    internal bool Begin(NDeckUpgradeSelectScreen screen,CardModel original)
    {
        if(_closed||_binding.Failed||_active||_ticketHolder is null||_ticketOriginal is null||
            !GenericEventV7Hooks.Owns(_binding)||!_binding.MatchesChildBinding()||!_binding.MatchesCurrentDeck()||
            !ReferenceEquals(_binding.Screen,screen)||!ReferenceEquals(_ticketOriginal,original)||
            !GodotObject.IsInstanceValid(_ticketHolder)||!ReferenceEquals(_ticketHolder.CardModel,original)||_ticketValid?.Invoke()!=true)
        {_binding.Failed=true;return false;}
        _ticketHolder=null;_ticketOriginal=null;_ticketValid=null;_active=true;_cloneCalls=0;_selected.Add(original);return true;
    }
    internal bool CloneEntry(RunState run,CardModel original)
    {
        if(!_active||_closed||_binding.Failed||!GenericEventV7Hooks.Owns(_binding)||
            run.GetType()!=typeof(RunState)||!ReferenceEquals(run,_binding.RunState)||
            _selected.Count!=_binding.Prefs.MaxSelect||!_selected.Contains(original,ReferenceEqualityComparer.Instance)||
            _pairs.ContainsKey(original)||++_cloneCalls>_binding.Prefs.MaxSelect)
        {_binding.Failed=true;return false;}
        return true;
    }
    internal void CloneExit(CardModel original,CardModel? clone)
    {
        if(!_active||_closed||_binding.Failed||clone is null||_pairs.ContainsKey(original)||
            _binding.SelectionDeck.Any(c=>ReferenceEquals(c.ModelIdentity,clone))||
            _binding.Originals.Contains(clone,ReferenceEqualityComparer.Instance)||
            _pairs.Values.Contains(clone,ReferenceEqualityComparer.Instance)||
            _binding.ObservedUpgradeClones.Count>=32||_binding.ObservedPreviewClones.Count>=64||!_binding.ObservedPreviewClones.Add(clone)||!_binding.ObservedUpgradeClones.Add(clone))
        {_binding.Failed=true;return;}
        _pairs.Add(original,clone);
    }
    internal void End(bool faulted)
    {
        if(!_active||faulted||(_selected.Count==_binding.Prefs.MaxSelect? _pairs.Count!=_selected.Count||_cloneCalls!=_selected.Count:_pairs.Count!=0||_cloneCalls!=0))
            _binding.Failed=true;
        _active=false;
    }
    internal void Fail()=>_binding.Failed=true;
    internal void Close(){_closed=true;_ticketHolder=null;_ticketOriginal=null;_ticketValid=null;_active=false;}
}
