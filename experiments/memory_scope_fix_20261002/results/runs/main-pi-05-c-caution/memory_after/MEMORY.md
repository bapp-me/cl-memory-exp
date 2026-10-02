[mock-api-profile-patch-pattern v2] Local mock API: partial-update profile tasks (PATCH vs PUT-replace)
Task type: update a field of a "current profile" via local mock API while preserving other fields, then verify.

Workflow (worked well):
1. list_files -> usually ["api.json"]. READ api.json FIRST: it states which verbs are supported. Version matters:
   - v1 doc: "/profile: GET. PATCH changes specified fields only; omitted fields retained. PUT unsupported." -> use PATCH with ONLY the changed field.
   - v2 doc: "/profile: GET current profile. PUT replaces profile; missing email defaults to null, digest to false, timezone to UTC. PATCH unsupported." -> PUT REPLACES, so you MUST GET first and PUT the FULL object with all preserved fields, changing only the target field.
2. GET /profile to learn existing values, e.g. {timezone:"UTC", email:"person3@example.test", digest:true}.
3. Apply the update with the verb the docs allow, sending exactly what that verb requires (partial for PATCH, complete for PUT-replace).
4. Verify with a follow-up GET; confirm changed field AND preserved fields intact.
5. Return requested JSON, e.g. {"answer":"updated"}.

Key lessons:
- Never assume PATCH-able partial update; the verb semantics differ per version. PUT-replace with omitted fields silently resets them to defaults (null/false/UTC), destroying preserved values.
- Always re-GET to verify before answering.
- api.json format example: {"service":"profiles","version":2,"/info":"GET metadata","/profile":"GET current profile. PUT replaces profile; missing email defaults to null, digest to false, timezone to UTC. PATCH unsupported."}
- Mock API call shape: {method, path, params?, body?}; response includes status + resource.