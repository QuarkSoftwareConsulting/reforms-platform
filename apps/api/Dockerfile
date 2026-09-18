# Contexto desde la raiz: docker build -t reformahub-api:local apps/api
# Los digest fijan tambien las capas del sistema, no solo la version de Python.
FROM python:3.13.15-slim-bookworm@sha256:ed86c82274b3c69b52fb5820f358f0bd7df0b603332063cb5c6e32bd220c3e6e AS base

FROM base AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.29@sha256:eb2843a1e56fd9e30c7276ce1a52cba86e64c7b385f5e3279a0e08e02dd058fc /uv /usr/local/bin/uv

ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy
WORKDIR /app

# Cambiar codigo no invalida la instalacion; el entorno se crea dentro del build.
COPY pyproject.toml uv.lock .python-version ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project --no-editable --no-build

FROM base AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    PORT=8080
WORKDIR /app

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --no-create-home --no-log-init \
        --shell /usr/sbin/nologin app

# El usuario de ejecucion puede leer, pero no modificar codigo ni dependencias.
COPY --from=builder /opt/venv /opt/venv
COPY app/ ./app/
USER 10001:10001

EXPOSE 8080
# exec entrega las senales a Uvicorn; migraciones y seeds son tareas separadas.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port \"${PORT:-8080}\""]
