# Per-question-type patterns (verified) and interpretation candidates

Read this when the question matches a pattern below or a previous style was rejected. 'CORRECT' means the listed answer was accepted by the grader in a real instance; reuse the exact interpretation.

## Verified patterns

- **Priced vs unpriced average rating** ('how much higher is the avg rating for products with a listed price vs without'): compute BOTH candidates in one scalar-subquery query — stored `AVG(avg_rtg)` over items, and review-level `AVG(f.rtg)` joined via ref_id — plus `COUNT(*) WHERE prc IS NULL` and `WHERE prc=0`. 'Without a price' = prc IS NULL (zero-price rows typically don't exist). If both candidates round to the same 2-dp value, answer directly with no further probing. Verified (g3/Musical Instruments): review-level 4.2857 vs 4.1670 -> 0.12, CORRECT in 5 queries (4 without a wasted existence probe).

- **Discontinued by manufacturer, avg rating below X, across attribute-storing categories** (g1+g3): the attr lives in attrs_gN as attr_val 'Yes'/'No' (a few 'True'/'False' and case variants — fold with LOWER() and LIKE '%iscontinued%'). One UNION ALL of attrs_gN JOIN items_gN on ref_id with the rating filter covers both groups; g2 has no attrs table. CORRECT: 21 (g1 17 + g3 4) in 4 queries.

- **Most common Brand / most products per brand**: `SELECT attr_val, COUNT(*) FROM attrs_gN WHERE attr_key='Brand' GROUP BY attr_val ORDER BY COUNT(*) DESC LIMIT 5`. CORRECT (g3): Fender 243. No need to inspect items for a brand column.

- **Two product identifier columns — which has more distinct values**: `SELECT sql FROM sqlite_master WHERE name IN (...)` shows which is PRIMARY KEY vs declared FOREIGN KEY, then one `COUNT(DISTINCT a), COUNT(DISTINCT b), COUNT(*)` aggregate. CORRECT (g1, rtg<=2.0): item_id 10,059 vs ref_id 8,227 -> 1,832.

- **Verified reviews, avg body length difference between star levels** (g2): fdbk_g2.vrf is TEXT 'true'/'false'. One grouped query `SELECT vrf, rtg, COUNT(*), AVG(LENGTH(body)) FROM fdbk_g2 WHERE body IS NOT NULL AND TRIM(body)!='' AND rtg IN (1,5) GROUP BY vrf, rtg` covers both star levels and verification at once. CORRECT: 101.8.

- **Zero-review items (g2)**: items_g2 has NO rtg_ct — define as NOT EXISTS on fdbk_gN.ref_id (g1/g3 have rtg_ct; prefer `rtg_ct > 0` there). 'Has a price listed' = `prc IS NOT NULL AND prc<>0`. CORRECT (g2): 3395/11345 -> 29.93.

- **Percentage among reviews with body > N chars, product price filter** (g2): one aggregate computing candidates over `prc_usd<=X` and `prc<=100*X` — identical sets (prc=100*prc_usd exact). CORRECT: 10.22 in 2 queries.

- **Average listed price of electronics (g2)**: `AVG(prc)/100.0 WHERE prc IS NOT NULL AND prc<>0` — CORRECT: 96.23 in 2 queries. No prc=0 rows exist in g2, so the `prc<>0` guard is harmless; 'listed price' = the prc column (cents), never prc_usd (52.96 in that instance).

- **Avg review rating for products with a price filter, office products (multi-group)**: 'review rating given to' = review-level AVG(fdbk.rtg), not stored avg_rtg. CORRECT (Q19, answer 4.13): pooled review-level AVG over fdbk JOIN items filtered on main_cat='Office Products' AND price>$50 — g1 dominates (20,816 reviews) so pooled ≈ g1-only (4.1286 vs 4.1282, both round to 4.13); item-stored candidates gave 4.16. Price column per group: g1/g3 `prc>50`, g2 `prc_usd>50`. CAUTION: a single UNION ALL over all three groups with GROUP BY ref_id subqueries TIMES OUT (>10s) — run g1 alone first, then a g2+g3 UNION, then the review-level aggregate per group (each fits in the timeout). g1 office: 573/13933 items >$50, all with reviews; g2: 14 (6 reviewed); g3: 3 (3 reviewed).

- **Has reviews but absent from attrs**: `rtg_ct > 0 AND NOT EXISTS (SELECT 1 FROM attrs_gN a WHERE a.ref_id = i.ref_id)`. CORRECT (g1): 267. attrs does not cover every item (~19.7k/20k), so a small non-zero count is expected, not a data error.

## Rejected answers — interpretation candidates to test first

When a near-certain answer is rejected, the instance ENDS immediately (no retry). Next time, compute ALL candidate interpretations in ONE cheap pre-answer query before submitting.

- **Median electronics price (g2)**: answered via prc_usd -> WRONG. See group quirks in SKILL.md; test prc (cents) vs prc_usd candidates before answering any g2 price question.

- **Stored avg_rtg vs mean of review scores mismatch count (g1)**: `main_cat='Office Products' AND rtg_ct>0 AND ABS(avg_rtg - AVG(fdbk.rtg)) > 1` -> 1833 WRONG. Consistency checks passed, so it is interpretation: candidates = ALL g1 items (not just main_cat match), different gap metric, or join fdbk on item_id instead of ref_id.

- **% of products priced above category-wide average (g2)**: category-scoped, prc>0 -> 17.81 WRONG. Candidates in order: (a) average/denominator over the whole g2 table, not just the category; (b) COALESCE(price,0) average; (c) percentage among ALL priced items above the category average.

- **Listing date before year X, office products (multi-group)**: listing date = attrs 'Date First Available' (g1/g3 only; g2 has NO attrs table and no date column). Pooled g1+g3 answer 3798 (g1 office 3783 + g3 office 15) was WRONG at Q20. Candidates to test FIRST, all in one query: (a) g1-only (3783), (b) g1+g3 pooled, (c) g3-only. Trailing-4-char year extraction (SUBSTR(attr_val,-4)) is safe: odd formats are old years like 'June 1, 1999'. g3 is nominally Musical Instruments but still has ~46 main_cat='Office Products' items; pooled vs primary-dataset scope is the key ambiguity. Workspace DBs are per-instance — 'gN' contents differ between questions.

- **% of reviewers spanning 2+ top-level categories (g1)**: taxn cat_lvl=0 gives only 2 root cats (0.0026% multi-cat — implausible); via items_g1.main_cat (35 distinct, 741 NULL): 1.48% WRONG. Candidates: (a) taxn cat_lvl=1 slicing, (b) categories unioned across ALL THREE datasets per uid (real uid overlap exists across groups), (c) NULL main_cat as its own category.

- **% of musical-instrument reviews missing a full event timestamp, on products priced above the avg list price (Q22, g3=Musical Instruments, 286,626 joined reviews)**: answered 38.2 WRONG (85,990 missing-ts reviews, 32,874 above avg). My interpretation: missing = `ts IS NULL OR TRIM(ts)=''`, scope = g3 only, avg list price over all non-null-priced g3 instruments, pct base = all missing-ts reviews. Candidates to test FIRST in one batched query: (a) 'missing a FULL event timestamp' = incomplete format, not NULL — fdbk_g3.ts is TEXT and this instance also had review_year/review_month INTEGER helper columns; check ts length/format distribution (date-only vs date+time) and treat 'not full' as missing; (b) scope includes g1 items with main_cat='Musical Instruments' (multi-group phrasing); (c) pct base = only priced missing-ts reviews; (d) avg list price from a different source (this instance had product_attributes_g3 and attrs_g3_legacy instead of attrs_g3 — check for price attrs there).
