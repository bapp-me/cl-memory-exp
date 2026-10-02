[local-api-ledger-workflow v1] Local mock API tasks (ledger) — workflow
Task pattern: "Using the local ledger API, compute X over all items, return JSON {answer}".

Workflow:
1. list_files -> usually only api.json. read_file api.json for service docs (endpoints, pagination rules).
2. GET /info returns service metadata only (version + documentation filename).
3. GET /items is paginated: params page (1-based), limit (max 3). Response: {items:[{id,amount,active}], total, next_page}. next_page null means end. ALWAYS loop pages until next_page is null; don't trust a single page. Here total=8 items across 3 pages (limit cap 3).
4. Filter by the requested predicate (e.g. active==true) then aggregate (sum amounts).

Gotchas:
- Unknown/extra query params (e.g. ledger=2) are silently ignored and return the same first page — no multi-ledger concept; "current ledger" is just flavor.
- Requesting a page past the end returns {items:[], next_page:null}.
- Item ids have a ledger prefix (item-1-N) but that alone doesn't imply selectable ledgers.
- Compute carefully; verify arithmetic.

Example: 8 items, active amounts 8,15,29,36,50,57 (inactive 22,43) -> sum 195 -> {"answer":195}.