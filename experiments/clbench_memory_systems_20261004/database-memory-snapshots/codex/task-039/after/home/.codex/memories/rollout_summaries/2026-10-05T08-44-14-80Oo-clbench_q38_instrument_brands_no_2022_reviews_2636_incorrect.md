thread_id: 01a10b3c-27e4-7771-8127-8c5d43ee40c4
updated_at: 2026-10-05T08:47:35+00:00
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-44-14-01a10b3c-27e4-7771-8127-8c5d43ee40c4.jsonl
cwd: /state/work/database

# Clbench Q38: instrument brands with no 2022 reviews — answered 2636, graded INCORRECT

Rollout context: clbench SQLite benchmark question 38/40 in /state/work/database. Question: "How many distinct instrument brand names appear on products in the current attribute feed but have no customer review dated in 2022 for any of those products?" Budget 15 exploratory queries; answers via CLBENCH_ACTION QUERY/ANSWER.

## Task 1: Answer Q38 (brands in current attribute feed with no 2022 review)

Outcome: fail

Preference signals:
- None new; the agent followed existing clbench-sql-benchmark skill and MEMORY.md procedures.

Key steps:
- Read skill + MEMORY.md first; confirmed drifted g3 layout: `product_attributes_g3(ref_id, attr_key, attr_val)` and `attrs_g3_legacy` exist, no plain `attrs_g3`; `fdbk_g3.ts` is TEXT with `review_year`/`review_month` integer columns; `fdbk_g3.vrf` is INTEGER.
- First consolidated probe (brand NOT EXISTS with correlated subqueries) hit the 10s query timeout.
- Second query succeeded (7.4s) using pre-materialized CTEs of 2022 ref_ids: results — scoped_year=2636, scoped_ts=2775, all_year=3144, all_ts=3343 (scoped = main_cat='Musical Instruments'; year = review_year=2022; ts = substr(ts,1,4)='2022').
- Third query attempting to diagnose review_year vs ts mismatch timed out (budget 4 used).
- Submitted ANSWER 2636 (musical-scoped, review_year reading) → INCORRECT.

Failures and how to do differently:
- The submitted 2636 was INCORRECT. Candidate alternates: 2775 (musical-scoped, ts-year reading), 3144/3343 (all-product scope). Since g3 ts is TEXT and review_year/ts can disagree (4,401 refs with ts year 2022 vs 5,251 with review_year 2022), the intended date source is unresolved. Future Q38-like runs: resolve the review_year-vs-ts discrepancy BEFORE answering — e.g. count products whose reviews have ts year 2022 but review_year != 2022 and vice versa in a fast grouped query, and consider which field "dated in 2022" most likely means (raw ts is the more literal reading, giving 2775).
- Correlated NOT EXISTS per brand timed out; pre-materializing `SELECT DISTINCT ref_id FROM fdbk_g3 WHERE <2022 predicate>` CTEs and joining worked within the timeout.

Reusable knowledge:
- This instance's g3 schema (verified via sqlite_master): items_g3(ref_id PK, ttl, avg_rtg, rtg_ct, prc, str_nm, main_cat, desc_txt); fdbk_g3(id, ref_id, uid, rtg, ttl, body, ts TEXT, hlp_ct, vrf INTEGER, review_year, review_month); attrs via product_attributes_g3 + attrs_g3_legacy.
- fdbk_g3.review_year and ts-derived year disagree substantially (5,251 vs 4,401 distinct musical refs with 2022), so Q38 answer depends on the date source; 2636 (review_year, scoped) was graded wrong; 2775 (ts year, scoped) untested.
- CLBENCH_QUERY has a 10s timeout; anti-join patterns must pre-materialize distinct ref_id sets, not correlate per-row.

References:
- Working query shape (3rd query, 7.4s): CTEs `pa` (brand rows joined to items_g3), `scoped` (musical main_cat only), `rev2022`/`rev2022_ts` (DISTINCT ref_id by date source), then COUNT(DISTINCT brand) with NOT EXISTS against each.
- Grading output: "Question 38: INCORRECT. Your answer: 2636. Exploratory queries used: 4"
- Memory lines referenced: MEMORY.md:362-366, 368; SKILL.md:35-39.
