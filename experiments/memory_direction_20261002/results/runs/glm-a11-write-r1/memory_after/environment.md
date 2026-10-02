# Environment Notes — Product Catalog & Review Database

## Scope
- Read-only SQLite database accessed via the SQL query tool. Workspace: `D:\campus_re\experiments\memory_direction_20261002\workspaces\glm-a11-write-r1`.
- Product catalog + review data, split into three parallel table groups (g1, g2, g3), each holding 20,000 products.

## Schema (verified via sqlite_master, 2026-10-02)
- `items_g1(ref_id PK, ttl, avg_rtg, avg_rtg_30d, rtg_ct, prc, str_nm, main_cat, desc_txt, feat_lst)`
- `fdbk_g1(id PK AI, item_id, ref_id FK->items_g1.ref_id, uid, rtg, ttl, body, ts INTEGER, hlp_ct, vrf INTEGER)`
- `items_g2(ref_id PK, ttl, avg_rtg, prc INTEGER, prc_usd REAL, str_nm, main_cat, feat_lst, img_ct)`
- `fdbk_g2(..., ts INTEGER, vrf TEXT)` — note: `vrf` is TEXT here, unlike g1/g3.
- `items_g3(ref_id PK, ttl, avg_rtg, rtg_ct, prc, str_nm, main_cat, desc_txt)` — no feat_lst.
- `fdbk_g3(..., ts TEXT)` — timestamp is TEXT here, INTEGER in g1/g2.
- Auxiliary: `taxn_g1(ref_id, cat_lvl, cat_nm)`, `attrs_g1(ref_id, attr_key, attr_val)`, `fdbk_stats_g1(ref_id PK, avg_rtg, review_ct, pct_5star, avg_hlp)`. No taxn/attrs tables exist for g2/g3.

## Verified facts (observed directly)
- **Price units:** `items_g1.prc` and `items_g3.prc` are in USD (min 0.18 / max 13914.85 and 0.05 / 5369.0). `items_g2.prc` is in CENTS (min 9, max 2,688,800); `items_g2.prc_usd` is the USD equivalent (min 0.09, max 499.99). Use `prc_usd` for g2 price filters.
- **Rating values:** `fdbk_g1.rtg` takes only 1.0–5.0 in whole-star steps.
- **Review volume:** `fdbk_g2` has 20,000 items in g2's items table; g1/g3 also 20,000 each (per COUNT(*) on items).
- **Categories containing "Electronics" in main_cat:** g1: "All Electronics" (1308 products); g2: "All Electronics" (4562), "Car Electronics" (346); g3: "All Electronics" (534), "Car Electronics" (8).
- **Duplicate review rows exist:** exact duplicates on (ref_id, uid, ts, body) — 3,236 groups in fdbk_g1, 276 in fdbk_g2, 2,805 in fdbk_g3. In the "electronics, price ≤ $40, body > 500 chars" slice this was only 17 of 1,379 rows.

## Inferences (not verified)
- "Electronics" questions were interpreted as `main_cat = 'All Electronics'` (dominant electronics category); "Car Electronics" was NOT included. This is an interpretation choice, not a database fact.
- Whether duplicates should be deduplicated before percentage computations is ambiguous; row-level counting was used and the effect in the observed slice was negligible.

## NULL/quality notes
- `items_g2.prc` is populated for 6,570 of 20,000 rows; `prc_usd` for 6,346. g1: `prc` populated for 7,867; g3: 7,949. `main_cat` is NULL for ~741 (g1) / ~1,304 (g2) rows.
