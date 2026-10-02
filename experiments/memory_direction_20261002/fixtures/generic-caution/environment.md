---
name: multi-category-sqlite-layout
description: "Layout, group-to-category mapping, join keys and price units of the 3-category product/review SQLite database"
metadata:
  node_type: memory
  type: reference
  originSessionId: 6943a139-f675-4581-b14a-097549b7b36e
  modified: 2026-10-01T17:25:11.354Z
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

Review fields: `fdbk_g*.rtg` is a real rating in [1,5] (so 1-star = `rtg = 1`); `fdbk_g*.body` is non-null in all 77,022 `fdbk_g2` rows; `fdbk_g2.ts` is an integer epoch (note `fdbk_g3.ts` is TEXT, a type difference between groups).

Schema varies between groups, so per-group SQL cannot be copy-pasted blindly: `items_g1`/`items_g3` carry `desc_txt` (and g1 also `avg_rtg_30d`, `rtg_ct`), `items_g2` carries `prc_usd`/`img_ct` but no `desc_txt`; `attrs_*` and `fdbk_stats_g1` exist for only some groups.


Before reusing a remembered fact, verify the assumptions relevant to the present question against the actual data. Do not assume a finding applies outside its verified scope.
