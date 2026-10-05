thread_id: 01a10b22-8144-7d82-909d-db91205696f6
updated_at: 2026-10-05T08:18:25+00:00
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-16-13-01a10b22-8144-7d82-909d-db91205696f6.jsonl
cwd: /state/work/database

# clbench Q29: percentage of office-product reviews missing text-verification label whose product is archived — answered 6.1, CORRECT in 4 queries

Rollout context: SQLite benchmark question 29/40 in /state/work/database. Agent consulted saved memory/skill files first (`/state/home/.codex/memories/MEMORY.md` and `clbench-sql-benchmark/SKILL.md`), enabling schema discovery without exploratory queries.

## Task 1: Q29 — office reviews missing verification label, archived products %

Outcome: success

Key steps:
- Grep'd memory + skill file for office/missing/verified/archived patterns; got schema conventions (g1=office, attrs_g1/fdbk_g1/items_g1) without spending a query.
- Q1: failed with `ERROR: no such column: v` — assumed attribute value column was `v` from a generic memory pattern; actual column is `attr_val`.
- Q2: targeted `SELECT name, sql FROM sqlite_master` for attrs_g1/fdbk_g1/items_g1. Revealed `fdbk_g1` has BOTH `vrf INTEGER` and `verified_status TEXT`, and `items_g1` has a `status TEXT DEFAULT 'active'` column (archived products live there, not only in attrs).
- Q3: consolidated query timed out (>10s) due to correlated `EXISTS` subquery per row.
- Q4: rewrote with pre-aggregated discontinued CTE + LEFT JOINs instead of correlated EXISTS; returned domains in one shot: missing `verified_status` population 113,242 rows; status archived=6,912 (6.1%), attr-discontinued=2,213 (1.9%); vrf domain {0,1}; status domain {active, archived}.
- ANSWER `6.1` → CORRECT.

Failures and how to do differently:
- Column-name assumption: memory implied attrs value column `v`; actual is `attrs_gN.attr_val`. Verify exact schema before referencing generic patterns (cost 1 query).
- Correlated EXISTS over ~113k rows exceeded the 10s query timeout. Pre-materialize the filter set in a CTE and LEFT JOIN instead (turned timeout into 5.1s success).

Reusable knowledge:
- `fdbk_g1` has both `vrf INTEGER` (0/1) and `verified_status TEXT`; "missing text verification label" maps to `verified_status IS NULL` (verified by CORRECT answer).
- `items_g1.status` is TEXT DEFAULT 'active' with value 'archived' for no-longer-offered products; this outperformed the attrs_g1 'Is Discontinued By Manufacturer' route (6.1% vs 1.9% divergence — the attrs route was wrong for this question).
- clbench queries have a 10s timeout; avoid correlated EXISTS on fdbk tables (~hundreds of thousands of rows); use CTE + JOIN.
- attrs value column is `attr_val`, not `v`.

References:
- Q4 winning query shape: `WITH d AS (SELECT ref_id FROM attrs_g1 WHERE lower(attr_key) LIKE '%discontinu%' AND lower(attr_val) IN ('yes','true') GROUP BY ref_id), m AS (SELECT f.ref_id, f.vrf, i.status, ... FROM fdbk_g1 f LEFT JOIN items_g1 i ... LEFT JOIN d ... WHERE f.verified_status IS NULL) ...`
- Result: archived_status_pct=6.1 (n=6,912), attr_disc_pct=1.9 (n=2,213), total missing=113,242.
- sqlite_master schema snippets for attrs_g1 (ref_id, attr_key, attr_val), fdbk_g1 (vrf INTEGER, verified_status TEXT), items_g1 (status TEXT DEFAULT 'active').
