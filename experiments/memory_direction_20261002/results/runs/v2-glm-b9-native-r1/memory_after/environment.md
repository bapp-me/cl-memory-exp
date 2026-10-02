# Database environment notes (observed 2026-10-02)

## Schema layout (verified via sqlite_master)
Three independent product datasets, table names suffixed `_g1` / `_g2` / `_g3`:

- **g1 = Office Products** — tables: `items_g1`, `fdbk_g1`, `fdbk_stats_g1`, `attrs_g1`, `taxn_g1`
- **g2 = Electronics** — tables: `items_g2`, `fdbk_g2`, `taxn_g2` (no attrs/stats tables)
- **g3 = Musical Instruments** — tables: `items_g3`, `fdbk_g3`, `attrs_g3` (no taxonomy table)

Category assignment is **verified** from `main_cat` value counts in each `items_*` table:
- `items_g1`: Office Products 13,933 (dominant)
- `items_g2`: Computers 5,247, All Electronics 4,562, Camera & Photo 2,789, Cell Phones & Accessories 1,775 (electronics-dominant)
- `items_g3`: Musical Instruments 17,162 (dominant)

## Key columns (verified via CREATE TABLE statements)
- `items_g2`: `ref_id` PK, `ttl`, `avg_rtg`, `prc` (INTEGER), `prc_usd` (REAL), `main_cat`, `feat_lst`, `img_ct`
- `fdbk_g2`: `ref_id` (FK → items_g2), `uid`, `rtg` REAL, `ttl`, `body` TEXT, `ts`, `hlp_ct`, `vrf` (TEXT in g2, INTEGER in g1/g3)

## Data facts (verified by query)
- `items_g2.prc` is **in cents**, `prc_usd` is in dollars — confirmed consistent (0 rows where `ABS(prc - prc_usd*100) > 0.01`); 224 rows have null-pattern mismatch between the two fields. Use `prc_usd <= 40` for dollar thresholds.
- `items_g2` has 20,000 rows; 6,570 have `prc`, 6,346 have `prc_usd` (many null prices).
- `fdbk_g2.rtg` values are only 1.0–5.0 (counts: 5★ 49,611; 4★ 10,492; 3★ 5,682; 2★ 3,791; 1★ 7,446).
- All `fdbk_g2.ref_id` values match `items_g2.ref_id` (0 unmatched on LEFT JOIN) — inner join safe.

## Inference vs. verification
- Price-unit interpretation (cents vs dollars) is **verified** numerically, not inferred from column names.
- Electronics = g2 is **verified** from `main_cat` dominance; g1/g3 assignments likewise.
