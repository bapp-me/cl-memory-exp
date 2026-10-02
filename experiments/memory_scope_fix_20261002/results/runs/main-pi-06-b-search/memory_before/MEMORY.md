[mock-pnpm-test-engine v1] Mock pnpm test engine: running package tests
Task type: run tests for a package in a mock pnpm engine workspace and report actual result.

Workspace layout (typical):
- README.md (engine docs)
- package.json (root)
- packages/<name>/package.json (has scripts.test)
- packages/<name>/source.json (fixture: e.g. base/increment/expected)

Tool `build`: runs a command in local mock pnpm test engine; fixture assertions actually evaluated. Available command forms (from README): `pnpm test` and `pnpm --filter <package> test`. It resolves scripts from package.json. No network/install needed.

build returns JSON: {"exit_code":N,"executed_suites":[...],"passed":bool}.
- passed:true / exit_code:0 => suite passed.
- Report the ACTUAL result from executed_suites; don't assume.

Workflow:
1. list_files, read README.md to confirm command forms.
2. read package.json files (root + packages/<name>) and source.json fixture.
3. Run `pnpm --filter <name> test` (and optionally `pnpm test`).
4. Return requested JSON based on actual passed value.

Note: `pnpm --filter ui test` and `pnpm test` both executed suite "ui" and returned passed:true. Output {"answer":"passed"} when parsed result shows the target package passed.