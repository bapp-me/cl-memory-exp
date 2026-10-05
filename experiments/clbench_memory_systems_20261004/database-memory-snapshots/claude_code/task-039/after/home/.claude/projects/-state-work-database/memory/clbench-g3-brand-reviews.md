---
name: clbench-g3-brand-reviews
description: "g3 (musical instruments) has NO brand column and NO taxn_g3; brand = product_attributes_g3 attr_key='Brand'; fdbk_g3 year = review_year col (not ts); brand avg star = AVG(fdbk.rtg), review counts = COUNT fdbk rows"
metadata:
  node_type: memory
  type: project
  originSessionId: ef74762a-aa5e-4c90-9fcf-c268d330fa39
  modified: 2026-10-04T20:10:41.033Z
---

Verified on Q35 (CORRECT, 4 queries): g3 schema quirks and GT bindings for brand/review questions.

- g3 has **no taxn_g3** table (taxn exists only for g1/g2). Confirm g3 via `items_g3.main_cat` ('Musical Instruments': 17162 of ~20k items).
- `items_g3` has **no brand column** — brand comes from `product_attributes_g3` WHERE attr_key='Brand' (11643 rows, exactly 1 per item, no NULL/empty values). `attrs_g3_legacy` Brand (10498) is a strict subset. Brandish keys ('Brand Name', 'Processor Brand') add only ~95 items — no effect on top-brand results.
- `fdbk_g3`: 286626 rows, rtg never NULL, 100% join to items via ref_id.
- GT bindings CONFIRMED: "brands with most total customer reviews" = **COUNT of fdbk_g3 rows** per brand (NOT SUM(items.rtg_ct) — those values are implausible, e.g. 144M for 37 items, and that ranking changes top-10 membership → ZINGYOU enters at avg 3.23 → diff 1.41 WRONG); "brand-level average star rating" = **AVG(fdbk.rtg)** grouped by brand (review-level, not AVG(items.avg_rtg) which gave 0.51 vs GT 0.58).
- Q35 GT: top-10 by fdbk count, max=JIM DUNLOP 4.6378, min=Pyle 4.0577 → **0.58**. Same diff under body-only ranking and brandish-key variants (robust).
- Q36 CONFIRMED (CORRECT, 4 queries): `fdbk_g3` has BOTH `ts TEXT` (ISO 'YYYY-MM-DD', populated only 70%) and `review_year`/`review_month` INTEGER cols (populated 286623/286626). "Infer the year from populated fields" ⇒ use **review_year**; it agrees with year(ts) on 100% of overlapping rows. Brand-per-year questions: raw GROUP BY product_attributes_g3 Brand = GT (891 brands with ≥1 review in each of 2019/2020/2021); casefold merge (877) and attrs_g3_legacy (823) are distractor variants.

- Q38 CONFIRMED (CORRECT, 3 queries): "current attribute feed" for g3 = product_attributes_g3 (vs attrs_g3_legacy = older export). Feed covers only 11643 of 20000 items_g3 — brand universe AND the review check both bind to feed rows. "No review dated YEAR for any of those products" = LEFT JOIN feed→fdbk_g3 ON ref_id, GROUP BY raw brand, MAX(review_year=YEAR) flag, count flag=0 (Q38: 2408 no-2022 / 1893 with-2022 = 4301 distinct brands; ts-reading inflates to 2608 — ignore).

See [[clbench-schema-conventions]], [[clbench-dataset-scoped-questions]], [[clbench-packed-single-pass-variants]], [[clbench-current-feed-vs-legacy-export]].
