[local-api-ledger-workflow v2] Local mock API tasks (ledger) — workflow
Task pattern: "Using the local ledger API, compute X over all items, return JSON {answer}".

Workflow:
1. list_files -> usually only api.json. read_file api.json for service docs (endpoints, pagination rules).
2. GET /info returns service metadata only (version + documentation filename).
3. GET /items is paginated. Pagination scheme VARIES BY VERSION — read api.json each time:
   - v2 (current): cursor-based; use `next_cursor` token, pass back as `cursor` param; `page` is ignored. limit max 3. next_cursor null ends the list.
   - v1: page-based (page 1-based, limit max 3), use next_page.
4. ALWAYS loop until the end token is null; don't trust a single page.
5. Filter by the requested predicate (e.g. active==true) then aggregate (sum amounts).

Gotchas:
- Unknown/extra query params (e.g. ledger=2) are silently ignored and return the same first page — no multi-ledger concept; "current ledger" is just flavor.
- Requesting past the end returns {items:[], next_cursor:null}.
- Item ids have a ledger prefix (item-3-N) that alone doesn't imply selectable ledgers.
- Verify arithmetic.

Examples: v1: 8 items, active amounts 8,15,29,36,50,57 (inactive 22,43) -> 195. v2: 8 items, active amounts 10,17,31,38,52,59 (inactive 24,45) -> 207.