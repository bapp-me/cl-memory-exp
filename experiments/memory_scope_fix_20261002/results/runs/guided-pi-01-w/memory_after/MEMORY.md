[sql-money-unit-thresholds v1] Workspace SQL tasks: check export.json for amount_unit before threshold comparisons
ENV: Local isolated task workspace. Tools: list_files, read_file, sql (read-only SQLite, max 50 rows, PRAGMAs + sqlite_master available). Observed in this task (dataset "orders", export_version 1).

WORKFLOW that worked:
1. list_files -> found only export.json.
2. read_file export.json -> METADATA ONLY, no data. Key field: "amount_unit":"USD cents".
3. sql: SELECT name,type FROM sqlite_master -> one table "orders".
4. sql: PRAGMA table_info(orders) -> columns id INTEGER(pk), price REAL, status TEXT.
5. sql: SELECT * FROM orders LIMIT 20 -> only 9 rows total (confirm with SELECT COUNT(*)); SELECT DISTINCT status -> "paid","cancelled".
6. Aggregate: SELECT COUNT(*),SUM(price) FROM orders WHERE status='paid' AND price>5000; plus COUNT(*) to confirm no truncation.

CRITICAL GOTCHA (applicability: whenever export.json declares a non-dollar amount_unit): prices were stored in CENTS. "price greater than 50 dollars" => price > 5000 (cents). Forgetting the unit conversion is the main error source. Always read export.json / metadata before comparing money thresholds, and convert the threshold to the stored unit, not the stored values to dollars.
RESULT here: 4 paid rows with price>5000 (7100,8800,12200,13900) summed to 42000 cents = $420.

CAVEAT/UNTESTED: Only observed one dataset with amount_unit "USD cents" and status values {paid,cancelled}. Exact status spelling/format for other exports is unknown; other units (e.g. plain USD) untested. The sql tool caps output at 50 rows — use COUNT(*)/SUM aggregates to avoid silent truncation bias.
CHEAP APPLICABILITY CHECK: read export.json's amount_unit field; run SELECT DISTINCT status and SELECT COUNT(*) before aggregating.