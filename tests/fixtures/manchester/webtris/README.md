# Minimal official WebTRIS Manchester fixtures

These are exact base64-encoded response bodies fetched from the anonymous
National Highways WebTRIS API v1.0 on 2026-07-22. Tests decode the bodies
before hashing and parsing; base64 prevents repository newlines changing the
captured response bytes.

| Fixture | Meaning | SHA-256 of decoded bytes |
|---|---|---|
| site-34.json.b64 | GET /api/v1.0/sites/34 | f88cfc3442beb93a3e78b342891d8533566f50d6345a869152ee5aa1585488f7 |
| daily-site-34-20260301.json.b64 | One complete 96-row daily report for site 34 on 2026-03-01 | 0a4d9f35f65c5f579102e23e4cc19525984701e610a56bb51196723941f550b5 |
| quality-site-34-20260301.json.b64 | Daily availability response for site 34 on 2026-03-01 | 0c64204d9a32b3ae21aee61667103ee8d46e6fc5f2ba421fb0332ae1c0906654 |

Site 34 is the active M56/8150A National Highways strategic-road site. These
fixtures are schema evidence, not a representative Manchester traffic sample
or dissertation result. Source times remain verbatim because their timezone is
not documented.

Source: National Highways WebTRIS. Re-use is recorded under the Open
Government Licence v3.0, as named by the WebTRIS privacy-policy page. Logos
are excluded. The service's announced 2026 interruption remains a documented
availability limitation.
