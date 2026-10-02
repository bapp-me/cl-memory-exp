[local-api-ledger-workflow v2] Local mock API tasks (ledger) — workflow
Task pattern: "Using the local ledger API, compute X over all items, return JSON {answer}".

Workflow:
1. list_files -> usually only api.json. read_file api.json for service docs (endpoints, pagination rules).
2. GET /info returns service metadata only (version + documentation filename).
3. GET /items is paginated. Pagination style varies by version — READ api.json each time:
   - v2 (observed): docs say "limit (max 3); cursor token and next_cursor, null ends the list. page is ignored." Use params {"limit":3} first, then {"limit":3,"cursor":<next_cursor>} (token like "pos:3"). Loop until next_cursor is null.
   - v1 (observed): page-based, params page (1-based), limit (max 3), response {items,total,next_page}; next_page null ends.
   Response items: {id, amount, active}. total is given (e.g. 8 items across 3 pages).
4. ALWAYS loop all pages until the end token is null; don't trust a single page.
5. Filter by predicate (e.g. active==true) then aggregate (sum amounts). Cross-check: sum(all) - sum(excluded) .

Gotchas:
- Unknown/extra query params (e.g. ledger=2 or wrong cursor param name) are silently ignored -> returns same first page. No multi-ledger concept; "current ledger" is flavor. Item ids carry a ledger prefix (item-3-N) but that alone doesn't imply selectable ledgers.
- Requesting a page/offset past the end returns empty items + null end token.
- Compute carefully; verify arithmetic.

Examples: v2: 8 items, active amounts 10,17,31,38,52,59 (inactive 24,45) -> 207 -> {"answer":207}. v1: active 8,15,29,36,50,57 -> 195.