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
    internal Reward? Reward;
    internal object? Model;
    internal string Key=string.Empty;
    internal int Index;
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
        if(list is null||list.Count!=1)return false;
        var reward=list[0];
        if(reward is null||(reward.GetType()!=typeof(PotionReward)&&reward.GetType()!=typeof(RelicReward))||!ReferenceEquals(reward.Player,Binding.Player)||reward.ParentRewardSet is not null||
            reward.RewardsSetIndex<0||reward.RewardsSetIndex>255||!reward.IsPopulated||reward.SuccessfullySelected)return false;
        if(reward.GetType()==typeof(PotionReward)&&reward is PotionReward p&&p.Potion is PotionModel potion)
        {Kind=ItemV1ItemKind.Potion;Model=potion;Key=potion.Id.Entry;}
        else if(reward.GetType()==typeof(RelicReward)&&reward is RelicReward r&&r.Relic is RelicModel relic)
        {Kind=ItemV1ItemKind.Relic;Model=relic;Key=relic.Id.Entry;}
        else return false;
        if(!ValidKey(Key))return false;
        Rewards=list;Reward=reward;Index=reward.RewardsSetIndex;
        return Domain();
    }
    internal bool Domain()
    {
        if(!Context()||Rewards is null||!ReferenceEquals(Set.Rewards,Rewards)||Rewards.Count!=1||
            !ReferenceEquals(Rewards[0],Reward)||Reward is null||!ReferenceEquals(Reward.Player,Binding.Player)||
            Reward.ParentRewardSet is not null||Reward.RewardsSetIndex!=Index||!Reward.IsPopulated)return false;
        return Kind==ItemV1ItemKind.Potion&&Reward is PotionReward p&&p.Potion is PotionModel potion&&ReferenceEquals(potion,Model)&&potion.Id.Entry==Key||
            Kind==ItemV1ItemKind.Relic&&Reward is RelicReward r&&r.Relic is RelicModel relic&&ReferenceEquals(relic,Model)&&relic.Id.Entry==Key;
    }
    internal bool Overlay()=>Binding.Overlays.ScreenCount==0||Binding.Overlays.ScreenCount==1&&ReferenceEquals(Binding.Overlays.Peek(),Screen);
    internal bool TryButton(out NRewardButton? result)
    {
        result=null;
        if(!Domain()||Screen is null||!GodotObject.IsInstanceValid(Screen)||!Screen.IsVisibleInTree()||
            Binding.Overlays.ScreenCount!=1||!ReferenceEquals(Binding.Overlays.Peek(),Screen))return false;
        var nodes=new List<Node>{Screen};int buttons=0;
        for(int i=0;i<nodes.Count;i++)
        {
            var node=nodes[i];if(!GodotObject.IsInstanceValid(node))return false;
            if(node is NRewardButton button)
            {
                if(++buttons!=1||!ReferenceEquals(button.Reward,Reward)||
                    !button.IsVisibleInTree()||!button.IsEnabled)return false;
                result=button;
            }
            int count=node.GetChildCount(false);
            if(count<0||count>2048-nodes.Count)return false;
            for(int j=0;j<count;j++)nodes.Add(node.GetChild(j,false));
        }
        if(result is null)return false;
        if(Button is null)Button=result;
        return ReferenceEquals(Button,result);
    }
    internal bool Ready=>!Dispatched&&OfferTask is not null&&Binding.ChosenTask is not null&&Screen is not null;
    internal bool FailedTask=>OfferTask?.IsFaulted==true||OfferTask?.IsCanceled==true||CollectionTask?.IsFaulted==true||CollectionTask?.IsCanceled==true;
    internal static bool ValidKey(string key)=>key.Length is >=1 and <=128&&System.Linq.Enumerable.All(key,c=>c is >= 'A' and <= 'Z' or >= 'a' and <= 'z' or >= '0' and <= '9' or '_');
}
