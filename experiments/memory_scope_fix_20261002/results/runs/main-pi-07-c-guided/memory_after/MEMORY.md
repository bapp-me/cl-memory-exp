[local-config-override v2] Local app config: file vs deployment override resolution
Local app config precedence (files: README.md, deployment.json, settings.json; tool: config shows EFFECTIVE merged runtime config).

Rule (README.md): settings.json provides base values (e.g. {"port":8001,"host":"127.0.0.1"}). deployment.json = {"environment":{...},"config_file":"settings.json"}. If deployment.json environment.APP_PORT is present (non-empty), it OVERRIDES the file port. config output reflects merged effective settings.

Procedure to change effective port, retain host:
1. list_files + config to see current effective values.
2. read settings.json, deployment.json, README.md.
3. Identify the WINNING source: if environment.APP_PORT is present/non-empty it wins -> edit deployment.json environment.APP_PORT. Otherwise edit settings.json port.
4. write_file full JSON text, then re-run config to VERIFY.

Verified observations:
- Case A (override absent): settings.json -> {"port":8101,"host":"127.0.0.1"} gave effective {"port":8101,...}.
- Case B (override PRESENT): settings.json port=8003, deployment.json environment.APP_PORT="9003" -> effective port 9003 (file ignored). Changing deployment.json environment.APP_PORT to "8103" (string), keeping host, gave effective {"port":8103,"host":"127.0.0.1"}. So editing settings.json alone would NOT work when override present.
- APP_PORT value stored as a STRING; keep that type.
Confirmed: only port/host keys seen; exact override key is APP_PORT.