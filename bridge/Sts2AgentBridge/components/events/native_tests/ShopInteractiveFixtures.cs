using System;
using System.Text.Json.Nodes;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens.Shops;
using MegaCrit.Sts2.Core.Nodes.Screens.ScreenContext;
using MegaCrit.Sts2.Core.Nodes.Screens.Capstones;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using Sts2AgentBridge.Successors.RoomFlowsV1.Shop.Native;

internal static partial class Program
{
    private static JsonObject ShopRead(ShopInteractiveSession s) => JsonNode.Parse(s.Handle(false, null, null))!.AsObject();
    private static JsonObject ShopApply(ShopInteractiveSession s, JsonObject view, string action) =>
        JsonNode.Parse(s.Handle(true, view["decision_id"]!.GetValue<string>(), action))!.AsObject();
    private static void ShopInteractiveCases()
    {
        foreach (string mode in new[] { "purchase", "closed_leave", "stale", "inspect_open", "inspect_buy", "lost_open", "changed_inventory", "pending_purchase" })
        {
            NModalContainer.Instance = null;
            MegaCrit.Sts2.Core.Nodes.NRun.Instance = new() { GlobalUi = new() { CapstoneContainer = new() } };
            var room = new NMerchantRoom(); var inventory = new NMerchantInventory();
            ActiveScreenContext.Instance = new() { Current = room };
            var f = new MultiplePurchaseFixture(1) { Closed = true, CanOpen = true, RoomOverride = room, InventoryOverride = inventory };
            f.OnOpened = () => {
                ActiveScreenContext.Instance.Current = inventory;
                if (mode == "lost_open") throw new InvalidOperationException();
                if (mode == "changed_inventory") f.Gold--;
            };
            f.OnClosed = () => ActiveScreenContext.Instance.Current = room;
            var s = new ShopInteractiveSession("0123456789abcdef0123456789abcdef", f);
            try
            {
                var before = ShopRead(s);
                Check(before["status"]!.GetValue<string>() == "ready" && before["phase"]!.GetValue<string>() == "entrance", "closed shop is a shared policy decision");
                if (mode == "stale") f.Gold--;
                if (mode == "inspect_open") ActiveScreenContext.Instance.Blocker = new();
                var receipt = ShopApply(s, before, mode == "closed_leave" ? "leave" : "open");
                if (mode is "stale" or "inspect_open")
                {
                    Check(receipt["status"]!.GetValue<string>() == "unsupported" && f.Opens == 0, "shop stale/foreground guard prevents opening");
                    continue;
                }
                if (mode == "lost_open")
                {
                    Check(receipt["status"]!.GetValue<string>() == "uncertain" && f.Opens == 1, "lost open never retries");
                    continue;
                }
                Check(receipt["status"]!.GetValue<string>() == "accepted", "shop entrance action accepted once");
                var view = ShopRead(s);
                if (mode == "changed_inventory") { Check(view["status"]!.GetValue<string>() == "unsupported", "opening cannot adopt an unexplained inventory effect"); continue; }
                if (mode == "closed_leave")
                {
                    Check(view["status"]!.GetValue<string>() == "complete" && f.Leaves == 1 && f.Opens == 0, "closed shop leaves directly with one reconciled input");
                    continue;
                }
                Check(view["completed"]!.AsArray().Count == 1 && f.Opens == 1, "opening reconciles before buying");
                if (mode == "inspect_buy") ActiveScreenContext.Instance.Blocker = new();
                if (mode == "pending_purchase") f.Delay = true;
                var buy = ShopApply(s, view, "buy:card:0");
                if (mode == "inspect_buy") { Check(buy["status"]!.GetValue<string>() == "unsupported" && f.Purchases == 0, "inspector blocks shop purchase"); continue; }
                Check(buy["status"]!.GetValue<string>() == "accepted" && f.Purchases == 1, "shop purchase dispatched once");
                if (mode == "pending_purchase") { Check(ShopRead(s)["status"]!.GetValue<string>() == "waiting", "accepted purchase waits for its effect"); continue; }
                view = ShopRead(s); Check(view["completed"]!.AsArray().Count == 2 && f.Gold == 90, "purchase and open receipts are distinct");
                Check(ShopApply(s, view, "inventory:close")["status"]!.GetValue<string>() == "accepted", "shop closes via original owner");
                view = ShopRead(s);
                Check(ShopApply(s, view, "leave")["status"]!.GetValue<string>() == "accepted", "shop leaves after close");
                view = ShopRead(s);
                Check(view["status"]!.GetValue<string>() == "complete" && view["completed"]!.AsArray().Count == 4 && f.Leaves == 1, "four exact shop receipts through map handoff");
                Check(ShopRead(s).ToJsonString() == view.ToJsonString(), "shop terminal retained");
            }
            finally
            {
                bool failed = false; try { s.Dispose(); } catch (InvalidOperationException) { failed = true; }
                Check(failed == (mode is "lost_open" or "changed_inventory" or "pending_purchase"), "shop cleanup respects unresolved mutations " + mode);
                ActiveScreenContext.Instance = new();
            }
        }
    }
}
