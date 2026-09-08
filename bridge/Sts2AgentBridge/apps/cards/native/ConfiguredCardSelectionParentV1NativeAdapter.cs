using System;
using Sts2AgentBridge.Successors.CardSelectionV1.Parents;

namespace Sts2AgentBridge.Successors.CardSelectionReleaseV1;

internal sealed class ConfiguredCardSelectionParentV1NativeAdapter :
    ICardSelectionParentV1NativeAdapter
{
    private readonly CardSelectionReleaseSelection _selection;
    private readonly ICardSelectionParentV1NativeAdapter _inner;

    internal ConfiguredCardSelectionParentV1NativeAdapter(
        CardSelectionReleaseSelection selection,
        ICardSelectionParentV1NativeAdapter inner)
    {
        if (selection is not (CardSelectionReleaseSelection.Cheese or
            CardSelectionReleaseSelection.Smith))
        {
            throw new ArgumentOutOfRangeException(nameof(selection));
        }
        _selection = selection;
        _inner = inner ?? throw new ArgumentNullException(nameof(inner));
    }

    public CardSelectionParentV1SurfaceCapture CaptureSurface()
    {
        CardSelectionParentV1SurfaceCapture capture = _inner.CaptureSurface() ??
            throw new InvalidOperationException("Native capture was null.");
        if (capture.Status == CardSelectionParentV1SurfaceStatus.Available &&
            capture.Policy.Kind != ExpectedPolicy(_selection))
        {
            throw new InvalidOperationException("Observed card-selection policy is not configured.");
        }
        return capture;
    }

    public void Dispose() => _inner.Dispose();

    private static CardSelectionParentV1PolicyKind ExpectedPolicy(
        CardSelectionReleaseSelection selection) => selection switch
        {
            CardSelectionReleaseSelection.Cheese =>
                CardSelectionParentV1PolicyKind.CheeseGorgeAddTwo,
            CardSelectionReleaseSelection.Smith =>
                CardSelectionParentV1PolicyKind.RestSmithUpgradeOne,
            _ => throw new InvalidOperationException("Unsupported configured policy."),
        };
}
