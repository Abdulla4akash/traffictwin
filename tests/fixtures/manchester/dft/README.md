# Minimal official DfT Manchester fixtures

These are exact, base64-encoded response bodies fetched from the unauthenticated
DfT Road Traffic Statistics API on 2026-07-22. Base64 avoids altering the raw
response bytes with a repository newline. Tests decode before hashing/parsing.

| Fixture | Official request | SHA-256 of decoded bytes |
|---|---|---|
| raw-count-43177.json.b64 | GET /api/raw-counts?page[size]=1&page[number]=1&filter[id]=43177 | 06869d2d3ff2606a719bd043bcf8f3e30ad7fca17df1084c12598912c4a56c22 |
| count-point-6046.json.b64 | GET /api/count-points?page[size]=1&page[number]=1&filter[id]=6046 | 525250e7df43cbd8738e841fccf1d3b1a2787c229f87c6dd7d00ca019c122635 |
| aadf-9219.json.b64 | GET /api/average-annual-daily-flow?page[size]=1&page[number]=1&filter[id]=9219 | d46e8c8fa29dbf72b3cd974a5dc6349fb8750e32e6758aad91b8b588cb4571a5 |

The selected rows are Manchester local-authority records
(local_authority_id=85, ONS E08000003). They are used only as minimal
schema/contract evidence, not as research results or a representative dataset.

Source: Crown copyright, Department for Transport Road Traffic Statistics API.
Re-use is recorded under the Open Government Licence v3.0. No fixture contains
personal data. See the repository Gate-A audit for the licence and attribution
evidence.
