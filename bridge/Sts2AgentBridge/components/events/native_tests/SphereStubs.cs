using System;
using System.Threading.Tasks;
using System.Runtime.CompilerServices;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
namespace MegaCrit.Sts2.Core.Events.Custom.CrystalSphereEvent {
    public sealed class CrystalSphereCell {public object? Item;public int X,Y;public bool IsHidden=true;}
    public sealed class CrystalSphereMinigame {
        private Player _owner;
        public CrystalSphereCell[,] cells=new CrystalSphereCell[11,11];
        public int DivinationCount=10;
        public enum CrystalSphereToolType {Small=1,Big=2}
        public CrystalSphereToolType CrystalSphereTool=CrystalSphereToolType.Small;
        public Func<CrystalSphereCell,Task>? Click;
        public CrystalSphereMinigame(Player owner){_owner=owner;for(int x=0;x<11;x++)for(int y=0;y<11;y++)cells[x,y]=new(){X=x,Y=y};}
        public void SetOwner(Player owner)=>_owner=owner;
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Events.Custom.CrystalSphere {
    using MegaCrit.Sts2.Core.Events.Custom.CrystalSphereEvent;
    using MegaCrit.Sts2.Core.Nodes.CommonUi;
    public sealed class NCrystalSphereCell:NClickableControl {public CrystalSphereCell Entity=null!;}
    public sealed class NCrystalSphereScreen:Control,MegaCrit.Sts2.Core.Nodes.Screens.Overlays.IOverlayScreen {
        private CrystalSphereMinigame _entity=null!;
        public static Action<CrystalSphereMinigame>? Factory;
        public void Initialize(CrystalSphereMinigame game)=>_entity=game;
        [MethodImpl(MethodImplOptions.NoInlining)]public static void ShowScreen(CrystalSphereMinigame game)=>Factory!(game);
        private Task OnCellClicked(NCrystalSphereCell cell)=>_entity.Click!(cell.Entity);
    }
}

namespace MegaCrit.Sts2.Core.Models.Cards { public sealed class Doubt:CardModel { } }
namespace MegaCrit.Sts2.Core.Commands {
    public static class CardPileCmd {
        public static async Task<MegaCrit.Sts2.Core.Models.CardModel> AddCurseToDeck<T>(Player player) where T:MegaCrit.Sts2.Core.Models.CardModel,new() {var card=new T{Owner=player};card.Id.Entry="DOUBT";var result=await AddCursesToDeck(new[]{card},player);return System.Linq.Enumerable.First(result).cardAdded;}
        [MethodImpl(MethodImplOptions.NoInlining)]public static Task<System.Collections.Generic.IEnumerable<MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult>> AddCursesToDeck(System.Collections.Generic.IEnumerable<MegaCrit.Sts2.Core.Models.CardModel> cards,Player player) {
            var results=new System.Collections.Generic.List<MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult>();foreach(var card in cards){player.Deck.Cards.Add(card);results.Add(new(){success=true,cardAdded=card});}return Task.FromResult<System.Collections.Generic.IEnumerable<MegaCrit.Sts2.Core.Entities.Cards.CardPileAddResult>>(results);
        }
    }
}
