[report-prefs-merge v1] Numeric report + preference inheritance pattern
Task type: "Save the current numeric report using applicable preferences" -> return {"answer":"saved"}.

Workspace layout: README.md (rules), figures.json (holds "value"), preferences/default.json (team defaults), preferences/project.json (project overrides).

Method:
1. list_files, then read ALL config/data files in parallel (README.md, figures.json, preferences/default.json, preferences/project.json).
2. Resolve settings by MERGE with project overriding default per-key: for each key (language/layout/decimals), use project value if present else default value. Empty project.json {} => all defaults apply. Never blindly overwrite whole default with project.
3. Get the number from figures.json "value" (can be a float like 131.456...; pass as-is, don't pre-round).
4. Call render_report(language, layout, decimals, value) with resolved values. It saves report.json.
5. Reply exactly {"answer":"saved"}.

General lesson: read the README first for override/merge semantics; prefer per-key inheritance over wholesale file replacement. Do parallel reads. Honor the exact required output JSON.