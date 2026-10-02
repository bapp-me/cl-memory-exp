---
name: multi-category-sqlite-layout
description: "Layout, group-to-category mapping, join keys and price units of the 3-category product/review SQLite database"
metadata:
  node_type: memory
  type: reference
  originSessionId: 6943a139-f675-4581-b14a-097549b7b36e
  modified: 2026-10-01T17:36:30.982Z
---

Scope: the read-only SQLite database exposed by the `sql` query tool in this workspace, which bundles three per-category product datasets (office products, electronics, musical instruments). Observations below are from that database only.

Tables (12 + sqlite_sequence): `items_g1`, `items_g2`, `items_g3`; `fdbk_g1`, `fdbk_g2`, `fdbk_g3`; `taxn_g1`, `taxn_g2`; `attrs_g1`, `attrs_g3`; `fdbk_stats_g1`.

Group -> category mapping (INFERENCE, strongly supported by `main_cat` distributions over 20,000 items per group):
- g1 -> office products (13,933 `Office Products` items)
- g2 -> electronics (15,975 items in electronics categories: All Electronics / Camera & Photo / Cell Phones & Accessories / Car Electronics / Home Audio & Theater / Computers / Video Games)
- g3 -> musical instruments (17,162 `Musical Instruments` items)
No column in any table labels the group, so the mapping must be derived from `main_cat` counts, not read off directly.

Join keys (VERIFIED by join-coverage counts):
- `fdbk_g2.ref_id` -> `items_g2.ref_id` matches all 77,022 review rows.
- `fdbk_g2` also has an `item_id` column, but it matches `items_g2.ref_id` for only 49,393/77,022 rows, so `item_id` is NOT the reliable FK; use `ref_id`.
- `fdbk_g3` has no `item_id` column at all, so joins there can only use `ref_id`.

Price units in `items_g2` (VERIFIED over the 6,346 rows where both are non-null): `prc = prc_usd * 100` exactly (min and max ratio both 100.0). Thus `prc` is USD cents, `prc_usd` is USD dollars. A "$N" threshold can be written either as `prc_usd <= N` or `prc <= 100*N`; both give identical row sets. 13,430 rows have NULL `prc` and 13,654 have NULL `prc_usd`.

New (2026-10-02 session): `prc_usd` is populated ONLY for `prc < 50000` (= < $500); max `prc_usd` = 499.99 and min `prc` among prc-only rows = 50000, so 6,346 rows have `prc_usd` vs 6,570 with `prc`. Electronics average price in dollars is therefore ambiguous: AVG(prc_usd) = 52.9567 (6,346 rows) vs AVG(prc)/100 = 96.2335 (6,570 rows). Also, `prc` in g1 (AVG 47.64) and g3 (AVG 123.39) is plausibly already DOLLARS (REAL), unlike g2's integer cents — INFERENCE from plausible magnitudes, not verified.

Review fields: `fdbk_g*.rtg` is a real rating in [1,5] (so 1-star = `rtg = 1`); `fdbk_g*.body` is non-null in all 77,022 `fdbk_g2` rows; `fdbk_g2.ts` is an integer epoch (note `fdbk_g3.ts` is TEXT, a type difference between groups).

Schema varies between groups, so per-group SQL cannot be copy-pasted blindly: `items_g1`/`items_g3` carry `desc_txt` (and g1 also `avg_rtg_30d`, `rtg_ct`), `items_g2` carries `prc_usd`/`img_ct` but no `desc_txt`; `attrs_*` and `fdbk_stats_g1` exist for only some groups.
