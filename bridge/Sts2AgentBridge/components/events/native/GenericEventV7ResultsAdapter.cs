using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using Godot;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using Sts2AgentBridge.Successors.CardSelectionV1;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

internal sealed class GenericEventV7ResultsAdapter:IGenericEventV7ResultsAdapter {
    internal readonly GenericEventV7Binding Binding;
    internal readonly List<CardPileAddResult> Results;
    private readonly CardModel[] _models;
    private readonly CardSelectionV1DeckCard[] _deck;
    private readonly GenericEventV7RewardCard[] _cards;
    private readonly NCapstoneContainer _container;
    internal NSimpleCardsViewScreen? Screen;
    private NButton? _confirm;private object? _screenCards;
    private bool _attempted,_disposed;
    internal int Count=>_models.Length;
    internal GenericEventV7ResultsAdapter(GenericEventV7Binding binding,List<CardPileAddResult> results){
        Binding=binding;Results=results;
        Require(results is not null&&results.Count is >=1 and <=64);_models=results!.Select(r=>r.cardAdded).ToArray();
        Require(results!.All(r=>r.success)&&_models.All(c=>c is not null)&&_models.Distinct(ReferenceEqualityComparer.Instance).Count()==Count);
        _deck=GenericEventV7Binding.CopyDeck(binding.Player);
        Require(_models.All(c=>_deck.Count(d=>ReferenceEquals(d.ModelIdentity,c))==1));
        _cards=_models.Select((c,i)=>new GenericEventV7RewardCard(i,c.Id.Entry,c.CurrentUpgradeLevel)).ToArray();
        _container=NCapstoneContainer.Instance!;Require(Valid(_container)&&!_container.InUse&&_container.CurrentCapstoneScreen is null);
    }
    private void Require(bool value){if(!value){Binding.Failed=true;throw new InvalidOperationException("Unowned card results.");}}
    private static bool Valid(GodotObject? obj)=>obj is not null&&GodotObject.IsInstanceValid(obj);
    private static object? Field(object obj,Type type,string name)=>type.GetField(name,BindingFlags.Instance|BindingFlags.NonPublic)?.GetValue(obj);
    internal bool OwnsCapstone()=>!_disposed&&ReferenceEquals(NCapstoneContainer.Instance,_container)&&Valid(_container)&&
        (_container.CurrentCapstoneScreen is null||Screen is not null&&ReferenceEquals(_container.CurrentCapstoneScreen,Screen));
    internal void BindScreen(NSimpleCardsViewScreen result){
        Require(Screen is null&&ReferenceEquals(NCapstoneContainer.Instance,_container)&&_container.CurrentCapstoneScreen is NSimpleCardsViewScreen&&ReferenceEquals(_container.CurrentCapstoneScreen,result));
        Screen=(NSimpleCardsViewScreen)_container.CurrentCapstoneScreen!;
        Require(Screen.GetType()==typeof(NSimpleCardsViewScreen)&&Valid(Screen)&&ReferenceEquals(Field(Screen,typeof(NSimpleCardsViewScreen),"_cardResults"),Results));
    }
    private void Domain(){
        Require(!_disposed&&!Binding.Failed&&!Binding.Closed&&GenericEventV7Hooks.Owns(Binding)&&Binding.ContextValid(false)&&OwnsCapstone()&&Binding.Overlays.ScreenCount==0);
        Require(Results.Count==Count);
        for(int i=0;i<Count;i++)Require(Results[i].success&&ReferenceEquals(Results[i].cardAdded,_models[i]));
        var deck=GenericEventV7Binding.CopyDeck(Binding.Player);Require(deck.Length==_deck.Length);
        for(int i=0;i<deck.Length;i++)Require(ReferenceEquals(deck[i].ModelIdentity,_deck[i].ModelIdentity)&&deck[i].StableKey==_deck[i].StableKey&&deck[i].UpgradeLevel==_deck[i].UpgradeLevel&&CardSelectionV1Enchantment.Same(deck[i].Enchantment,_deck[i].Enchantment)&&
            deck[i].ModelIdentity is CardModel c&&ReferenceEquals(c.Owner,Binding.Player)&&ReferenceEquals(c.RunState,Binding.RunState));
        Require(_cards.All(c=>GenericEventV7ItemState.ValidKey(c.Key)&&c.UpgradeLevel>=0));
    }
    public GenericEventV7ResultsCapture Capture(){
        try {
            Domain();Require(Binding.ChosenTask?.IsFaulted!=true&&Binding.ChosenTask?.IsCanceled!=true);
            if(_attempted) {
                if(_container.CurrentCapstoneScreen is not null)return new("waiting",Array.Empty<GenericEventV7RewardCard>());
                Require(!_container.InUse);if(Binding.ChosenTask?.IsCompletedSuccessfully!=true)return new("waiting",Array.Empty<GenericEventV7RewardCard>());
                return new("resolved",_cards);
            }
            Require(Screen is not null&&Valid(Screen)&&ReferenceEquals(_container.CurrentCapstoneScreen,Screen)&&_container.InUse);
            Require(ReferenceEquals(Field(Screen!,typeof(NSimpleCardsViewScreen),"_cardResults"),Results));
            var cards=Field(Screen!,typeof(NCardsViewScreen),"_cards");Require(cards is IReadOnlyList<CardModel> list&&list.Count==Count&&!list.Where((c,i)=>!ReferenceEquals(c,_models[i])).Any());
            if(_screenCards is not null)Require(ReferenceEquals(cards,_screenCards));_screenCards=cards;
            var button=Screen!.GetNodeOrNull<NButton>("ConfirmButton");Require(Valid(button)&&ReferenceEquals(Field(Screen,typeof(NSimpleCardsViewScreen),"_confirmButton"),button));
            if(_confirm is not null)Require(ReferenceEquals(_confirm,button));_confirm=button;
            if(!Screen.IsVisibleInTree()||!button!.IsVisibleInTree()||!button.IsEnabled)return new("waiting",Array.Empty<GenericEventV7RewardCard>());
            return new("ready",_cards);
        }catch{Binding.Failed=true;return new("unsupported",Array.Empty<GenericEventV7RewardCard>());}
    }
    public void Confirm(){Require(Capture().Status=="ready"&&!_attempted);_attempted=true;_confirm!.ForceClick();}
    public void Dispose(){_disposed=true;}
}
