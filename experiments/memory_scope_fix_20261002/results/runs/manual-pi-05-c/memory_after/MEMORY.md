[human-scoped-diagnostic v2] profiles service: pick update method from api.json version
Always re-read workspace api.json per task; the profiles service changes version and semantics.
- v1: PATCH /profile changes only supplied fields, retains omitted fields. PUT unsupported. Flow: GET, PATCH changed field, GET verify.
- v2: PUT /profile replaces the whole profile; missing email -> null, digest -> false, timezone -> UTC. PATCH unsupported. Flow: GET current profile, PUT all fields (changed value + preserved current email/digest), then GET verify.
Rule: never generalize omission-preserves-fields across methods/versions; preserve required existing values by sending them explicitly when the documented method replaces the resource.