# This app's own image. Self-contained: the build context is this directory, so nothing
# outside it is referenced and the app still builds after being lifted into its own
# repository.

FROM ghcr.io/astral-sh/uv:0.9-python3.13-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependency layer first: it rebuilds only when the lockfile or the project metadata
# changes, not on every edit to the source.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY src src
COPY README.md README.md
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# The app writes nothing outside stdout unless asked to, so an unprivileged user is free.
RUN useradd --create-home --uid 10001 app && chown -R app:app /app
USER app

ENTRYPOINT ["prompt-chaining"]
