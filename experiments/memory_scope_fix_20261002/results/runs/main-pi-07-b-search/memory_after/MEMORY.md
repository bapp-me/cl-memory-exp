[config-override-port v1] Config override precedence: change effective app port safely
Task pattern: "Set effective application port to N, retaining host; verify runtime config."
Workspace: README.md, deployment.json, settings.json.
Precedence (from README): settings.json is base config; deployment.json "environment".APP_PORT, if present, OVERRIDES the file port. `config` tool shows EFFECTIVE runtime settings after overrides.

Workflow:
1. list_files + config to see current effective values.
2. read README.md, deployment.json, settings.json to learn precedence and current state.
3. Decide where to edit:
   - If deployment.json environment.APP_PORT is present, it wins -> edit that key; editing settings.json port would have NO effect.
   - If environment empty (APP_PORT absent), edit settings.json port directly.
4. write_file (JSON text) to update the file, retaining other keys (e.g. host) unchanged.
5. Re-run config to VERIFY effective port/host, then return requested JSON.

Key gotcha: always check deployment.json overrides before editing settings.json; verification must use `config`, not the raw file. Preserve host. Return only the requested JSON shape.