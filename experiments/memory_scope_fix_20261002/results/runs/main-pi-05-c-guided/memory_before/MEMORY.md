[profiles-api-partial-update v1] Profiles mock API: partial field update + verify
Service "profiles" v1 mock API (local workspace, no external network). Doc lives at workspace file api.json {"service":"profiles","version":1}.
Endpoints observed:
- GET /info -> metadata.
- GET /profile -> current profile, e.g. {"timezone":"UTC","email":"person1@example.test","digest":true}.
- PATCH /profile -> partial update: only fields in body change; omitted fields retained. PUT unsupported.
Applicability check (cheap): list_files to find api.json; read it to confirm service=profiles and the PATCH semantics line; GET /profile to see current fields.
Procedure for "change one field, preserve others": GET /profile first to record current values -> PATCH /profile with body containing ONLY the field(s) to change -> GET /profile again to verify changed field AND that untouched fields are unchanged. Return requested JSON.
Observed evidence: PATCH {"timezone":"Asia/Tokyo"} returned status 200 with {"timezone":"Asia/Tokyo","email":"person1@example.test","digest":true}; follow-up GET matched. Email and digest were preserved.
Untested: other field names, invalid values, PUT, POST/DELETE, multi-field PATCH, error responses/status codes beyond 200, /info shape. Do not assume behavior beyond the single observed profile value set.