---
title: Agent guide
slug: agents
updated_at: 2026-09-02T13:35:00+07:00
---

# Working in this repo

A monorepo of runnable agentic-system demos. One pattern per app under `apps/`, LangGraph
for the graphs.

Read [docs/architecture.md](docs/architecture.md) first — above all the isolation rule it
explains. Then [docs/adding-an-app.md](docs/adding-an-app.md) for the house style.

## The isolation rule

**Every app must build and run with its own directory as the whole world.** Nothing in an
app's `Dockerfile` or `docker-compose.yaml` may reference a path above itself. Apps
therefore duplicate the lint config and the small modules `settings.py` / `llm.py` /
`console.py`.

That duplication is intended, not technical debt. It is what lets an app be lifted into its
own repository and pulled back in as a git submodule. Do **not** "fix" it by adding a
`packages/` directory, a workspace lockfile, a shared root `Dockerfile`, or a compose
`include:` of a parent path — each of those silently breaks the property.

Repo-level tooling (`scripts/`, `.mise/tasks/`, `.github/`) is the exception: it operates
*on* apps rather than belonging to one. An app is any `apps/*/` with a
`docker-compose.yaml`; it additionally gets the Python gates if it has a `pyproject.toml`.
`bifrost-gateway` has no Python and is still discovered and compose-validated.

## Rules that are easy to break by accident

- **Keys come from the environment, never a file at run time**, and are typed
  `SecretStr` so a traceback cannot print one. See [docs/secrets.md](docs/secrets.md).
- **`build_graph()` must not need a credential.** Read settings inside the nodes. The
  tests compile the graph and drive its non-LLM nodes with no key, and that is what keeps
  CI offline — putting `get_settings()` in `build_graph()` turned CI red once already.
- **Model choice is configuration.** Read it from the environment and funnel every call
  through one `chat_model()` factory.
- **Do not add a gateway an app does not route through.** `prompt-chaining` runs on one
  model and calls Google directly on purpose; the Bifrost gateway lives in its own app for
  a demo that needs several providers or per-step model routing.
- **`.text`, never `str(.content)`, to read a model reply.** Gemini returns a list of
  content blocks; stringifying it shipped a Python repr into a finished post once.
- **Do not add `_.file = ".env"` to `mise.toml`.** Secrets are resolved per command by
  `scripts/with-secrets.sh`, not loaded into every shell that enters the directory.
- **Keep checkable logic in plain Python nodes.** Validation gates, routing and assembly
  must be testable without a network — that is what keeps CI offline.
- **The console script goes in the Dockerfile's `ENTRYPOINT`, with `command: []` in
  compose.** `docker compose run` overrides `command` wholesale, so a script placed there
  is replaced by the first argument the user passes.
- **Tasks that take arguments live in `.mise/tasks/` as scripts, not as `run =` blocks.**
  mise executes `run =` with `sh` (no `pipefail`) and its parser rejects unrecognised flags
  before the block sees them.
- **A new app needs a Dependabot entry.** `.github/dependabot.yml` is the one place apps
  are named explicitly; everything else discovers them.

## Commands

```bash
mise run install [app]     # sync dependencies — every app, or one
mise run check [app]       # what CI runs: ruff, mypy, pytest, bandit, pip-audit, compose config
mise run demo <app> ...    # run an app in Docker, secrets resolved for that command only
mise run gateway <app>     # start just an app's bifrost service; UI + request log on :8080
mise run demo-down <app>   # stop it again
```

## CI

`.github/workflows/ci.yml` — code quality only. A `discover` job globs `apps/*/` and fans
out a matrix, so each app gets its own job. This repo publishes no images, so the org's
reusable build-and-push workflow is deliberately not used here.
