# Environment & Schema Findings

## Scope
Read-only SQLite database provided via `mcp__sql__query`. Contains three product
datasets (one per product category), each in its own table group `g1` / `g2` / `g3`.
Task observed: counting reviews by time window. All facts below were verified by
running queries against the live DB; inferences are marked.

## Table inventory (verified)
12 user tables + `sqlite_sequence`:

- Items: `items_g1`, `items_g2`, `items_g3`
- Feedback/reviews: `fdbk_g1`, `fdbk_g2`, `fdbk_g3`
- Attributes: `attrs_g1`, `attrs_g3` (no `attrs_g2`)
- Taxonomy: `taxn_g1`, `taxn_g2` (no `taxn_g3`)
- Review stats: `fdbk_stats_g1` (only g1)

### Reusable schema facts (verified)
- Every group keys items by `ref_id` (TEXT). Reviews (`fdbk_g*`) carry `ref_id`
  FK -> `items_g*(ref_id)`, plus `rtg`, `ttl`, `body`, `ts`, `hlp_ct`, `vrf`.
- **Timestamp column type differs by group** (important gotcha):
  - `fdbk_g1.ts` = INTEGER (epoch seconds)
  - `fdbk_g2.ts` = INTEGER (epoch seconds; see mixed-unit note below)
  - `fdbk_g3.ts` = TEXT
- `vrf` differs: `fdbk_g1.vrf` INTEGER, `fdbk_g2.vrf` TEXT, `fdbk_g3.vrf` INTEGER.
- `fdbk_g2` has BOTH `id` and `item_id`/`ref_id`; `fdbk_g3` lacks `item_id`.

## Dataset -> category mapping (verified via `items_g*.main_cat` + `str_nm`)
- **g1 = Office Products** (dominant `main_cat` "Office Products"; brands AT-A-GLANCE,
  AVERY, BIC, SHARPIE, PILOT, Paper Mate).
- **g2 = Electronics** (dominant `main_cat` values: Computers, All Electronics,
  Camera & Photo, Cell Phones & Accessories, Home Audio & Theater).
- **g3 = Musical Instruments** (dominant `main_cat` "Musical Instruments", 17162 items).

## Time-series caveat for `fdbk_g2` (verified)
- 77,022 rows total. Timestamps are integer epoch **seconds** for 77,010 rows
  (range 1008272539 .. 1679763604 => 2001-12 .. 2023-03).
- 12 outlier rows are 12-digit **milliseconds** (951582719000 .. 999482389000
  => years 2000-2001). Inference: these are mixed-unit data-entry artifacts;
  they do not fall in 2021, so a seconds-based range filter naturally excludes them.
- Therefore: when filtering `fdbk_g2` by date, compare against epoch SECONDS and
  use `strftime('%Y-%m', ts, 'unixepoch')` / `datetime(ts,'unixepoch')` for bucketing.

## Evidence log (queries run)
1. Listed `sqlite_master` tables + `CREATE TABLE` SQL.
2. Grouped `items_g*.main_cat` counts -> identified dominant category per group.
3. Sampled `items_g1.str_nm` -> stationery brands, confirming Office Products.
4. `GROUP BY LENGTH(CAST(ts AS TEXT))` on `fdbk_g2` -> exposed mixed seconds/milliseconds.
5. Bucketed `fdbk_g2` by month around the target window, then counted the window directly.

## Not done / open
- No reusable fact confirmed about review-quality or verification semantics of `vrf`.
- Did not validate `items_g2.main_cat` NULLs (1304 items) against taxonomy.
