[sqlite-order-revenue-procedure v1] SQLite local-workspace order analysis procedure
Task type: local workspace with schema.md + read-only SQLite; answer with JSON {"answer": number}.

Observed environment (single run, no version recorded): tools = list_files, read_file, sql (read-only SQLite, max 50 rows/result, sqlite_master & PRAGMA available), experience. Schema docs live in schema.md (read via read_file).

Observed schema: orders(id INTEGER PRIMARY KEY, customer_id INTEGER, amount_usd REAL); customer_tags(customer_id INTEGER, tag TEXT, PRIMARY KEY(customer_id,tag)). amount is USD.

Procedure that worked:
1) list_files -> read schema.md for semantic rules (e.g. which tags qualify).
2) sql: SELECT sql FROM sqlite_master WHERE name IN (...tables...) for DDL/constraints; also SELECT name,type FROM sqlite_master WHERE type IN ('table','view').
3) SELECT * ... LIMIT 50 to eyeball rows (mind 50-row cap; paginate/aggregate if more).
4) Compute in one aggregate, e.g. SELECT SUM(o.amount_usd) FROM orders o WHERE o.customer_id IN (SELECT DISTINCT customer_id FROM customer_tags WHERE tag LIKE 'vip-%').

Key correctness note: use DISTINCT (or EXISTS) on the tag-filtered subquery when a customer can hold multiple qualifying tags, so each order/amount counts once (PK allows multiple tags per customer). "at least one" = membership test, not a per-tag join.

Remains untested: larger/multi-file datasets, non-SQLite sources, LIMIT truncation, other prefix rules, NULLs/negative amounts, currency conversion.
Cheap applicability check: read schema.md, then SELECT name,type FROM sqlite_master WHERE type IN ('table','view'); if orders & customer_tags with same columns exist, procedure applies.