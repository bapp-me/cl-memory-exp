[local-api-ledger-workflow v2] Local mock API tasks (ledger) — workflow
Task pattern: "Using the local ledger API, compute X over all items, return JSON {answer}".

Workflow:
1. list_files -> usually only api.json. read_file api.json for service docs (endpoints, pagination rules). ALWAYS re-read api.json per task: pagination scheme is VERSION-DEPENDENT.
2. GET /info returns service metadata only (version + documentation filename).
3. GET /items is paginated (limit max 3). Terminator/param scheme depends on version:
   - v1: PAGE-based. params: page (1-based), limit. Response {items:[{id,amount,active}], total, next_page}. Loop until next_page is null. (Observed: total=8 across 3 pages.)
   - v2: CURSOR-based. params: limit, cursor. Response {items, total, next_cursor}. `page` is IGNORED. Start with no cursor; then pass cursor=<next_cursor> from the previous response; loop until next_cursor is null. (Observed: total=8 across 3 pages.)
   In BOTH: ALWAYS loop until the null terminator; don't trust a single page.
4. Filter by the requested predicate (e.g. active==true) then aggregate (sum amounts). Verify arithmetic.

Gotchas:
- Unknown/extra query params (e.g. ledger=2) are silently ignored and return the same first page — no multi-ledger concept; "current ledger" is just flavor.
- Requesting a page/cursor past the end returns {items:[], next_<page|cursor>:null}.
- Item ids have a ledger prefix (item-3-N in v2; item-1-N in v1) but that alone doesn't imply selectable ledgers.
- Compute carefully; verify arithmetic.

Examples:
- v2 observed: ids item-3-1..8 amounts 10,17,24,31,38,45,52,59; inactive 24,45 -> active sum 207 -> {"answer":207}.
- v1 example: 8 items, active amounts 8,15,29,36,50,57 (inactive 22,43) -> sum 195 -> {"answer":195}.