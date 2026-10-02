[mock-api-profile-patch-pattern v1] Local mock API: partial-update profile tasks
Task type: update a field of a "current profile" via local mock API while preserving other fields, then verify.

Workflow (worked well):
1. list_files -> usually returns ["api.json"]. Read api.json to discover service, endpoints, and which methods are supported (PATCH vs PUT).
2. GET the current resource to learn existing field values (e.g. GET /profile -> {timezone, email, digest}).
3. Apply ONLY the changed field with PATCH (omit unchanged fields; the API docs state omitted fields are retained). Do NOT use PUT if unsupported. Do NOT send the whole object.
4. Verify with a follow-up GET and confirm both the changed field and preserved fields are intact.
5. Return the requested JSON, e.g. {"answer": "updated"}.

Key lessons:
- Always read the workspace api.json/doc first; it tells which verbs are allowed (PUT may be unsupported).
- PATCH = partial update; preserve untouched fields by omitting them.
- Always re-GET to verify saved state before answering.
- api.json format example: {"service":"profiles","version":1,"/info":"GET metadata","/profile":"GET current profile. PATCH changes specified fields only; omitted fields retained. PUT unsupported."}
- Mock API call shape: {method, path, params?, body?}; response includes status + resource.