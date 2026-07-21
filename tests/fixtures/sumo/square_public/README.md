# Public SUMO square validation fixture

This fixture contains `tripinfo.xml` and `summary.xml` generated with Eclipse SUMO 1.27.1 from
the official `tools/game/square` scenario at tag `v1_27_1`, commit
`7717f2379d9e314a0c81c5cec748444de06a2a91`.

Generation command, executed from a local copy of `tools/game`:

```bash
sumo --configuration-file square.sumocfg --seed 42 \
  --tripinfo-output tripinfo.xml --summary-output summary.xml \
  --write-metadata true --write-license true --no-step-log true
```

The source scenario and generated XML carry the Eclipse Public License 2.0 with the documented
GPL-2.0-or-later secondary-licence option. The XML files retain their generated licence notices.
They are immutable test evidence: tests verify their declared SHA-256 checksums and the adapter
does not rewrite them.

This is synthetic simulated traffic, not observed Manchester traffic and not a Randy/VEC run.
