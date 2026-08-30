namespace Sts2AgentBridge.Core.Public;

public static class PublicScreenProjector
{
    private static readonly PublicScreenSnapshot Waiting = new(
        PublicScreenStatus.Waiting,
        PublicScreenKind.Unknown);

    private static readonly PublicScreenSnapshot Unsupported = new(
        PublicScreenStatus.Unsupported,
        PublicScreenKind.Unknown);

    private static readonly PublicScreenSnapshot MainMenu = new(
        PublicScreenStatus.Ready,
        PublicScreenKind.MainMenu);

    private static readonly PublicScreenSnapshot Settings = new(
        PublicScreenStatus.Ready,
        PublicScreenKind.Settings);

    public static PublicScreenSnapshot Project(PublicScreenFacts facts)
    {
        if (!facts.HasValidGame || !facts.HasValidRoot)
        {
            return Waiting;
        }

        if (facts.MenuState != PublicMenuState.Visible ||
            facts.SubmenuStackState != PublicSubmenuStackState.Visible)
        {
            return Unsupported;
        }

        return facts.TopSubmenuState switch
        {
            PublicTopSubmenuState.None => MainMenu,
            PublicTopSubmenuState.VisibleSettings => Settings,
            _ => Unsupported,
        };
    }
}
