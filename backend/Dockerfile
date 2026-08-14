FROM python:3.11-slim-bookworm

ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PYTHONPATH=/workspace/backend \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_INDEX_URL=${PIP_INDEX_URL}

WORKDIR /workspace
RUN useradd --create-home --uid 10001 forgeguard
COPY backend/requirements.lock.txt /workspace/backend/requirements.lock.txt
RUN python -m pip install --no-cache-dir --prefer-binary -r /workspace/backend/requirements.lock.txt
COPY backend/pyproject.toml /workspace/backend/pyproject.toml
COPY backend/app /workspace/backend/app
COPY backend/knowledge /workspace/backend/knowledge
COPY backend/research /workspace/backend/research
COPY frontend /workspace/frontend
COPY data /workspace/data
RUN mkdir -p /workspace/artifacts/bench-evidence /workspace/artifacts/benchmarks /workspace/artifacts/fault-campaigns /workspace/runtime-data \
    && chown -R forgeguard:forgeguard /workspace

USER forgeguard
WORKDIR /workspace/backend
EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=20s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
