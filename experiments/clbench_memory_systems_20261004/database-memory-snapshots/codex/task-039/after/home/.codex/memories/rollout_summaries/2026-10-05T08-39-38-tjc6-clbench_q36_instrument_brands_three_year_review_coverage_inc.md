thread_id: 01a10b37-f129-7472-b37d-54f14b4773a2
updated_at: 2026-10-05T08:42:24+00:00
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-39-38-01a10b37-f129-7472-b37d-54f14b4773a2.jsonl
cwd: /state/work/database

# clbench Q36 (instrument brands with reviews in each of 2019/2020/2021): submitted 749, INCORRECT

Rollout context: cwd /state/work/database, single benchmark question with a 15-query budget. The agent first read saved memory/skill guidance (`/state/home/.codex/memories/MEMORY.md`, `skills/clbench-sql-benchmark/SKILL.md`), then ran 4 SQL queries before answering.

## Task 1: Count instrument brands with at least one review in each of 2019, 2020, 2021

Outcome: fail (benchmark replied "Question 36: INCORRECT. Your answer: 749. Exploratory queries used: 4")

Preference signals:
- None new; user-side instruction was the benchmark's standard "infer the review year from the fields that are actually populated on each review after you inspect the data" -> inspect populated fields rather than assuming which timestamp column to use.

Key steps:
- Query 1: dumped `sqlite_master` DDL for `%g3%` tables. This instance's `fdbk_g3` has explicit populated columns `review_year INTEGER` and `review_month INTEGER`, so no timestamp conversion was needed (the skill's epoch/length(ts) checklist did not apply to this instance).
- Query 2: consolidated CTE computing three population variants side by side (current `product_attributes_g3` brands, `attrs_g3_legacy` brands, UNION of both) over musical-scoped reviews with `review_year BETWEEN 2019 AND 2021`: current=761, legacy=701, combined=761; only 3 musical reviews had NULL review_year; year histogram 2019:28865, 2020:34061, 2021:32748.
- Query 3: normalization check — 761 brands with years=3 by exact TRIM spelling, but 749 by `lower(trim(attr_val))` distinct.
- Query 4: listed the 12 case-duplicate spellings (e.g. YAMAHA|Yamaha, BOSS|Boss, GIBRALTAR|Gibraltar, pearl, snark, etc.), confirming 761 − 12 = 749.
- Submitted 749 (the normalized count) -> INCORRECT. The agent's post-answer message said "761", implying the intended answer was the exact-spelling count of 761.

Failures and how to do differently:
- Chose the normalized (lowercased) brand count 749 over the exact-spelling count 761, and the benchmark marked it incorrect. In this benchmark, "instrument brands" counts appear to use the raw `attr_val` spelling (via `COUNT(DISTINCT ref_id)`-style grouping per brand row), not case-normalized dedup. When two counts differ by case variants, prefer the exact/TRIM count unless wording says to treat spellings as the same brand, and/or verify both interpretations more before ANSWER.
- Prior memory already warned to compute candidate interpretations side by side; the agent did compute 749 vs 761 side by side but picked the wrong one. Dedup-by-brand-name questions in prior tasks (Q24 top brands: Fender 241, Yamaha 143) used per-ref grouping with raw values.

Reusable knowledge:
- This benchmark instance's `fdbk_g3` includes populated `review_year INTEGER` / `review_month INTEGER` columns; when they exist, use them directly instead of timestamp epoch conversion.
- Verified schema: `fdbk_g3(id INTEGER PK, ref_id FK, uid, rtg, ttl, body, ts TEXT, hlp_ct, vrf INTEGER, review_year INTEGER, review_month INTEGER)`; brand attributes live in `product_attributes_g3` and `attrs_g3_legacy` (`attr_key='Brand'`, value in `attr_val`); no plain `attrs_g3`.
- Musical-scoped review year histogram (2019–2021 only): 2019:28865, 2020:34061, 2021:32748; 3 NULL-year reviews; brand-with-3-year-coverage counts: current attrs 761, legacy 701, union 761 exact-spelling, 749 case-normalized.
- 12 case-duplicate brand spellings existed among 761: adm, an-do-er, blucoil, boss, comica, flatsons, gibraltar, hercules, pearl, snark, sunflower, yamaha.
- Q36 final: answer 749 INCORRECT -> 761 (exact spelling) is the likely intended reading; do not case-normalize brand counts in this benchmark unless explicitly asked.

References:
- Query 2 consolidated CTE (populations side by side) and result row `761 | 701 | 761 | 3 | 2019:28865, 2020:34061, 2021:32748`.
- Query 3 result `761 | 761 | 749` (exact_trim_brands, exact_distinct_brands, normalized_distinct_brands).
- Benchmark feedback verbatim: "Question 36: INCORRECT. Your answer: 749. Exploratory queries used: 4".

