---
name: clbench-schema-conventions
description: "CLBENCH product-DB conventions — obfuscated g1/g2/g3 tables, ms-epoch ts, dollar prc, taxonomy defines dataset identity (main_cat is noisy)"
metadata:
  node_type: memory
  type: reference
  originSessionId: b9018d9f-0b8d-4349-9f8e-4b1c8443a64c
  modified: 2026-10-04T18:08:00.057Z
---

Observed conventions in the CLBENCH 3-dataset product database (office/electronics/musical instruments, Oct 2026 instance):

- Tables are obfuscated per group: `items_gN`, `fdbk_gN`, `attrs_gN`, `taxn_gN`, `fdbk_stats_gN` (N = 1/2/3) — but the table set varies per instance (the Oct 2026 question-4 instance had only `items_gN`/`fdbk_gN`/`taxn_gN`). Column aliases: `prc`=price, `rtg`=rating, `ts`=timestamp, `hlp_ct`=helpful votes, `vrf`=verified, `ttl`=title, `ref_id`/`item_id` keys.
- Group identity: g1 = Office Products, g2 = Electronics, g3 = Musical Instruments — but verify per instance by querying `taxn_gN` at `cat_lvl = 0` (top-level taxonomy names), NOT by `items.main_cat`. The `main_cat` column is noisy raw Amazon data (NULLs, cross-category values like 'All Electronics' inside the office dataset); taxonomy level 0 is authoritative (office g1 had only 'Office Products' + 'Office Electronics').
- `items.prc` is already in dollars (office: 0.18–13914.85); `items_g2` has both `prc` (INTEGER) and `prc_usd` (REAL), and in g2 **`prc` is CENTS** (`prc/100 == prc_usd` on every overlapping row; max prc 2688800 = $26,880). Use `prc_usd` or `prc/100` for dollar thresholds in g2 — naive `prc > 50` inflates counts ~3x. Units differ per group, so always check with a min/max + overlap comparison.
- `fdbk.ts` is INTEGER ms epoch ([[clbench-timestamp-naive-ms]]); filter years with `ts >= 1640995200000 AND ts < 1672531200000` for 2022, and cross-check with `strftime('%Y', ts/1000, 'unixepoch')`.
- attrs tables hold no price keys — `items.prc` is the only price source.
- `fdbk_stats_gN.avg_rtg` is a DERIVED distractor: it equals the exact `fdbk.rtg` mean grouped by `ref_id` (0 mismatches on every row). The "stored average rating" of a product is `items.avg_rtg`, which diverges from the review mean for many products (raw metadata vs the reviews actually present).
- Join `fdbk`→`items` on `ref_id` only (declared FK, 0 orphans). `fdbk.item_id` is a different key (likely parent ASIN) — thousands of orphans vs items; grouping by it gives wrong/different answers.
- Rating-comparison questions: compute `ABS(items.avg_rtg - AVG(fdbk.rtg)) > 1` in plain float64, exactly like a pandas reference solution. Don't "fix" float noise at the boundary: mathematically-exact 1.0 gaps land on either side (4.4−3.4 = 1.0000000000000004 counts, 4.6−3.6 = 0.9999999999999996 doesn't), and since 0.5-grid ratings have exactly representable partial sums, every implementation agrees. "More than N" = strict `>`; products with no reviews are excluded (NaN/inner-join).
- fdbk rows had no orphans (FK satisfied), and ts was never NULL.

**Why:** identifying the right group and units cheaply (2-3 queries) leaves budget for verification of the actual metric.

**How to apply:** query 1 = sqlite_master DDL; query 2 = main_cat counts per group; query 3 = taxn lvl-0 roots + ts min/max + candidate counts in one UNION ALL.
