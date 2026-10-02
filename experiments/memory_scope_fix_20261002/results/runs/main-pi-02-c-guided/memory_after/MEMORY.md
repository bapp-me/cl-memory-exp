[price-minor-cents-sqlite v2] Price aggregation when minor-unit (cents) column exists — catalog.md + SQLite tasks
Price aggregation when minor-unit (cents) column exists — catalog.md + SQLite tasks

Env: workspace has one file catalog.md plus a read-only SQLite DB. Procedure: list_files -> read_file catalog.md -> sql. sqlite_master shows e.g. CREATE TABLE products(id INTEGER PRIMARY KEY, price_minor INTEGER, display_usd REAL). catalog.md: "price_minor is the source price in USD cents. display_usd is a nullable display field in USD."

Lesson: when a minor-unit column exists, treat it as authoritative and convert via price_minor/100.0. Express dollar thresholds in cents (below $60 => price_minor < 6000). Do NOT filter or aggregate on display_usd — it is display-only and nullable (multiple NULLs observed in every run). For "mean price of all products" just AVG(price_minor)/100.0 with no WHERE clause.

Queries used:
- SELECT COUNT(*), AVG(price_minor)/100.0 AS mean_usd, SUM(price_minor IS NULL), SUM(display_usd IS NULL) FROM products;
- threshold variant: SELECT AVG(price_minor)/100.0 FROM products WHERE price_minor < 6000;
- SELECT * FROM products to eyeball units/nullability.

Cheap applicability check: confirm which column catalog.md calls the source price; check unit (cents vs dollars) and boundary (strict < vs <=) from task wording; verify display_usd equals price_minor/100 where non-null (it did).

Observed runs (all same schema, display_usd NULL on latent rows):
- run A: rows (1,2037,20.37)...(5,9637,96.37),(6..9, 11537..17237, null). price_minor<6000 => rows 1-3; mean 39.37.
- run B: rows (1,2311,23.11)...(5,9911,99.11),(6..9, 11811..17511, null). All rows mean = 99.11; AVG(display_usd)=61.11 (wrong, NULLs skipped).

Untested/limits: single products table, 9 rows; strict "<" boundary; no case where display_usd is populated but price_minor missing/zero, multiple tables, or non-cent minor units. Reuse the procedure (prefer source minor-unit column, filter in minor units, divide by 100), not the specific numbers.