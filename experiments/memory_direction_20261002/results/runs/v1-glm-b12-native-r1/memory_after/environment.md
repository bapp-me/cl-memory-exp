# Database Environment Notes

## Schema (verified via sqlite_master, 2026-10-02)
Three independent product datasets, suffixed `_g1`, `_g2`, `_g3`:

| Table | Content |
|---|---|
| `items_g1` | ref_id (PK), ttl, avg_rtg, avg_rtg_30d, rtg_ct, prc, str_nm, main_cat, desc_txt, feat_lst |
| `fdbk_g1` | id, item_id, ref_id (FK→items_g1), uid, rtg, ttl, body, ts (INTEGER), hlp_ct, vrf (INTEGER) |
| `taxn_g1`, `attrs_g1`, `fdbk_stats_g1` | taxonomy (cat_lvl/cat_nm), attributes, per-product review stats |

| Table | Content |
|---|---|
| `items_g2` | ref_id (PK), ttl, avg_rtg, prc (INTEGER), prc_usd (REAL), str_nm, main_cat, feat_lst, img_ct |
| `fdbk_g2` | id, item_id, ref_id (FK→items_g2), uid, rtg, ttl, body, ts, hlp_ct, vrf (TEXT) |
| `taxn_g2` | taxonomy |

| Table | Content |
|---|---|
| `items_g3` | ref_id (PK), ttl, avg_rtg, rtg_ct, prc, str_nm, main_cat, desc_txt |
| `fdbk_g3` | id, ref_id (FK→items_g3), uid, rtg, ttl, body, ts (TEXT), hlp_ct, vrf (INTEGER) |
| `attrs_g3` | attributes (no taxonomy table for g3) |

## Dataset identity (verified)
- **g1 = Office Products**: `taxn_g1` level-0 categories dominated by "Office Electronics" (2670), "Office & School Supplies" (14008); sqlite_master level-0 max = "Office Products".
- **g2 = Electronics**: `taxn_g2` level-0 is "Electronics" (18,396 of ~18,421 rows), plus tiny "Car & Vehicle Electronics" (23) and "Amazon Devices & Accessories" (2).
- **g3 = Musical Instruments**: inferred from item titles sampled in `items_g3` (guitars, saxophone straps, clarinet reeds, drumsticks, all with main_cat = "Musical Instruments"). No taxonomy table exists for g3, so identity rests on the title sample, not a category table.

## Data conventions (verified by sampling)
- `items_g2.prc` is an integer in **cents**; `prc_usd` is the dollar value (e.g. prc=7499 ↔ prc_usd=74.99).
- Review join key: `fdbk_g*.ref_id` → `items_g*.ref_id` (declared FK). `item_id` also exists in fdbk_g1/g2 but is not the FK.
- `fdbk_g2.rtg` values observed: integer-like 1.0–5.0 only.
- `main_cat` in items_g1/g2/g3 is noisy/mixed across datasets and NOT a reliable dataset indicator; use `taxn_g*` instead (except g3, which has none).
