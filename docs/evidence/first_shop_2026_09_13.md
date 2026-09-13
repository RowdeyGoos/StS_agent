# First headless shop — 2026-09-13

This batch implements the first restricted merchant room (HF-35): card/relic/potion
purchases, one card sale, permanent card removal, an optional Act 1 route stop and
exact private JSON continuation. It is static source inspection and synthetic
headless execution, not a live merchant demonstration or native RNG parity claim.

## Native source boundary

Source: Steam build 23811903, game v0.107.1, the existing pinned `sts2.dll` reference.
SHA-256: `e7ceb80669bfaf5c8fccabaa126ae2bb283aba514be5b5b55612579cfd285f18`.
The bounded metadata reader verified that hash, read only selected merchant,
card-selection and supported-item types, and did not execute game code or read
profiles, saves, history or Cloud data. Scratch outputs were under
`/private/tmp/sts-headless-shop-native/`; the method identities below are the
reproducible source anchors, not a dependency on retaining those scratch files.

| Native method / metadata token | Verified rule |
| --- | --- |
| `MerchantCardEntry.GetCost`, 100696243; `CalcCost`, 100696254 | Common/uncommon/rare card bases 50/75/150; multiply by Shops variation 0.95–1.05, round, then integer-divide by two for a sale. Native colorless multiplier exists but is outside this stock. |
| `RelicModel.get_MerchantCost`, 100682940; `MerchantRelicEntry.CalcCost`, 100696332 | Common/uncommon/rare bases 175/225/275, variation 0.85–1.15, `System.Math.Round`. Strawberry/Pear/Mango are those respective rarities. |
| `MerchantPotionEntry.GetCost`, 100696321; `CalcCost`, 100696322 | Common potion base 50, ordinary-runtime variation 0.95–1.05 and rounding. Fire and Block are common. |
| `MerchantEntry.OnTryPurchaseWrapper` async body, 100711769 | Check stock and affordability before purchase; clear the purchased entry when no restock modifier applies. |
| `MerchantPotionEntry.OnTryPurchase` async body, 100711777 | Failed potion procurement returns before gold deduction. |
| `MerchantCardRemovalEntry.get_BaseCost`, 100696261; `get_PriceIncrease`, 100696262; `CalcCost`, 100696264 | At A0, 75 + 25 × successful prior shop removals. Higher-ascension changes remain unsupported. |
| `MerchantCardRemovalEntry.get_IsStocked`, 100696260; `NMerchantCardRemoval.OnCardRemovalUsed`, 100671636 | Removal stock is `!Used`; using the service sets it used. |
| `OneOffSynchronizer.DoMerchantCardRemoval` async body, 100706215 | Cancelable one-card deck choice; null selection skips debit/removal. A selected card is removed from the master deck and increments `CardShopRemovalsUsed`. |
| `CardModel.get_IsRemovable`, 100682146; `CardSelectCmd.FromDeckForRemoval` predicate, 100712290 | Exclude the Eternal keyword; no minimum remaining deck size in this eligibility filter. `CardKeyword` value 7 is Eternal. No currently supported card has it. |

The rounding implementation uses nearest-even, consistent with
[Godot's C# Mathf.Round source](https://github.com/godotengine/godot/blob/4.5/modules/mono/glue/GodotSharp/GodotSharp/Core/Mathf.cs#L1380)
and `System.Math.Round`. Native single-precision arithmetic and its RNG sequence
are not reproduced by the authored basis-point sampler.

## Implementation and scope

`shops/catalog.py` owns immutable stock slots and price metadata. It provides one
common card, one uncommon, one rare, one unowned fruit relic and Fire/Block
Potions. One of the three card slots is on sale. If all fruits are owned, that
slot is omitted. This is an authored restricted inventory, not native merchant
slot counts, rarity weighting, colorless stock or depletion/refill rules.

`run/shop.py` owns entry, affordability, purchases, removal and exit. It uses the
existing permanent deck and inventory acquisition operations. Offers carry exact
run-owned shop/slot IDs, price and sold state; purchased cards/items receive their
own allocator IDs. A sold offer cannot be purchased again, and a previous shop's
ID cannot select stock in a later shop. Potion slot and duplicate-relic failures
leave gold, ownership and allocators unchanged.

Removal costs 75, then 100, then 125 across successful visits. Opening and canceling
are free. Completion removes the exact selected deck instance, consumes this
shop's service and increments the run counter. Other shop/potion commands are
unavailable during selection. Purchases can continue after a removal or cancel.

Stock and price generation use independent owned `shop.stock` and `shop.prices`
streams. Price variation is sampled in discrete basis points. Room construction
builds with a cloned RNG before committing, so missing card content also rolls
back navigation without consuming a shop ID or random draw.

Private run schema is `headless_run_state_v5`, binding the shop catalog, allocator,
removal history, stock and pending choice. Earlier run schemas reject; combat
schema stays v4 and reduced public fixtures are unchanged. Validation lives in
`run/shop_validation.py`. Restoring never rerolls stock or reapplies purchases.

The `overgrowth-act1` fourth fight now offers `merchant` or `boss_camp`; the
merchant leads to the camp. The existing smaller routes remain unchanged. The
CLI's example policy buys one affordable card, removes a starter if affordable,
and leaves. Direct commands permit other legal purchase sequences.

## Validation

- New focused shop regression: **47 passed in 0.54 s**. Covers exact transaction
  boundaries, multiple purchases, potion slot recovery, fruit pickup, duplicate
  ownership, last-card removal, cancel, escalating cost, stale IDs, rejected entry,
  malformed snapshots, next-combat persistence and the authored route.
- Final compilation: `python -m compileall -q game tests` passed.
- Final integration: **770 passed in 15.16 s** over `tests/headless`, simulation,
  analysis, engine, headless backends, content, lazy imports, package layout and
  headless CLI. The reduced fixture and existing combat consumers still pass.
- Independent semantic review found no blocking issues. The reviewer additionally
  exercised 794 restored decisions across 140 repeated shops, malformed snapshots,
  illegal actions, cancellation and entry rollback. These are headless probes.
- Built and installed `sts_agent-0.1.0-py3-none-any.whl` outside the source tree.
  SHA-256: `9a48444e520646e41eb8283241377365b4b6945155000359c41325a546bd1180`.
  Installed `sts-headless-play` ran with `PYTHONPATH` unset and restore checking:
  first-slice seed 2 finished at 66 HP in 38 commands; Act 1 left/smith seed 2
  bought one card and removed one card, then lost to Vantom after 104 commands;
  Act 1 right/rest bypassed the shop and lost after 100 commands. All continuations
  matched. No full Act 1 win is claimed.

The turn started at 14:29:15 UTC. Implementation and focused validation were done
by 14:40:22 UTC (about 11 minutes including source inspection); the final test
matrix took 15.16 seconds. Review ran alongside implementation. No separate
review-only duration was recorded and no user wait was required.

Remaining HF-35 work: complete native stock and RNG, discounts/restock modifiers,
colorless cards, pickup child selectors, event merchants and higher ascensions.
The next bounded room family is treasure (HF-36), followed by a verified ordinary
event; see the [current implementation assignment](../HEADLESS_FULL_GAME_IMPLEMENTATION.md#next-bounded-implementation-assignment).
