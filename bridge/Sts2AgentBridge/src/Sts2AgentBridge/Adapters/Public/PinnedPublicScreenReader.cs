using Godot;
using MegaCrit.Sts2.Core.Nodes;
using MegaCrit.Sts2.Core.Nodes.Screens.MainMenu;
using MegaCrit.Sts2.Core.Nodes.Screens.Settings;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Adapters.Public;

public sealed class PinnedPublicScreenReader : IPublicScreenReader
{
    public PublicScreenFacts Read()
    {
        NGame? game = NGame.Instance;
        if (game is null || !GodotObject.IsInstanceValid(game))
        {
            return new PublicScreenFacts(
                HasValidGame: false,
                HasValidRoot: false,
                PublicMenuState.MissingOrInvalid,
                PublicSubmenuStackState.MissingOrInvalid,
                PublicTopSubmenuState.TransitionAmbiguous);
        }

        NSceneContainer? root = game.RootSceneContainer;
        if (root is null || !GodotObject.IsInstanceValid(root))
        {
            return new PublicScreenFacts(
                HasValidGame: true,
                HasValidRoot: false,
                PublicMenuState.MissingOrInvalid,
                PublicSubmenuStackState.MissingOrInvalid,
                PublicTopSubmenuState.TransitionAmbiguous);
        }

        NMainMenu? menu = game.MainMenu;
        if (menu is null || !GodotObject.IsInstanceValid(menu))
        {
            return new PublicScreenFacts(
                HasValidGame: true,
                HasValidRoot: true,
                PublicMenuState.MissingOrInvalid,
                PublicSubmenuStackState.MissingOrInvalid,
                PublicTopSubmenuState.TransitionAmbiguous);
        }

        if (!menu.IsVisibleInTree())
        {
            return new PublicScreenFacts(
                HasValidGame: true,
                HasValidRoot: true,
                PublicMenuState.Hidden,
                PublicSubmenuStackState.MissingOrInvalid,
                PublicTopSubmenuState.TransitionAmbiguous);
        }

        NMainMenuSubmenuStack? stack = menu.SubmenuStack;
        if (stack is null || !GodotObject.IsInstanceValid(stack))
        {
            return new PublicScreenFacts(
                HasValidGame: true,
                HasValidRoot: true,
                PublicMenuState.Visible,
                PublicSubmenuStackState.MissingOrInvalid,
                PublicTopSubmenuState.TransitionAmbiguous);
        }

        if (!stack.IsVisibleInTree())
        {
            return new PublicScreenFacts(
                HasValidGame: true,
                HasValidRoot: true,
                PublicMenuState.Visible,
                PublicSubmenuStackState.Hidden,
                PublicTopSubmenuState.TransitionAmbiguous);
        }

        NSubmenu? top = stack.Peek();
        if (top is null)
        {
            return new PublicScreenFacts(
                HasValidGame: true,
                HasValidRoot: true,
                PublicMenuState.Visible,
                PublicSubmenuStackState.Visible,
                PublicTopSubmenuState.None);
        }

        if (!GodotObject.IsInstanceValid(top))
        {
            return new PublicScreenFacts(
                HasValidGame: true,
                HasValidRoot: true,
                PublicMenuState.Visible,
                PublicSubmenuStackState.Visible,
                PublicTopSubmenuState.Invalid);
        }

        if (!top.IsVisibleInTree())
        {
            return new PublicScreenFacts(
                HasValidGame: true,
                HasValidRoot: true,
                PublicMenuState.Visible,
                PublicSubmenuStackState.Visible,
                PublicTopSubmenuState.Hidden);
        }

        if (top is NSettingsScreen)
        {
            return new PublicScreenFacts(
                HasValidGame: true,
                HasValidRoot: true,
                PublicMenuState.Visible,
                PublicSubmenuStackState.Visible,
                PublicTopSubmenuState.VisibleSettings);
        }

        return new PublicScreenFacts(
            HasValidGame: true,
            HasValidRoot: true,
            PublicMenuState.Visible,
            PublicSubmenuStackState.Visible,
            PublicTopSubmenuState.Other);
    }
}
