---
name: clbench-db-quiz
description: Use for CLBENCH database quiz questions via CLBENCH_ACTION.
---

# CLBENCH database quiz workflow

Answer natural-language questions about an unknown SQLite database using as few CLBENCH_ACTION QUERY calls as possible. Regret = max(0, queries - 1); wrong answers burn the full budget, so verify before answering.

Before planning an answer, check `references/question-patterns.md` — it holds verified per-question-type recipes (reuse the exact accepted interpretation) and candidate interpretations for previously-rejected question styles. The instance ENDS on a wrong ANSWER with no retry, so an ambiguous question gets one cheap pre-answer query computing all candidates.

## Query plan (aim for 3-5 total)
1. `SELECT name FROM sqlite_master WHERE type='table'` — one call gets all tables. Note which taxn_/attrs_/fdbk_stats_ tables exist BEFORE referencing them: a multi-subquery aggregate that names an absent table (e.g. taxn_g3) fails entirely and wastes the query.
2. Schema discovery: `SELECT sql FROM sqlite_master WHERE name IN ('items_gN','fdbk_gN',...)` for the tables the question touches — one call, never PRAGMA per table.
3. Category mapping: if taxn_gN exists, `SELECT cat_nm, COUNT(*) FROM taxn_gN WHERE cat_lvl=0 GROUP BY cat_nm` gets root categories (never probe cat_lvl=1 first — it returns leaf/store names and wastes a query). If taxn_gN is absent (g3), fall back to `SELECT main_cat, COUNT(*) FROM items_gN GROUP BY main_cat ORDER BY COUNT(*) DESC LIMIT 3` — the dominant value names the category.
4. Count or compute with a single aggregate filtering on the exact condition asked. Batch independent aggregates into ONE query as scalar subqueries with no FROM driving table — counts, both candidate interpretations, and NULL/zero breakdowns in a single call. Calendar-year filter on fdbk timestamps: `ts >= <start_epoch_ms> AND ts < <next_year_start_ms>` (e.g. 2022 = 1640995200000 to 1672531200000).
5. If the answer depends on a JOIN, spend one query on an integrity check: LEFT JOIN plus `SUM(child.fk IS NULL)` and a total count. fdbk_gN.ref_id matched items_gN.ref_id with zero orphans in every verified instance; ref_id is the reliable join key (fdbk also has item_id, a legacy/alternate key).
6. Submit with ANSWER; the answer value only, no explanation.
7. 'Two product identifier columns' questions: one `SELECT sql FROM sqlite_master WHERE name IN (...)` shows which column is PRIMARY KEY vs declared FOREIGN KEY; then one `COUNT(DISTINCT a), COUNT(DISTINCT b), COUNT(*)` aggregate answers it.

## Pitfalls
- CLBENCH_ACTION arguments are {"action": "QUERY"|"ANSWER", "content": "<sql or answer>"} — the SQL/answer parameter is `content`, not `query`; `query` fails schema validation and wastes a turn.
- tool_call batching: each calls[] entry needs the 'name' field present — omitting it errors without consuming query budget.
- Result output is capped at 50 rows; use aggregates or LIMIT.
- Do not write `SELECT 'g1' g, (SELECT COUNT(*) ...) FROM sqlite_master UNION ALL ...` — the correlated subquery repeats once per sqlite_master row, producing hundreds of duplicates. Use scalar subqueries with no driving table, or a UNION ALL of plain `SELECT 'g1', COUNT(*) FROM fdbk_g1` terms.
- Do not put ORDER BY or trailing LIMIT inside individual UNION ALL arms — SQLite rejects it. Filter per arm with WHERE; wrap the whole UNION in an outer ORDER BY/LIMIT.
- Correlated EXISTS-subquery joins on uid time out (>10s) — use INTERSECT instead (e.g. `SELECT (SELECT COUNT(*) FROM (SELECT uid FROM fdbk_g1 INTERSECT SELECT uid FROM fdbk_g2)), ...`).
- Feedback timestamps vary per instance: g1/g2 are usually epoch ms but one instance had seconds, and g3 uses TEXT dates like '2020-01-15'. Peek at `SELECT ts FROM fdbk_gN LIMIT 3` (or `SUM(LENGTH(ts)<=11), SUM(LENGTH(ts)>=12)`) before date math — epoch math on TEXT dates returns 1970-01 for every row; on g3 TEXT use `substr(ts,1,7)`.

## Group quirks (verified)
- g1/g3: items have `prc REAL` (dollars as-is), `rtg_ct`, and an attrs_gN long-format table (ref_id, attr_key, attr_val — one row per pair, so aggregate by ref_id with DISTINCT/EXISTS, never per-row).
- g2 (electronics): NO rtg_ct column — zero reviews = NOT EXISTS on fdbk_gN.ref_id. Two price columns: `prc` INTEGER = `prc_usd`*100 exactly for every non-null pair, and prc is a strict superset (prc-only rows exist, usd-only rows do not). Both are NULL for most rows; 'has a price listed' = `prc IS NOT NULL AND prc<>0` (equivalently prc_usd, with an IS NOT NULL guard). Dollar comparisons use prc_usd or prc/100 — never raw prc against a dollar value.
- fdbk_g2.vrf is TEXT 'true'/'false'; g1/g3 vrf is INTEGER 0/1.
- SCHEMA DRIFT: schemas vary between instances even for the same group. One instance had items_g2 gain `img_ct INTEGER` (catalog image count — 'has an image' = img_ct>0) and a new `prc_v2 INTEGER` column, and prc stopped equalling prc_usd*100 for ~13% of rows. 'List price' still meant the prc column (accepted median prc/100 over img_ct>0 AND prc>0 = 21.99, vs prc_usd 20.95 / prc_v2/100 22.09). Never assume the old invariants hold; always read sqlite_master first and batch candidate interpretations.
- items_gN.avg_rtg agrees with AVG(fdbk.rtg) for every item that has reviews (no avg_rtg NULL with reviews present).
- Typical schema: items_gN (products: ref_id PK, ttl, avg_rtg, rtg_ct, prc, str_nm, main_cat, desc_txt), fdbk_gN (id, ref_id, uid, rtg, ttl, body, ts, hlp_ct, vrf), taxn_gN (category hierarchy; may be absent for a group), attrs_gN, fdbk_stats_gN.

## Rejected answers from this agent's own runs (interpretation candidates to test FIRST)
- **Priced-above-X with ONLY unverified reviews, office products (multi-group)**: answered 57 (g1 38 + g2 19 + g3 0; filter main_cat='Office Products' AND prc/prc_usd>20 AND rtg_ct>0, zero verified reviews via ref_id LEFT JOIN) — WRONG. Candidates to test FIRST in one query: (a) count ONLY products with at least one review ('have reviews, all unverified' implies >0 reviews — my run included zero-review items, the likely error); (b) vrf semantics: check `SELECT vrf, COUNT(*) FROM fdbk_gN GROUP BY 1` before assuming 0/1 (g2 is TEXT 'true'/'false'); (c) scope by taxn office subtree instead of main_cat; (d) price on a different column or >=20. Performance: NOT EXISTS on fdbk_g1 times out — LEFT JOIN to a pre-aggregated DISTINCT verified ref_id subquery works. Per-group counts (zero-review items included): g1 38 (1753 office>20), g2 19 (31 office>20), g3 0 (8 office>20).
