---
title: "Bifrost gateway"
slug: bifrost-gateway
updated_at: 2026-09-02T13:35:00+07:00
tags:
  - bifrost
  - llm-gateway
---

# Bifrost gateway

An [LLM gateway](https://github.com/maximhq/bifrost) — one OpenAI-shaped endpoint in front
of several providers. **There is no demo code here yet**; this app is the gateway itself,
ready for the pattern that needs it.

```bash
mise run gateway bifrost-gateway     # start it
mise run demo-down bifrost-gateway   # stop it
```

Then <http://localhost:8080> is the UI and request log, and
`http://localhost:8080/openai/v1/chat/completions` is an OpenAI-compatible endpoint.

```bash
curl -s http://localhost:8080/openai/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"gemini/gemini-3.5-flash-lite","messages":[{"role":"user","content":"say ok"}]}'
```

## Why it is not in `prompt-chaining`

Prompt chaining runs every step on a single Gemini model, so it calls Google directly. A
gateway it never routes through would be a second moving part in a demo about prompt
structure — you would be reading Docker plumbing to learn about prompts.

The gateway earns its place the moment a demo actually needs one of these:

- **Several providers behind one client.** Model ids are `provider/model`, so
  `gemini/gemini-3.5-flash-lite` and `openrouter/anthropic/claude-sonnet-4.5` are the same
  API call with a different string. No second SDK.
- **Per-step model routing.** A cheap model for a chain's structural steps and a strong one
  for its prose becomes two env vars rather than two clients.
- **Credential containment.** The keys live in this container. Nothing that talks to the
  gateway holds one.
- **One request log across a whole run.** Every call, with model, token count, cost and
  latency, in one place — which is how you see where a multi-step run actually spends.

## Configuration

`config.json` is the source of truth. The gateway runs with `config_store.enabled: false`,
so it re-reads the file on every start and UI edits are not persisted — change the file,
`docker compose restart bifrost`, and the change is live.

Providers are declared there with `"value": "env.GEMINI_API_KEY"`-style references; the
compose file passes those two variables in from
[`scripts/with-secrets.sh`](../../docs/secrets.md). Both currently allow `"models": ["*"]`.

## When you build the demo here

Add the usual app files alongside what is here — `pyproject.toml`, `Dockerfile`,
`src/<module>/`, `tests/` — and a `demo` service to `docker-compose.yaml` with
`depends_on: {bifrost: {condition: service_healthy}}` and
`GATEWAY_BASE_URL: http://bifrost:8080/openai`. Point a `ChatOpenAI` at that URL with any
non-empty `api_key` (the gateway runs with `enforce_auth_on_inference: false`).

See [docs/adding-an-app.md](../../docs/adding-an-app.md).
