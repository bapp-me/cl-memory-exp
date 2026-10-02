[mock-api-profile-patch-pattern v2] Local mock API: partial-update profile tasks (ONLY when api.json says PATCH is supported / v1)
APPLICABILITY (important): Use this pattern ONLY when the workspace api.json /profile doc states PATCH is supported (e.g. version 1: "PATCH changes specified fields only; omitted fields retained. PUT unsupported."). Always read api.json FIRST. On other versions (e.g. v2: "PUT replaces profile; missing fields default... PATCH unsupported.") this pattern is WRONG/INAPPLICABLE and its PATCH call will silently reset omitted fields to defaults -> data loss. For those, see entry "mock-api-profile-update-by-version" (GET then PUT the FULL object).

Workflow when PATCH is the documented verb (v1):
1. list_files -> usually ["api.json"]. Read api.json to discover service, endpoints, and which methods are supported (PATCH vs PUT).
2. GET the current resource to learn existing field values (e.g. GET /profile -> {timezone, email, digest}).
3. Apply ONLY the changed field with PATCH (omit unchanged fields; the docs state omitted fields are retained). Do NOT use PUT if unsupported. Do NOT send the whole object.
4. Verify with a follow-up GET and confirm both the changed field and preserved fields are intact.
5. Return the requested JSON, e.g. {"answer": "updated"}.

Key lessons:
- Always read the workspace api.json/doc first; the version determines which verb is valid AND whether omission preserves or resets fields. Never assume PATCH.
- (v1) PATCH = partial update; preserve untouched fields by omitting them.
- Always re-GET to verify saved state before answering.
- api.json format example: {"service":"profiles","version":1,"/info":"GET metadata","/profile":"GET current profile. PATCH changes specified fields only; omitted fields retained. PUT unsupported."}
- Mock API call shape: {method, path, params?, body?}; response includes status + resource.

[mock-api-profile-update-by-version v1] Local mock profile API: verb & semantics depend on api.json version
Always read api.json first; the correct verb and its semantics vary by version.

v1 ("/profile": "...PATCH changes specified fields only; omitted fields retained. PUT unsupported.")
- Use PATCH with ONLY the changed field; omit unchanged fields. Re-GET to verify.

v2 ("/profile": "GET current profile. PUT replaces profile; missing email defaults to null, digest to false, timezone to UTC. PATCH unsupported.")
- PATCH is UNSUPPORTED. PUT REPLACES the whole resource.
- DANGER: PUT with omitted fields resets them to defaults (null/false/UTC). To change one field, you MUST GET first, then PUT the FULL object including all existing fields plus the change.
- Example: GET /profile -> {timezone:"UTC",email:"person3@example.test",digest:true}; PUT body {"timezone":"Asia/Tokyo","email":"person3@example.test","digest":true} -> preserves email/digest.

Key lesson: don't reuse prior-version guidance blindly; a PATCH/partial-update habit on a v2 PUT endpoint silently destroys data. Always re-GET after writing to verify all fields.

Call shape: {method, path, params?, body?}; response {status, profile}.