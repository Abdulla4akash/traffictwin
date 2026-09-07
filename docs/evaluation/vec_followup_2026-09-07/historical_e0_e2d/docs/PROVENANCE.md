# Provenance and Authoritative Identities

## Scope

The scientific experiments were executed in private, frozen repositories. This public repository records their exact identities and publishes only public-safe evidence. Commit identifiers below are provenance anchors, not links to redistributed private source.

## Shared artifacts

- Frozen Paper-2A 17-dimensional MAPPO actor SHA-256: `93c970594447efbfa76c25629307ba4bbbbacd0661f9f4423496850d899dc208`
- Manchester incident trace SHA-256: `e188ce076b0d000113dca3a53db8586dc424cbde51915a441f9d6b9990328056`
- tos-data commit: `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`

## E0 — discovered authority chain

E0 did not expose a single manifest identity in the later user-supplied summary, so the highest-authority E0 branch history and records were inspected directly. The discovered identities are:

- Initial TrafficTwin audit/start commit: `95e7b1e4048a11a2002473e83eb0aa1c584c9bbc`
- Corrected-smoke evidence commit: `1c344e1061bba5da9521aad8c170c7d1228e9566`
- Full corrected-reference final evidence commit: `29d8945862b7df1bd5d7879ba1d980a388f6be0d`
- Branch: `agent/e0-corrected-reference-v1`
- Corrected-smoke manifest: `8d81cf30f1ada3e9af7c799c9ebd0e01a427a67c570f583b658b11717a5eab93`
- Corrected-smoke validation: `ff095ac91765c1e59410c4b902ff47e018cf00a7c9513ca33e2983a8e18ae38d`
- Full corrected-reference manifest: `eae09f31bd049b70f99930507873b0efb84a7a7cbeab2a37adb7b3a0bae6b12f`
- Full corrected-reference validation: `3970b89e371a05cae6f5baa8142c98587b302d0c5a467601d50aa021e1368bfa`
- Full run checksum manifest: `3596554ca3c0dddab9bc352881b6c320035af427b2cfa183843f500794bbdb0c`
- Full raw-root checksum ledger: `688baf8155afb848487a3b1393066e36f01e20560bd178ede03d55f4bbc3fec4`
- vec_env commit: `0f01f4d2082d3e8b735e74a873095ab8eeba37cc`
- Evaluator SHA-256: `260b90ff400cb5048ae4e74fb6c407d197fbfc80d91d7b7edf0c65640b5bd669`
- Imported environment module SHA-256: `73d83d062fad030941f5236835cce8e86caacc4d44eb7a1129047e99228886ff`

The full-reference manifest records `1c344e...` as its execution-record parent; `29d894...` is the later commit that committed the complete full-reference evidence package. This distinction is retained rather than collapsing them into an invented single identity.

## E1

- TrafficTwin final evidence commit: `a1423e604078f70c95d4115287d3f0391348becf`
- Frozen manifest SHA-256: `0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d`
- vec_env scientific source: `0f01f4d2082d3e8b735e74a873095ab8eeba37cc`
- tos-data: `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`

## E2

- TrafficTwin final evidence commit: `c05736125a401b8176c53212b3915ec57b95fdc3`
- TrafficTwin reviewed execution commit: `b2ce160c64a3ce6e9fef9f23cdb52c9ee1940dbb`
- Manifest SHA-256: `53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8`
- vec_env instrumentation commit: `e11f4445a9cc939a79d4f419c6f48b43ce110664`
- vec_env original scientific source: `0f01f4d2082d3e8b735e74a873095ab8eeba37cc`

## E2b

- TrafficTwin reviewed execution commit: `f4e1897d6c17cf106880303a6be839407abe663e`
- TrafficTwin final evidence commit: `fe2ed4e9bd9043b19b96a5f179390db629b01ccb`
- Manifest SHA-256: `9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91`
- vec_env commit: `0e5ed2f79b50011fe0475a5c2069978f9fdd778d`

## E2c

- TrafficTwin scientific execution commit: `676f132406877bbc6fb92b6c2a08b675571aa9fa`
- Original scientific-evidence commit: `715ce2cf1e943951e13586756f07d7432e24fe69`
- Frozen final reporting-amendment head: `1a08d6e148a1e8c430da39c3d575eda3f8ea5929`
- Manifest SHA-256: `fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a`
- vec_env commit: `0e5ed2f79b50011fe0475a5c2069978f9fdd778d`

## E2d

- Approved TrafficTwin execution head: `095e0c1fbd5307b60722cac2be89ae480911e7df`
- Final independently approved evidence head: `80e8ae55dfbcc0aa271ed7ed1d67aeae8f384761`
- vec_env commit: `2f63706f46319433a2ba3af1df97afd0e56a95d1`
- tos-data commit: `a75bbdb1a956f828ee0e9b97b33506bd32d31b85`
- Manifest SHA-256: `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740`
- Raw evidence root ledger SHA-256: `eb5de7ce1eea202fee4d08d28bf7f4e38888b24709550cfc78dca71b16b250ca`
- Post-run independent exact-head technical review verdict: `APPROVE`

Independent exact-head technical review was an internal experimental quality-control gate, not scholarly peer review.

## Byte-identical public evidence copies

The following records passed the public-source path/secret scan and were copied without transformation. Their public bytes retain the frozen private SHA-256:

| Study | Public file | SHA-256 |
|---|---|---|
| E0 | `e0_full_reference_manifest_v1.json` | `eae09f31bd049b70f99930507873b0efb84a7a7cbeab2a37adb7b3a0bae6b12f` |
| E0 | `e0_manifest_v1.json` | `8d81cf30f1ada3e9af7c799c9ebd0e01a427a67c570f583b658b11717a5eab93` |
| E0 | `e0_full_reference_validation_v1.json` | `3970b89e371a05cae6f5baa8142c98587b302d0c5a467601d50aa021e1368bfa` |
| E0 | `e0_validation_v1.json` | `ff095ac91765c1e59410c4b902ff47e018cf00a7c9513ca33e2983a8e18ae38d` |
| E1 | `e1_multidraw_physical_campaign_comparison_v1.json` | `b2f7e8bf8769e7359bf5731b4b98d1007d294ed55595ec4977886f976d600ec3` |
| E1 | `e1_multidraw_physical_campaign_validation_v1.json` | `f1edacf318109eb0b9ccb7c8848b68fa199056c78d8329e1aa5e92c2e2395e0b` |
| E2 | `e2_native_placement_path_forwarding_summary_v1.json` | `54721d9a4b403e36e99123394193db06d7b6c596e66121975001a8d02196287e` |
| E2b | `e2b_placement_admission_path_summary_v1.json` | `dd48da132856e6199463cc195d93d007436c2cdb187133f8fa68962710c14c38` |

The E1 evidence index was also copied unchanged; its hash is retained in the directory-local checksum file.

## Sanitized public derivatives

Only string fields containing private absolute paths or private repository URLs were redacted. Numeric scientific content was not transformed. The original and public hashes are deliberately different:

| Study/file stem | Original private SHA-256 | Public-sanitized SHA-256 |
|---|---|---|
| E1 manifest | `0631f7b80a8575139c5dcbb7a110487fa57a0952555f0518a5bb9d37a1b93a2d` | `43fafbd73b5e5e0035fe9bf23f4046ff3a50fdd665352a3d6c415f50059fa19d` |
| E2 evidence index | `8c04c833f6b04140bac0f2dfcba788c50d29cc4be1dadf39cfacf5d8e366bba9` | `8431afb31ba7de7960d0c947970ee7d0c627d61d70f293c15f6512c3a177743b` |
| E2 comparison | `67d626ca4e6b60afb6beb5c9d4c8cc2bf7b15c72922eba633194848439fe3d52` | `988660bd2a2783cf45ab8bb8d5631e65fc8fbb9e11b5c8f0be99030712b2222d` |
| E2 manifest | `53bcd2e26b913b64ce0c4546da7c01cb7f9290382a036a20ce9fd28229ed02a8` | `69790a0736bb62bb9cd9822e989cdb52596597fbc047a9bc1770cfc375319939` |
| E2 validation | `30f6d117402e91decf8581b2b42030c0f9795881dd5eaef1a380bbf6408f0d38` | `99102cfc72d50f147dc94dd51f26631500a51b952fda7a4e1fcc9b918ea6169f` |
| E2b evidence index | `aedc625696f2c2fd9939ddaefd846aab94341810d4f39062a660a217b8f3e0c8` | `74b041ac254ad4709e1b5de5bd3d80886e461e01978f76a3ef12659c1ba41d6e` |
| E2b comparison | `8d35e55e2952d71b1c04479b310d1f5b48da7cf7bc2e171a1ca6359c9fa98aaf` | `ef1821f94739816ac2777323029e1a0711294116d23eba43215e7a5aa1d5c2fd` |
| E2b manifest | `9383ec767dccf2f390b498e0c20283a74cd64fa521d6137fe23ce38d0022af91` | `f2af61bf936d77ec8a78c156058e0404a7a2b7bd826705390e5d7b8c3779f701` |
| E2b validation | `e45ee4016887596476032b441762c38a92e0faed83738c30fbf590385243d8c1` | `c73a23a98342d58ed6a54a26d32b27f702e33705b2489c2ba0ffae9a8eec1389` |
| E2c evidence index | `038453d0b4bd03a07ebf6f42984875e4fd2d5187fe6c7fef33cd9d9399038da2` | `5d2b39d077b332503d7aec9985fa7145a13c0b54ca465da1f4d4cb5580961f49` |
| E2c comparison | `b0bc17ef097e8a8ca3639482bbf5ae05ef249c1221836cc6591207e87b511970` | `300fbadb332ea08c68d531e752a1e41423192fdc74219150f67fe6ec6c9fc2ba` |
| E2c mechanism | `5556f0fcd3e72c03c1efeb42df33697e77005e6151357b33a908d9154ae94baa` | `7150beae11ce62adc9374c4da07259f00ba4bb41711f055dfe107f4a0c7912bd` |
| E2c manifest | `fcaf2ee34b68ca4e4ef2e088d72ce2c5a410cf66ff9934a451fd8047204c480a` | `2cb5a05582ac907a630206bffd4de0c2850a20368bd7eb73807992e218f8a7b9` |
| E2c validation | `25b80d66d991b424e20a7fd18d9e45c641cddc4b4aa9ffeed0cbdccacb5f8f2f` | `ec0f7db4e28c4494973db1e1d228bffa3affb0415cde2532d0d76fcb46f62f0c` |
| E2d evidence index | `a6027fc17d1477547ba9d34c1fe95b224f79e6b0cedcfa49534b60c36265db4b` | `76638238c0b6026faf4650a492b5fa4ec3eb86b1d58fc669c7b8e1889b2bd53d` |
| E2d comparison | `1655ae76d3c9a6aac77d66b53555a35d608394427f86f0f19828fa5fb148afd0` | `95b70613461c56c0cebd1b4eed78af80db1760a4f1991c0b3d9149394f15dfdb` |
| E2d mechanism | `4975ab8792242a56c241d6513e7e49bcdfa5117ab462bcb6b9bb3c5d2a5e5410` | `887e2268d541624a67c193d719d3340bc4e54237337ab49029539ac0ad7012f8` |
| E2d manifest | `f77afb231f7d0be2c13627e9fbdc6bf635ea86b351bf0a0e7c83295ef0435740` | `582c5c0b254ab780f75b0c5b1f11829449c17d59bfe65443746724441552e096` |
| E2d validation | `0e3f27cdec9d13ec8e340bf1d83b3afcd127e90d7bdcf316bc2a2b2738fd313f` | `34c28b36087c4371136cb03e7aba8d121bb4341548bde84b13b793f84cda481e` |

Directory-local `checksums.sha256` files bind every included evidence file.

## Public curation event

This repository was assembled from read-only frozen sources. The curation process did not launch an evaluator or modify TrafficTwin, vec_env, tos-data or any E0–E2d raw artifact.
