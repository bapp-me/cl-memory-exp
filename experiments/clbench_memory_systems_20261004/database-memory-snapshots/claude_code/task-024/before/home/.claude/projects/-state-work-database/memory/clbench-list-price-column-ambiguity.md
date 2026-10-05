---
name: clbench-list-price-column-ambiguity
description: "CLBENCH: 'list price' questions are WRONG with prc when items_g2 also has prc_v2 — compute the metric under EVERY price column in one query before answering"
metadata:
  node_type: memory
  type: reference
  originSessionId: bc751919-efeb-4633-b517-d428ff68992c
  modified: 2026-10-04T19:15:20.737Z
---

Q23 (2026-10-04, electronics instance): "How many electronics products have a list price at least 15% higher than the mean list price across all electronics with a positive list price?" I answered the `prc` reading — **1035, marked INCORRECT** (5 queries).

That instance's `items_g2` had THREE price columns (earlier instances had only two — see [[clbench-schema-conventions]]):
- `prc` INTEGER cents — 6570 non-null, 0 nonpositive, 13430 NULL; mean(prc>0) = 9623.34¢, 1.15× threshold = 11066.85, count ≥ = **1035** (no boundary ties: nearest rows 11049 / 11091, so strict vs ≥ and float noise are irrelevant). ← the WRONG answer
- `prc_usd` REAL — exactly `prc/100` on all 6346 overlapping rows; NULL exactly when prc ≥ 50000¢. Its reading (mean over its own 6346 positive rows) = **1370**.
- `prc_v2` INTEGER — non-null on exactly the same 6570 rows as `prc`, ≈ **1.0102× `prc`** on average. Its reading was **NOT COMPUTED** — that was the regret.

**Why:** `prc_v2`'s profile fits "list price" semantics (same coverage as the real price, values ~1% higher = list ≥ selling). The question generator appears to bind the phrase "list price" to a per-instance column, and when a `prc_v2` exists it is the likely target; `prc` is only the safe default when `prc_v2` is absent (Q21 instance, "median list price in dollars", `prc`/100 = CORRECT, no prc_v2 recorded there).

**How to apply:** if `items_g2` (or any group) carries more than one price column AND the question says "list price", compute the answer under EVERY price column in a single UNION ALL query before answering — never burn the answer on the `prc` reading alone. Rank: (1) a column that is row-wise ≥ the base price (v2-style, list-price semantics); (2) `prc` (canonical, complete); (3) `prc_usd` (partial unit-variant — its smaller population shifts means). Remaining untested alternatives for Q23 if seen again: main_cat-filtered population ('All Electronics' only), and COALESCE(NULL→0) denominators — both lower probability than the prc_v2/prc_usd bindings.
