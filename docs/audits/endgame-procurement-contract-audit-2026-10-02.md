# Ship material procurement contract audit — 2026-10-02

This is offline source/API contract evidence. No game, director process, observer or model weights were launched. Python fixture decisions and source guards do not prove trained Laya competence, trader stock appearing, affordability in a particular save or successful escape.

## Fixed local and orbital purchase path

LiveTradeAutomationHelper.GetPreview previously enumerated a fixed goods shortlist plus implants/weapons. AIPersonaCore was absent. It now also derives `item:<exact loaded defName>` options from actual willing native trader stock, excluding currency and pawn races. Native GetPriceFor(PlayerBuys), held count, current currency and the requested reserve/spending cap establish affordability. An exact item choice buys one unit, including across multiple equivalent rows; existing category purchases retain their targets. Items are never created or granted by the endpoint.

Director preview requests previously capped spend at 4000, excluding a normal expensive core despite sufficient silver. Discovery now requests the integer maximum, while preview still bounds purchases by actual deal silver. Trader comparisons explicitly expose affordable persona-core price before the small stock summary. Laya chooses trader, sale, reserve, purchase and budget. Budget alternatives range from the rounded minimum price to actual available funds after the chosen reserve; fixed caps survive only when within that range. Native core/stock description, owned cores and colony ending context reach the purchase comparison. A selected exact item that disappeared or cannot be afforded leaves its priority pending and rejects the deal before native execution; it cannot silently execute the financing sale alone.

Local execution recomputes native stock/prices and normal currency transfer after selections. It uses ForceToSource and TradeDeal.TryExecute; there is no automatic core purchase or fabricated bargain price. Exact `item:` matching requires the complete loaded defName and excludes pawn/currency purchases. Automated local trade rejects an existing active session rather than closing a caravan/manual session.

## Fixed caravan settlement purchase path

The caravan session formerly exposed only sale categories and people purchases. Preview now exposes all willing native nonpawn, noncurrency item rows with representative native ThingId, description, current unit price and held stock. Laya can decline recruitment and explicitly select one item, then explicitly select its budget. The request carries `purchase_thing_id`, `expected_unit_price`, chosen reserve and cap. C# rejects simultaneous person/item choices, a missing native item, a changed price or insufficient funds. It rechecks the actual rounded currency reserve after ForceToSource(1) and uses normal TradeDeal.TryExecute. Selected item stock is transferred to the caravan and inventory recached.

Financing estimates now use native preview's computed sale proceeds across all matching rows, including the existing 2500 sale ceiling and trader currency. The Python legacy fallback is also capped to 2500. This prevents offering a core funded by proceeds the execution handler would not sell. An already edited manual deal is rejected instead of executing unselected transfers. Failed selections are cleared; successful trade closes the existing dialog/session and uses the existing home route when a home map exists. With no map ID, the director uses native_session state, preserving its campaign doctrine and ledger. No home-map requirement is imposed on settlement purchase itself.

## Preview mutation and cleanup evidence

Installed Assembly-CSharp.dll was inspected offline with ILSpy for RimWorld.TradeSession and TradeDeal. SetupWith assigns trader, playerNegotiator, giftMode and a new TradeDeal. It may issue a cannot-sell message. TradeSession.Close only sets trader=null; it leaves the other three fields changed. GetPreview now saves and restores all four previous fields in finally, setting its ownership flag before SetupWith so partial setup failure also restores the scope. It refuses an already active session.

This is scoped restoration, **not a mutation-free read**. TradeDeal construction enumerates native willing stock and may allocate a zero-count Silver Thing when no currency row exists; native setup may display messages. The audit does not claim to restore those allocations, message side effects or global unique-ID advancement. Preview never calls TryExecute. Caravan preview reads the already open native deal and performs no transfer selection.

## Offline verification

`tests/test_procurement_contracts.py` covers a 6000-silver core surviving discovery and budget formation, exact local order payload, explicit caravan item/budget decisions, reserve rejection, executable financing rather than inflated raw stock value, mapless caravan doctrine preservation and native source guards for exact nonpawn matching, price rejection, manual-selection protection, normal transfer and four-field preview restoration. Six tests pass. The director suite's 285 tests pass after three trade fixtures were updated to choose a cap within actual available funds or answer the added caravan budget question. Root owns the final C# build; this worker did not build or commit.

Remaining gameplay requirements: a willing trader must actually stock a core, the colony/caravan must possess enough normal silver or approved sale goods, ship research/materials/construction must complete, reactor defenses must survive and normal launch must finish. This patch opens procurement; it does not prove any of those outcomes.
