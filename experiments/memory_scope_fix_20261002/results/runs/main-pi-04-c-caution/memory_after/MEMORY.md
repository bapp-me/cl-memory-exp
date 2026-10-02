[local-api-ledger-workflow v2] Local mock API tasks (ledger) — workflow
Task pattern: "Using the local ledger API, compute X over all items, return JSON {answer}".

Workflow:
1. list_files -> usually only api.json. read_file api.json for service docs (endpoints, pagination rules). ALSO GET /info: it reports the live version/documentation, which may differ from stored habits.
2. Pagination varies by version:
   - v2 (current): GET /items params limit (max 3) and cursor (opaque token). Response {items:[{id,amount,active}], total, next_cursor}. Pass next_cursor from prior response as cursor; next_cursor null ends list. "page" is IGNORED in v2.
   - v1 (older): page (1-based) + limit; response had next_page.
3. ALWAYS loop until the end token is null; don't trust one page. Observed total=8 across 3 calls (limit 3).
4. Filter by predicate (e.g. active==true) then aggregate (sum amounts).

Gotchas:
- Unknown/extra query params (e.g. ledger=2) are silently ignored and return the same first page — "current ledger" is flavor; no multi-ledger selection. Item id prefix (item-3-N) is not a selectable ledger.
- Requesting a page past the end returns empty items + null token.
- Compute carefully; verify arithmetic.

Example (v2 run): items amounts 10,17,24,31,38,45,52,59; inactive 24,45; active sum = 10+17+31+38+52+59 = 207 -> {"answer":207}.