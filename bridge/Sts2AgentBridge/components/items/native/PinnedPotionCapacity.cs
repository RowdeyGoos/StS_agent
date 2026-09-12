using System;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.Models.Relics;
namespace Sts2AgentBridge.Items.Native;

// Pinned PotionBelt.AfterObtained appends two empty slots through PlayerCmd.
// Share the same narrow capability across terminal and owned event rewards.
internal static class PinnedPotionCapacity
{
    internal static int Gain(object? model)
    {
        if(model is not RelicModel relic || relic.GetType()!=typeof(PotionBelt))return 0;
        int gain=relic.DynamicVars["PotionSlots"].IntValue;
        if(gain!=2 || relic.Id.Entry!="POTION_BELT")throw new InvalidOperationException("Unsupported Potion Belt effect.");
        return gain;
    }
}
