[catalog-price-minor-cents-trap v1] Catalog price units trap: use price_minor (cents) as source of truth
Task class: SQL aggregate over a products table with a price-unit trap.

Pattern observed:
- Files: catalog.md plus a SQLite DB. catalog.md describes schema: price_minor (INTEGER, source price in USD cents) and display_usd (REAL, nullable display field).
- Schema: products(id INTEGER PRIMARY KEY, price_minor INTEGER, display_usd REAL).
- Trap: display_usd is NULL for many rows (decoy), so it can't be trusted/used for filtering or averaging. price_minor is the source of truth.

Correct approach:
1. list_files -> read catalog.md for schema/units notes.
2. Inspect schema: SELECT name,sql FROM sqlite_master.
3. SELECT * FROM products to eyeball data and spot NULLs/decoys.
4. Filter threshold must be converted to cents: "below $60" => price_minor < 6000.
5. Mean in dollars: SELECT AVG(price_minor)/100.0 AS mean_usd FROM products WHERE price_minor < 6000.
   Example answer: {"answer": 39.37}

General lessons:
- When a doc states a "source" field vs a "nullable display" field, always compute from the source field; ignore nullable/decoy columns.
- Convert dollar thresholds to minor units (cents) before filtering integer price columns, else you get wrong rows.
- Verify with a raw SELECT * to confirm which rows satisfy the filter and sanity-check the count.