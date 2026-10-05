---
name: clbench-db-quiz
description: Use for CLBENCH database quiz questions via CLBENCH_ACTION.
---

# CLBENCH database quiz workflow

Answer natural-language questions about an unknown SQLite database using as few CLBENCH_ACTION QUERY calls as possible. Regret = max(0, queries - 1); wrong answers burn the full budget, so verify before answering.

## Query plan (aim for 3-5 total)
1. `SELECT name FROM sqlite_master WHERE type='table'` — one call gets all tables.
2. Schema discovery: query one row (`LIMIT 1`) from a small-looking table rather than PRAGMA-ing each table separately.
3. Category mapping: taxonomy tables (`taxn_gN` with ref_id/cat_lvl/cat_nm) reveal which group belongs to which product category (e.g. g1 = Office Products). Verify with one LIMIT query before counting.
4. Count with a single aggregate, filtering on the exact condition asked.
5. Submit with ANSWER; the answer value only, no explanation.

## Pitfalls
- Result output is capped at 50 rows; use aggregates or LIMIT.
- Do not write `SELECT 'g1' g, (SELECT COUNT(*) ...) FROM sqlite_master UNION ALL ...` — the correlated subquery repeats once per sqlite_master row, producing hundreds of duplicate rows. Compute per-table counts with separate scalar subqueries without a FROM driving table, or one UNION ALL of plain `SELECT 'g1', COUNT(*) FROM fdbk_g1` terms.
- Feedback tables (`fdbk_gN`) store timestamps as epoch **milliseconds** (column `ts`); compare against `ts/1000 >= <epoch-seconds>` or multiply the date threshold by 1000. Compute the epoch boundary with `date -d` in terminal, not by hand.
- Typical schema: items_gN (products), fdbk_gN (reviews: id, item_id, uid, rtg, ttl, body, ts, hlp_ct, vrf), taxn_gN (category hierarchy), attrs_gN, fdbk_stats_gN.
- Q2 (median electronics price) answered '20.92' via items_g2.prc_usd and was marked WRONG. g2 has two price columns (prc INTEGER = cents-ish values like 2199, prc_usd REAL). Which column the grader expects is unresolved — for future instances, when an answer over one candidate column is rejected, the instance ends immediately so there is no retry; do not over-trust 'usd'-suffixed columns. If a question involves g2 prices, consider computing candidates over both columns before answering and weigh which interpretation the question wording supports ('in dollars' did NOT clearly select prc_usd here).
