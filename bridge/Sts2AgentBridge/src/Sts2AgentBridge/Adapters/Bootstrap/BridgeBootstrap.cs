using Sts2AgentBridge.Adapters.Diagnostics;
using Sts2AgentBridge.Adapters.Identity;
using Sts2AgentBridge.Adapters.Public;
using Sts2AgentBridge.Adapters.Threading;
using Sts2AgentBridge.Core.Configuration;
using Sts2AgentBridge.Core.Hosting;
using Sts2AgentBridge.Core.Identity;
using Sts2AgentBridge.Core.Protocol;
using Sts2AgentBridge.Core.Public;
using Sts2AgentBridge.Core.Transport;

namespace Sts2AgentBridge.Adapters.Bootstrap;

internal static class BridgeBootstrap
{
    private static readonly object Gate = new();
    private static BridgeRuntime? _runtime;

    public static void Initialize()
    {
        lock (Gate)
        {
            if (_runtime is not null)
            {
                return;
            }

            var logger = new GodotBridgeLogger();
            ConfigurationLoadResult? configurationResult = null;
            GodotFrameDispatcher? frameDispatcher = null;
            BoundedLoopbackServer? listener = null;
            BridgeRuntime? runtime = null;

            try
            {
                configurationResult = new StrictConfigurationLoader().Load();
                if (configurationResult.Status == ConfigurationLoadStatus.Disabled)
                {
                    logger.Info("disabled");
                    configurationResult.Dispose();
                    return;
                }

                if (!configurationResult.IsEnabled || configurationResult.Configuration is null)
                {
                    logger.Error("invalid_configuration");
                    configurationResult.Dispose();
                    return;
                }

                LoadedBridgeConfiguration configuration = configurationResult.Configuration;
                string processCorrelationId = CorrelationIdGenerator.Create();
                BuildIdentityResult identity = new PinnedBuildGuard().Evaluate();
                if (!identity.ListenerAllowed)
                {
                    logger.Error("uncertain_build_identity");
                    configurationResult.Dispose();
                    return;
                }

                ProbeMode mode;
                BoundedFrameWorkQueue? frameQueue;
                IPublicScreenService? publicScreenService;
                IPublicCombatDecisionService? publicCombatDecisionService;
                IPublicCombatActionService? publicCombatActionService;
                IPublicRewardDecisionService? publicRewardDecisionService;
                IPublicRewardActionService? publicRewardActionService;
                IPublicMapDecisionService? publicMapDecisionService;
                IPublicMapActionService? publicMapActionService;
                IPublicRoomDecisionService? publicRoomDecisionService;
                IPublicRoomActionService? publicRoomActionService;
                if (identity.PublicScreenAllowed)
                {
                    mode = ProbeMode.Compatible;
                    frameQueue = new BoundedFrameWorkQueue();
                    publicScreenService = new PublicScreenService(new PinnedPublicScreenReader());
                    var combatDecisionReader = new PinnedPublicCombatDecisionReader();
                    publicCombatDecisionService = new PublicCombatDecisionService(combatDecisionReader);
                    publicCombatActionService = new PublicCombatActionService(
                        new PinnedPublicCombatActionApplier(combatDecisionReader));
                    var rewardDecisionReader = new PinnedPublicRewardDecisionReader();
                    publicRewardDecisionService = new PublicRewardDecisionService(rewardDecisionReader);
                    publicRewardActionService = new PublicRewardActionService(
                        new PinnedPublicRewardActionApplier(rewardDecisionReader));
                    var mapDecisionReader = new PinnedPublicMapDecisionReader();
                    publicMapDecisionService = new PublicMapDecisionService(mapDecisionReader);
                    publicMapActionService = new PublicMapActionService(
                        new PinnedPublicMapActionApplier(mapDecisionReader));
                    var roomDecisionReader = new PinnedPublicRoomDecisionReader();
                    publicRoomDecisionService = new PublicRoomDecisionService(roomDecisionReader);
                    publicRoomActionService = new PublicRoomActionService(
                        new PinnedPublicRoomActionApplier(roomDecisionReader));
                    frameDispatcher = new GodotFrameDispatcher(frameQueue.DrainFrame);
                }
                else
                {
                    mode = ProbeMode.IncompatibleLocked;
                    frameQueue = null;
                    publicScreenService = null;
                    publicCombatDecisionService = null;
                    publicCombatActionService = null;
                    publicRewardDecisionService = null;
                    publicRewardActionService = null;
                    publicMapDecisionService = null;
                    publicMapActionService = null;
                    publicRoomDecisionService = null;
                    publicRoomActionService = null;
                    logger.Info("incompatible_locked");
                }

                listener = new BoundedLoopbackServer(
                    mode,
                    processCorrelationId,
                    configuration.Authenticator,
                    frameQueue,
                    publicScreenService,
                    publicCombatDecisionService,
                    publicCombatActionService,
                    publicRewardDecisionService,
                    publicRewardActionService,
                    publicMapDecisionService,
                    publicMapActionService,
                    publicRoomDecisionService,
                    publicRoomActionService);
                runtime = new BridgeRuntime(
                    configurationResult,
                    frameQueue,
                    frameDispatcher,
                    listener);

                configurationResult = null;
                frameDispatcher = null;
                listener = null;

                if (!runtime.Start())
                {
                    logger.Error("startup_failed");
                    runtime.Dispose();
                    return;
                }

                _runtime = runtime;
                logger.Info("running");
            }
            catch
            {
                runtime?.Dispose();
                listener?.Dispose();
                frameDispatcher?.Dispose();
                configurationResult?.Dispose();
                logger.Error("startup_failed");
            }
        }
    }

    internal static void Stop()
    {
        lock (Gate)
        {
            BridgeRuntime? runtime = _runtime;
            _runtime = null;
            if (runtime is null)
            {
                return;
            }

            runtime.Dispose();
            new GodotBridgeLogger().Info("stopped");
        }
    }
}
