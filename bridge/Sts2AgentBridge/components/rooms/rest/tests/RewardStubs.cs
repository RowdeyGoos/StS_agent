using System;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using Godot;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Rewards;
using Sts2AgentBridge.Core.Public;

namespace Sts2AgentBridge.Core.Public { public enum PublicDecisionStatus { Ready = 1, Waiting = 2, Unsupported = 3, Complete = 4 } }
namespace MegaCrit.Sts2.Core.Rewards
{
    public class RewardsSet
    {
        public Player Player = null!;
        [MethodImpl(MethodImplOptions.NoInlining)] public Task Offer() => Task.CompletedTask;
    }
}
namespace MegaCrit.Sts2.Core.Nodes.Screens
{
    public class NRewardsScreen : Control
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        public static NRewardsScreen ShowScreen(RewardsSet set, bool terminal, MegaCrit.Sts2.Core.Runs.IRunState run) => new();
    }
}
namespace MegaCrit.Sts2.Core.Entities.RestSite
{
    public class HealRestSiteOption(Player player) : RestSiteOption(player)
    {
        [MethodImpl(MethodImplOptions.NoInlining)]
        public override async Task<bool> OnSelect() { Owner.Creature.CurrentHp += 10; await new RewardsSet { Player = Owner }.Offer(); return true; }
    }
}
namespace Sts2AgentBridge.Rooms.Rest
{
    // Parent ownership fixture stand-in; the real reward continuation is tested
    // with the existing native reward reader and control fixtures separately.
    internal sealed class RestRewardContinuation : IDisposable
    {
        internal static PublicRewardDecisionSnapshot? FixtureView;
        private Task? _task;
        private readonly Func<bool> _context;
        internal bool Completed { get; private set; }
        internal RestRewardContinuation(RewardsSet set, Player player, NOverlayStack overlays, Func<bool> context) { _context = context; }
        internal void Offering(Task task) => _task = task;
        internal void ScreenEntering(RewardsSet set, bool terminal, object run) { }
        internal void ScreenEntered(MegaCrit.Sts2.Core.Nodes.Screens.NRewardsScreen screen) { }
        internal PublicRewardDecisionSnapshot Read()
        { if (!_context()) throw new InvalidOperationException(); Completed = FixtureView is null && _task?.IsCompletedSuccessfully == true; return FixtureView ?? PublicRewardDecisionSnapshot.Waiting(); }
        internal bool CanDismiss(PublicRewardDecisionSnapshot view) => false;
        internal void Apply(string decision, string action) => throw new InvalidOperationException();
        public void Dispose() { if (!Completed) throw new InvalidOperationException(); }
    }
}
