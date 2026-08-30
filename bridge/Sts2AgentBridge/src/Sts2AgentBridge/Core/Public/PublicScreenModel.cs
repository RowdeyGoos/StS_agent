namespace Sts2AgentBridge.Core.Public;

public enum PublicScreenStatus
{
    Ready = 1,
    Waiting = 2,
    Unsupported = 3,
}

public enum PublicScreenKind
{
    MainMenu = 1,
    Settings = 2,
    Unknown = 3,
}

public readonly record struct PublicScreenSnapshot(
    PublicScreenStatus Status,
    PublicScreenKind ScreenKind);

public enum PublicMenuState
{
    MissingOrInvalid = 1,
    Hidden = 2,
    Visible = 3,
}

public enum PublicSubmenuStackState
{
    MissingOrInvalid = 1,
    Hidden = 2,
    Visible = 3,
}

public enum PublicTopSubmenuState
{
    None = 1,
    VisibleSettings = 2,
    Invalid = 3,
    Hidden = 4,
    Other = 5,
    TransitionAmbiguous = 6,
}

public readonly record struct PublicScreenFacts(
    bool HasValidGame,
    bool HasValidRoot,
    PublicMenuState MenuState,
    PublicSubmenuStackState SubmenuStackState,
    PublicTopSubmenuState TopSubmenuState);

public enum PublicScreenReadOutcome
{
    Success = 1,
    BackendFault = 2,
}

public readonly record struct PublicScreenReadResult
{
    private PublicScreenReadResult(
        PublicScreenReadOutcome outcome,
        PublicScreenSnapshot snapshot)
    {
        Outcome = outcome;
        Snapshot = snapshot;
    }

    public PublicScreenReadOutcome Outcome { get; }

    public PublicScreenSnapshot Snapshot { get; }

    public bool IsSuccess => Outcome == PublicScreenReadOutcome.Success;

    public static PublicScreenReadResult FromSnapshot(PublicScreenSnapshot snapshot)
    {
        return new PublicScreenReadResult(PublicScreenReadOutcome.Success, snapshot);
    }

    public static PublicScreenReadResult BackendFault()
    {
        return new PublicScreenReadResult(PublicScreenReadOutcome.BackendFault, default);
    }
}
