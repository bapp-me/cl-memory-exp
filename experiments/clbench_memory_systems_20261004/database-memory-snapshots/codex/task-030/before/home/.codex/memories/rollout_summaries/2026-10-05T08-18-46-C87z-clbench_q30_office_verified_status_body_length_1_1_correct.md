thread_id: 01a10b24-d6d9-75b1-b3f8-1bbc07966b45
updated_at: 2026-10-05T08:22:30+00:00
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-18-46-01a10b24-d6d9-75b1-b3f8-1bbc07966b45.jsonl
cwd: /state/work/database

# clbench Q30 (office products): compare avg review body length — missing vs present text-verification label; answer 1.1 CORRECT in 6/15 queries

Rollout context: clbench SQLite benchmark in /state/work/database, Question 30/40. Office group = g1. Agent leaned on saved memory (/state/home/.codex/memories/MEMORY.md and skills/clbench-sql-benchmark/SKILL.md) before any SQL, per the stored playbook.

## Task 1: Q30 — unlabeled minus labeled average review text length for active office products

Outcome: success (benchmark replied "Question 30: CORRECT. Your answer: 1.1. Exploratory queries used: 6")

Preference signals:
- The agent opened by reading MEMORY.md and the clbench SKILL.md before running SQL, consistent with the stored playbook; the run solved in 6/15 queries with only one targeted group-schema query.

Key steps:
- Query 1 failed: assumed `attrs_g1.attr_value` — actual column is `attr_val` (ERROR: no such column: attr_value).
- Query 2: dumped g1 schema from sqlite_master, revealing two columns not in prior memory: `items_g1.status TEXT DEFAULT 'active'` and `fdbk_g1.verified_status TEXT` (plus existing `vrf INTEGER`).
- Query 3: broad GROUP BY verified_status/vrf with multiple length variants hit the 10-second timeout on fdbk_g1 (354k rows joined).
- Query 4: minimal `SELECT verified_status IS NULL AS missing, COUNT(*), AVG(LENGTH(body)) ... GROUP BY missing` succeeded in 4.5s: labeled n=247,892 avg 180.95; missing n=106,215 avg 182.04.
- Query 5 failed: `quoted_label(...)` is not an available SQLite function here; replaced with CASE.
- Query 6: consolidated MATERIALIZED-CTE query returned all candidate variants identical: raw_diff_null = trim_diff_null = raw_diff_blank = 1.0924; verified_status domain is NULL (106,215), 'unverified' (17,111), 'verified' (230,781).
- ANSWER 1.1 → CORRECT.

Failures and how to do differently:
- attrs_g1 uses `attr_val`, not `attr_value` — memory previously recorded only attr_key conventions.
- Heavy multi-variant grouped probes over fdbk_g1 can exceed the 10-second query timeout; prefer the minimal direct split first, then a consolidated CTE query with MATERIALIZED hints if label-domain detail is needed.
- No custom SQL functions like `quoted_label` exist in this benchmark environment; use CASE for NULL labeling.

Reusable knowledge:
- Verified g1 schema additions: `items_g1.status TEXT DEFAULT 'active'` (catalog-status filter = `i.status='active'`) and `fdbk_g1.verified_status TEXT` with domain {NULL, 'unverified', 'verified'}. "Missing a text verification label" for g1 maps to `verified_status IS NULL`; note `vrf INTEGER` also exists separately.
- For Q30, answer 1.1 was CORRECT (unlabeled avg minus labeled avg over non-blank bodies of active-item reviews).
- Query-order lesson: run the cheap minimal split (queries ~4.5s) before multi-variant consolidation on fdbk_g1 to avoid burning budget on timeouts.

References:
- Q30 winning split query: `SELECT f.verified_status IS NULL AS missing, COUNT(*) AS n, AVG(LENGTH(f.body)) AS avg_len FROM items_g1 i JOIN fdbk_g1 f ON f.ref_id=i.ref_id WHERE i.status='active' AND f.body IS NOT NULL AND TRIM(f.body)<>'' GROUP BY missing;`
- Group counts: missing 106,215 rows avg_len 182.0433; labeled 247,892 rows avg_len 180.9509.
- Error strings: `ERROR: no such column: attr_value`; `ERROR: no such function: quoted_label`; `ERROR: query exceeded 10s timeout`.
- Skill/memory paths: /state/home/.codex/memories/MEMORY.md, /state/home/.codex/memories/skills/clbench-sql-benchmark/SKILL.md
