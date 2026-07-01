# syntax=docker/dockerfile:1.7
FROM python:3.13.14-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    VIRTUAL_ENV=/opt/venv

RUN python -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
WORKDIR /build
COPY requirements.txt ./
RUN pip install --require-hashes -r requirements.txt
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-deps .

FROM python:3.13.14-slim-bookworm AS test

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements-dev.txt ./
RUN pip install --require-hashes -r requirements-dev.txt
COPY pyproject.toml README.md alembic.ini ./
COPY app ./app
COPY alembic ./alembic
COPY tests ./tests
COPY scripts ./scripts
RUN pip install --no-deps .

FROM python:3.13.14-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PATH=/opt/venv/bin:$PATH \
    HOME=/home/vibid \
    TMPDIR=/tmp

RUN apt-get update \
    && apt-get install --no-install-recommends -y ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 vibid \
    && useradd --uid 10001 --gid vibid --home-dir /home/vibid --create-home --shell /usr/sbin/nologin vibid

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app
COPY --chown=vibid:vibid alembic.ini ./
COPY --chown=vibid:vibid alembic ./alembic
COPY --chown=vibid:vibid app ./app

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import os, urllib.parse, urllib.request; host=urllib.parse.urlparse(os.environ['APP_BASE_URL']).hostname; request=urllib.request.Request('http://127.0.0.1:8000/health/live', headers={'Host': host}); urllib.request.urlopen(request, timeout=3).read()"]
CMD ["python", "-m", "app.run"]
