# environment.md — Reusable findings from the SQLite product-review database

## Scope
Read-only SQLite DB exposed only via the `query` tool. Contains three 20,000-row product
datasets, each with its own `*_gN` table set. Task context: office products, electronics,
musical instruments. This note records schema/join/encoding facts reusable for any future
query; it deliberately EXCLUDES the numerical answer to the current request.

## Table layout (verified via sqlite_master)
- Group tables: `items_g1/2/3`, `fdbk_g1/2/3`, plus `attrs_g1`, `attrs_g3`,
  `taxn_g1`, `taxn_g2`, `fdbk_stats_g1`.
- `items_gN`: `ref_id` (PK), `ttl`, `avg_rtg`, `rtg_ct`, `prc`, `str_nm`, `main_cat`,
  and per-group extras:
  - g1: `avg_rtg_30d`, `desc_txt`, `feat_lst`
  - g2: `prc INTEGER`, `prc_usd REAL`, `feat_lst`, `img_ct`
  - g3: `desc_txt` (no `prc_usd`)
- `fdbk_gN`: review rows keyed by `ref_id` (FK -> items_gN). Columns `id`, `ref_id`,
  `uid`, `rtg REAL`, `ttl`, `body`, `ts`, `hlp_ct`, `vrf`.
  - g1 additionally has `item_id`; g2 has `item_id` and `vrf TEXT`; g3 has no `item_id`
    and `ts TEXT`. => schema is NOT identical across groups; alias per group.

## Category -> group mapping (INFERRED from dominant `main_cat`, high confidence)
`main_cat` is a multi-valued subcategory field (Amazon-style), NOT one value per dataset.
Counting `main_cat` per group showed a clear dominant category:
- g1 -> Office Products (13,933 of 20,000; also All Electronics 1,308)
- g2 -> Electronics (Computers 5,247; All Electronics 4,562; Camera & Photo 2,789;
  Cell Phones & Accessories 1,775)
- g3 -> Musical Instruments (17,162 of 20,000)
NOTE: this mapping is inferred from counts, not stated in schema. Every group also holds
minority `main_cat` values, so a category-framed question should target the whole group,
not a `main_cat` filter.

## Price encoding (VERIFIED)
- In g2 only, `prc` is price in **cents** (integer). `prc_usd` = `prc / 100` in dollars.
- Verified: 0 rows where `prc/100` differs from `prc_usd` by > 0.001.
- g2 coverage: 6,570 rows have `prc`; 6,346 have `prc_usd`; 224 have `prc` only
  (no `prc_usd`); 0 have `prc_usd` only. g1/g3 have `prc` only; their units were not verified in this source task.
- Consequence: a "$40 list price" filter gives the SAME result via `prc_usd <= 40`
  or `prc <= 4000` — confirmed for the current dataset/review slice.
- `prc_usd` range in g2 ≈ 0.09..499.99; `prc` range ≈ 9..2,688,800.

## Data-quality facts (VERIFIED)
- All three item tables have exactly 20,000 rows each.
- `main_cat` can be NULL (g1 741, g2 1,304, g3 321).
- `fdbk_g2`: 77,022 reviews; 9,875 have `LENGTH(body) > 500`; 0 NULL bodies.
- `rtg` in g2 is non-null, integer-valued 1.0..5.0 (no half stars).
- Every `fdbk_g2.ref_id` matches an `items_g2.ref_id` (0 orphan reviews) — ref_id join is safe.
- Reviews-per-group are large (tens of thousands), so joins on `ref_id` are the intended path.

## Practical guidance
- `LENGTH(body)` counts characters incl. spaces (SQLite semantics) — "longer than 500
  characters" => `LENGTH(body) > 500`.
- To tie reviews to price, join `fdbk_gN.ref_id = items_gN.ref_id`; do not rely on
  `fdbk_g2.item_id` (only g1/g2 have it).
- Prefer group-level interpretation when the prompt names a product category.
