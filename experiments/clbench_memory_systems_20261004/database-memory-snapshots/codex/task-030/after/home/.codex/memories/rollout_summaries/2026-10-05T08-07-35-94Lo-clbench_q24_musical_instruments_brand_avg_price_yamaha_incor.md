thread_id: 01a10b1a-9a7c-7130-a719-9adebe5e4fc2
updated_at: 2026-10-05T08:10:00+00:00
rollout_path: /state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-07-35-01a10b1a-9a7c-7130-a719-9adebe5e4fc2.jsonl
cwd: /state/work/database

# clbench Q24: highest average list price among musical-instrument brands with ≥50 products — answered Yamaha, graded INCORRECT

Rollout context: Benchmark SQL question in /state/work/database via mcp__clbench (15 exploratory QUERY budget, exact-value ANSWER). Agent consulted saved memory (/state/home/.codex/memories/MEMORY.md and skills/clbench-sql-benchmark/SKILL.md) first per established workflow.

## Task 1: Q24 — brand with highest average list price among musical-instrument brands with ≥50 products

Outcome: fail (Yamaha marked INCORRECT; instance closed after 3 queries)

Preference signals:
- (carried from prior memory, not new user steering) benchmark expects exact value in ANSWER with no explanation; memory-first consolidated-query approach is the established default.

Key steps:
- [1] First QUERY assumed saved schema (`attrs_g3`) -> `ERROR: no such table: attrs_g3` (query 1/15). This instance's schema differs from prior memory.
- [2] Second query dumped `sqlite_master`: this instance has BOTH `attrs_g3_legacy` and `product_attributes_g3` (no `attrs_g3`), plus `fdbk_stats_g1`, `items_g1.status` column, `items_g2.prc_v2`, and `fdbk_g3` with `review_year`/`review_month` columns. Attribute columns are `attr_key`/`attr_val` in both tables.
- [3] Third query compared both brand sources (UNION ALL) with HAVING COUNT(DISTINCT ref_id)>=50 counting ALL products but averaging only non-NULL `items_g3.prc`: top rows — legacy Yamaha avg 466.23 (131 total, 37 priced), current Yamaha 422.82 (143 total, 42 priced), current Fender 362.20 (243 total, 71 priced). Note: `items_g3.prc` appears to already be dollars (min 5.99, max 5186.99), so the /100 variants were distractors.
- [4] ANSWER 'Yamaha' -> INCORRECT, instance_complete=true, 3/15 queries used.

Failures and how to do differently:
- Schema drift: saved memory said `attrs_g3` exists; this instance renamed it to `attrs_g3_legacy` + `product_attributes_g3`. Always dump sqlite_master before trusting exact table names from memory — but ideally fold the schema check into the first consolidated query rather than burning query 1 on a failed join.
- Likely wrong interpretation: the ≥50 threshold was applied to ALL products while averaging only priced ones. Only 37 (legacy) / 42 (current) Yamaha products are priced — under 50. If the intended reading is 'sells at least fifty priced products' (or the average must cover ≥50 priced items), Yamaha does not qualify and Fender (71 priced, avg ~362.20) becomes the top candidate. A prior related question (Q11) was CORRECT with 'Fender' as top brand by product count.
- Other unprobed interpretations: average over all products treating NULL as excluded vs zero (ranking unaffected for Yamaha), legacy vs current attr source choice, and whether 'products' should be main_cat='Musical Instruments' filtered (items_g3 contains cross-category rows per prior memory).
- For future qualifying-threshold questions: compute the qualifying count and the averaged population on the SAME population, and when they can differ, include both variants in the consolidated query before answering.

Reusable knowledge:
- This instance's g3 attribute tables: `attrs_g3_legacy(ref_id, attr_key, attr_val)` and `product_attributes_g3(ref_id, attr_key, attr_val)` — no `attrs_g3`. Both join items_g3 on ref_id; brand is `attr_key='Brand'`.
- `items_g3.prc` is in dollars in this instance (range ~4.49–5186.99); no /100 conversion needed for g3 (unlike items_g2 where prc is cents).
- Confirmed graded-incorrect result: 'Yamaha' for this exact Q24 wording under all-products-count/priced-average interpretation.
- Instance schema drift is real: MEMORY.md facts about exact table names must be re-verified via `SELECT name, sql FROM sqlite_master WHERE type='table'` on every new instance.

References:
- sqlite_master dump output (query 2/15) — full DDL for all 13 tables including attrs_g3_legacy, product_attributes_g3, fdbk_stats_g1, items_g1.status, items_g2.prc_v2, fdbk_g3.review_year/review_month.
- Consolidated comparison query (query 3/15) with brand_items CTE UNION ALL over both attr tables, HAVING COUNT(DISTINCT ref_id)>=50, ordering avg_nonnull DESC — reusable template, add a priced>=50 variant.
- Grading output: "Question 24: INCORRECT. Your answer: Yamaha. Exploratory queries used: 3".
- MEMORY.md:222 (prior Q11 facts: attrs_g3 brand rows, Fender 241 / Yamaha 143 / Ibanez 108 — Fender was the verified top brand by count).
