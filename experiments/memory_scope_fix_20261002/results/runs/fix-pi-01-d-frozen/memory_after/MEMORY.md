[sqlite-orders-unit-conversion v1] SQLite orders tasks: check metadata/units before aggregate
Pattern for "compute total dollar amount of orders ..." workspace tasks:

1. list_files first. Workspaces often contain a small metadata JSON (e.g. export.json) alongside data. ALWAYS read it before querying — it may declare fields like "amount_unit": "USD cents". That single field flips the whole computation.
2. Data lives in a SQLite DB exposed via the sql tool (read-only, 50-row cap). Discover it with `SELECT name,type FROM sqlite_master;`, then `PRAGMA table_info(<table>);` for columns.
3. Inspect values cheaply: `SELECT DISTINCT status FROM <table>;` to learn category labels (e.g. 'paid' vs 'cancelled'), and `SELECT * ... LIMIT 20` plus a `COUNT(*)` to confirm you saw all rows.

UNIT-CONVERSION TRAP (most common failure):
- If metadata says prices are in cents, then a threshold "dollar price > 50" must be applied in cents: `price > 5000`. Do NOT compare raw value > 50.
- Sum in the stored unit, then convert to the requested unit at the end (cents sum / 100 = dollars).
- Example: WHERE status='paid' AND price>5000 -> SUM(price)=42000 cents = $420 answer.

Checklist: read metadata for units -> confirm columns -> filter on status AND the correctly-converted threshold -> SUM -> convert to requested unit -> sanity-check count and magnitude -> return {"answer": number}.

[sqlite-orders-unit-conversion v1 v1] SQLite orders tasks: check metadata/units before aggregate
Pattern for "compute total dollar amount of orders ..." workspace tasks:
1. list_files first; read the metadata JSON (e.g. export.json). Read the ACTUAL value of amount_unit — it is NOT always cents. Seen values: "USD" (prices already dollars) and "USD cents". Only convert when the value is literally a cents unit.
2. Data in a SQLite DB via sql tool (read-only, 50-row cap). `SELECT name,type FROM sqlite_master;` then `SELECT * ... LIMIT 20` + COUNT(*) to confirm all rows seen.
3. Inspect DISTINCT status to learn labels ('paid' vs 'cancelled').
4. Unit trap: if amount_unit is cents, a "dollar price > 50" filter is `price > 5000`, then SUM(price)/100. If amount_unit is USD, filter `price > 50` and SUM as-is (no conversion). Sanity-check magnitude against MIN/MAX price.
Return {"answer": number}.