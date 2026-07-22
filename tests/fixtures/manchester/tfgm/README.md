# Minimal attributed TfGM traffic-signal fixture

`signals-manchester-3.csv.b64` is a three-row derivative of the exact official
`CSV-format/TrafficSignals.csv` member fetched on 2026-07-22. Base64 preserves
the UTF-8 BOM and CRLF bytes.

- Source archive SHA-256: `85a52992ba2ef30b4bdb4aca4162a2ffd8a5244f7139be50e0b0ffbee7a4f3fa`
- Full official CSV SHA-256: `c45ad8439c9058a239f7e0ad33f39e2da8d79a80194229ad3b67a50f12fc3a81`
- Derived three-row CSV SHA-256: `becf158f1bbb1b15ab3eafd2e312ffd736a2f49497726c6802e1a4dacbdcf0f2`
- Official full row count: 2,529
- Dataset label: Nov 2025 data, published 14 January 2026

The three rows are exact official Manchester records selected in source order.
This is a redistributable derived schema fixture, not a complete dataset, live
signal state, traffic observations, or dissertation results. The complete ZIP
and CSV remain workspace-only.

Licence: Open Government Licence v3.0.

Required archive attribution:

> Contains Transport for Greater Manchester data. Contains OS data © Crown
> copyright and database right 2026.

The supporting PDF uses year 2025, while the OGL text shipped inside the
January 2026 archive uses 2026. This fixture follows the attribution shipped
with the acquired artifact and records the discrepancy rather than hiding it.
