[sqlite-workspace-revenue-vip-tags v1] SQLite workspace tasks: VIP/membership tag revenue queries
Workspace pattern (seen in "total order revenue from customers with vip tag" task):
- Workspace often contains only schema.md describing rules + a SQLite DB exposed via `sql` tool. Read schema.md first; it defines semantics (e.g. "tags starting with vip- qualify"; "each order contributes amount once").
- Discover tables/schema: `SELECT name,type FROM sqlite_master WHERE type IN ('table','view')` then `SELECT sql FROM sqlite_master WHERE name IN (...)`. Then `SELECT * FROM t LIMIT 50` to eyeball rows.

Key trap: customer_tags is MANY-TO-MANY (PK customer_id,tag). A customer may hold >1 qualifying tag. Never JOIN orders directly to tags for aggregation — duplicate rows inflate the sum. Instead:
  SELECT SUM(o.amount_usd) FROM orders o
  WHERE o.customer_id IN (SELECT DISTINCT customer_id FROM customer_tags WHERE tag LIKE 'vip-%');
The DISTINCT + IN subquery ensures each order counted once.

General reusable advice:
- "At least one tag" => EXISTS / IN(DISTINCT...) / LIKE prefix, and dedupe the qualifying-customer set.
- "Each order contributes once" is a hint to guard against join fan-out.
- Cross-check the SQL total against a manual sum of matched rows when dataset is small.
- Return exactly the requested JSON shape, e.g. {"answer": 356} (number).

[vip-segment-order-revenue v1] VIP segment order revenue query
Task: total order revenue from customers with >=1 'vip-' tag.
Schema: orders(id, customer_id, amount_usd); customer_tags(customer_id, tag). Tags starting with "vip-" qualify (LIKE 'vip-%').
Key: use DISTINCT/IN-subquery so each order counts once (avoid join fanout when a customer has multiple vip tags). Amounts numeric USD.
Query: SELECT SUM(amount_usd) FROM orders WHERE customer_id IN (SELECT DISTINCT customer_id FROM customer_tags WHERE tag LIKE 'vip-%');
Result for sample data: 361.