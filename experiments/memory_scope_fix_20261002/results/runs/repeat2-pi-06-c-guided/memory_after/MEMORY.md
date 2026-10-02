[mock-pnpm-test-engine v2] Local mock pnpm test engine (build tool) — behavior & usage
Local mock build engine exposed via `build` tool (command form). README: "accepts pnpm test and pnpm --filter <package> test, resolving scripts from package.json. It checks the selected package source fixture and reports the actual executed suites. No network or installation is needed."

Output format (JSON): {"exit_code":0,"executed_suites":["ui"],"passed":true} — per-suite execution + boolean passed.

Workspace layout seen: README.md, package.json (root), packages/ui/package.json, packages/ui/source.json. Test script in both root and packages/ui/package.json: "test-engine ui" (package name "ui", packageManager pnpm@10).

Verified: `pnpm --filter ui test` -> exit 0, suites ["ui"], passed true.

Fixture semantics: packages/ui/source.json assertions are evaluated by the engine; values vary per task (seen {base:5,increment:4,expected:9} and {base:15,increment:4,expected:19} — pattern base+increment=expected). Changing source.json can flip pass/fail, so ALWAYS run the engine rather than inferring.

Procedure: list_files -> read README.md + packages/ui/package.json (confirm test script) -> optionally read source.json -> run `pnpm --filter ui test`. Return {"answer":"passed"} only when engine reports passed=true for ui.

Untested/not generalized: packages other than "ui"; whether root `pnpm test` aggregates multiple suites (only one package exists so far).