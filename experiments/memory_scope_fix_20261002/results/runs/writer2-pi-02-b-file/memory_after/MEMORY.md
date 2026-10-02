[catalog-price-tasks v1] Pricing tasks: use price_minor (cents) as source of truth, not display_usd
Pattern for catalog/price tasks in this workspace:
- Workspace typically contains catalog.md describing schema, plus a SQLite DB queried via read-only `sql` tool.
- Schema example: products(id, price_minor INTEGER, display_usd REAL nullable).
- catalog.md states: price_minor is the SOURCE price in USD cents; display_usd is a nullable display field (often NULL for later rows) and should NOT be trusted as source.

Correct approach:
- Do all filtering and math on price_minor (cents); convert to dollars at the end by /100.
- "priced below 60 dollars" => WHERE price_minor < 6000.
- Ignore/null out display_usd.

Worked example: rows price_minor = 2037,3937,5837,7737,9637,11537,... display_usd null after row 5. Below $60 => 2037,3937,5837. Mean = 11811/3 = 3937 cents = $39.37.

Method notes:
- First list_files, read_file(catalog.md) for schema hints, then sql sqlite_master / PRAGMA table_info / SELECT * to see real data.
- Return answer as {"answer": number} with plain number (no $ sign).
- Watch for nullable/decoy columns and unit mismatches (cents vs dollars); always prefer the documented source column.