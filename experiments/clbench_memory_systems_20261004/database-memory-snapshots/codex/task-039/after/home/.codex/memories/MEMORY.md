# Task Group: clbench SQL benchmark
scope: SQLite benchmark questions in /state/work/database, including schema/category mapping, schema drift, attribute/taxonomy tables, brand and listing-date attributes, price units and population/format semantics, review-rating sources, verified-review flags, catalog status, body-length calculations, reviewer spans, float-sensitive numeric thresholds, timestamp filtering, and median calculations over anonymized product-feedback tables; use before writing any data query.
applies_to: cwd=/state/work/database; reuse_rule=Safe for this clbench product-reviews benchmark and analogous SQLite schema/epoch/median questions; verify schema names, category mapping, and units before transferring exact table names to another checkout.

## Task 31: Compute unlabeled minus labeled average body length for active office products (Q30)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-18-46-C87z-clbench_q30_office_verified_status_body_length_1_1_correct.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-18-46-01a10b24-d6d9-75b1-b3f8-1bbc07966b45.jsonl, updated_at=2026-10-05T08:22:30+00:00, thread_id=01a10b24-d6d9-75b1-b3f8-1bbc07966b45, status=success, usefulness=high)

### keywords

- clbench, items_g1.status, fdbk_g1.verified_status, vrf, LENGTH(body), active, unlabeled, labeled, attr_val, answer 1.1, 6 of 15 queries

## Task 32: Compute percentage of office missing-verification-label reviews on archived products (Q29)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-16-13-IsUm-clbench_q29_office_missing_verification_archived_pct.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-16-13-01a10b22-8144-7d82-909d-db91205696f6.jsonl, updated_at=2026-10-05T08:18:25+00:00, thread_id=01a10b22-8144-7d82-909d-db91205696f6, status=success, usefulness=high)

### keywords

- clbench, verified_status IS NULL, archived, items_g1.status, attrs_g1, attr_val, discontinued, correlated EXISTS, CTE JOIN, answer 6.1, 4 of 15 queries

## Task 33: Compute musical-instruments current versus legacy attribute-line ratio (Q28)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-15-09-TODx-clbench_q28_attribute_line_ratio_2_queries.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-15-09-01a10b21-86fe-71a1-a880-bb620b5c9c63.jsonl, updated_at=2026-10-05T08:15:52+00:00, thread_id=01a10b21-86fe-71a1-a880-bb620b5c9c63, status=success, usefulness=high)

### keywords

- clbench, product_attributes_g3, attrs_g3_legacy, attr_key, attr_val, Musical Instruments, current feed, legacy export, line ratio, answer 1.11, 2 of 15 queries

## Task 34: Compute percentage of electronics with at least three reviews priced strictly above $60 (Q27)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-14-12-xcvO-clbench_q27_electronics_3reviews_price_above60_answer_10_inc.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-14-12-01a10b20-a8c9-7a81-b419-c724159bff5c.jsonl, updated_at=2026-10-05T08:14:48+00:00, thread_id=01a10b20-a8c9-7a81-b419-c724159bff5c, status=fail, usefulness=high)

### keywords

- clbench, items_g2, fdbk_g2, at least three reviews, COUNT(f.ref_id), COUNT(DISTINCT f.uid), prc_usd, strictly above 60, percentage, answer 10.0, INCORRECT, 1 of 15 queries

## Task 35: Count office products over $20 with only unverified reviews (Q26)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-11-37-ByCl-clbench_q26_office_over20_only_unverified_reviews_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-11-37-01a10b1e-4bf8-76d2-9c0d-24215fa73c69.jsonl, updated_at=2026-10-05T08:13:47+00:00, thread_id=01a10b1e-4bf8-76d2-9c0d-24215fa73c69, status=fail, usefulness=high)

### keywords

- clbench, fdbk_g1.vrf, verified reviews, unverified, active, discontinued, only-unverified, prc>20, answer 86, INCORRECT, 3 of 15 queries

## Task 36: Compute average list price of electronics with at least three images (Q25)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-10-27-iaMt-clbench_q25_electronics_img_ct_ge3_avg_list_price_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-10-27-01a10b1d-39c1-74c2-b08c-96f1f5fbf0c5.jsonl, updated_at=2026-10-05T08:11:15+00:00, thread_id=01a10b1d-39c1-74c2-b08c-96f1f5fbf0c5, status=fail, usefulness=high)

### keywords

- clbench, items_g2, img_ct>=3, prc_usd, main_cat, AMAZON FASHION, Video Games, electronics scope, average list price, 52.94, INCORRECT, 1 of 15 queries

## Task 37: Identify musical-instrument brand with highest average list price among at least fifty products (Q24)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-07-35-94Lo-clbench_q24_musical_instruments_brand_avg_price_yamaha_incor.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-07-35-01a10b1a-9a7c-7130-a719-9adebe5e4fc2.jsonl, updated_at=2026-10-05T08:10:00+00:00, thread_id=01a10b1a-9a7c-7130-a719-9adebe5e4fc2, status=fail, usefulness=high)

### keywords

- clbench, attrs_g3_legacy, product_attributes_g3, schema drift, Brand, Yamaha, Fender, >=50 products, priced products, avg list price, INCORRECT, 3 of 15 queries

## Task 38: Count electronics products at least 15% above mean list price (Q23)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-05-51-hgz0-clbench_q23_electronics_price_15pct_above_mean_incorrect_137.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-05-51-01a10b19-0348-7c72-a9ad-12a35851b172.jsonl, updated_at=2026-10-05T08:07:15+00:00, thread_id=01a10b19-0348-7c72-a9ad-12a35851b172, status=fail, usefulness=high)

### keywords

- clbench, items_g2, mean list price, 1.15 threshold, prc_usd, main_cat scope, NULL-as-zero, 1370, known-bad candidate, INCORRECT, 1 of 15 queries

## Task 39: Compute percentage of musical reviews missing a full timestamp above average list price (Q22)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-02-33-RchZ-clbench_q22_musical_missing_timestamp_pct_10_3_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-02-33-01a10b16-004e-71c2-a9dc-2ed0f1327ef3.jsonl, updated_at=2026-10-05T08:05:24+00:00, thread_id=01a10b16-004e-71c2-a9dc-2ed0f1327ef3, status=fail, usefulness=high)
- extensions/ad_hoc/notes/2026-10-05-clbench-q22-missing-full-timestamp-incorrect.md (authoritative ad-hoc note [ad-hoc note])

### keywords

- clbench, fdbk_g3, ts TEXT, missing full timestamp, 75572, average list price, 132.34761019812626, grouped single-pass, GLOB error, 10s timeout, 10.3, INCORRECT [ad-hoc note]

## Task 40: Compute median list price of electronics with images and positive price (Q21)

### rollout_summary_files

- rollout_summaries/2026-10-05T07-53-25-UByY-clbench_q21_electronics_median_list_price_with_images_correc.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-53-25-01a10b0d-a435-77d3-ab98-0dc606f822bc.jsonl, updated_at=2026-10-05T08:02:09+00:00, thread_id=01a10b0d-a435-77d3-ab98-0dc606f822bc, status=success, usefulness=high)

### keywords

- clbench, items_g2, median, ROW_NUMBER, img_ct>0, prc>0, prc_usd, prc_v2, 21.99, single-statement error, 13 of 15 queries

## Task 21: Count office products with listing date before 2015

### rollout_summary_files

- rollout_summaries/2026-10-05T07-42-52-ALQn-clbench_q20_office_listing_date_before_2015.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-42-52-01a10b03-f9bb-74b0-9669-418ac40bd72b.jsonl, updated_at=2026-10-05T07:44:28+00:00, thread_id=01a10b03-f9bb-74b0-9669-418ac40bd72b, status=success, usefulness=high)

### keywords

- clbench, attrs_g1, Date First Available, items_g1, listing date, year extraction, substr, UNION ALL error, exact-count, answer 5254, 6 of 15 queries

## Task 22: Compute average review rating of office products priced over $50

### rollout_summary_files

- rollout_summaries/2026-10-05T07-41-45-319N-clbench_q19_office_products_rating_over_50.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-41-45-01a10b02-f4b5-7e10-af24-db97b73c874b.jsonl, updated_at=2026-10-05T07:42:36+00:00, thread_id=01a10b02-f4b5-7e10-af24-db97b73c874b, status=success, usefulness=high)

### keywords

- clbench, items_g1, fdbk_g1, Office Products, prc, AVG(rtg), avg_rtg, ref_id, feedback-derived rating, answer 4.128218677940046, 1 of 15 queries

## Task 23: Compute average listed price of electronics products

### rollout_summary_files

- rollout_summaries/2026-10-05T07-40-20-jdZq-clbench_q18_electronics_avg_listed_price_incorrect_52956.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-40-20-01a10b01-a946-76c0-ae52-6958943cb4fc.jsonl, updated_at=2026-10-05T07:41:22+00:00, thread_id=01a10b01-a946-76c0-ae52-6958943cb4fc, status=fail, usefulness=high)

### keywords

- clbench, items_g2, prc_usd, prc, electronics, average price, NULL handling, rounding, exact-match scoring, INCORRECT, 52.95666246454459, 1 of 15 queries

## Task 24: Compute musical-instruments rating gap for priced versus unpriced products

### rollout_summary_files

- rollout_summaries/2026-10-05T07-39-17-3g0p-clbench_q17_musical_instruments_priced_vs_unpriced_rating_ga.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-39-17-01a10b00-b43e-7c71-be41-510bfb0e8311.jsonl, updated_at=2026-10-05T07:40:02+00:00, thread_id=01a10b00-b43e-7c71-be41-510bfb0e8311, status=success, usefulness=high)

### keywords

- clbench, items_g3, fdbk_g3, ref_id, Musical Instruments, prc, priced vs unpriced, LEFT JOIN, review-weighted, answer 0.12, 1 of 15 queries

## Task 25: Compute percentage of 1-star electronics reviews with body over 500 characters on items priced <=$40

### rollout_summary_files

- rollout_summaries/2026-10-05T07-38-25-aKL2-clbench_q16_electronics_body_gt500_price_le40_pct_1star_answ.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-38-25-01a10aff-e6cc-7141-af16-318e8b4f35ac.jsonl, updated_at=2026-10-05T07:39:01+00:00, thread_id=01a10aff-e6cc-7141-af16-318e8b4f35ac, status=success, usefulness=high)

### keywords

- clbench, items_g2, fdbk_g2, ref_id, prc_usd, rtg, body, LENGTH, one-star percentage, review body length, answer 10.22, 2172 reviews, 222 one-star, 1 of 15 queries

## Task 26: Compute percentage of office reviewers spanning at least two top-level categories

### rollout_summary_files

- rollout_summaries/2026-10-05T07-29-00-8WAI-clbench_q15_office_reviewers_multi_toplevel_cat_pct_incorrec.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-29-00-01a10af7-4677-7233-8065-ce6f1b6e117c.jsonl, updated_at=2026-10-05T07:37:56+00:00, thread_id=01a10af7-4677-7233-8065-ce6f1b6e117c, status=fail, usefulness=high)

### keywords

- clbench, fdbk_g1, items_g1, taxn_g1, uid, main_cat, cat_lvl, top-level category, percentage, query timeout, 10s timeout, INCORRECT, 0.00, 1.87, 358837, reviewer denominator, 14 of 15 queries

## Task 27: Count discontinued products with catalog average rating under 3.0

### rollout_summary_files

- rollout_summaries/2026-10-05T07-27-12-Rvs8-clbench_q14_discontinued_attrs_avg_rtg_under_3.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-27-12-01a10af5-a2ca-7322-a611-0893b2ab5244.jsonl, updated_at=2026-10-05T07:28:42+00:00, thread_id=01a10af5-a2ca-7322-a611-0893b2ab5244, status=success, usefulness=high)

### keywords

- clbench, attrs_g1, attrs_g3, discontinued, Is Discontinued By Manufacturer, avg_rtg, items_g1, items_g3, ref_id, answer 21, 3 of 15 queries

## Task 28: Compute percentage of zero-review electronics items with a listed price

### rollout_summary_files

- rollout_summaries/2026-10-05T07-26-10-fjtU-clbench_q13_electronics_zero_reviews_priced_pct_answer_2867.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-26-10-01a10af4-af95-76e0-b16b-9c47171de2b2.jsonl, updated_at=2026-10-05T07:26:57+00:00, thread_id=01a10af4-af95-76e0-b16b-9c47171de2b2, status=fail, usefulness=high)

### keywords

- clbench, items_g2, fdbk_g2, prc_usd, zero reviews, NOT EXISTS, percentage, INCORRECT, 28.67, interpretation probing, 1 of 15 queries

## Task 29: Count electronics reviews posted in Q4 2021

### rollout_summary_files

- rollout_summaries/2026-10-05T07-24-22-PjzM-clbench_q12_electronics_reviews_q4_2021_correct.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-24-22-01a10af3-0c55-7a52-a6db-28c4570a937e.jsonl, updated_at=2026-10-05T07:25:52+00:00, thread_id=01a10af3-0c55-7a52-a6db-28c4570a937e, status=success, usefulness=high)

### keywords

- clbench, fdbk_g2, items_g2, ref_id, timestamp, epoch, strftime, length(ts), unixepoch, Q4 2021, electronics, memory-first, answer 1867, 1 of 15 queries

## Task 30: Identify brand with most musical instrument products

### rollout_summary_files

- rollout_summaries/2026-10-05T07-22-49-6nEe-clbench_q11_musical_instruments_top_brand_fender_correct.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-22-49-01a10af1-9ea0-7e12-82eb-420e11b4962a.jsonl, updated_at=2026-10-05T07:24:06+00:00, thread_id=01a10af1-9ea0-7e12-82eb-420e11b4962a, status=success, usefulness=high)

### keywords

- clbench, attrs_g3, items_g3, attr_key, Brand, ref_id, main_cat, Fender, Yamaha, musical instruments, join key, answer Fender, 3 of 15 queries

## Task 1: Compute percentage of Computers & Accessories electronics above category-wide average price

### rollout_summary_files

- rollout_summaries/2026-10-05T06-38-05-VQ4J-clbench_q8_electronics_computers_accessories_pct_above_avg_p.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-38-05-01a10ac8-abff-7f21-87e2-efd65aa82d8d.jsonl, updated_at=2026-10-05T06:39:19+00:00, thread_id=01a10ac8-abff-7f21-87e2-efd65aa82d8d, status=fail, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, items_g2, taxn_g2, prc_usd, cat_lvl, cat_nm, main_cat, Computers & Accessories, category-wide average, percentage above average, INCORRECT, 24.44, sqlite_master, category mapping, top-level category

## Task 2: Compute average body-length difference for verified electronics 1-star versus 5-star reviews

### rollout_summary_files

- rollout_summaries/2026-10-05T06-32-13-sBIv-clbench_q7_verified_electronics_body_length_diff_answer_101.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-32-13-01a10ac3-4b11-72b1-89ee-329b2e346cbb.jsonl, updated_at=2026-10-05T06:33:26+00:00, thread_id=01a10ac3-4b11-72b1-89ee-329b2e346cbb, status=success, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, sqlite_master, fdbk_g2, items_g2, vrf, rtg, body, LENGTH, TRIM, verified, review body length, answer 101.8, 3 of 15 queries

## Task 3: Count distinct item_id minus distinct ref_id for office reviews rated <=2.0

### rollout_summary_files

- rollout_summaries/2026-10-05T06-27-20-GicW-clbench_q6_office_rtg_le_2_distinct_item_id_vs_ref_id_fk_cor.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-27-20-01a10abe-d341-78e3-8683-bfff91ec306a.jsonl, updated_at=2026-10-05T06:28:20+00:00, thread_id=01a10abe-d341-78e3-8683-bfff91ec306a, status=success, usefulness=high)

### keywords

- clbench, sqlite, fdbk_g1, items_g1, item_id, ref_id, foreign key, COUNT DISTINCT, rtg, exact-value answer, 1832, 2 of 15 queries

## Task 4: Count office products where stored avg_rtg differs from feedback-derived mean by >1 star

### rollout_summary_files

- rollout_summaries/2026-10-05T06-20-41-MFIw-clbench_q5_office_stored_vs_actual_rating_diff_over_1_correc.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-20-41-01a10ab8-bdf2-7361-8e37-0dcc93c6535c.jsonl, updated_at=2026-10-05T06:22:07+00:00, thread_id=01a10ab8-bdf2-7361-8e37-0dcc93c6535c, status=success, usefulness=high)

### keywords

- clbench, sqlite, items_g1, fdbk_g1, avg_rtg, rtg, ref_id, actual_mean, ABS, boundary floating point, exact-value answer, 2715, 2 of 15 queries

## Task 5: Count electronics products >$50 with >=5 reviews and avg review rating <3.0

### rollout_summary_files

- rollout_summaries/2026-10-05T05-53-11-HquC-clbench_q4_electronics_price_reviews_rating_answer_8.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-53-11-01a10a9f-9035-7461-8016-764c7ccd0e4a.jsonl, updated_at=2026-10-05T05:56:10+00:00, thread_id=01a10a9f-9035-7461-8016-764c7ccd0e4a, status=success, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, sqlite_master, items_g2, fdbk_g2, prc_usd, prc, main_cat, avg rating, review count, consolidated verification query, answer 8, 4 of 15 queries

## Task 6: Count office-product reviews in 2022 with price strictly in (20, 200)

### rollout_summary_files

- rollout_summaries/2026-10-05T05-33-54-sC2G-clbench_office_reviews_2022_price_20_200_count_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-33-54-01a10a8d-e6fc-7e61-8a29-0d1ed3c89d5e.jsonl, updated_at=2026-10-05T05:34:56+00:00, thread_id=01a10a8d-e6fc-7e61-8a29-0d1ed3c89d5e, status=fail, usefulness=high)

### keywords

- clbench, sqlite, fdbk_g1, items_g1, prc, main_cat, timestamp precision, mixed epoch, length(ts), sqlite_master, benchmark question, INCORRECT, 8164, price boundaries, 2022

## Task 7: Count office-product reviews dated >= 2031

### rollout_summary_files

- rollout_summaries/2026-10-05T05-21-52-P0KB-clbench_office_reviews_2031_timestamp_count_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-21-52-01a10a82-e3f0-7cf3-8171-c1d42698ad61.jsonl, updated_at=2026-10-05T05:23:34+00:00, thread_id=01a10a82-e3f0-7cf3-8171-c1d42698ad61, status=fail, usefulness=high)

### keywords

- clbench, sqlite, fdbk_g1, items_g1, timestamp precision, unixepoch, millisecond, microsecond, sqlite_master, benchmark question, strftime, year 2031, mixed precision

## Task 8: Median price of non-zero electronics products

### rollout_summary_files

- rollout_summaries/2026-10-05T05-27-13-XSJx-sqlite_median_electronics_price_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T05-27-13-01a10a87-c94a-7d71-bbdb-ce5c5e357ba7.jsonl, updated_at=2026-10-05T05:27:53+00:00, thread_id=01a10a87-c94a-7d71-bbdb-ce5c5e357ba7, status=fail, usefulness=high)

### keywords

- clbench, sqlite, median, electronics, items_g2, prc_usd, prc, ROW_NUMBER, `ERROR: no such column: price`, sqlite_master, category mapping, main_cat, 20.92

## Task 9: Count office products with reviews but absent from attributes

### rollout_summary_files

- rollout_summaries/2026-10-05T07-17-25-yGfc-clbench_q10_office_reviewed_not_in_attrs_count_correct_267.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T07-17-25-01a10aec-ae82-7191-a55c-d19c0a2e47f6.jsonl, updated_at=2026-10-05T07:18:06+00:00, thread_id=01a10aec-ae82-7191-a55c-d19c0a2e47f6, status=success, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, attrs_g1, fdbk_g1, ref_id, NOT EXISTS, reviewed but absent, not represented in attributes at all, unrepresented products, answer 267, 2 of 15 queries

## Task 10: Find year-month with most musical instrument reviews

### rollout_summary_files

- rollout_summaries/2026-10-05T06-53-17-hPnC-clbench_q9_musical_instruments_peak_month_2020_01_correct.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T06-53-17-01a10ad6-93c7-7a33-ae86-6c7a88c487ac.jsonl, updated_at=2026-10-05T06:55:31+00:00, thread_id=01a10ad6-93c7-7a33-ae86-6c7a88c487ac, status=success, usefulness=high)

### keywords

- clbench, CLBENCH_ACTION, fdbk_g3, items_g3, ref_id, Musical Instruments, main_cat, timestamp, epoch, strftime, ts is TEXT, 2020-01, ERROR: no such column: f.item_id, 5 of 15 queries

## Task 50: Band active office products and compute the verified-rating gap across price bands (Q40)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-51-27-EKUv-clbench_q40_office_price_band_verified_gap_incorrect_0_23.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-51-27-01a10b42-c41e-7d00-ab90-553adb0086a7.jsonl, updated_at=2026-10-05T08:57:00+00:00, thread_id=01a10b42-c41e-7d00-ab90-553adb0086a7, status=fail, usefulness=high)

### keywords

- clbench, Q40, items_g1, fdbk_g1, vrf, verified_status, price bands, verified-purchase, AVG rtg, gap 0.23, INCORRECT, 7 of 15 queries, per-item pre-aggregation

## Task 49: Find the broadest electronics taxonomy category with products priced above $200 (Q39)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-47-52-Kavq-clbench_q39_electronics_broadest_category_over_200_computers.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-47-52-01a10b3f-7d30-7d53-8668-00f933bd19f4.jsonl, updated_at=2026-10-05T08:53:35+00:00, thread_id=01a10b3f-7d30-7d53-8668-00f933bd19f4, status=success, usefulness=high)

### keywords

- clbench, Q39, taxn_g2, cat_lvl=1, cat_nm, Computers & Accessories, Camera & Photo, prc_usd, prc, prc_v2, threshold 200, answer Computers & Accessories, 2 of 15 queries

## Task 48: Count instrument brands with no reviews dated 2022 (Q38)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-44-14-80Oo-clbench_q38_instrument_brands_no_2022_reviews_2636_incorrect.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-44-14-01a10b3c-27e4-7771-8127-8c5d43ee40c4.jsonl, updated_at=2026-10-05T08:46:13+00:00, thread_id=01a10b3c-27e4-7771-8127-8c5d43ee40c4, status=fail, usefulness=high)

### keywords

- clbench, Q38, fdbk_g3, review_year, ts TEXT, substr(ts,1,4), 2022, product_attributes_g3, attrs_g3_legacy, NOT EXISTS, correlated timeout, answer 2636, INCORRECT, 4 of 15 queries

## Task 47: Compute percentage of rated positive-price electronics with avg rating >=4.5 (Q37)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-42-47-CpR3-clbench_q37_electronics_rating_4_5_positive_price_36_1_incor.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-42-47-01a10b3a-d364-7dc0-bc68-4af77772057d.jsonl, updated_at=2026-10-05T08:43:50+00:00, thread_id=01a10b3a-d364-7dc0-bc68-4af77772057d, status=fail, usefulness=high)

### keywords

- clbench, Q37, items_g2, fdbk_g2, avg_rtg, AVG(rtg), rating >=4.5, positive price, main_cat LIKE '%Electronics%', answer 36.1, 35.4, 40.9, 54.4, INCORRECT, 1 of 15 queries

## Task 46: Count instrument brands with a review in each of 2019, 2020, and 2021 (Q36)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-39-38-tjc6-clbench_q36_instrument_brands_three_year_review_coverage_inc.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-39-38-01a10b37-f129-7472-b37d-54f14b4773a2.jsonl, updated_at=2026-10-05T08:42:24+00:00, thread_id=01a10b37-f129-7472-b37d-54f14b4773a2, status=fail, usefulness=high)

### keywords

- clbench, Q36, fdbk_g3.review_year, review_year BETWEEN 2019 AND 2021, product_attributes_g3, attrs_g3_legacy, exact brand spelling, case-normalized, answer 749, 761, INCORRECT, 4 of 15 queries

## Task 45: Compute musical top-10 brand review-count rating spread (Q35)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-38-05-jyq3-clbench_q35_musical_brand_rating_spread_0_58.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-38-05-01a10b36-866d-79f3-8a82-ecc3164bd6cf.jsonl, updated_at=2026-10-05T08:39:17+00:00, thread_id=01a10b36-866d-79f3-8a82-ecc3164bd6cf, status=success, usefulness=high)

### keywords

- clbench, Q35, product_attributes_g3, attrs_g3_legacy, fdbk_g3, AVG(rtg), top ten brands, ROW_NUMBER, Pyle, JIM DUNLOP, answer 0.58, 1 of 15 queries

## Task 44: Count active office products with exactly-5.0 average verified rating and at least five verified reviews (Q34)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-36-49-BDRI-clbench_q34_office_active_verified_5_0_avg_incorrect_430.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-36-49-01a10b35-5d7f-7483-a45d-010cad28d0b6.jsonl, updated_at=2026-10-05T08:37:45+00:00, thread_id=01a10b35-5d7f-7483-a45d-010cad28d0b6, status=fail, usefulness=high)

### keywords

- clbench, Q34, items_g1.status='active', fdbk_g1, verified_status='verified', vrf=1, AVG(rtg), exactly 5.0, at least 5 verified reviews, answer 430, 514, 278, INCORRECT, 1 of 15 queries

## Task 43: Count musical products with current brand info but no legacy brand line (Q33)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-35-20-52xI-clbench_q33_musical_current_brand_no_legacy_line_980_incorre.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-35-20-01a10b34-039c-7d80-81ce-e1e55d6e0baa.jsonl, updated_at=2026-10-05T08:36:27+00:00, thread_id=01a10b34-039c-7d80-81ce-e1e55d6e0baa, status=fail, usefulness=high)

### keywords

- clbench, Q33, product_attributes_g3, attrs_g3_legacy, attr_key='Brand', attr_val, current feed, legacy export, no brand line, answer 980, INCORRECT, 1 of 15 queries

## Task 42: Compute electronics mean absolute deviation from overall average list price (Q32)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-33-42-xhWl-clbench_q32_electronics_price_mad_correct.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-33-42-01a10b32-841e-7491-b0b5-f1ed9008818d.jsonl, updated_at=2026-10-05T08:35:00+00:00, thread_id=01a10b32-841e-7491-b0b5-f1ed9008818d, status=success, usefulness=high)

### keywords

- clbench, Q32, items_g2, MAD, mean absolute deviation, list price, prc/100.0, prc_usd, prc_v2, positive prc, answer 116.71, 1 of 15 queries

## Task 41: Compute percentage of verified purchases among archived office reviews (Q31)

### rollout_summary_files

- rollout_summaries/2026-10-05T08-31-44-FHsT-clbench_q31_archived_office_verified_purchases_fail_66_3.md (cwd=/state/work/database, rollout_path=/state/home/.codex/sessions/2026/10/05/rollout-2026-10-05T08-31-44-01a10b30-b63b-7c62-925b-7f60348e5213.jsonl, updated_at=2026-10-05T08:33:22+00:00, thread_id=01a10b30-b63b-7c62-925b-7f60348e5213, status=fail, usefulness=high)

### keywords

- clbench, Q31, items_g1.status='archived', fdbk_g1, verified purchases, verified_status='verified', vrf=1, answer 66.3, 94.8, Mcp error: -32603, instance_complete, 1 of 15 queries

## User preferences

- When answering a benchmark question, read `MEMORY.md` and `skills/clbench-sql-benchmark/SKILL.md` before SQL, then run one consolidated verification query before ANSWER; Q12/Q16/Q17/Q19 each used only 1/15 exploratory queries this way, and Q11 used 3/15. [Task 21][Task 22][Task 24][Task 25][Task 29][Task 30]
- The benchmark format expects the exact requested value in ANSWER with no explanation; memory-first, consolidated-query, minimal-query behavior is the proven default. [Task 21][Task 22][Task 24][Task 25][Task 27][Task 29][Task 30]
- Do not spend ANSWER on one plausible interpretation when wording, category scope, price column, verification flag, or threshold population is ambiguous. Put the candidate interpretations side by side in one consolidated query while budget remains; Q23–Q27 show the one-shot failure, while Q28–Q30 show memory-first consolidated-query solves in 2/15, 4/15, and 6/15. [Task 33][Task 34][Task 35][Task 36][Task 37][Task 38][Task 39]
- When one query produces multiple candidate interpretations, still decide semantically before ANSWER: Q31 submitted the first candidate and failed, Q33 repeated the one-interpretation failure, and the harness locks after `instance_complete=true` (`Mcp error: -32603: HTTPError`). [Task 41][Task 43]

## Reusable knowledge

- For g1 "verified-purchase" wording, `fdbk_g1.vrf=1` and `verified_status='verified'` are not equivalent: vrf=1 includes verified_status=NULL rows (domain pairs `(0,NULL)=7,764`, `(0,'unverified')=17,963`, `(1,NULL)=105,478`, `(1,'verified')=246,267`). Q31 failed at 66.3 via verified_status while vrf=1 gave 94.8; Q40 failed at 0.23 via vrf=1 while verified_status gave 0.22—so map the wording and compare materially different variants before ANSWER. [Task 41][Task 50]
- Q32's CORRECT electronics MAD was `116.71` over 6,570 positive-`prc` rows using `AVG(ABS(prc/100.0 - overall_avg))`. Again use `items_g2.prc/100` for "list price", not `prc_usd` (MAD 50.79) or `prc_v2` (117.69); unlike Q25/Q23, the full positive-price population—not `main_cat`—was correct. [Task 42]
- Q35's CORRECT musical rating spread was `0.58`: use current `product_attributes_g3` brand rows, rank by total feedback review count, take the top 10, and use feedback `AVG(rtg)`; Pyle 4.0577 and JIM DUNLOP 4.6378 were top/bottom. Legacy top-10 differed and was not intended. [Task 45]
- Q36 proves brand counts use raw `attr_val` spelling, not case-normalized dedup: 761 exact/TRIM-spelling instrument brands had coverage in 2019/2020/2021 versus 749 after lowercasing; submitted 749 was INCORRECT. `fdbk_g3.review_year`/`review_month` may be populated and should be used directly when available. [Task 46]
- Q39 validates `taxn_g2.cat_lvl=1` grouped by `cat_nm` for "broadest category label (taxonomy level just below department)"; `Computers & Accessories` won at all three price interpretations (158 `prc_usd>200`, 282 `prc>20000`, 283 `prc_v2>20000`). This wording-specific success contrasts with Q8's failed cat_lvl=1 interpretation. [Task 49]
- A fast multi-variant office shape is per-item pre-aggregation (`GROUP BY i.ref_id` with conditional SUM/COUNT per flag), then `CROSS JOIN` a flags `VALUES` CTE (~3.5s); raw multi-scope UNION over the full items×fdbk join exceeded 10s. [Task 50]
- Known Q34 alternatives: active office exactly-5.0 average with >=5 verified reviews gave 430 via `verified_status` (submitted, INCORRECT), 514 via `vrf=1`, and 278 via both; test whether the wording means average of verified reviews or an average among items with >=5 verified reviews, and whether a status filter is intended. [Task 44]
- Q37's unvalidated alternatives were 35.4 (`main_cat`, `prc_usd>0`), 40.9 (whole `items_g2`, `prc>0`), and 54.4 (feedback-derived rating); submitted 36.1 (stored `avg_rtg`, `main_cat`, `prc>0`) was INCORRECT. Whole-table electronics scope has repeatedly mattered. [Task 47]
- Q38's known-bad 2636 used musical scope + `review_year=2022`; musical scope + `substr(ts,1,4)='2022'` gave 2775, all-product variants gave 3144/3344. `review_year` and `ts`-derived year disagreed substantially (5,251 versus 4,401 distinct musical refs), so resolve the literal date source before answering. [Task 48]
- Office listing dates live in `attrs_g1` under `attr_key='Date First Available'` (18,198 distinct refs of 20,000 items). Values are variable-length text such as `December 1, 2005`; extract the trailing year with `v LIKE '% 19__' OR v LIKE '% 20__'` and `CAST(substr(v,length(v)-3) AS INTEGER)`. `items_g1` has no date column. Q20's verified counts were total 20,000, dated 18,198, before 2015 `5254`, and on-or-after `12944`. [Task 21]
- Q19's one-query pattern grouped `fdbk_g1` joined to `items_g1` by `main_cat`, filtered `i.prc > 50`, and returned `COUNT(f.rtg)`, `AVG(f.rtg)`, `COUNT(DISTINCT i.ref_id)`, and `AVG(i.avg_rtg)`. Office Products used 20,816 reviews across 573 items and full-precision `4.128218677940046` was accepted; stored `avg_rtg` was 4.285, confirming "average review rating" means feedback `AVG(rtg)`. [Task 22]
- Q18's known-bad result is unrounded `AVG(items_g2.prc_usd)` over non-null rows, `52.95666246454459`. The instance had 20,000 items, 6,346 non-NULL prices, 13,654 NULLs, 0 zero prices, and verified `prc=prc_usd*100`; the intended population and/or format remains unresolved. Probe `ROUND(...,2)`, NULL-as-zero versus exclusion, `main_cat` scope, and distinct-item semantics. [Task 23]
- Q17 used review-weighted `AVG(fdbk_g3.rtg)` with a LEFT JOIN, bucketing NULL versus non-zero `prc`: null price 4.166955695450766 over 84,190 reviews, non-zero price 4.2857199312375265 over 202,436; the full-precision difference was about 0.1188 and answer `0.12` was CORRECT. g3 had no zero-price rows. [Task 24]
- Q16's CORRECT one-query result: electronics (`g2`) reviews with `LENGTH(body)>500` and `items_g2.prc_usd<=40` had 2,172 reviews, 222 one-star, and `10.22` percent. No NULL/blank-body exclusion was needed for that wording. [Task 25]
- `fdbk_g1` has 377,472 rows, 19,999 reviewed `ref_id`s, and 358,837 distinct non-null `uid`s; it has indexes on `ref_id`, `rtg`, `ts`, and `vrf` but no `uid` index. Single-pass `GROUP BY f.uid` with `COUNT(DISTINCT i.main_cat)` ran in about 5–6 seconds, while materializing `SELECT DISTINCT uid` pair sets timed out five times at 10 seconds. [Task 26]
- For Q15, `taxn_g1.cat_lvl=0` has only Office Electronics and Office Products, yielding 9 cross-taxonomy reviewers and `0.00` — graded INCORRECT. The likely `items_g1.main_cat` interpretation was 4,620 of 247,484 Office-Products reviewers = `1.87` (or 5,313/355,617 = `1.48` across all main-cat-covered reviewers), but it was never graded. [Task 26]
- Only `attrs_g1` (office) and `attrs_g3` (musical instruments) exist; there is no `attrs_g2`. Discontinued data uses `attr_key='Is Discontinued By Manufacturer'` with noisy casing/values; normalize key and value with `lower()` and treat `yes`/`true` as discontinued. "Catalog average star rating" means stored `items.avg_rtg`. Q14's verified total was 21 (g1=17, g3=4). [Task 27]
- Q13's known-bad interpretation is zero reviews via `NOT EXISTS` on `fdbk_g2.ref_id` plus priced as `prc_usd IS NOT NULL AND <> 0`, yielding `11345/3253 = 28.67`. Before resubmitting, probe `fdbk_stats_gN`, a review-count column, `prc` versus `prc_usd`, NULL-only filtering, `main_cat` scope, and `LEFT JOIN ... IS NULL`. [Task 28]
- Q12's per-length epoch CASE confirmed all linked `fdbk_g2.ts` values in 2021 were 10-digit seconds: Oct 641, Nov 552, Dec 674, total `1867`. Join through `ref_id`, never `item_id`. [Task 29]
- In `attrs_g3`, brand data is under `attr_key='Brand'` (11,643 products, exactly one attr row per product). Join to `items_g3` on `ref_id`, filter `main_cat='Musical Instruments'` when category-scoped, and rank by `COUNT(DISTINCT a.ref_id)`. The verified top brands were Fender 241, Yamaha 143, Ibanez 108, Behringer 71, JIM DUNLOP 68. [Task 30]
- `taxn_g2 (ref_id TEXT, cat_lvl INTEGER, cat_nm TEXT, FK→items_g2.ref_id)` is the taxonomy table; prior memories recorded `items_g2`/`fdbk_g2` but omitted `taxn_g2`. For `cat_nm='Computers & Accessories'`, `cat_lvl=1` has 8089 distinct `ref_id`s, 2447 with non-zero `prc_usd`, and `AVG(prc_usd)=54.925925623212095`. [Task 1]

- `taxn_g2 (ref_id TEXT, cat_lvl INTEGER, cat_nm TEXT, FK→items_g2.ref_id)` is the taxonomy table; prior memories recorded `items_g2`/`fdbk_g2` but omitted `taxn_g2`. For `cat_nm='Computers & Accessories'`, `cat_lvl=1` has 8089 distinct `ref_id`s, 2447 with non-zero `prc_usd`, and `AVG(prc_usd)=54.925925623212095`. [Task 1]
- For Q8, 24.44 (598/2447 distinct non-zero `prc_usd` items above 54.93), computed via `taxn_g2.cat_lvl=1`, was marked INCORRECT. Before reusing that interpretation, probe all-non-zero-electronics average, non-DISTINCT populations, other `cat_lvl` values, zero-price handling, and `main_cat`-based selection. [Task 1]
- Known-good g2 facts re-confirmed: `items_g2` is electronics; `prc` is cents, `prc_usd` is dollars (`prc = prc_usd*100`); discover schema with `SELECT name, sql FROM sqlite_master WHERE type='table'`. [Task 1][Task 5]

- In `fdbk_g2`, `vrf` is TEXT and `vrf='true'` selects verified reviews. For the verified electronics body-length question, 1-star n=6634 averaged 286.3 characters and 5-star n=46717 averaged 184.5; the validated difference was `101.8`. [Task 2]
- For body-length questions, raw `LENGTH(body)` and `LENGTH(TRIM(body))` produced identical rounded averages in the Q7 instance (`whitespace_affected=0`); one consolidated query can compare both as a cheap hedge. [Task 2]
- The prior-memory-first workflow (`MEMORY.md` plus the skill) supplied the `g2=electronics` mapping/schema and answered Q7 in 3/15 queries, with only a targeted `fdbk_g2`/`items_g2` schema dump. [Task 2]
- Office attributes live in `attrs_g1 (ref_id TEXT, attr_key TEXT, attr_val TEXT)`, with `ref_id` as FK to `items_g1.ref_id`. "Not represented in attributes at all" maps to `NOT EXISTS (SELECT 1 FROM attrs_g1 a WHERE a.ref_id = f.ref_id)`; the exact-shape query returned 267 in 2/15 queries. [Task 9]
- `g3` is the musical instruments group: `items_g3` has 17,162 of 20,000 `main_cat='Musical Instruments'` (g1: 19; g2: 85). `fdbk_g3` contains cross-category rows (252,172 musical of 286,626 total), so filter through `items_g3` when wording restricts category; Q9's peak month was `2020-01` in both scopes. [Task 10]
- `fdbk_g3.ts` is TEXT; this instance's convertible values were all length-10 seconds with 3 unconvertible rows. Use the defensive multi-length CASE (already ISO string, then 10/13/16/19 digit epochs) and include the length histogram in one consolidated query. [Task 10]
- In `fdbk_g1`, the two product identifier columns are `item_id` (non-primary, TEXT) and `ref_id` (the declared FK to `items_g1.ref_id`). Verified from sqlite_master. [Task 3]
- For "how many more distinct values" questions, one consolidated query returning `COUNT(DISTINCT a) - COUNT(DISTINCT b)` plus both distinct counts can provide answer and sanity checks in one budgeted query; it solved Q6 in 2/15 queries. [Task 3]
- Consulting `MEMORY.md` and the skill first supplied office schema/rating-source rules and enabled a 2/15-query solve with no schema exploration. [Task 3][Task 4]

- For this benchmark instance, `items_g2` is the electronics dataset even though `main_cat='Electronics'` has 0 rows; only `All Electronics` (4,562 items) and other `%Electronics%` labels exist. Verify group/category mapping from content aggregates, never an exact label or table ordinal. [Task 5][Task 8]
- In `items_g2`, `prc` is cents and `prc_usd` is dollars; the relationship `prc = prc_usd * 100` was verified with 0 mismatches. For dollar-phrased questions, use `prc_usd` — `prc > 50` gave 26 versus the correct 8. [Task 5]
- When a question asks for "average review rating" and both sources exist, compute `AVG(rtg)` from the feedback rows per item: `fdbk_g2` gave answer 8, whereas `items.avg_rtg` gave 3; the feedback aggregate matched the grader. [Task 5]
- When the question explicitly contrasts the "stored average rating" with the "actual mean review score", use `items.avg_rtg` for stored and feedback-derived `AVG(rtg)` for actual; do not replace stored `avg_rtg` with feedback-derived AVG merely because both sources exist. [Task 4]
- Question 5, office products with `|items_g1.avg_rtg − feedback AVG(rtg)| > 1`, was CORRECT at `2715` with: `WITH actual AS (SELECT ref_id, AVG(rtg) AS actual_mean FROM fdbk_g1 WHERE rtg IS NOT NULL GROUP BY ref_id) SELECT COUNT(*) FROM items_g1 i JOIN actual a ON i.ref_id=a.ref_id WHERE i.avg_rtg IS NOT NULL AND ABS(i.avg_rtg-a.actual_mean)>1`. [Task 4]
- For exact-count threshold questions, submit the count from the plain, direct predicate (`ABS(diff)>1`). Diagnostic aggregation with epsilon `>1.000000001` returned 2,711 while the direct plain predicate returned the correct 2,715; 333 rows sit within ±1e-6 of the boundary. Use diagnostics to understand data, not as the submitted number. [Task 4]
- Efficient 4-query aggregate workflow: schema dump from `sqlite_master`; one UNION-ALL per group joining items to per-`ref_id` feedback `COUNT/AVG`, grouped by `main_cat`; targeted narrowing probe on the candidate group; then one wide semantic/unit verification covering price, rating, null handling, and candidate answers. [Task 5]
- clbench product DB schema: three anonymized groups — g1 is office products (`items_g1.main_cat = 'Office Products'`, 13,933 items); g2 and g3 are described as electronics and musical instruments respectively. Review tables are `fdbk_g1/g2/g3`; supporting tables are `attrs_gN`, `taxn_gN`, and `fdbk_stats_gN`. The office mapping was verified, but an attempted electronics run never validated that its target was the correct table/category before answering. [Task 7][Task 8]
- Verified `fdbk_g3(id INTEGER PK, ref_id TEXT FK->items_g3(ref_id), uid, rtg REAL, ttl, body, ts TEXT, hlp_ct INTEGER, vrf INTEGER)` and `items_g3(ref_id TEXT PK, ttl, avg_rtg REAL, rtg_ct INTEGER, prc REAL, str_nm, main_cat, desc_txt)`. Join feedback to items on `ref_id`, never `item_id`. [Task 10]
- In the benchmark DB, `fdbk_g1.ts` is INTEGER and has mixed precision: 13-digit rows (377,414 rows; dates 2001–2023 when interpreted as milliseconds) and 15-digit rows (58 rows; dated 1999–2001 when interpreted as microseconds, an unverified assumption). `fdbk_g2.ts` is INTEGER and `fdbk_g3.ts` is TEXT. [Task 7]
- `datetime(ts,'unixepoch')` returns NULL for large millisecond/microsecond epoch integers; divide by the appropriate power of 1,000 before conversion. [Task 7]
- Start unfamiliar-schema discovery with `SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name;`; identify product groups through `main_cat`, then inspect `length(ts)` distributions with `COUNT`, `MIN`, and `MAX`. For item questions, map every table/category pair and inspect discriminating columns before calculating. [Task 7][Task 8]
- Verified `items_g2` schema: `ref_id TEXT PRIMARY KEY, ttl TEXT, avg_rtg REAL, prc INTEGER, prc_usd REAL, str_nm TEXT, main_cat TEXT, feat_lst TEXT, img_ct INTEGER`; column names are abbreviated and `price` does not exist. [Task 8]
- `items_g1.avg_rtg` had no NULLs among feedback-joined rows; 19,999 office items have feedback rows; stored-versus-actual rating diffs range 0–4 stars. [Task 4]
- Verified `items_g1` schema: `ref_id TEXT PRIMARY KEY, ttl TEXT, avg_rtg REAL, avg_rtg_30d REAL, rtg_ct INTEGER, prc REAL, str_nm TEXT, main_cat TEXT, desc_txt TEXT, feat_lst TEXT`; g1 has no `prc_usd` — only `items_g2` does. `fdbk_g1` joins `items_g1` on `ref_id`. [Task 4][Task 5]
- For calendar-year 2022, the epoch bounds are `1640995200..1672531199` (UTC). [Task 6]
- Known-bad result: the office-product 2022 count using `items_g1.prc > 20 AND prc < 200` and the mixed-epoch CASE returned `8164`; that exact answer was graded INCORRECT. [Task 6]
- For an odd/even-safe SQLite median, filter nulls and zeros as appropriate, use `ROW_NUMBER() OVER (ORDER BY price)`, count rows, then `ROUND(AVG(price),2)` over `rn IN ((n+1)/2, (n+2)/2)`. The pattern executed successfully; its specific 20.92 result was marked INCORRECT because the target/category selection was not verified. [Task 8]
- Benchmark harness rules: submit an exact-value ANSWER, a 15-query cap applies to exploratory QUERY calls, each QUERY call consumes budget, results are capped at 50 rows, and grading gives only INCORRECT/CORRECT without diagnosis. The timestamp attempt used 6 queries; the median attempt used 3. [Task 7][Task 8]
- Q30's CORRECT answer was `1.1`: on `items_g1.status='active'` rows with non-blank bodies, `fdbk_g1.verified_status IS NULL` average length 182.0433 minus labeled average 180.9509. `verified_status` domain is NULL 106,215, `unverified` 17,111, `verified` 230,781; `vrf INTEGER` is separate. Raw, trimmed, and blank-as-missing length variants all gave 1.0924. [Task 31]
- Q29 proved that "archived/no-longer-offered" maps first to `items_g1.status='archived'`, not `attrs_g1` discontinued data: 6,912 of 113,242 `verified_status IS NULL` reviews = `6.1` CORRECT, versus 2,213 (1.9%) via discontinued attrs. `items_g1.status` domain was active 106,330 and archived 6,912. [Task 32]
- This instance's musical attribute tables are `product_attributes_g3(ref_id, attr_key, attr_val)` and `attrs_g3_legacy(ref_id, attr_key, attr_val)`; prior memory's plain `attrs_g3` did not exist. Q28's CORRECT ratio was total-row current 202,543 / legacy 182,566 = `1.11` (distinct products 19,692/17,723; musical-scoped lines 174,037/156,790). [Task 33]
- Q27's known-bad interpretation grouped `items_g2` by `ref_id`, counted `fdbk_g2.ref_id>=3`, filtered `prc_usd>60`, and produced 324/3,250 = `10.0`. Probe `COUNT(DISTINCT f.uid)`, `prc`/`prc>6000`, `main_cat LIKE '%Electronics%'`, and duplicate/hidden feedback semantics. [Task 34]
- `fdbk_g1.vrf` is integer-encoded 1/0, not `true`/`false`; copying the g2 literal made all verified counts zero. For office `prc>20`, only-unverified item counts were 65 explicit-discontinued `no`, 88 across all non-discontinued variants including no-attr/false, 2 `yes`, and 0 `false`; Q26's submitted 86 was INCORRECT and the intended "active"/zero-review population remains unresolved. [Task 35]
- Q25's known-bad 52.94 averaged `items_g2.prc_usd` over all 14,954 `img_ct>=3` rows, spanning `AMAZON FASHION`..`Video Games`; only 3,646 matched `main_cat LIKE '%Electronics%'`. Table membership does not establish category scope. [Task 36]
- Q24's known-bad Yamaha answer used all-product count for the >=50 threshold but priced-only average. This instance had no `attrs_g3`; it had `attrs_g3_legacy` and `product_attributes_g3`. Yamaha had 131 total/37 priced (legacy) or 143/42 (current), while current Fender had 243 total/71 priced and avg 362.20, making Fender the likely intended answer under a priced-products reading. [Task 37]
- Q23's known-bad candidate 1,370 came from `items_g2.prc_usd>0`, mean 52.95666246454459, and `>=1.15*mean` (strict also 1,370). Reuse of Q18's unresolved population is the failure; probe NULL-as-zero, `prc` versus `prc_usd`, `main_cat`/taxonomy scope, and distinct-ref semantics. [Task 38]
- Q22's known-bad 10.3 used 75,572 musical reviews with NULL/empty `fdbk_g3.ts`, 7,784 above nonzero avg `items_g3.prc` 132.34761019812626. Probe convertible/full date-time validation, another timestamp field, missing rows, zero-price inclusion, taxonomy population, and distinct-item averages. Per-ref grouped conditional SUM ran ~3.7s; wide correlated CTE timed out. [Task 39] [ad-hoc note]
- Q21's CORRECT median was `21.99` = median(`items_g2.prc`)/100 where `img_ct>0 AND prc>0` (6,568 rows). `prc_usd` median was 20.95 over 6,344 rows; `prc_v2` median/100 was 22.09 and its semantics are unclear. `prc=prc_usd*100` had zero mismatches; `prc_v2 != prc_usd*100` for 1,261 rows. [Task 40]
- Related skill: skills/clbench-sql-benchmark/SKILL.md

## Failures and how to do differently

- Q31: submitted `verified_status='verified'` (66.3) after one query even though vrf=1 gave 94.8 -> semantic mapping should precede candidate order -> after `instance_complete=true`, queries and corrected ANSWER fail with `Mcp error: -32603: HTTPError`; never assume the first candidate is intended. [Task 41]
- Q33: submitted 980 after one query despite 14 unused -> unprobed table/population variants (any brand row vs nonempty value, current-feed table choice, category scope, empty legacy rows) -> for current-vs-legacy attribute questions, verify each phrase's physical table and compute count variants side by side before ANSWER. [Task 43]
- Q34: submitted 430 immediately after a good multi-variant query -> "average verified review rating ... with at least 5 verified reviews" can combine populations (filter count and average source independently) -> keep budget to disambiguate population and average source before answering. [Task 44]
- Q36: computed 761 exact-spelling versus 749 lowercase and chose 749 -> benchmark grouped brands by raw spelling -> prefer exact/TRIM brand counts unless wording explicitly says to treat spellings as the same brand. [Task 46]
- Q37/Q38: one or four strong candidates were insufficient because answer semantics remained ambiguous -> use remaining budget to resolve whole-table vs `main_cat` electronics scope, stored vs feedback rating, and `review_year` vs raw `ts` before ANSWER. [Task 47][Task 48]
- Q40: correlated-style wide aggregation exceeded 10s; after rewrite, chose vrf=1 and failed at 0.23 -> use per-item pre-aggregation for speed and map "verified-purchase" to `verified_status='verified'` unless evidence favors vrf, with 0.22 as the leading untested office price-band gap. [Task 50]
- Q18: submitted a full-precision average after one query and benchmark replied "Question 18: INCORRECT. Your answer: 52.95666246454459. Exploratory queries used: 1" -> unit and zero checks do not validate population/format -> when an average has many NULLs or ambiguous exact formatting, use leftover budget to probe rounding, NULL-as-zero versus exclusion, category scope, and rows versus distinct items before ANSWER. [Task 23]
- Q23–Q27 one-shot failures -> reused a plausible population/column/flag/price interpretation even though a prior one was unresolved or the query's own diagnostic showed off-category rows -> compute every candidate in one side-by-side query, inspect its row/category diagnostics, and reserve budget to recompute before ANSWER. [Task 34][Task 35][Task 36][Task 37][Task 38]
- Q24/Q28: `ERROR: no such table: attrs_g3` and earlier attr-column assumptions -> schema drift between benchmark instances -> run compact `sqlite_master` discovery before trusting exact supporting-table names, and verify `attr_val`, `status`, `verified_status`, `prc_v2`, and other new columns with `PRAGMA table_info`. [Task 31][Task 33][Task 37]
- Q21: `ERROR: You can only execute one statement at a time` still consumed budget -> CLBENCH_ACTION QUERY accepts exactly one statement -> never append PRAGMA or second SELECT to a QUERY call; fold needed diagnostics into one CTE/statement. [Task 40]
- Q21: `ERROR: no such column: img_ct` despite the column existing -> outer query referenced a column omitted from the CTE SELECT list -> check the CTE projection before concluding schema drift. [Task 40]
- Q22: `ERROR: wrong number of arguments to function GLOB()` -> used function-call syntax -> write the binary operator form `expr GLOB pattern`; use the grouped single-pass feedback shape to avoid 10-second timeouts. [Task 39]
- Q26: copied `fdbk_g2.vrf='true'` to `fdbk_g1` and got 0 verified counts -> verification flag encodings differ by group -> run `GROUP BY vrf` or encode every observed domain variant in the first consolidated query. [Task 35]
- Q15: submitted the degenerate taxonomy interpretation `0.00` after 14/15 queries, including five timeouts, while `1.87` was already computed under the likely `main_cat` interpretation -> expensive `uid`-DISTINCT materialization and late interpretation testing consumed the budget -> avoid `SELECT DISTINCT uid` materialization in this DB, compute reviewer spans with single-pass `GROUP BY f.uid`, and reserve 1–2 queries for alternate interpretations. When one interpretation gives 0.00 and another a small nonzero percentage, do not default to 0.00. [Task 26]
- Q13: submitted `28.67` after one interpretation with 14 queries unused, repeating the Q8 population/percentage failure -> benchmark population and zero/NULL semantics can differ from the obvious query -> for percentage/population questions, probe alternate review-count sources, price columns/filters, category scopes, and join-existence variants before ANSWER. [Task 28]
- Q14: first query hit `ERROR: no such table: attrs_g2` -> assumed the attrs table existed for every group -> check `sqlite_master`/memory before a cross-dataset UNION. [Task 27]
- Q20: two queries were wasted on UNION branches with mismatched column counts and a CTE aliasing error (`no such column: ref_id`) -> consolidated queries can waste budget silently on SQL shape mistakes -> check column counts/aliases and use `SELECT a.ref_id AS rid` inside the CTE before spending budget. [Task 21]

- Q8 symptom: submitted 24.44 after 3 queries with no wide semantic verification, despite 12 queries remaining -> cause: skipped the skill's schema → aggregate → narrow → wide-verification shape at the interpretation step -> fix: for taxonomy/category-level questions, resolve population ambiguity (dedup vs not, which `cat_lvl`, scope of average, zero-price handling) with extra probes before spending ANSWER; exact-match scoring punishes one wrong interpretation. [Task 1]

- Symptom: submitted `0` and benchmark replied "Question 1: INCORRECT. Your answer: 0. Exploratory queries used: 6." Cause: the epoch-unit interpretation was flawed somewhere despite min/max probes. Fix: before answering "count rows with date >= X" on an unfamiliar epoch column, compute a full per-year histogram under the chosen interpretation and test s/ms/µs/ns for domain plausibility. [Task 7]
- Do not submit 0 from a single-unit interpretation. Apply a per-row `CASE` on `length(ts)` in the final count, not merely in min/max probes, and consider that the short 58-row minority-precision bucket may use a different epoch than assumed. [Task 7]
- Precise per-row shape to adapt: convert each bucket by `length(ts)`, verify the resulting date-range and year-count distribution, and only then apply the `>= 2031` predicate. Avoid a uniform `strftime('%Y', ts/1000, 'unixepoch')` conversion when mixed lengths are present. [Task 7]
- Symptom: `ERROR: no such column: price` wasted query 1/15. Cause: guessed an unabbreviated column on `items_g2`. Fix: run `PRAGMA table_info` or read `sqlite_master.sql` before the first data query; this benchmark uses `prc`, `prc_usd`, `ttl`, and `avg_rtg`. [Task 7]
- Symptom: `ERROR: no such column: f.item_id` in a `fdbk_g3` join wasted one query. Cause: assumed an `item_id` join instead of checking DDL. Fix: use `fdbk_gN.ref_id` (FK to `items_gN.ref_id`) directly, or dump the relevant `CREATE TABLE` statements before writing the join. [Task 10]
- Symptom: submitted `20.92` and benchmark replied "Question 2: INCORRECT. Your answer: 20.92. Exploratory queries used: 3." Cause: the run computed from `items_g2.prc_usd` without verifying the electronics table/category mapping or choosing between `prc` and `prc_usd`. Fix: first list and inspect tables, confirm category discrimination through `main_cat` or related evidence, and identify the intended dollar column before spending budget on the final calculation. [Task 8]
- Symptom: submitted `8164` after only 2 of 15 queries and benchmark replied "Question 3: INCORRECT. Your answer: 8164. Exploratory queries used: 2." Cause: the run trusted the stored mixed-epoch CASE without running the required `length(ts)` histogram/year verification and did not independently re-test price-column semantics. Fix: reserve 1–2 queries for `SELECT LENGTH(ts), COUNT(*), MIN(ts), MAX(ts) FROM fdbk_g1 GROUP BY LENGTH(ts);` plus a year histogram, then re-verify the boundary predicate and price column before the final count. [Task 6]
