# Environment / Dataset Notes

Scope: read-only SQLite catalog+review database accessed only via the read-only SQL query tool.
Platform: win32, working dir `ds-a11-write-r1`. Date: 2026-10-02.

## Structure (verified by querying sqlite_master)
The DB contains THREE disjoint datasets, each with exactly 20,000 items and separate review tables:

| group | items table | reviews table | extra | dominant / root category |
|-------|-------------|---------------|-------|--------------------------|
| g1 | items_g1 | fdbk_g1 | taxn_g1, attrs_g1, fdbk_stats_g1 | Office Products (`taxn_g1` root, 17,825 rows) |
| g2 | items_g2 | fdbk_g2 | taxn_g2 | Electronics (`taxn_g2` cat_lvl=0 = "Electronics", 18,421 items) |
| g3 | items_g3 | fdbk_g3 | taxn_g3, attrs_g3 | Musical Instruments |

- Verified `ref_id` sets are disjoint across g1/g2/g3 (0 overlap in every pairwise check).
- Therefore a question naming a category (e.g. "electronics") selects one group; do not union groups.

## Key/tables for reviews (verified)
- `fdbk_g2` columns: id, item_id, ref_id, uid, rtg, ttl, body, ts, hlp_ct, vrf.
- Join reviews to items on **`ref_id`** (the declared FK; all 77,022 g2 reviews match an items_g2.ref_id).
  `item_id` is NOT a reliable join key: only 49,393/77,022 reviews have item_id present in items_g2.ref_id.
- Review text length: use SQLite `LENGTH(body)` (character count). "longer than 500" => `LENGTH(body) > 500` (strict).
- Item category: `items_g2.main_cat` (browse node, e.g. "All Electronics", "Computers") AND
  `taxn_g2(cat_lvl, cat_nm)` hierarchy whose level-0 name is "Electronics". `taxn_g2` has exactly one row per level per item (no duplicate roots).

## Price fields (verified)
- g2 has BOTH `prc` (INTEGER) and `prc_usd` (REAL). Where both present, `prc_usd == prc/100` exactly
  (0 mismatches), i.e. `prc` is in CENTS and `prc_usd` is the USD amount.
- Non-null coverage in items_g2: prc 6,570; prc_usd 6,346; 224 rows have prc but NULL prc_usd; 0 rows have prc_usd but NULL prc.
- g1/g3 have only `prc` (REAL/INTEGER) already in dollar-like ranges (g1 avg ~47.6, g3 avg ~123.4).
- No column or `attrs` key literally named "list price" exists (checked attrs_g1/attrs_g3 keys). Inference: "list price" maps to the item price column (`prc_usd` for g2, equivalently `prc`).

## Other (verified)
- `attrs_g1`/`attrs_g3` hold spec key/value pairs (Brand, Item Weight, Date First Available, ...); no price attr observed in the top keys.
- `fdbk_stats_g1` = per-item aggregates (avg_rtg, review_ct, pct_5star, avg_hlp) for g1 only; not a source of raw review rows.
- `rtg` is REAL; 1-star values are stored as `1.0`, so `rtg = 1` works.

## Inferences (not verified)
- The mapping "electronics => g2" is inferred from the taxonomy root name "Electronics" plus g2's category mix; exact intended scope (all of g2 vs. root-Electronics items vs. main_cat='All Electronics') affects the denominator.
- "list price" is inferred to be the item price field; the DB exposes no separate list-price field.
