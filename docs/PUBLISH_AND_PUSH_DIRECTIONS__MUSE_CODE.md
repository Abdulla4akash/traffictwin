# PUBLISH AND PUSH DIRECTIONS — TRAFFICTWIN v0.6.0

**Author:** Muse Code powered by Meta Muse Spark
**File label:** `PUBLISH_AND_PUSH_DIRECTIONS__MUSE_CODE.md` — prepared by Muse Code
**Date:** 2026-08-06
**Repository:** `traffictwin/` (local workspace `/root/traffictwin`)
**Canonical design:** `docs/traffictwin-design-v0_6.md` v0.6 — Status: VEC-01..VEC-12 accepted, Gates A-G complete
**Purpose of this file:** Clearly state what you MAY publish/push to a public GitHub (or Netlify) vs. what is dissertation-only vs. what must NEVER be pushed, based on the checked-in permission manifests.

> This file is informational only. It does not grant legal permission. The governing artifacts are the checked-in manifests and `docs/integration/randy_publication_policy.md`. When in doubt, do NOT push — ask Randy Putra / supervisor for written clearance.

---

## 1. At-a-glance decision table

| Category | What | Public GitHub / Netlify push? | Where it lives now | Condition |
|---|---|---|---|---|
| **SAFE — PUBLIC** | Your TrafficTwin source code, docs, synthetic fixtures, generated contracts | **YES** | `src/traffictwin/`, `docs/`, `tests/`, `examples/`, `docs/reference/generated/*.json` (synthetic) | Keep `CITATION.cff` + licence, no external raw data |
| **SAFE — PUBLIC** | Synthetic demo artifacts & `ING-01` SUMO square fixture | **YES** | `tests/fixtures/sumo/square_public`, `docs/reference/generated/sumo_*`, Netlify demo `https://traffictwin-research-demo.netlify.app` | Explicitly synthetic / EPL-2.0 SUMO square (with licence notice) |
| **CONDITIONAL — DISSERTATION ONLY** | VEC-11 dissertation pack: 3-row sanitised sample + 26 aggregates | **NO to public GitHub** — dissertation/private repo only | `docs/reference/generated/vec_dissertation_pack/` (3 files) `manifest.json` says `"public_hosting_authorized": false` | Only with full citations + `v2_post_nrsus_fix` + `_s102_best_of_seeds` label + limitations (§1.4) |
| **CONDITIONAL — DISSERTATION ONLY** | VEC-12 end-to-end research artifact ZIP (27 members, 2 MB) | **NO to public GitHub** — dissertation/private only | `docs/reference/generated/vec_end_to_end_research_artifact.zip` + `vec_end_to_end_research_artifact_receipt.json` | Same VEC-11 bounds; `public_hosting_authorized=false`; hashes prove identity not truth; pseudonymised ≠ anonymous |
| **CONDITIONAL — DISSERTATION ONLY** | RO-Crate 1.3 exports from ordinary generic bundles (permission-aware) | **YES if synthetic/generic only; NO if derived from `tos-data`/`vec_env`** | Generated via `traffictwin bundle export-ro-crate` | Must set embed/reference/exclude correctly; verify offline checksums |
| **NEVER PUSH** | Full `vec_env` / `tos-data` repos, raw NPZ/XML traces, checkpoints, machine records, SUMO proprietary networks | **NEVER** | `../external/vec_env`, `../external/tos-data` (read-only, not in `diss/`) | Written permission 2026-07-21 covers *sanitised samples + aggregates only* |
| **NEVER PUSH** | Full raw datasets, actor binaries, source vehicle IDs / slot mappings, private paths/hostnames | **NEVER** | Excluded inventory in VEC-11/VEC-12 manifests | Must remain in `excluded` list per `TosPublicationManifest` policy v1.0 |

---

## 2. What you CAN publish and push publicly (no extra permission needed)

These are your own research-software artifacts. They are already public-safe by design (§13, VEC-11 policy: “Public hosting remains blocked until …” applies *only* to VEC-derived artifacts — not to synthetic/core code).

**a) Core repository (recommended public repo content):**
- `src/traffictwin/` — all `v0.5` (ING-01..05, MET-01..06, DIA-01..07, STA-01..05, PRO-01..03, EXP-01..03, REP-01..05, OPS-01..05) + `v0.6` library services (`vec_identity`, `vec_task_join`, `vec_trip_join`, `vec_preprocessing`, `vec_runner`, `vec_reproduction`, `vec_science`, `vec_interface`, `vec_publication`, `vec_research`, `sumo_execution`)
- `docs/` — except you should keep the 2 private permission screenshots referenced by VEC-01 audit redacted (they are already only hashes + excluded)
- `tests/`, `scripts/`, `examples/`, `Dockerfile`, `pyproject.toml`, `.venv` lock, `CITATION.cff` (v0.6.0, Abdulla Al Mamun Akash)
- Generated synthetic references: `docs/reference/generated/*.json` that are synthetic (verify field `source_mode: synthetic`)
- Synthetic bundle presets: `traffictwin synthetic generate-preset baseline` etc., plus `docs/reference/generated/sumo_*` and `tests/fixtures/sumo/square_public` (EPL-2.0, with embedded licence notice)

**Public demo:** `https://traffictwin-research-demo.netlify.app` — static, precomputed synthetic values only, no Randy/TOS artifacts, already public.

**Push checklist for this tier:**
```bash
# verify offline before push — these are the project gates listed in implementation-status.md:
# - 1,110 tests pass, mypy strict 530 files, ruff format/check, link verification 1,420 links
# - git diff --check clean, dependency lock current
# - no ../external content staged
```

---

## 3. What you CAN publish ONLY inside dissertation / private submission (NOT public GitHub)

### VEC-11 Sanitised Dissertation Pack — `docs/reference/generated/vec_dissertation_pack/`
- **Contains exactly 3 files:** `sanitised_matched_sample_s102.csv` (3 rows, local/V2I/V2V, 439 bytes), `aggregate_metrics_s102.csv` (26 rows, 18 available + 8 unavailable, 2238 bytes), `manifest.json` (citations, hashes, limitations)
- **Governance:** `docs/integration/vec_dissertation_pack.md` + `docs/integration/randy_publication_policy.md` + `TosPublicationManifest` policy `tos-publication-policy-1.0`
- **Manifest extract (checked-in):**
  - `"public_hosting_authorized": false`
  - `"engine_version": "v2_post_nrsus_fix"`, `"pack_version": "vec-dissertation-pack-1.0"`
  - `"pseudonym_mapping_retained": false`, `"anonymity_claimed": false` — pseudonymised, NOT anonymous
  - Citations required: `vec_env@068b4ea33e640f206ce6a7d04f3d6fae2ac831f4` and `tos-data@f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`
  - Must retain `uses_selected_seed: true` + `selected_seed_disclosure: _s102_best_of_seeds` wherever those rows appear
  - `verify_vec_dissertation_pack()` must return `status == "accepted"` (see snippet in `vec_dissertation_pack.md`)

**Allowed:** Include as appendix/attached ZIP in dissertation PDF submission, and in a private university GitLab / Overleaf project shared with examiners, with the manifest alongside it.

**Not allowed:** Push to `github.com/yourname/traffictwin` public, or to public Netlify, Zenodo, Figshare, Hugging Face, etc., without new written permission converting owner permission into a formal licence. VEC-11 doc: “Public hosting remains unauthorised.” Implementation-status: “Public hosting remains blocked until the TrafficTwin project licence and every included external artifact's publication basis are explicit.”

### VEC-12 End-to-End Research Artifact — `docs/reference/generated/vec_end_to_end_research_artifact.zip`
- 27 sorted, stored members, fixed 1980 timestamp, ≤1 MB/member, ≤2 MB total, checksums prove byte identity
- Binds VEC-01..VEC-11 lineage; distinguishes `ukfleettrain-mappo_we_uk2030_fs0` protocol-seed (VEC-08) vs `fcd_s102_uk2030_we_fs0 _s102_best_of_seeds` (VEC-09/VEC-11) — do NOT collapse labels
- Same public-hosting restriction as VEC-11. Verifier: `traffictwin integration vec research-verify docs/reference/generated/vec_end_to_end_research_artifact.zip`

### How to include correctly in dissertation
1. Keep the 3 VEC-11 files + manifest together — never publish the 3-row CSV without `manifest.json`.
2. Cite verbatim in thesis text (required by §13 of design): `vec_env` + `tos-data` with reviewed commits, engine `v2_post_nrsus_fix`, and `_s102_best_of_seeds` label.
3. State limitations: deadline success ≠ physical completion, eligible target ≠ confirmed transfer, per-task energy unavailable, R1/R2/R7 blocked, R6 conditional, pseudonymised not anonymous.
4. Do NOT embed: source vehicle IDs, slots, task indices, clocks, coordinates, paths, checkpoints, full NPZ/XML (these are in the `excluded` inventory by policy).
5. Run offline verification and paste receipt into appendix:
```python
from pathlib import Path
from traffictwin.integration.vec_publication import verify_vec_dissertation_pack
manifest = verify_vec_dissertation_pack(Path("docs/reference/generated/vec_dissertation_pack"))
assert manifest.status == "accepted"
assert manifest.public_hosting_authorized is False
```

---

## 4. What you MUST NEVER publish or push (blocklist)

Derived from `TosPublicationManifest.default_excluded_inventory()` and VEC-01 audit (154 files, 889 MB hashed, but never redistributed):

- ❌ Entire `vec_env` and `tos-data` repositories (or their `.git` history) — `../external/` is read-only; `diss/` must never contain their raw files
- ❌ Full raw TOS result datasets (`tos-data` traces, per-step NPZ 60 files, per-task files, occupancy tables, tripinfo XML beyond the 3 sanitised rows)
- ❌ Actor / checkpoint binaries (frozen baseline + `ukfleettrain-MAPPO`, ~22 KB observed, 17→64→64→3 float32)
- ❌ Private machine/environment records, hostnames, usernames, absolute paths, `file://` URIs
- ❌ Third-party SUMO network/FCD assets beyond the public `square_public` fixture (Manchester-specific placements are private)
- ❌ Source identity mappings (slot↔`sumo_vehicle_id` full table), full 45,299 occupancy spans with IDs, 46M task rows

If you ran `traffictwin integration vec` or `sumo_execution` locally, the generated `*.npz`, `*.xml.gz`, `trace/`, `occupancy/` outputs in your `../external` or `/tmp` workspaces are also **never** to be staged — they are validated then hashed, not copied into `diss/`.

---

## 5. Minimal safe public GitHub push plan (if you want to push today)

**Safe branch to push:** `main` as-is, **excluding** VEC-derived private artifacts if you want a strictly public-safe repo.

Option A — **Push everything except VEC packs (safest for public GitHub):**
- Publish full `src/`, `docs/`, `tests/`, synthetic fixtures, `CITATION.cff`, `README.md`, `CHANGELOG.md`, `Dockerfile`
- Keep `docs/reference/generated/vec_dissertation_pack/` and `vec_end_to_end_research_artifact.zip` **out of the public remote** (add to `.gitignore` on the public mirror, or keep them only in a private dissertation branch)
- Netlify demo remains as-is (synthetic only)

Option B — **Push repo as-is including VEC packs, but keep repo PRIVATE:**
- If your GitHub repo is private (university org, examiners only), the checked-in VEC-11/VEC-12 files are within the 2026-07-21 written permission (sanitised + aggregates, with manifest). Still not a public licence.

**Never do:** `git add ../external`, `git add /tmp/trace`, `--force` push of large binaries, or `filter-branch` history rewrite to “clean” a mistaken push — report exposure instead (per bundled:git skill).

**Pre-push verification (run locally before `git push`):**
```bash
# 1. Ensure no external raw data staged
git status --porcelain | grep -E "external|tos-data|vec_env|\.npz|\.xml\.gz" && echo "STOP - external raw data staged"

# 2. Verify VEC packs still verify offline
python -c "from pathlib import Path; from traffictwin.integration.vec_publication import verify_vec_dissertation_pack; m=verify_vec_dissertation_pack(Path('docs/reference/generated/vec_dissertation_pack')); print(m.status, m.public_hosting_authorized)"

# 3. Check public_hosting_authorized is still false — if true, do NOT push publicly
jq .public_hosting_authorized docs/reference/generated/vec_dissertation_pack/manifest.json
jq .public_hosting_authorized docs/reference/generated/vec_end_to_end_research_artifact.zip  # via research-verify --format json

# 4. Standard gates (from implementation-status.md Gate G evidence)
# ruff format --check + ruff check + mypy --strict + pytest -q (1,110 tests) + link check
```

**Required citations when you share ANY VEC-derived number (even in slides):**
> `vec_env` `068b4ea33e640f206ce6a7d04f3d6fae2ac831f4` and `tos-data` `f6c67acbed3360dba3a0d5c8d1fd557caa99ecff`, engine `v2_post_nrsus_fix`, run label `_s102_best_of_seeds` (VEC-11 pack) or `protocol_seed_not_best_of_seeds` (VEC-08), with manifest `fingerprint` and `public_hosting_authorized=false` disclosed.

---

## 6. What to ask for if you need public hosting of VEC results

To make VEC-11/VEC-12 public (e.g., Zenodo DOI for thesis), you need **all** of:

1. TrafficTwin project licence decision (currently blocked per implementation-status.md)
2. Written conversion of Randy Putra’s 2026-07-21 owner permission into a formal data/software licence that explicitly allows public redistribution (currently “owner permission ≠ formal licence”)
3. Confirmation that `third_party_sumo_asset` rights are cleared (SUMO is EPL-2.0, but Manchester network is not)
4. Updated `TosPublicationManifest` with `public_hosting_authorized: true` and new pack rebuild (builder will refuse strengthened claims otherwise)

Until then, keep VEC packs dissertation-private and publish only the synthetic/core repo publicly.

---

## 7. File provenance

- This directions file was authored by **Muse Code powered by Meta Muse Spark** (not a human author) at the user’s request to “clearly label file as your name.”
- Sources consulted: `traffictwin/docs/traffictwin-design-v0_6.md` §13, `traffictwin/docs/integration/randy_publication_policy.md`, `traffictwin/docs/integration/vec_dissertation_pack.md`, `traffictwin/docs/integration/vec_end_to_end_research_artifact.md`, `traffictwin/docs/implementation-status.md` (VEC-11/VEC-12 status + Gate G gates), `traffictwin/docs/reference/generated/vec_dissertation_pack/manifest.json`, `traffictwin/CITATION.cff`, `traffictwin/README.md`.
- No git commit or push was performed — this file is left uncommitted for your review, per project git safety rules. Ask explicitly if you want it committed.

---
*If you want this file committed, say: “commit `PUBLISH_AND_PUSH_DIRECTIONS__MUSE_CODE.md`” and I will stage only this file.*
