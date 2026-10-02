[profiles-api-partial-update v2] Profiles mock API: partial field update + verify
Service "profiles" v1 mock API (local workspace, no external network). Doc: api.json {"service":"profiles","version":1}.
Endpoints:
- GET /profile -> {"timezone","email","digest"}.
- PATCH /profile -> partial update: only body fields change; omitted fields retained. PUT unsupported.
Procedure for "change one field, preserve others": GET /profile to record current values -> PATCH /profile with ONLY the target field -> GET /profile to verify change AND untouched fields unchanged. Return requested JSON.
Evidence: PATCH {"timezone":"Asia/Tokyo"} -> status 200, body {"status":200,"profile":{...}}. Follow-up GET matched. Confirmed twice with different seeded emails (person1@example.test, person2@example.test) -> email is per-task seeded, so always read it fresh, do not hardcode; digest true in both.
Untested: invalid values, PUT/POST/DELETE, error status codes, /info shape.