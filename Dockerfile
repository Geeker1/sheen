FROM python:3.12-slim-bookworm AS base

COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first so code changes don't bust the layer cache.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY README.md alembic.ini ./
COPY db ./db
COPY rules ./rules
COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 1000 sheen
USER sheen

EXPOSE 8000
CMD ["uvicorn", "sheen.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
