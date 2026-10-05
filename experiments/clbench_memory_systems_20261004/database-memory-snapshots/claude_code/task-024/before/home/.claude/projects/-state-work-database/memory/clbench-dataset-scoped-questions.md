---
name: clbench-dataset-scoped-questions
description: "Questions naming a dataset's category (\"office products\", \"electronics\", \"musical instruments\") count the WHOLE dataset group, not a main_cat filter"
metadata:
  node_type: memory
  type: project
  originSessionId: 1691ab15-ff13-49b9-ae60-fbb27adf566d
  modified: 2026-10-04T19:02:37.337Z
---

In CLBENCH product-DB instances, when a question uses the category name of one of the three datasets (office/electronics/musical), the gold counts ALL items in that dataset's tables — do NOT filter `items.main_cat = 'Office Products'`. Verified Q20 (2026-10-04): "office products with listing date before 2015" → whole-g1 answer 5254 was CORRECT; main_cat-filtered would have been 3783, taxn lvl0-filtered 4885.

**Why:** the three table groups are per-category Amazon review corpora; `main_cat` inside a corpus is noisy Amazon metadata (non-'Office Products' rows were still real office items: toner, printers, calculators). The prompt's hint "determine which tables belong to which product category" signals dataset-scoped reading.

**How to apply:** identify the group (taxn cat_lvl=0 fused with dominant main_cat per [[clbench-schema-conventions]]), then count over the group's items table only. Contrast with [[clbench-spanning-categories]]: per-ITEM category semantics (e.g. "spanning N categories") still use items.main_cat.
