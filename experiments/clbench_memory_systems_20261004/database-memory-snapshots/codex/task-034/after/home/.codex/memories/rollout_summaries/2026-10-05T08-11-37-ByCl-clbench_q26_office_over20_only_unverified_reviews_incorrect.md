thread_id: 01a10b1e-4bf8-76d2-9c0d-24215fa73c69
updated_at: 2026-10-05T08:13:47+00:00
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-11-37-01a10b1e-4bf8-76d2-9c0d-24215fa73c69.jsonl
cwd: /state/work/database

# clbench Q26: count office products >$20 with only unverified reviews — answered 86, graded INCORRECT

Rollout context: clbench SQLite benchmark in /state/work/database, Question 26/40, up to 15 exploratory queries, exact-value answer. Memory-first workflow (MEMORY.md + skill) was consulted before querying.

## Task 1: Count active office products priced >$20 whose reviews are entirely unverified

Outcome: fail (answer `86` graded INCORRECT with 3/15 queries used; instance ended)

Preference signals:
- No explicit user steering beyond the question itself; the workflow followed the saved playbook (memory-first, consolidated queries), which was consistent with prior successful runs.

Key steps:
- [1] Read MEMORY.md and clbench-sql-benchmark SKILL.md for schema and semantics.
- [2] Query 1: single consolidated query joining items_g1 + fdbk_g1 review CTE + attrs_g1 discontinued CTE, filtering `i.prc>20`, grouping by discontinued status. Used `SUM(CASE WHEN lower(vrf)='true' ...)` per Q16 playbook (`fdbk_g2.vrf='true'`) — returned verified_reviews=0 for ALL groups, exposing that g1 encodes vrf differently.
- [3] Query 2: `SELECT vrf, COUNT(*), COUNT(DISTINCT ref_id) FROM fdbk_g1 GROUP BY vrf` → g1 uses `vrf` values `1` (351,745 rows, 19,294 items) and `0` (25,727 rows, 4,494 items), NOT 'true'/'false' strings.
- [4] Query 3: rerun with `vrf='1'`. Only-unverified counts by discontinued status: <no_attr>=65, no=21, yes=2, false=0. Submitted `86` (no_attr + no + yes, treating missing attr / 'no' as active and excluding 'false'? — actually 65+21+2=86 includes yes... 86 = 65+21+0+? unresolved; the submitted 86 counted missing/'no' plus some combination) → graded INCORRECT.

Failures and how to do differently:
- Wasted Query 1 by copying the g2 verification-flag literal (`vrf='true'`) to g1 without a per-group check. The skill itself warns "Confirm the verification flag type and literal" but the run trusted the g2 example for g1. Future runs: verify flag literals per group (cheap `GROUP BY vrf` check) or include all flag variants in the first consolidated query.
- The 'active' population semantics remain unresolved and were the likely cause of the INCORRECT answer. Candidate populations from Query 3 (only-unverified counts): no_attr=65, no=21, yes=2, false=0. Candidate totals: 65 (only explicit 'no'), 86 (65+21, treating no_attr and 'no' as active), 88 (65+21+2), 65+21+0+... Future similar 'active vs discontinued' questions should enumerate ALL population combinations and consider whether 'false'/missing attrs count, plus whether products with zero reviews count, BEFORE submitting — the run did not probe alternatives with its 12 remaining queries.

Reusable knowledge:
- `fdbk_g1.vrf` is encoded as `1`/`0` integers (351,745 '1' rows / 25,727 '0' rows), NOT 'true'/'false' strings. The playbook's `fdbk_g2.vrf='true'` literal does NOT transfer to g1. Always check per-group flag encoding.
- Verified review stats for office products priced >$20: no discontinued attr: 1,687 items, 41,237 reviews, 38,427 verified; status 'no': 1,422 items, 80,976 reviews, 74,837 verified; 'yes': 11 items, 87 reviews, 54 verified; 'false': 1 item, 7 reviews, 7 verified.
- Only-unverified (zero verified purchases among reviews) counts for that population: no_attr=65, no=21, yes=2, false=0; the accepted answer is NOT 86.

References:
- Query 3 pattern: `WITH rev AS (SELECT ref_id, COUNT(*) total, SUM(CASE WHEN vrf='1' THEN 1 ELSE 0 END) verified FROM fdbk_g1 GROUP BY ref_id), disc AS (SELECT ref_id, lower(attr_val) status FROM attrs_g1 WHERE lower(attr_key)='is discontinued by manufacturer') SELECT COALESCE(d.status,'<no_attr>'), COUNT(*), SUM(only_unverified)... FROM items_g1 i LEFT JOIN disc d LEFT JOIN rev r WHERE i.prc>20 GROUP BY 1`
- Flag check: `SELECT vrf, COUNT(*), COUNT(DISTINCT ref_id) FROM fdbk_g1 GROUP BY vrf LIMIT 20;`
- Grader response: "Question 26: INCORRECT. Your answer: 86. Exploratory queries used: 3"
- Prior Q14 memory used for discontinued semantics: rollout_summaries/2026-10-05T07-27-12-Rvs8-clbench_q14_discontinued_attrs_avg_rtg_under_3.md
