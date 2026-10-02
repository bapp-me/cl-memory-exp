[mock-pnpm-test-engine v1] Local mock pnpm test engine (build tool) — behavior & usage
Environment: isolated workspace with a "Local mock build engine" exposed via the `build` tool (command form), described in README.md as: "accepts pnpm test and pnpm --filter <package> test, resolving scripts from package.json. It checks the selected package source fixture and reports the actual executed suites. No network or installation is needed." Version observed: task timestamp 1790914536, packageManager pnpm@10 (root package.json).

Observed workspace layout: README.md, package.json (root), packages/ui/package.json, packages/ui/source.json.

Observed command output format (JSON): {"exit_code": 0, "executed_suites": ["ui"], "passed": true}. So the engine reports per-suite execution and a boolean `passed`.

Applicability check (cheap): `list_files` then `read_file README.md` and the target package's package.json to confirm the test script exists before running.

Commands verified: `pnpm --filter ui test` and root `pnpm test` both returned exit_code 0, executed_suites ["ui"], passed true. Script in both root and packages/ui/package.json was "test-engine ui".

Fixture semantics: packages/ui/source.json = {base:5, increment:4, expected:9}; fixture assertions are evaluated against this file, so changing source.json could change pass/fail (untested here).

Untested / not generalized: behavior for packages other than "ui"; whether root `pnpm test` runs multiple suites when more packages exist (here only one). Report actual engine output; return {"answer":"passed"} only when the engine reports passed=true for ui.

[mock-pnpm-test-engine v1 v1] Local mock pnpm test engine (build tool) — behavior & usage
Local mock build engine (build tool, command form) — accepts `pnpm test` and `pnpm --filter <package> test`, resolving scripts from package.json. It checks the selected package source fixture and reports the actual executed suites. No network/installation needed.

Workspace layout: README.md, package.json (root), packages/ui/package.json, packages/ui/source.json.

Output format (JSON): {"exit_code":0,"executed_suites":["ui"],"passed":true} — per-suite execution + boolean `passed`.

Root package.json: name "workspace", scripts.test = "test-engine core", packageManager pnpm@10.
packages/ui/package.json: name "ui", scripts.test = "test-engine ui".

Cheap applicability check: list_files, then read README.md + target package.json to confirm test script exists before running.

Verified: `pnpm --filter ui test` => exit_code 0, executed_suites ["ui"], passed true (confirmed twice, at different timestamps).

Fixture semantics: packages/ui/source.json currently {base:15, increment:4, expected:19} (15+4=19, consistent). Earlier observed {base:5,increment:4,expected:9}. Assertions evaluate against this file, so editing source.json can change pass/fail.

Untested/not generalized: other package names besides "ui"; whether root `pnpm test` runs multiple suites (only one package here). Report actual engine output; return {"answer":"passed"} only when engine reports passed=true for ui.