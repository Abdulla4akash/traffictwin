# TrafficTwin Deployment Targets

TrafficTwin has two deliberately different deployment forms.

## Netlify Static Demonstration

The root `netlify.toml` builds a public-safe site from repository-generated **synthetic fixtures
only**. The build initialises a temporary standalone workspace and stages precomputed metrics,
diagnostic statuses, and deterministic HTML reports under `public/`.

It does not include Randy's TOS package, live data, raw bundles, SQLite state, or a Python runtime.
The scenario selector is client-side inspection of precomputed values; it does not calculate
metrics in the browser.

Build locally with:

```bash
traffictwin demo initialise .netlify-demo
traffictwin release stage-demo-site .netlify-demo --output public
netlify dev --dir public
```

## Streamlit Container

The root `Dockerfile` packages the full standalone synthetic Streamlit application. It creates the
demo workspace during image construction and exposes port `8501`.

```bash
docker build -t traffictwin:0.6.0 .
docker run --rm -p 8501:8501 traffictwin:0.6.0
```

This container remains synthetic and import-first. It does not include external TOS data or enable
direct simulator launch.

## TOS Publication Gate

Private TOS supervisor packs can be generated locally. Public atlas staging is a separate command
that refuses to run without `--confirm-publication-permission`. Supplying that flag is an explicit
human attestation; TrafficTwin cannot infer permission.

The repository licence is not yet specified. Do not describe either target as production-ready.
