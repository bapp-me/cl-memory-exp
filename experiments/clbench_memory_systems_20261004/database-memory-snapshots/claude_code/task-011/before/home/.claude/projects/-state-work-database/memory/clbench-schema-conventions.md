---
name: clbench-schema-conventions
description: "CLBENCH product-DB conventions — obfuscated g1/g2/g3 tables, ms-epoch ts, dollar prc, taxonomy defines dataset identity (main_cat is noisy)"
metadata:
  node_type: memory
  type: reference
  originSessionId: b9018d9f-0b8d-4349-9f8e-4b1c8443a64c
  modified: 2026-10-04T18:25:00.719Z
---

Observed conventions in the CLBENCH 3-dataset product database (office/electronics/musical instruments, Oct 2026 instance):

- Tables are obfuscated per group: `items_gN`, `fdbk_gN`, `attrs_gN`, `taxn_gN`, `fdbk_stats_gN` (N = 1/2/3) — but the table set varies per instance (the Oct 2026 question-4 instance had only `items_gN`/`fdbk_gN`/`taxn_gN`). Column aliases: `prc`=price, `rtg`=rating, `ts`=timestamp, `hlp_ct`=helpful votes, `vrf`=verified, `ttl`=title, `ref_id`/`item_id` keys.
- Group identity: g1 = Office Products, g2 = Electronics, g3 = Musical Instruments — but verify per instance by querying `taxn_gN` at `cat_lvl = 0` (top-level taxonomy names), NOT by `items.main_cat`. The `main_cat` column is noisy raw Amazon data (NULLs, cross-category values like 'All Electronics' inside the office dataset); taxonomy level 0 is authoritative (office g1 had only 'Office Products' + 'Office Electronics').
- `items.prc` is already in dollars (office: 0.18–13914.85); `items_g2` has both `prc` (INTEGER) and `prc_usd` (REAL), and in g2 **`prc` is CENTS** (`prc/100 == prc_usd` on every overlapping row; max prc 2688800 = $26,880). Use `prc_usd` or `prc/100` for dollar thresholds in g2 — naive `prc > 50` inflates counts ~3x. Units differ per group, so always check with a min/max + overlap comparison.
- **`prc_usd` in g2 is INCOMPLETE — only `prc` is the canonical price.** Coverage (all 20000 items_g2 rows): 13430 both NULL, 6346 both present (prc ≤ 49999 cents = $499.99), 224 with prc only (prc ≥ 50000 cents, i.e. $500–$2688 — real laptops/motherboards/TVs). prc_usd is NULL exactly when prc ≥ 50000; no zeros anywhere in either column, in any group. So the two columns differ in WHICH rows count, not just units: for g2 the same category/priced set gave 17.27% using `prc` (verified CORRECT) vs 24.44% using `prc_usd`. Rule: unit-free/relative price questions (averages, "% above category average") → use `prc` (complete + canonical across all groups; scale-invariant anyway); only dollar-AMOUNT threshold questions need the /100 conversion.
- `fdbk.ts` type is NOT uniform across groups — check `LENGTH(ts)`/samples before converting. g1/g2: INTEGER ms epoch ([[clbench-timestamp-naive-ms]]); g3 (Oct 2026 instance): TEXT `'YYYY-MM-DD'` (len 10), so use `substr(ts,1,7)` directly. Filter years with `ts >= 1640995200000 AND ts < 1672531200000` for 2022 in the epoch groups, and cross-check with `strftime('%Y', ts/1000, 'unixepoch')`.
- attrs tables hold no price keys — `items.prc` is the only price source.
- `fdbk_stats_gN.avg_rtg` is a DERIVED distractor: it equals the exact `fdbk.rtg` mean grouped by `ref_id` (0 mismatches on every row). The "stored average rating" of a product is `items.avg_rtg`, which diverges from the review mean for many products (raw metadata vs the reviews actually present).
- Join `fdbk`→`items` on `ref_id` only (declared FK, 0 orphans). `fdbk.item_id` is a different key (likely parent ASIN) — thousands of orphans vs items; grouping by it gives wrong/different answers.
- Instance table sets differ: the Oct 2026 q9 instance had NO `taxn_g3`, `attrs_g2`, or `fdbk_stats_g2/g3` (only taxn_g1/g2, attrs_g1/g3, fdbk_stats_g1). There, identifying g3 fell back on `items.main_cat` samples (clean 'Musical Instruments' in items_g3, unlike the noisy g1 case). For time-bucket questions, raw `fdbk_gN` GROUP BY and the join-to-items version agreed (2020-01 = 4715 either way) — the raw count suffices.
- Rating-comparison questions: compute `ABS(items.avg_rtg - AVG(fdbk.rtg)) > 1` in plain float64, exactly like a pandas reference solution. Don't "fix" float noise at the boundary: mathematically-exact 1.0 gaps land on either side (4.4−3.4 = 1.0000000000000004 counts, 4.6−3.6 = 0.9999999999999996 doesn't), and since 0.5-grid ratings have exactly representable partial sums, every implementation agrees. "More than N" = strict `>`; products with no reviews are excluded (NaN/inner-join).
- Brand questions ("most products for brand X"): the canonical source is `attrs_gN` with `attr_key = 'Brand'`; count `COUNT(DISTINCT ref_id) GROUP BY attr_val`. A secondary `attr_key = 'Manufacturer'` exists with much lower coverage (q11 instance: 2481 vs 11643 rows) — check it in the same UNION ALL query, but it has never out-ranked Brand's top value. Values are raw-cased ('JIM DUNLOP', 'Hohner Accordions'), so don't case-fold unless ties look suspicious; answer with the `attr_val` string verbatim (q11: 'Fender', 243 products, CORRECT).
- fdbk rows had no orphans (FK satisfied), and ts was never NULL.
- `fdbk.vrf` is a TEXT boolean written literally `'true'`/`'false'` (lowercase); the review body column is `body` (plain `TEXT`, no padding whitespace — `AVG(LENGTH(body))` == `AVG(LENGTH(TRIM(body)))` exactly). `rtg` values are whole floats (1.0/2.0/3.0/4.0/5.0 only). "Non-empty body" edge cases (NULL / whitespace-only) were rare and absent among verified 1-star & 5-star rows, so that filter is usually insensitive.

**Why:** identifying the right group and units cheaply (2-3 queries) leaves budget for verification of the actual metric.

**How to apply:** query 1 = sqlite_master DDL; query 2 = main_cat counts per group; query 3 = taxn lvl-0 roots + ts min/max + candidate counts in one UNION ALL.
