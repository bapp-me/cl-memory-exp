---
name: clbench-db-quiz
description: Use for CLBENCH database quiz questions via CLBENCH_ACTION.
---

# CLBENCH database quiz workflow

Answer natural-language questions about an unknown SQLite database using as few CLBENCH_ACTION QUERY calls as possible. Regret = max(0, queries - 1); wrong answers burn the full budget, so verify before answering.

## Query plan (aim for 3-5 total)
1. `SELECT name FROM sqlite_master WHERE type='table'` — one call gets all tables.
2. Schema discovery: query one row (`LIMIT 1`) from a small-looking table rather than PRAGMA-ing each table separately.
3. Category mapping: taxonomy tables (`taxn_gN` with ref_id/cat_lvl/cat_nm) reveal which group belongs to which product category (e.g. g1 = Office Products). `SELECT '<g>' g, cat_nm, COUNT(*) FROM taxn_gN WHERE cat_lvl=0 GROUP BY cat_nm` per group gets the root categories in one call. Taxonomy tables may not exist for every group (taxn_g3 was absent in one instance) — fallback to `SELECT DISTINCT main_cat FROM items_gN LIMIT 10` for category mapping. Verify before counting.
4. Count with a single aggregate, filtering on the exact condition asked. Calendar-year filter on fdbk timestamps: `ts >= <start_epoch_ms> AND ts < <next_year_start_ms>` (e.g. 2022 = 1640995200000 to 1672531200000).
5. If the answer depends on a JOIN, spend one query on an integrity check before answering: LEFT JOIN and `SUM(child.fk IS NULL)` plus a total count — confirms no rows silently dropped and guards the full-budget burn of a wrong answer. In a verified instance, fdbk_gN.ref_id matched items_gN.ref_id with zero unmatched rows; ref_id is the reliable join key (fdbk also has item_id, which may be a legacy/alternate key).
6. Submit with ANSWER; the answer value only, no explanation.

## Pitfalls
- Result output is capped at 50 rows; use aggregates or LIMIT.
- Do not write `SELECT 'g1' g, (SELECT COUNT(*) ...) FROM sqlite_master UNION ALL ...` — the correlated subquery repeats once per sqlite_master row, producing hundreds of duplicate rows. Compute per-table counts with separate scalar subqueries without a FROM driving table, or one UNION ALL of plain `SELECT 'g1', COUNT(*) FROM fdbk_g1` terms.
- Do not put ORDER BY (or trailing LIMIT) inside individual UNION ALL arms — SQLite rejects it with 'ORDER BY clause should come after UNION ALL'. Write plain SELECT terms and, if needed, filter per arm with WHERE; wrap the whole UNION in an outer ORDER BY/LIMIT if ordering is needed.
- g1/g3 items price column `prc REAL` is dollar-denominated as-is; only g2 has the ambiguous prc/prc_usd pair.
- Feedback tables (`fdbk_gN`) store timestamps as epoch **milliseconds** (column `ts`); compare against `ts/1000 >= <epoch-seconds>` or multiply the date threshold by 1000. Compute the epoch boundary with `date -d` in terminal, not by hand.
- Typical schema: items_gN (products), fdbk_gN (reviews: id, item_id, uid, rtg, ttl, body, ts, hlp_ct, vrf), taxn_gN (category hierarchy), attrs_gN, fdbk_stats_gN.
- Q2 (median electronics price) answered '20.92' via items_g2.prc_usd and was marked WRONG. g2 has two price columns (prc INTEGER = cents-ish values like 2199, prc_usd REAL). Which column the grader expects is unresolved — for future instances, when an answer over one candidate column is rejected, the instance ends immediately so there is no retry; do not over-trust 'usd'-suffixed columns. If a question involves g2 prices, consider computing candidates over both columns before answering and weigh which interpretation the question wording supports ('in dollars' did NOT clearly select prc_usd here). CONFIRMED in a later verified instance (Q4 'electronics priced above $50', answered 8 via prc_usd>50 and marked CORRECT): items_g2.prc = prc_usd*100 exactly for every non-null pair (e.g. 6495 vs 64.95), so prc is cents-denominated and any raw `prc > <dollars>` comparison is wrong; also prc/prc_usd are NULL for most rows and price>50 questions count only non-null prices. Verified join: fdbk_gN.ref_id matches items_gN.ref_id with zero unmatched rows; items_g2.avg_rtg column agrees with AVG(fdbk.rtg), and every item with reviews has avg_rtg set.
