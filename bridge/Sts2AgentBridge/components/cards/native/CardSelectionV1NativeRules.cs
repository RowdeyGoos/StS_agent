using System;

namespace Sts2AgentBridge.Successors.CardSelectionV1.Native;

internal enum CardSelectionV1HighlightEndpoint
{
    Transient = 0,
    Unselected = 1,
    Selected = 2,
}

internal static class CardSelectionV1NativeRules
{
    internal const int SelectedWidthBits = 1033476506;

    internal static CardSelectionV1HighlightEndpoint ClassifyHighlight(float width)
    {
        int bits = BitConverter.SingleToInt32Bits(width);
        if (bits == 0) return CardSelectionV1HighlightEndpoint.Unselected;
        return bits == SelectedWidthBits
            ? CardSelectionV1HighlightEndpoint.Selected
            : CardSelectionV1HighlightEndpoint.Transient;
    }

    internal static bool IsExactRuntimeType(object? value, Type expected) =>
        value is not null && value.GetType() == expected;

    internal static bool IsCheesePolicy(CardSelectionV1ParentContext context) =>
        context.ParentKind == CardSelectionV1ParentKind.Event &&
        context.Operation == CardSelectionV1Operation.Add &&
        context.MinSelect == 2 && context.MaxSelect == 2 &&
        context.CommitMode == CardSelectionV1CommitMode.AutoAtMax &&
        context.ExpectedDomainCount == 8;

    internal static bool IsSmithPolicy(CardSelectionV1ParentContext context) =>
        context.ParentKind == CardSelectionV1ParentKind.Rest &&
        context.Operation == CardSelectionV1Operation.Upgrade &&
        context.MinSelect == 1 && context.MaxSelect == 1 &&
        context.CommitMode == CardSelectionV1CommitMode.PreviewConfirm &&
        context.ExpectedDomainCount is >= 1 and <= CardSelectionV1Limits.MaximumCandidates;

    internal static bool TryCheeseGeometry(
        float scrollWidth,
        float scrollHeight,
        float scrollPositionY,
        float gridHeight,
        float cardWidth,
        float cardHeight,
        int yOffset,
        out int columns,
        out int rows)
    {
        const float padding = 40f;
        const float topPadding = 80f;
        const float bottomPadding = 320f;
        columns = 0;
        rows = 0;
        if (!FinitePositive(scrollWidth) || !FinitePositive(scrollHeight) ||
            !FinitePositive(gridHeight) || !FinitePositive(cardWidth) ||
            !FinitePositive(cardHeight) || yOffset < 0) return false;
        columns = (int)((scrollWidth + padding) / (cardWidth + padding));
        if (columns < 1 || columns > CardSelectionV1Limits.MaximumCandidates) return false;
        rows = (8 + columns - 1) / columns;
        float containedHeight = rows * cardHeight + (rows - 1) * padding;
        float expectedScrollHeight = containedHeight + topPadding + bottomPadding + yOffset;
        float expectedPositionY = Math.Max(0f, (gridHeight - scrollHeight) * 0.5f);
        return SameFloat(scrollHeight, expectedScrollHeight) &&
            SameFloat(scrollPositionY, expectedPositionY) &&
            containedHeight + topPadding + yOffset <= gridHeight;
    }

    private static bool FinitePositive(float value) =>
        float.IsFinite(value) && value > 0f;

    private static bool SameFloat(float left, float right) =>
        BitConverter.SingleToInt32Bits(left) == BitConverter.SingleToInt32Bits(right);

    internal static bool IsStableKey(string? value)
    {
        if (value is null || value.Length is < 1 or > CardSelectionV1Limits.MaximumKeyLength)
            return false;
        foreach (char c in value)
            if (!(c is >= 'a' and <= 'z' or >= 'A' and <= 'Z' or >= '0' and <= '9' or '_'))
                return false;
        return true;
    }
}
