using System;
using System.Collections.Generic;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
namespace Godot {public class Label:Control {public string Text {get;set;}="";}}
namespace MegaCrit.Sts2.Core.Entities.Merchant {
    public enum PurchaseStatus {Success,Failure}
    public class MerchantEntry {
        private Player _player=null!;public void SetPlayer(Player player)=>_player=player;
        public int Cost {get;set;}
        public bool IsStocked {get;set;}=true;
        public bool EnoughGold {get;set;}=true;
        public event Action<PurchaseStatus,MerchantEntry>? PurchaseCompleted;
        public int Subscribers=>PurchaseCompleted?.GetInvocationList().Length??0;
        public void Complete(PurchaseStatus status)=>PurchaseCompleted?.Invoke(status,this);
    }
    public class MerchantCardRemovalEntry:MerchantEntry {
        public bool Used {get;set;}
        public Func<MerchantInventory,bool,bool,System.Threading.Tasks.Task<bool>>? Wrapper;
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public System.Threading.Tasks.Task<bool> OnTryPurchaseWrapper(MerchantInventory inventory,bool ignoreCost,bool cancelable)=>Wrapper!(inventory,ignoreCost,cancelable);
    }
    public class MerchantPotionEntry:MerchantEntry {public PotionModel? Model {get;set;}=new();}
    public class MerchantRelicEntry:MerchantEntry {public RelicModel Model {get;set;}=new();}
    public class MerchantInventory {public Player Player {get;set;}=null!;}
}
namespace MegaCrit.Sts2.Core.Nodes.Screens.Shops {
    public class NMerchantInventory:Godot.Control {
        public MerchantInventory Inventory {get;set;}=new();public bool IsOpen {get;set;}
        public List<NMerchantRelic> Slots {get;}=new();public IEnumerable<NMerchantRelic> GetAllSlots()=>Slots;
    }
    public class NMerchantRelic:Godot.Control {
        public MerchantEntry Entry {get;set;}=new MerchantRelicEntry();
        public NButton Hitbox {get;set;}=new();public Action? Purchase;public int Inputs;
        public void _GuiInput(Godot.InputEventAction input){Inputs++;Purchase?.Invoke();}
    }
}
namespace MegaCrit.Sts2.Core.Nodes.CommonUi {public class NBackButton:NButton {}}
namespace MegaCrit.Sts2.Core.Nodes.Rooms {public class NMerchantButton:NButton {public bool IsLocalPlayerDead {get;set;}}}
namespace MegaCrit.Sts2.Core.Models.Events {public class FakeMerchant:EventModel {
public Func<MegaCrit.Sts2.Core.Models.Potions.FoulPotion,System.Threading.Tasks.Task>? FoulHandler;
[System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
public System.Threading.Tasks.Task FoulPotionThrown(MegaCrit.Sts2.Core.Models.Potions.FoulPotion potion)=>FoulHandler!(potion);
public bool StartedFight {get;set;}public MerchantInventory Inventory {get;set;}=new();}}
namespace MegaCrit.Sts2.Core.Nodes.Events.Custom {
    public class NFakeMerchant:Godot.Control {
        private MegaCrit.Sts2.Core.Models.Events.FakeMerchant _event=null!;
        private MegaCrit.Sts2.Core.Nodes.CommonUi.NProceedButton _proceedButton=null!;
        private Godot.Control _inputBlocker=null!;
        public NMerchantInventory Inventory {get;set;}=new();
        public MegaCrit.Sts2.Core.Nodes.Rooms.NMerchantButton MerchantButton {get;set;}=new();
        public void Initialize(MegaCrit.Sts2.Core.Models.Events.FakeMerchant model,MegaCrit.Sts2.Core.Nodes.CommonUi.NProceedButton proceed,Godot.Control blocker){_event=model;_proceedButton=proceed;_inputBlocker=blocker;Bind("%ProceedButton",proceed);Bind("%InputBlocker",blocker);}
    }
}
