using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Successors.ItemV1;
namespace Sts2AgentBridge.Successors.GenericEventV7.Native;

// One actual Offer invocation owns one post-generation screen and one collection.
internal sealed class GenericEventV7ItemState
{
    internal readonly GenericEventV7Binding Binding;
    internal readonly RewardsSet Set;
    internal readonly bool DisallowSkipping;
    internal List<Reward>? Rewards;
    internal GenericEventV7ItemState[]? Entries;
    internal GenericEventV7ItemState? Root;
    internal int Position;
    internal int OfferCount=>Entries?.Length??1;
    internal Reward? Reward;
    internal GenericEventV7CardRewardAdapter? CardReward;
    internal object? Model;
    internal string Key=string.Empty;
    internal int Index, NativeIndex;
    internal ItemV1ItemKind Kind;
    internal NRewardsScreen? Screen;
    internal NRewardButton? Button;
    internal Task? OfferTask,CollectionTask;
    internal bool ScreenEntered,CollectionEntered,Dispatched,Closed;
    internal GenericEventV7ItemState(GenericEventV7Binding binding,RewardsSet set)
    { Binding=binding;Set=set;DisallowSkipping=set.DisallowSkipping; }
    internal bool Context()=>!Closed&&!Binding.Failed&&!Binding.Closed&&GenericEventV7Hooks.Owns(Binding)&&
        Binding.ContextValid(false)&&ReferenceEquals(Set.Player,Binding.Player)&&Set.DisallowSkipping==DisallowSkipping&&RewardsSet.testSelector is null;
    internal bool BindDomain()
    {
        if(!Context())return false;
        var list=Set.Rewards;
        if(list is null||list.Count is <1 or >8)return false;
        Rewards=list;
        if(list.TrueForAll(r=>r is not null&&r.GetType()==typeof(CardReward))) {
            if(GenericEventV7Binding.CopyDeck(Binding.Player).Length>512-list.Count)return false;
            var cards=new HashSet<object>(ReferenceEqualityComparer.Instance);
            var rewards=new HashSet<object>(ReferenceEqualityComparer.Instance);
            var cardEntries=new GenericEventV7ItemState[list.Count];
            for(int i=0;i<list.Count;i++) {
                var entry=i==0?this:new GenericEventV7ItemState(Binding,Set);
                entry.Rewards=list;entry.Position=i;entry.Root=this;entry.Reward=list[i];
                entry.Index=entry.NativeIndex=list[i].RewardsSetIndex;
                if(!rewards.Add(list[i])||!ReferenceEquals(list[i].Player,Binding.Player)||list[i].ParentRewardSet is not null||!list[i].IsPopulated||list[i].SuccessfullySelected)return false;
                entry.CardReward=new GenericEventV7CardRewardAdapter(entry,(CardReward)list[i]);
                foreach(var card in entry.CardReward.Originals)if(!cards.Add(card))return false;
                cardEntries[i]=entry;
            }
            Entries=cardEntries;return Domain();
        }
        var entries=new GenericEventV7ItemState[list.Count];
        var identities=new HashSet<object>(ReferenceEqualityComparer.Instance);
        for(int i=0;i<list.Count;i++) {
            var entry=i==0?this:new GenericEventV7ItemState(Binding,Set);
            entry.Rewards=list;entry.Position=i;entry.Root=this;
            if(!entry.BindReward(list[i])||!identities.Add(entry.Reward!)||!identities.Add(entry.Model!))return false;
            if(list.Count>1)entry.Index=i;
            entries[i]=entry;
        }
        Entries=entries;
        return Domain();
    }
    private bool BindReward(Reward reward) {
        if(reward is null||(reward.GetType()!=typeof(PotionReward)&&reward.GetType()!=typeof(RelicReward))||!ReferenceEquals(reward.Player,Binding.Player)||reward.ParentRewardSet is not null||
            reward.RewardsSetIndex<0||reward.RewardsSetIndex>255||!reward.IsPopulated||reward.SuccessfullySelected)return false;
        if(reward.GetType()==typeof(PotionReward)&&reward is PotionReward p&&p.Potion is PotionModel potion)
        {Kind=ItemV1ItemKind.Potion;Model=potion;Key=potion.Id.Entry;}
        else if(reward.GetType()==typeof(RelicReward)&&reward is RelicReward r&&r.Relic is RelicModel relic)
        {Kind=ItemV1ItemKind.Relic;Model=relic;Key=relic.Id.Entry;}
        else return false;
        if(!ValidKey(Key))return false;
        Reward=reward;Index=NativeIndex=reward.RewardsSetIndex;
        return true;
    }
    private bool LocalDomain() {
        if(!Context()||Reward is null||!ReferenceEquals(Reward.Player,Binding.Player)||
            Reward.ParentRewardSet is not null||Reward.RewardsSetIndex!=NativeIndex||(CardReward is null&&!Reward.IsPopulated)||
            Reward.SuccessfullySelected&&!Dispatched)return false;
        if(CardReward is not null)return CardReward.Domain();
        return Kind==ItemV1ItemKind.Potion&&Reward is PotionReward p&&p.Potion is PotionModel potion&&ReferenceEquals(potion,Model)&&potion.Id.Entry==Key||
            Kind==ItemV1ItemKind.Relic&&Reward is RelicReward r&&r.Relic is RelicModel relic&&ReferenceEquals(relic,Model)&&relic.Id.Entry==Key;
    }
    internal bool Domain() {
        var root=Root??this;
        if(!root.Context()||root.Rewards is null||!ReferenceEquals(Set.Rewards,root.Rewards)||root.Entries is null||root.Rewards.Count!=root.Entries.Length)return false;
        for(int i=0;i<root.Entries.Length;i++) {
            var e=root.Entries[i];
            if(!ReferenceEquals(root.Rewards[i],e.Reward)||!e.LocalDomain())return false;
        }
        return true;
    }
    internal bool Overlay()=>Binding.Overlays.ScreenCount==0||Binding.Overlays.ScreenCount==1&&ReferenceEquals(Binding.Overlays.Peek(),Screen);
    internal bool TryButton(out NRewardButton? result)
    {
        result=null;
        if(!Domain()||Screen is null||!GodotObject.IsInstanceValid(Screen)||!Screen.IsVisibleInTree()||
            Binding.Overlays.ScreenCount!=1||!ReferenceEquals(Binding.Overlays.Peek(),Screen))return false;
        var nodes=new List<Node>{Screen};var seen=new HashSet<object>(ReferenceEqualityComparer.Instance);
        for(int i=0;i<nodes.Count;i++)
        {
            var node=nodes[i];if(!GodotObject.IsInstanceValid(node))return false;
            if(node is NRewardButton button)
            {
                var entries=(Root??this).Entries!;
                GenericEventV7ItemState? entry=null;
                foreach(var e in entries)if(ReferenceEquals(e.Reward,button.Reward))entry=e;
                if(entry is null||!seen.Add(entry.Reward!))return false;
                if(entry.Reward!.SuccessfullySelected)continue;
                if(!button.IsVisibleInTree()||!button.IsEnabled)return false;
                if(entry.Button is null)entry.Button=button;
                if(!ReferenceEquals(entry.Button,button))return false;
                if(ReferenceEquals(entry,this))result=button;
            }
            int count=node.GetChildCount(false);
            if(count<0||count>2048-nodes.Count)return false;
            for(int j=0;j<count;j++)nodes.Add(node.GetChild(j,false));
        }
        foreach(var e in (Root??this).Entries!)if(!e.Reward!.SuccessfullySelected&&!seen.Contains(e.Reward))return false;
        if(result is null)return false;
        if(Button is null)Button=result;
        return ReferenceEquals(Button,result);
    }
    internal bool Ready=>!Dispatched&&OfferTask is not null&&Binding.ChosenTask is not null&&Screen is not null;
    internal bool FailedTask=>OfferTask?.IsFaulted==true||OfferTask?.IsCanceled==true||CollectionTask?.IsFaulted==true||CollectionTask?.IsCanceled==true;
    internal static bool ValidKey(string key)=>key.Length is >=1 and <=128&&System.Linq.Enumerable.All(key,c=>c is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or >= '0' and <= '9' or '_');
}
