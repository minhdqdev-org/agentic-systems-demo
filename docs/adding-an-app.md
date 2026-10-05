---
title: Adding an app
slug: adding-an-app
updated_at: 2026-09-02T13:35:00+07:00
tags:
  - contributing
  - langgraph
---

# Adding an app

Every app is a self-contained directory under `apps/`, named for the pattern it teaches.
Copy `apps/prompt-chaining`, then change what follows.

Copying rather than sharing is the intended workflow here — see the isolation argument in
[architecture.md](architecture.md). If you find yourself wanting to factor something out
to the repository root, that is the moment to check it against the submodule rule: an app
must still build and run with its directory as the whole world.

## 1. The directory

```text
apps/parallelization/
├── README.md               what the pattern is, when to reach for it, how to run it
├── docker-compose.yaml     the app, plus whatever infrastructure it actually needs
├── Dockerfile              build context is this directory
├── .dockerignore
├── pyproject.toml          deps, entry point, and this app's ruff/mypy/pytest config
├── uv.lock
├── src/parallelization/
│   ├── __init__.py
│   ├── settings.py         model + key, from the environment
│   ├── llm.py              chat_model()
│   ├── console.py          step() / panel() output helpers
│   ├── models.py           the typed shapes that flow between steps
│   ├── prompts.py          one template per step, side by side
│   ├── graph.py            state, nodes, edges, build_graph()
│   └── cli.py              typer entry point
└── tests/
    └── test_graph.py       the offline parts: gates, routing, assembly
```

Bring only the infrastructure the pattern needs. If one model does the job, call the
provider directly as `prompt-chaining` does. If the pattern genuinely needs several
providers behind one client, per-step model routing, or one request log across the run,
add a `bifrost` service — copy it from
[`apps/bifrost-gateway`](../apps/bifrost-gateway/README.md), which exists for exactly that.

`settings.py`, `llm.py` and `console.py` are copied verbatim between apps. That is not an
oversight — it is the cost of an app being liftable, and it is a few dozen lines.

## 2. Rename the package

The directory name, the `src/<module>/` name, `[project].name`, `[project.scripts]`, the
`known-first-party` list in `[tool.ruff.lint.isort]`, and the `packages` list under
`[tool.hatch.build.targets.wheel]` all have to agree. Then:

```bash
cd apps/parallelization
uv sync --extra dev        # writes uv.lock — commit it
```

## 3. The compose file

Change `name:`, the image tag, and the `ENTRYPOINT` in the Dockerfile to the new console
script. If the app does add a `bifrost` service, give the demo service
`depends_on: {bifrost: {condition: service_healthy}}` — that is what stops it firing at a
gateway that is still booting.

The console script belongs in the Dockerfile's `ENTRYPOINT`, with `command: []` in compose.
`docker compose run` overrides `command` wholesale, so a script placed there would be
replaced by the first argument a user passes and the container would try to exec `--topic`.

Then, from the repository root:

```bash
mise run check parallelization
mise run demo parallelization
```

Nothing needs registering: `mise` and CI both discover apps by globbing `apps/*/`. An app
is any directory there with a `docker-compose.yaml`, and it additionally gets the Python
gates (ruff, mypy, pytest, bandit, pip-audit) if it has a `pyproject.toml` — so an
infrastructure-only app like `bifrost-gateway` is still validated, just not linted.

## 4. Add a Dependabot entry

`.github/dependabot.yml` needs one `uv` entry and one `docker` entry per app directory,
because there is no workspace root to watch. This is the one place a new app is named
explicitly.

## 5. Link it from the root README

Add a row to the apps table. An app nobody can find is an app nobody runs.

## House style

These are read more than they are run, so:

- **Model choice is configuration.** Read it from the environment and funnel every call
  through one `chat_model()` factory, so re-pointing the app never means editing the graph.
- **Keep non-LLM work in plain Python nodes.** Validation, assembly and routing belong in
  functions that a test can call without a network. Every app should have real tests that
  run in CI, and that is what makes it possible.
- **One prompt per step, in `prompts.py`.** The point of these patterns is that each step
  has a small, inspectable scope; that is much easier to see when the prompts sit together.
- **Say why, not what, in comments.** The code says what it does. Comments are for the
  decision behind it — why this step is split out, why this gate exists, why this model.
- **Narrate the run.** Use `step()` and `panel()` so the reader can watch the pattern
  happen.
- **Take keys from the environment, never from a file at run time,** and type them as
  pydantic `SecretStr` so a traceback cannot print one. See [secrets.md](secrets.md).
- **Build the graph without a credential.** Read settings inside the nodes, not in
  `build_graph()`. That is what lets the tests compile the graph and drive its non-LLM
  nodes with no key at all, which is what keeps CI offline.
