using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;
using System.Threading;
using Godot;
using HarmonyLib;
using MegaCrit.Sts2.Core.Commands;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;

namespace Sts2AgentBridge.Items.Native;

// Observe the native automatic effect, without reading or predicting a relic
// pool or random target. Only calls inside the retained AfterObtained invocation
// may advance the expected public inventory.
internal sealed partial class PinnedAutomaticRelicEffects : IDisposable
{
    internal sealed record Card(CardModel Model, string Key, int Level, EnchantmentModel? Enchantment, string? EnchantmentKey, decimal Amount);
    internal sealed class State
    {
        internal readonly Player Player;
        internal readonly object Run;
        internal readonly Card[] Deck;
        internal readonly (RelicModel Model, string Key)[] Relics;
        internal readonly (PotionModel? Model, string? Key)[] Potions;
        internal readonly int Gold, Hp, MaxHp;
        internal State(Player player)
        {
            Player=player; Run=player.RunState; Deck=player.Deck.Cards.Select(Copy).ToArray();
            Relics=player.Relics.Select(r=>(r,r.Id.Entry)).ToArray(); Potions=player.PotionSlots.Select(p=>(p,p?.Id.Entry)).ToArray();
            Gold=player.Gold; Hp=player.Creature.CurrentHp; MaxHp=player.Creature.MaxHp;
            if(Deck.Length>512||Relics.Length>128||Potions.Length>8||Gold<0||Hp<0||MaxHp<Hp||
                Deck.Select(c=>c.Model).Distinct(ReferenceEqualityComparer.Instance).Count()!=Deck.Length||
                Relics.Select(r=>r.Model).Distinct(ReferenceEqualityComparer.Instance).Count()!=Relics.Length||
                Deck.Any(c=>!ReferenceEquals(c.Model.Owner,player)||!ReferenceEquals(c.Model.RunState,Run))||
                Relics.Any(r=>!ReferenceEquals(r.Model.Owner,player))||Potions.Any(p=>p.Model is {} m&&!ReferenceEquals(m.Owner,player)))
                throw new InvalidOperationException("relic_public_inventory");
        }
        internal bool Same(State b) => ReferenceEquals(Player,b.Player)&&ReferenceEquals(Run,b.Run)&&Gold==b.Gold&&Hp==b.Hp&&MaxHp==b.MaxHp&&
            Deck.SequenceEqual(b.Deck)&&Relics.SequenceEqual(b.Relics)&&Potions.SequenceEqual(b.Potions);
        internal bool AddedRelic(State b, RelicModel relic) => ReferenceEquals(Player,b.Player)&&ReferenceEquals(Run,b.Run)&&Gold==b.Gold&&Hp==b.Hp&&MaxHp==b.MaxHp&&
            Deck.SequenceEqual(b.Deck)&&Potions.SequenceEqual(b.Potions)&&b.Relics.Length==Relics.Length+1&&Relics.SequenceEqual(b.Relics.Take(Relics.Length))&&ReferenceEquals(b.Relics[^1].Model,relic);
    }
    private static Card Copy(CardModel c)=>new(c,c.Id.Entry,c.CurrentUpgradeLevel,c.Enchantment,c.Enchantment?.Id.Entry,c.Enchantment?.Amount??0);
    private static readonly AsyncLocal<PinnedAutomaticRelicEffects?> Scope=new();
    private static readonly AsyncLocal<DragonFruit?> GoldHpSource=new();
    private readonly Player _player;
    private readonly RelicModel? _relic;
    private readonly CompoundPolicy? _compound;
    // Only the compound pickup owner supplies this policy, under the exact
    // retained AfterObtained invocation. Legacy Supports remains unchanged.
    internal sealed class CompoundPolicy
    {
        internal Func<bool> Authority=()=>false;
        internal bool GainGold,LoseGold,Hp,Damage;
        internal int Capacity=0;
        internal Func<CardModel,bool>? Upgrade,Added;
        internal Func<bool>? Modifying;
        internal Action? BeforeMutation;
    }
    private readonly Func<bool> _owner;
    private readonly int _thread=System.Environment.CurrentManagedThreadId;
    private readonly Harmony _hooks=new("sts.bridge.relic.effects."+Guid.NewGuid().ToString("N"));
    private readonly List<MethodInfo> _targets=new();
    private State _expected;
    private bool _failed,_disposed,_cleanupFailed;
    private int _calls;
    internal static bool Supports(RelicModel relic) => relic.GetType().Assembly==typeof(RelicModel).Assembly&&
        (relic.GetType().GetMethod("AfterObtained",Type.EmptyTypes)?.DeclaringType==typeof(RelicModel)||
        relic.GetType()==typeof(PotionBelt)||relic.GetType()==typeof(Strawberry)||relic.GetType()==typeof(Pear)||relic.GetType()==typeof(Mango)||
        relic.GetType()==typeof(LeesWaffle)||relic.GetType()==typeof(OldCoin)||relic.GetType()==typeof(WarPaint)||relic.GetType()==typeof(Whetstone)||relic.GetType()==typeof(BeltBuckle)||
        relic.GetType()==typeof(FakeMango)||relic.GetType()==typeof(FakeLeesWaffle));
    internal PinnedAutomaticRelicEffects(Player player,RelicModel relic,Func<bool> owner):this(player,relic,owner,null,null){}
    internal PinnedAutomaticRelicEffects(Player player,Func<bool> owner,Func<CardModel,bool> addedCard,Func<bool> modifyingCard):this(player,null,owner,addedCard,modifyingCard){}
    internal PinnedAutomaticRelicEffects(Player player,RelicModel relic,Func<bool> owner,CompoundPolicy compound):this(player,relic,owner,compound.Added,compound.Modifying,compound){}
    private PinnedAutomaticRelicEffects(Player player,RelicModel? relic,Func<bool> owner,Func<CardModel,bool>? addedCard,Func<bool>? modifyingCard,CompoundPolicy? compound=null)
    {
        _player=player;_relic=relic;_owner=owner;_expected=new(player);_addedCard=addedCard;_modifyingCard=modifyingCard;_compound=compound;
        Require((relic is not null?(Supports(relic)||compound is not null)&&ReferenceEquals(relic.Owner,player)&&player.Relics.Contains(relic):addedCard is not null)&&owner());
        try {
            Patch(typeof(Player).GetProperty("Gold")!.SetMethod!,nameof(GoldPrefix),nameof(GoldPostfix));
            Patch(player.Creature.GetType().GetMethod("SetCurrentHpInternal")!,nameof(HpPrefix),nameof(HpPostfix));
            Patch(player.Creature.GetType().GetMethod("SetMaxHpInternal")!,nameof(HpPrefix),nameof(HpPostfix));
            if(compound?.Damage==true)Patch(player.Creature.GetType().GetMethod("LoseHpInternal")!,nameof(DamagePrefix),nameof(DamagePostfix));
            Patch(typeof(Player).GetMethod("AddToMaxPotionCount")!,nameof(CapacityPrefix),nameof(CapacityPostfix));
            // CardCmd's single-card overload is a tiny forwarding wrapper and
            // can be inlined before its hook is installed. Observe the actual
            // model mutation without enumerating the native target sequence.
            Patch(typeof(CardModel).GetMethod("UpgradeInternal",Type.EmptyTypes)!,nameof(UpgradePrefix),nameof(UpgradePostfix));
            if((GoldEffect||addedCard is not null)&&player.Relics.Any(r=>r.GetType()==typeof(DragonFruit)))
                Patch(typeof(DragonFruit).GetMethod("AfterGoldGained")!,nameof(GoldHpPrefix),nameof(GoldHpPostfix));
            if(addedCard is not null)PatchCardAddEffects();
        } catch {_failed=true;Dispose();throw;}
    }
    internal PinnedAutomaticRelicEffects? Enter() { Require(Valid());var old=Scope.Value;Require(old is null);Scope.Value=this;return old; }
    internal static void Exit(PinnedAutomaticRelicEffects? old)=>Scope.Value=old;
    internal bool Valid()=>!_failed&&!_disposed&&System.Environment.CurrentManagedThreadId==_thread&&_owner()&&_expected.Same(new(_player))&&ExactHooks();
    private bool GoldEffect=>_relic?.GetType()==typeof(OldCoin)||_compound?.GainGold==true;
    private bool HpEffect => _compound?.Hp==true||_relic?.GetType()==typeof(Strawberry)||_relic?.GetType()==typeof(Pear)||_relic?.GetType()==typeof(Mango)||_relic?.GetType()==typeof(LeesWaffle)||_relic?.GetType()==typeof(FakeMango)||_relic?.GetType()==typeof(FakeLeesWaffle);
    private static PinnedAutomaticRelicEffects? Begin()
    {var s=Scope.Value;if(s is not null){s.Require(s._compound is null||s._compound.Authority());s._compound?.BeforeMutation?.Invoke();s.Require(s.Valid()&&++s._calls<=64);}return s;}
    private static void GoldPrefix(Player __instance,int __0,out PinnedAutomaticRelicEffects? __state)
    {__state=Begin();if(__state is {} s)s.Require(ReferenceEquals(__instance,s._player)&&
        ((s.GoldEffect||s.CardGoldEffect)&&__0>=s._expected.Gold||s._compound?.LoseGold==true&&__0>=0&&__0<=s._expected.Gold));}
    private static void GoldPostfix(PinnedAutomaticRelicEffects? __state) {if(__state is {} s)s.Accept("gold");}
    private static void HpPrefix(object __instance,decimal __0,out PinnedAutomaticRelicEffects? __state)
    {__state=Begin();if(__state is {} s)s.Require((s.HpEffect||s.CardHpEffect||(s.GoldEffect||s.CardGoldEffect)&&GoldHpSource.Value is {} source&&s._expected.Relics.Any(r=>ReferenceEquals(r.Model,source)))&&ReferenceEquals(__instance,s._player.Creature)&&__0>=0);}
    private static void HpPostfix(PinnedAutomaticRelicEffects? __state) {if(__state is {} s)s.Accept("hp");}
    private sealed record Damage(PinnedAutomaticRelicEffects Owner,int Hp,int MaxHp,decimal Amount);
    private static void DamagePrefix(object __instance,decimal __0,out Damage? __state)
    {
        __state=null;var owner=Begin();if(owner is null)return;
        owner.Require(owner._compound?.Damage==true&&ReferenceEquals(__instance,owner._player.Creature)&&__0>=0);
        __state=new(owner,owner._expected.Hp,owner._expected.MaxHp,__0);
    }
    private static void DamagePostfix(Damage? __state)
    {
        if(__state is not {} call)return;var owner=call.Owner;
        owner.Require(owner._player.Creature.MaxHp==call.MaxHp&&
            owner._player.Creature.CurrentHp==Math.Max(call.Hp-(int)Math.Min(call.Amount,999999999m),0));
        owner.Accept("hp");
    }
    private static void GoldHpPrefix(DragonFruit __instance,Player __0,out DragonFruit? __state)
    {
        __state=GoldHpSource.Value;var s=Scope.Value;if(s is null)return;
        s.Require(s.Valid()&&(s.GoldEffect||s.CardGoldEffect)&&__state is null&&ReferenceEquals(__0,s._player)&&
            ReferenceEquals(__instance.Owner,s._player)&&s._expected.Relics.Any(r=>ReferenceEquals(r.Model,__instance)));
        GoldHpSource.Value=__instance;
    }
    private static void GoldHpPostfix(DragonFruit? __state){if(Scope.Value is not null)GoldHpSource.Value=__state;}
    private static void CapacityPrefix(Player __instance,int __0,out PinnedAutomaticRelicEffects? __state)
    {__state=Begin();if(__state is {} s)s.Require(ReferenceEquals(__instance,s._player)&&
        (s._relic?.GetType()==typeof(PotionBelt)&&__0==2||s._compound?.Capacity>0&&__0==s._compound.Capacity));}
    private static void CapacityPostfix(PinnedAutomaticRelicEffects? __state) {if(__state is {} s)s.Accept("capacity");}
    private static void UpgradePrefix(CardModel __instance,out PinnedAutomaticRelicEffects? __state)
    {
        __state=Begin();if(__state is not {} s)return;
        // Egg modifiers may upgrade a detached copy. The insertion journal
        // binds the actual returned model; no existing deck card may change.
        if(s._addedCard is not null&&s._modifyingCard?.Invoke()==true&&ReferenceEquals(__instance.Owner,s._player)&&
            ReferenceEquals(__instance.RunState,s._player.RunState)&&!s._expected.Deck.Any(c=>ReferenceEquals(c.Model,__instance))){__state=null;return;}
        s.Require((s._relic?.GetType()==typeof(WarPaint)||s._relic?.GetType()==typeof(Whetstone)||s._compound?.Upgrade?.Invoke(__instance)==true)&&s._expected.Deck.Any(c=>ReferenceEquals(c.Model,__instance))&&__instance.IsUpgradable);
    }
    private static void UpgradePostfix(CardModel __instance,PinnedAutomaticRelicEffects? __state) {if(__state is {} s)s.Accept("upgrade",__instance);}
    private void Accept(string kind,CardModel? upgraded=null)
    {
        var next=new State(_player);var before=_expected;
        Require(_owner()&&ReferenceEquals(next.Run,before.Run)&&next.Relics.SequenceEqual(before.Relics));
        Require(kind=="gold"||next.Gold==before.Gold);
        Require(kind=="hp"||next.Hp==before.Hp&&next.MaxHp==before.MaxHp);
        Require(kind=="capacity" ? next.Potions.Length==before.Potions.Length+(_compound?.Capacity??2)&&next.Potions.Take(before.Potions.Length).SequenceEqual(before.Potions)&&next.Potions.Skip(before.Potions.Length).All(p=>p.Model is null):next.Potions.SequenceEqual(before.Potions));
        Require(next.Deck.Length==before.Deck.Length);
        for(int i=0;i<before.Deck.Length;i++) {
            var old=before.Deck[i];var card=next.Deck[i];
            Require(kind=="upgrade"&&ReferenceEquals(old.Model,upgraded)
                ? ReferenceEquals(old.Model,card.Model)&&old.Key==card.Key&&card.Level==old.Level+1&&old.Enchantment==card.Enchantment&&old.EnchantmentKey==card.EnchantmentKey&&old.Amount==card.Amount
                : old==card);
        }
        _expected=next;
    }
    private void Patch(MethodInfo method,string prefix,string postfix)
    {
        Require(method is not null&&method.GetMethodBody() is not null&&!(Harmony.GetPatchInfo(method)?.Owners.Any()??false));
        _targets.Add(method);_hooks.Patch(method,new HarmonyMethod(typeof(PinnedAutomaticRelicEffects),prefix),new HarmonyMethod(typeof(PinnedAutomaticRelicEffects),postfix));
    }
    private bool ExactHooks()=>_targets.All(m=>Harmony.GetPatchInfo(m) is {} p&&p.Owners.Count==1&&p.Owners.Contains(_hooks.Id));
    private void Require([System.Diagnostics.CodeAnalysis.DoesNotReturnIf(false)] bool condition){if(!condition){_failed=true;throw new InvalidOperationException("relic_effect_boundary");}}
    public void Dispose()
    {
        if(_disposed){if(_cleanupFailed)throw new InvalidOperationException("relic_effect_cleanup");return;}_disposed=true;
        try {
            _hooks.UnpatchAll(_hooks.Id);
            if(_targets.Any(m=>Harmony.GetPatchInfo(m)?.Owners.Contains(_hooks.Id)==true))throw new InvalidOperationException("relic_effect_cleanup");
        }catch{_cleanupFailed=true;throw;}
    }
}
