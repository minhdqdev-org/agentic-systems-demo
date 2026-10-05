---
title: agentic-systems-demo
slug: agentic-systems-demo
updated_at: 2026-09-02T13:35:00+07:00
tags:
  - langgraph
  - bifrost
  - agentic-systems
---

# agentic-systems-demo

Runnable demos of agentic-system patterns — one pattern per app, built with
[LangGraph](https://github.com/langchain-ai/langgraph). Every app comes up with a single
command and a Docker Compose file.

Each app under `apps/` is fully self-contained — its own dependencies, lockfile,
Dockerfile, gateway config and quality gates — so it can be lifted into its own repository
and pulled back in as a git submodule without changing a line.

## Apps

| Order | App | Pattern |
| --- | --- | --- |
| 1 | [prompt-chaining](apps/prompt-chaining/README.md) | A raw topic becomes a finished blog post through a linear chain: outline → write each section → review and polish. Includes a mid-chain validation gate and an optional human approval step. Calls Gemini directly. |
| — | [bifrost-gateway](apps/bifrost-gateway/README.md) | Not a demo yet: a [Bifrost](https://github.com/maximhq/bifrost) LLM gateway, waiting for a pattern that needs several providers behind one endpoint, per-step model routing, or one request log across a whole run. |

## Quick start

```bash
mise run install                     # sync every app's dependencies

# Put the two provider keys somewhere the gateway can reach them — pick one:
mise run vault-bootstrap             # (recommended) store them in Vault
cp .env.example .env && $EDITOR .env # or a local .env file

mise run demo prompt-chaining
```

`mise run demo` builds the app image and runs it, with the keys resolved for that one
command. Arguments after the app name go to the app:

```bash
mise run demo prompt-chaining --topic "Why Rust is worth a Python developer's time"
```

`--help` is the one flag `mise` keeps for itself; for an app's own help, invoke it
directly.

Without `mise`, from inside the app directory:

```bash
cd apps/prompt-chaining
../../scripts/with-secrets.sh docker compose run --rm --build demo --topic "..."
```

## Secrets

The apps need `GEMINI_API_KEY` (used by `prompt-chaining` and the gateway) and
`OPENROUTER_API_KEY` (gateway only). Nothing is ever read from a file at run time or baked
into an image — a key reaches a container as an environment variable, for the length of one
command, and nowhere else.

Two backends, one entry point (`scripts/with-secrets.sh`):

- **Vault** (default when a token is available) — keys are read from
  `kv/minhdqdev/dev/agentic-systems-demo` at run time and never touch the filesystem.
- **`.env`** (fallback) — fine for a throwaway experiment; it is still a credential at
  rest with nobody's name on its lifetime.

Full reasoning, AppRole setup for CI, and the Kubernetes/Vault-Agent story:
[docs/secrets.md](docs/secrets.md).

## Layout

```text
apps/<pattern>/       a complete, self-contained demo — see below
scripts/              with-secrets.sh, vault-bootstrap.sh
.mise/tasks/          the task scripts behind `mise run ...`
docs/                 architecture, secrets, how to add an app
```

Every app has the same shape:

```text
apps/prompt-chaining/
├── docker-compose.yaml   everything the app runs
├── Dockerfile            build context is this directory and nothing above it
├── pyproject.toml        deps *and* this app's ruff/mypy/pytest config
├── uv.lock
├── src/prompt_chaining/
└── tests/
```

An app brings whatever infrastructure it needs and nothing it does not: `prompt-chaining`
is one container, `bifrost-gateway` is a gateway with no app code yet.

- [docs/architecture.md](docs/architecture.md) — how the pieces fit and why there is a gateway at all
- [docs/adding-an-app.md](docs/adding-an-app.md) — the checklist for app number two
- [docs/secrets.md](docs/secrets.md) — where the keys live

## Development

```bash
mise tasks                     # everything available
mise run check                 # every gate CI runs, across every app
mise run check prompt-chaining # just one app
mise run fmt                   # ruff format + autofix
mise run gateway bifrost-gateway   # start the standalone gateway
```

The tests are offline by design: every graph keeps its checkable logic in plain Python
nodes, so no key, gateway or network is needed to run them.

## Requirements

- [mise](https://mise.jdx.dev) (installs Python 3.13 and `uv`)
- Docker with Compose v2
- A Gemini API key (and an OpenRouter key, if you run the gateway)
- Optional: the `vault` CLI, for the Vault secrets backend
