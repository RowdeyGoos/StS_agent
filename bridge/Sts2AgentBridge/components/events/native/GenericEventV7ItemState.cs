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
    internal bool HasCards=>System.Linq.Enumerable.Any(Entries!,e=>e.CardReward is not null);
    internal bool IsMixed=>HasCards&&System.Linq.Enumerable.Any(Entries!,e=>e.CardReward is null);
    internal int OfferCount=>Entries?.Length??1;
    internal Reward? Reward;
    internal GenericEventV7CardRewardAdapter? CardReward;
    internal object? Model;
    internal string Key=string.Empty;
    internal int Index, NativeIndex;
    internal int CapacityGain;
    internal ItemV1ItemKind Kind;
    internal NRewardsScreen? Screen;
    internal NRewardButton? Button;
    internal Task? OfferTask,CollectionTask;
    internal bool ScreenEntered,CollectionEntered,Dispatched,Closed;
    internal GenericEventV7ItemState(GenericEventV7Binding binding,RewardsSet set)
    { Binding=binding;Set=set;DisallowSkipping=set.DisallowSkipping; }
    internal bool Context()=>!Closed&&!Binding.Failed&&Binding.ItemContextValid()&&ReferenceEquals(Set.Player,Binding.Player)&&Set.DisallowSkipping==DisallowSkipping&&RewardsSet.testSelector is null;
    internal bool BindDomain()
    {
        if(!Context())return false;
        var list=Set.Rewards;
        if(list is null||list.Count is <1 or >8)return false;
        Rewards=list;
        int cardCount=list.FindAll(r=>r is not null&&r.GetType()==typeof(CardReward)).Count;
        if(Binding.Combat?.Resumes==true&&cardCount>0)return false;
        if(cardCount>0&&GenericEventV7Binding.CopyDeck(Binding.Player).Length>512-cardCount)return false;
        var entries=new GenericEventV7ItemState[list.Count];
        var identities=new HashSet<object>(ReferenceEqualityComparer.Instance);
        for(int i=0;i<list.Count;i++) {
            var entry=i==0?this:new GenericEventV7ItemState(Binding,Set);
            entry.Rewards=list;entry.Position=i;entry.Root=this;
            var reward=list[i];
            if(reward is not null&&reward.GetType()==typeof(CardReward)) {
                entry.Reward=reward;entry.Index=entry.NativeIndex=reward.RewardsSetIndex;
                if(!identities.Add(reward)||!ReferenceEquals(reward.Player,Binding.Player)||reward.ParentRewardSet is not null||!reward.IsPopulated||reward.SuccessfullySelected)return false;
                entry.CardReward=new GenericEventV7CardRewardAdapter(entry,(CardReward)reward);
                foreach(var card in entry.CardReward.Originals)if(!identities.Add(card))return false;
            }else {
                if(!entry.BindReward(reward!)||!identities.Add(entry.Reward!)||!identities.Add(entry.Model!))return false;
                if(list.Count>1)entry.Index=i;
            }
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
        CapacityGain=Sts2AgentBridge.Items.Native.PinnedPotionCapacity.Gain(Model);
        Reward=reward;Index=NativeIndex=reward.RewardsSetIndex;
        return true;
    }
    private bool LocalDomain() {
        if(!Context()||Reward is null||!ReferenceEquals(Reward.Player,Binding.Player)||
            Reward.ParentRewardSet is not null||Reward.RewardsSetIndex!=NativeIndex||(CardReward is null&&!Reward.IsPopulated)||
            Reward.SuccessfullySelected&&!Dispatched)return false;
        if(CardReward is not null)return CardReward.Domain();
        if(CapacityGain!=Sts2AgentBridge.Items.Native.PinnedPotionCapacity.Gain(Model))return false;
        if(CapacityGain>0) {
            var capacityRelic=(RelicModel)Model!;
            int owned=System.Linq.Enumerable.Count(Binding.Player.Relics,r=>ReferenceEquals(r,capacityRelic));
            bool absent=capacityRelic.Owner is null&&owned==0;
            bool acquired=ReferenceEquals(capacityRelic.Owner,Binding.Player)&&owned==1;
            if(!Dispatched?!absent:Reward.SuccessfullySelected?!acquired:!absent&&!acquired)return false;
        }
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
    // Preserve the native order. A later capacity grant cannot rescue an earlier
    // full-inventory potion; no pickup is sent for an impossible sequence.
    internal bool CapacityPlan()
    {
        if(!GenericEventV7ItemAdapter.Slots(Binding.Player,out int capacity,out var slots))return false;
        int free=System.Linq.Enumerable.Count(slots,s=>s.ModelIdentity is null);
        foreach(var entry in (Root??this).Entries!) {
            if(entry.CardReward is not null)continue;
            if(entry.CapacityGain>0) {capacity+=entry.CapacityGain;free+=entry.CapacityGain;if(capacity>8)return false;}
            if(entry.Kind==ItemV1ItemKind.Potion && --free<0)return false;
        }
        return true;
    }
    internal bool CapacityMatches(int baseline,int current)
    {
        int settled=baseline,pending=0;
        foreach(var entry in (Root??this).Entries!) {
            if(entry.CapacityGain==0)continue;
            if(entry.Dispatched&&entry.CollectionEntered) {
                if(entry.Reward!.SuccessfullySelected)settled+=entry.CapacityGain;
                else pending+=entry.CapacityGain;
            }
        }
        return current<=8&&(current==settled||current==settled+pending);
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
    internal bool Ready=>!Dispatched&&OfferTask is not null&&Binding.ItemParentTask is not null&&Screen is not null;
    internal bool FailedTask=>OfferTask?.IsFaulted==true||OfferTask?.IsCanceled==true||CollectionTask?.IsFaulted==true||CollectionTask?.IsCanceled==true;
    internal static bool ValidKey(string key)=>key.Length is >=1 and <=128&&System.Linq.Enumerable.All(key,c=>c is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or >= '0' and <= '9' or '_');
}
