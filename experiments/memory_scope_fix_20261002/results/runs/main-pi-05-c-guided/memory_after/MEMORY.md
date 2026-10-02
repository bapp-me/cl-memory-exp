[profiles-api-partial-update v2] Profiles mock API v2: PUT replaces profile (PATCH unsupported) — preserve fields by sending full body
Service "profiles" mock API (local workspace, no external network). Doc file: api.json.
IMPORTANT: doc version varies — always read api.json first; semantics differ by version.

Observed v2 ({"service":"profiles","version":2}):
- GET /info -> metadata.
- GET /profile -> {"timezone":"UTC","email":"person3@example.test","digest":true}.
- PATCH /profile -> 405 {"error":"Method not allowed","Allow":"GET, PUT"}.
- PUT /profile -> full replace. Missing email defaults to null, digest to false, timezone to UTC. So PUTing only {"timezone":...} WOULD WIPE email/digest.
- Correct "change one field, preserve others" procedure: GET /profile to capture current values -> PUT /profile with the FULL object (changed field + all existing fields) -> GET /profile to verify changed field AND untouched fields unchanged.
- Evidence: PUT {"timezone":"Asia/Tokyo","email":"person3@example.test","digest":true} -> 200 {"timezone":"Asia/Tokyo","email":"person3@example.test","digest":true}; follow-up GET matched exactly (email + digest preserved).

Superseded: an earlier stored note claimed v1 PATCH partial-update semantics; that is wrong for v2 and PATCH returns 405. Do not assume PATCH works.
Untested: v2 /info shape, invalid values, POST/DELETE, error codes beyond 405/200, behavior with version other than 2.