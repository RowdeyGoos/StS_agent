using System;
using System.Collections.Generic;

namespace Sts2AgentBridge.Tests;

internal static class Program
{
    private static int Main()
    {
        var suites = new List<(string Name, Action Run)>
        {
            ("contract", Contract.ContractTestSuite.Run),
            ("configuration", Configuration.ConfigurationTestSuite.Run),
            ("identity", Identity.IdentityTestSuite.Run),
            ("build_identity", BuildIdentity.BuildIdentityTestSuite.Run),
            ("hosting", Hosting.HostingTestSuite.Run),
            ("threading", Threading.ThreadingTestSuite.Run),
            ("public", Public.PublicTestSuite.Run),
            ("public_reward", Public.RewardInteractionTestSuite.Run),
            ("public_process_budget", Public.ProcessBudgetMultiFloorTestHelper.Run),
            ("public_room", Public.RoomInteractionTestSuite.Run),
            ("transport", Transport.TransportTestSuite.Run),
            ("security", Security.SecurityTestSuite.Run),
        };

        foreach ((string name, Action run) in suites)
        {
            try
            {
                run();
                Console.WriteLine($"PASS {name}");
            }
            catch (Exception exception)
            {
                Console.Error.WriteLine($"FAIL {name}: {exception.GetType().Name}: {exception.Message}");
                return 1;
            }
        }

        Console.WriteLine($"PASS all {suites.Count}");
        return 0;
    }
}
