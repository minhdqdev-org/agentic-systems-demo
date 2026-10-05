#!/usr/bin/env bash
# Run a command with the demo's provider API keys in its environment, and nowhere else.
#
#   scripts/with-secrets.sh docker compose -f demos/01-prompt-chaining/compose.yaml up
#
# The keys are exported into this process, inherited by the command, and gone when it
# exits. With the `vault` backend they never touch the filesystem at all -- which is the
# point: a `.env` file that outlives the session it was made for is the thing we are
# avoiding. See docs/secrets.md.
#
# Backend is chosen by SECRETS_BACKEND:
#   vault   (default when a Vault token is available) -- read from HashiCorp Vault
#   dotenv  -- source ./.env from the repo root
#   env     -- assume the keys are already exported (CI, or you sourced something yourself)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

VAULT_ADDR="${VAULT_ADDR:-https://vault.internal.minhdq.dev}"
VAULT_SECRET_PATH="${VAULT_SECRET_PATH:-kv/minhdqdev/dev/agentic-systems-demo}"
export VAULT_ADDR

# Keys the demos need. Add to this list when a demo adds a provider, and keep
# infra/bifrost/config.json's `env.*` references in step with it.
REQUIRED_KEYS=(GEMINI_API_KEY OPENROUTER_API_KEY)

die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
note() { printf '\033[2m%s\033[0m\n' "$*" >&2; }

have_vault_auth() {
  [[ -n "${VAULT_TOKEN:-}" ]] || [[ -f "${HOME}/.vault-token" ]] \
    || { [[ -n "${VAULT_ROLE_ID:-}" ]] && [[ -n "${VAULT_SECRET_ID:-}" ]]; }
}

pick_backend() {
  if [[ -n "${SECRETS_BACKEND:-}" ]]; then
    echo "$SECRETS_BACKEND"
  elif command -v vault >/dev/null 2>&1 && have_vault_auth; then
    echo vault
  elif [[ -f "$REPO_ROOT/.env" ]]; then
    echo dotenv
  else
    echo env
  fi
}

load_vault() {
  command -v vault >/dev/null 2>&1 || die "vault CLI not found — install it, or use SECRETS_BACKEND=dotenv"
  command -v jq >/dev/null 2>&1 || die "jq not found — needed to parse the Vault response"

  # AppRole login for non-interactive callers (CI, a runner). An operator on a workstation
  # already has ~/.vault-token from `vault login`, and skips this.
  if [[ -z "${VAULT_TOKEN:-}" && -n "${VAULT_ROLE_ID:-}" && -n "${VAULT_SECRET_ID:-}" ]]; then
    VAULT_TOKEN="$(vault write -field=token auth/approle/login \
      role_id="$VAULT_ROLE_ID" secret_id="$VAULT_SECRET_ID")" \
      || die "AppRole login failed against $VAULT_ADDR"
    export VAULT_TOKEN
  fi

  note "secrets: vault ($VAULT_ADDR :: $VAULT_SECRET_PATH)"

  local json
  json="$(vault kv get -format=json "$VAULT_SECRET_PATH")" \
    || die "could not read $VAULT_SECRET_PATH — run scripts/vault-bootstrap.sh, or check your token"

  local key value
  for key in "${REQUIRED_KEYS[@]}"; do
    value="$(jq -r --arg k "$key" '.data.data[$k] // empty' <<<"$json")"
    [[ -n "$value" ]] || die "$VAULT_SECRET_PATH has no key '$key' — see docs/secrets.md"
    export "$key=$value"
  done
}

load_dotenv() {
  local env_file="$REPO_ROOT/.env"
  [[ -f "$env_file" ]] || die "$env_file not found — copy .env.example, or use the vault backend"
  note "secrets: dotenv ($env_file)"
  # `set -a` exports everything the file defines; the subshell keeps `set -a` from
  # leaking into the command we exec.
  set -a
  # shellcheck disable=SC1090
  source "$env_file"
  set +a
}

check_present() {
  local key missing=()
  for key in "${REQUIRED_KEYS[@]}"; do
    [[ -n "${!key:-}" ]] || missing+=("$key")
  done
  (( ${#missing[@]} == 0 )) || die "missing from the environment: ${missing[*]} — see docs/secrets.md"
}

[[ $# -gt 0 ]] || die "usage: scripts/with-secrets.sh <command> [args...]"

backend="$(pick_backend)"

# When a backend is going to supply the keys, clear whatever is already in the environment
# first. Plenty of shells export a `GEMINI_API_KEY` from a profile, and without this a key
# the chosen backend does not actually have would be silently filled in from that -- so
# you would be running against a credential the backend never provided, and `check_present`
# would say everything is fine. Failing loudly is the point of having a backend at all.
if [[ "$backend" != env ]]; then
  unset "${REQUIRED_KEYS[@]}"
fi

case "$backend" in
  vault)  load_vault ;;
  dotenv) load_dotenv ;;
  env)    note "secrets: env (assuming the keys are already exported)" ;;
  *)      die "unknown SECRETS_BACKEND '${SECRETS_BACKEND:-}' — use vault, dotenv or env" ;;
esac

check_present
exec "$@"
