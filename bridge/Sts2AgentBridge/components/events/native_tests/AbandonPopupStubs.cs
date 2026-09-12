using System;
using Godot;
namespace MegaCrit.Sts2.Core.Nodes.Screens.MainMenu { public class NMainMenu:Control {} }
namespace MegaCrit.Sts2.Core.Nodes.CommonUi {
    public class NModalContainer:Control {
        public static NModalContainer? Instance {get;set;}
        public object? OpenModal {get;set;}
        public void Add(Node node,bool backstop=true){if(OpenModal is not null)return;OpenModal=node;Children.Add(node);}
        public void Clear(){OpenModal=null;Children.Clear();}
    }
    public class NPopupYesNoButton:MegaCrit.Sts2.Core.Nodes.GodotExtensions.NButton {}
    public class NVerticalPopup:Control {
        public NPopupYesNoButton YesButton {get;set;}=new();
        public NPopupYesNoButton NoButton {get;set;}=new();
    }
    public class NAbandonRunConfirmPopup:Control {
        private MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu? _mainMenuNode;
        private NVerticalPopup _verticalPopup=new();
        public NVerticalPopup Vertical=>_verticalPopup;
        public static Func<NAbandonRunConfirmPopup>? Factory;
        public NAbandonRunConfirmPopup(){Bind("VerticalPopup",_verticalPopup);_verticalPopup.NoButton.Clicked=()=>NModalContainer.Instance!.Clear();_verticalPopup.YesButton.Clicked=()=>{MegaCrit.Sts2.Core.Runs.RunManager.Instance!.Abandon();NModalContainer.Instance!.Clear();};}
        [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
        public static NAbandonRunConfirmPopup Create(MegaCrit.Sts2.Core.Nodes.Screens.MainMenu.NMainMenu? mainMenu){var popup=Factory?.Invoke()??new();popup._mainMenuNode=mainMenu;return popup;}
    }
}

namespace MegaCrit.Sts2.Core.Models.Events {
    public sealed class Trial:MegaCrit.Sts2.Core.Models.EventModel {
        public Func<System.Threading.Tasks.Task>? PopupHandler;
        public Func<System.Threading.Tasks.Task> PopupCallback=>DoubleDown;
        private System.Threading.Tasks.Task DoubleDown()=>PopupHandler?.Invoke()??System.Threading.Tasks.Task.CompletedTask;
    }
}
