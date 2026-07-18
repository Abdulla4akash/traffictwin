# Deployment

TrafficTwin has two deployment targets. They intentionally expose different capabilities.

## Netlify Static Demonstration

The Netlify target is a synthetic-only static research dashboard. It contains precomputed metrics,
existing diagnostic-rule statuses, and deterministic reports for six standalone scenarios. A
client-side scenario selector changes which precomputed values are displayed; it does not calculate
metrics or run Python in the browser.

Current public deployment: <https://traffictwin-research-demo.netlify.app>

The deployed page is suitable for sharing as a synthetic software demonstration. It is not the full
Streamlit application, a live traffic service, or a publication of Randy/TOS results.

Build locally:

```bash
traffictwin demo initialise .netlify-demo
traffictwin release stage-demo-site .netlify-demo --output public
```

Preview with the Netlify CLI:

```bash
netlify dev --dir public
```

The root `netlify.toml` performs the same build. The generated `site-manifest.json` records:

- `synthetic: true`;
- `live_data: false`;
- `external_integration: false`;
- scenario identifiers;
- package and licence status;
- SHA-256 hashes for staged pages.

Randy's package is never read by the Netlify build and is not copied into `public/`.

## Streamlit Container

The root `Dockerfile` builds the complete standalone Streamlit application with an initialised
synthetic workspace:

```bash
docker build -t traffictwin:0.1.0 .
docker run --rm -p 8501:8501 traffictwin:0.1.0
```

The container exposes `8501` and includes a Streamlit health check. It does not include TOS data,
SUMO files, checkpoints, credentials, or direct-launch support.

## TOS Atlas Publication

Local/private atlas generation remains available through `results-pack` and `supervisor-pack`.
Public staging requires a separate attestation:

```bash
traffictwin integration tos stage-public-atlas TOS_DATA_PATH \
  --output public-tos-atlas \
  --confirm-publication-permission
```

Do not use that flag until written permission has actually been obtained. The repository licence is
also not yet specified.

## Security Boundary

- Static deployment contains no SQLite database or raw bundle files.
- The static site uses escaped embedded JSON and finite numeric serialization.
- Netlify headers disable framing, MIME sniffing, camera, microphone, and geolocation.
- The container runs only the packaged Streamlit entry point.
- Neither deployment executes imported bundle contents.

## Related Documents

- [Standalone demo](standalone_demo.md)
- [Security and privacy](security_and_privacy.md)
- [Release guide](release_guide.md)
- [Limitations and future work](limitations_and_future_work.md)
