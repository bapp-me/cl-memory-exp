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

- **Has reviews but absent from attrs**: `rtg_ct > 0 AND NOT EXISTS (SELECT 1 FROM attrs_gN a WHERE a.ref_id = i.ref_id)`. CORRECT (g1): 267. attrs does not cover every item (~19.7k/20k), so a small non-zero count is expected, not a data error.

## Rejected answers — interpretation candidates to test first

When a near-certain answer is rejected, the instance ENDS immediately (no retry). Next time, compute ALL candidate interpretations in ONE cheap pre-answer query before submitting.

- **Median electronics price (g2)**: answered via prc_usd -> WRONG. See group quirks in SKILL.md; test prc (cents) vs prc_usd candidates before answering any g2 price question.

- **Stored avg_rtg vs mean of review scores mismatch count (g1)**: `main_cat='Office Products' AND rtg_ct>0 AND ABS(avg_rtg - AVG(fdbk.rtg)) > 1` -> 1833 WRONG. Consistency checks passed, so it is interpretation: candidates = ALL g1 items (not just main_cat match), different gap metric, or join fdbk on item_id instead of ref_id.

- **% of products priced above category-wide average (g2)**: category-scoped, prc>0 -> 17.81 WRONG. Candidates in order: (a) average/denominator over the whole g2 table, not just the category; (b) COALESCE(price,0) average; (c) percentage among ALL priced items above the category average.

- **% of reviewers spanning 2+ top-level categories (g1)**: taxn cat_lvl=0 gives only 2 root cats (0.0026% multi-cat — implausible); via items_g1.main_cat (35 distinct, 741 NULL): 1.48% WRONG. Candidates: (a) taxn cat_lvl=1 slicing, (b) categories unioned across ALL THREE datasets per uid (real uid overlap exists across groups), (c) NULL main_cat as its own category.
