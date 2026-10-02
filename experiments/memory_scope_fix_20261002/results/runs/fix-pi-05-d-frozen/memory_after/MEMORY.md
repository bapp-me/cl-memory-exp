[mock-api-profile-patch-pattern v2] Local mock API: update "current profile" field (verb depends on API version)
Task type: update one field of a "current profile" via local mock API while preserving other fields, then verify. Return requested JSON (e.g. {"answer":"updated"}).

Workflow (robust):
1. list_files -> usually ["api.json"]. Read api.json to learn service, version, endpoints, AND which verbs are supported. The doc is version-specific and CAN change between tasks.
2. GET the current resource first to learn existing field values (e.g. GET /profile -> {timezone,email,digest}).
3. Choose the verb the doc allows:
   - If PATCH is supported (partial update; omitted fields retained): send ONLY the changed field. Do NOT send the whole object. PUT may be unsupported.
   - If PATCH is UNSUPPORTED and PUT replaces/semantically overwrites the profile: you MUST PUT the FULL object including all fields you want preserved. Omitted fields get defaults (e.g. email->null, digest->false, timezone->UTC), silently wiping data.
4. Verify with a follow-up GET; confirm the changed field AND that preserved fields are intact (not defaults).
5. Return the requested JSON.

Key lessons:
- ALWAYS re-read api.json each task; do not assume the verb from memory. Observed variants: v1 "/profile": "...PATCH changes specified fields only; omitted fields retained. PUT unsupported." vs v2 "/profile": "...PUT replaces profile; missing email defaults to null, digest to false, timezone to UTC. PATCH unsupported."
- With replace-semantics PUT, partial bodies are destructive -> always include every field.
- Check the doc for default values of missing fields; they are the failure mode.
- Always re-GET to verify saved state before answering.
- Mock API call shape: {method, path, params?, body?}; response includes status + resource (or the profile fields directly). GET /info may just return version + doc pointer.
- Worked example (v2): GET /profile -> {"timezone":"UTC","email":"person4@example.test","digest":true}; then PUT /profile {"timezone":"Asia/Tokyo","email":"person4@example.test","digest":true} -> 200; GET -> {"timezone":"Asia/Tokyo","email":"person4@example.test","digest":true}.