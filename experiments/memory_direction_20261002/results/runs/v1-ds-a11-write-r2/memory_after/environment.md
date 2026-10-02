# Environment / dataset notes

## Scope
Read-only SQLite database with three separate product datasets, each using a
suffix group (`g1`, `g2`, `g3`) on its tables. Access is only via the SQL query
tool. Observed tables: `items_g{1,2,3}`, `fdbk_g{1,2,3}`, `fdbk_stats_g1`,
`taxn_g1`, `taxn_g2`, `attrs_g1`, `attrs_g3`, `sqlite_sequence`.

## Verified facts (observed directly)
- Category -> group mapping (verified by counting `main_cat` per group):
  - `g1` = office products (13,933 of 20,000 items `main_cat='Office Products'`)
  - `g2` = electronics (16,084 / 20,000 items in electronics categories; largest `main_cat='All Electronics'`)
  - `g3` = musical instruments (17,162 / 20,000 items `main_cat='Musical Instruments'`)
- Row counts: items_g1/g2/g3 = 20,000 each. Reviews: fdbk_g1 = 377,472;
  fdbk_g2 = 77,022; fdbk_g3 = 286,626.
- `fdbk_g*` columns include `ref_id`, `rtg` (REAL, distinct values 1.0..5.0),
  `body` (TEXT, no NULLs in g2), plus `item_id`, `uid`, `ttl`, `ts`, `hlp_ct`, `vrf`.
  g1/g2 `vrf` columns are declared differently (`vrf` INTEGER in g1, TEXT in g2) —
  schema is not identical across groups.
- Every `fdbk_g2.ref_id` joins to an `items_g2.ref_id` (77,022 / 77,022 matched).
  So reviews join to products on `ref_id` (NOT on `fdbk_g2.item_id`, which can
  differ from `ref_id` in sample rows).
- Price columns (g2): `items_g2.prc` (INTEGER, cents) and `items_g2.prc_usd` (REAL,
  dollars). Verified `prc_usd = prc/100` for all 6,346 rows where both are non-null
  (0 mismatches). `prc` non-null ~6,570 rows; 224 rows have `prc` but NULL `prc_usd`
  (no row with usd but no prc). Max `prc_usd` = 499.99.
- `attrs_g2` and `fdbk_stats_g2` do NOT exist; only g1 has `fdbk_stats_g1`, and only
  g1/g3 have `attrs_*`. `taxn_g1`/`taxn_g2` hold category taxonomy (ref_id, cat_lvl, cat_nm).

## Inferences (not fully proven)
- "List price" is not a literal column name anywhere observed. The only price
  columns are `prc` (cents, g1/g2/g3) and `prc_usd` (dollars, g2 only). Mapping
  "list price" -> `prc` (equivalently `prc_usd`) is a reasonable interpretation,
  not a verified label.
- `main_cat` is a mixed multi-category field in every group; the group identity is
  determined by the dominant category, not a single uniform category value.
- `fdbk_g2.item_id` vs `ref_id` distinction: ref_id is the product key to join on;
  the sample showed `item_id` differing from `ref_id`, so prefer `ref_id`.

## Query conventions that worked
- Text length: use `LENGTH(body)`; SQLite `length()` counts characters for TEXT.
- "longer than N" -> `LENGTH(body) > N` (strict).
- Rating filter: `rtg = 1` (stored as REAL 1.0).
- Price threshold $40 -> `prc <= 4000` (cents) or `prc_usd <= 40` (dollars); the
  two gave identical result sets in the computed scope, confirming the cents/dollars
  relationship.

## Verification status
- Group->category mapping: **verified** by direct aggregation.
- Price unit relationship: **verified** (0 mismatches over both-non-null rows).
- Join key `ref_id` for fdbk_g2: **verified** (100% match).
- "List price = prc": **inference** (best available interpretation).
