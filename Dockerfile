FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TRAFFICTWIN_WORKSPACE_PATH=/opt/traffictwin-demo \
    TRAFFICTWIN_REGISTRY_PATH=/opt/traffictwin-demo/registry.sqlite \
    TRAFFICTWIN_FIXTURE_PATH=/opt/traffictwin-demo/bundles

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN python -m pip install --no-cache-dir . \
    && traffictwin demo initialise /opt/traffictwin-demo

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8501/_stcore/health', timeout=3)"

CMD ["streamlit", "run", "src/traffictwin/ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
