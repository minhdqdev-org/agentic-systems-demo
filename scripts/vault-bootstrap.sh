#!/usr/bin/env bash
# One-time setup: put the demo's provider keys into Vault, and create the read policy and
# AppRole that scripts/with-secrets.sh uses non-interactively.
#
#   scripts/vault-bootstrap.sh                         # prompts for each key
#   GEMINI_API_KEY=... OPENROUTER_API_KEY=... scripts/vault-bootstrap.sh --from-env
#
# Requires a Vault token with write access (an operator token, not the demo's read-only
# AppRole). Idempotent: safe to re-run to rotate a key.

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-https://vault.internal.minhdq.dev}"
VAULT_SECRET_PATH="${VAULT_SECRET_PATH:-kv/minhdqdev/dev/agentic-systems-demo}"
POLICY_NAME="${POLICY_NAME:-agentic-systems-demo-reader}"
APPROLE_NAME="${APPROLE_NAME:-agentic-systems-demo}"
export VAULT_ADDR

die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m==>\033[0m %s\n' "$*"; }

command -v vault >/dev/null 2>&1 || die "vault CLI not found"
vault token lookup >/dev/null 2>&1 || die "not authenticated to $VAULT_ADDR — run 'vault login' first"

# `kv/data/...` is the KV-v2 read path; `kv/...` is what the CLI takes. Both appear below
# and they are not interchangeable -- the policy needs the `data/` form.
DATA_PATH="${VAULT_SECRET_PATH/#kv\//kv/data/}"

if [[ "${1:-}" == "--from-env" ]]; then
  : "${GEMINI_API_KEY:?--from-env needs GEMINI_API_KEY exported}"
  : "${OPENROUTER_API_KEY:?--from-env needs OPENROUTER_API_KEY exported}"
else
  # `-s` so the key never lands in the terminal scrollback or shell history.
  read -rsp "GEMINI_API_KEY: " GEMINI_API_KEY; echo
  read -rsp "OPENROUTER_API_KEY: " OPENROUTER_API_KEY; echo
  [[ -n "$GEMINI_API_KEY" && -n "$OPENROUTER_API_KEY" ]] || die "both keys are required"
fi

info "writing $VAULT_SECRET_PATH"
vault kv put "$VAULT_SECRET_PATH" \
  GEMINI_API_KEY="$GEMINI_API_KEY" \
  OPENROUTER_API_KEY="$OPENROUTER_API_KEY" >/dev/null

info "writing policy $POLICY_NAME"
vault policy write "$POLICY_NAME" - <<POLICY >/dev/null
path "$DATA_PATH" {
  capabilities = ["read"]
}
POLICY

info "ensuring the approle auth method is enabled"
vault auth list -format=json | grep -q '"approle/"' || vault auth enable approle >/dev/null

info "writing approle $APPROLE_NAME"
vault write "auth/approle/role/$APPROLE_NAME" \
  token_policies="$POLICY_NAME" \
  token_ttl=1h \
  token_max_ttl=4h \
  secret_id_num_uses=0 >/dev/null

ROLE_ID="$(vault read -field=role_id "auth/approle/role/$APPROLE_NAME/role-id")"

cat <<SUMMARY

Done.

  secret   $VAULT_SECRET_PATH
  policy   $POLICY_NAME  (read on $DATA_PATH)
  approle  $APPROLE_NAME
  role_id  $ROLE_ID

On this machine nothing more is needed -- 'vault login' leaves a token in ~/.vault-token
and scripts/with-secrets.sh picks it up.

For a machine that cannot log in interactively (CI, a runner), mint a secret_id and hand
the pair over as VAULT_ROLE_ID / VAULT_SECRET_ID:

  vault write -field=secret_id -f auth/approle/role/$APPROLE_NAME/secret-id

For a Kubernetes workload, create a k8s auth role bound to its service account instead of
using an AppRole, and let the Vault Agent injector template the file -- see docs/secrets.md.
SUMMARY
