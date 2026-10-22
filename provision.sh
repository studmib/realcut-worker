#!/bin/bash
# First start of a 리얼컷 serverless worker. vast's base image runs this once (PROVISIONING_SCRIPT, pinned to a
# commit of this public repo) before the PyWorker starts; a worker woken up again skips it.
#   1. the private 리얼컷 code, read with a read-only GitHub token (never written to disk or a command line)
#   2. ComfyUI x2, the Python venvs and the 24 models: deploy/vast/setup.sh in its worker role
# From the vast account's environment variables: REALCUT_GIT_TOKEN (fine-grained token, contents:read on the
# private repo only), CIVITAI_TOKEN (2 models need it). From the template: REALCUT_REPO, REALCUT_REF.
set -euo pipefail

W=${WORKSPACE:-/workspace}
R=$W/realcut
: "${REALCUT_GIT_TOKEN:?REALCUT_GIT_TOKEN is missing (vast account -> Environment Variables)}"
: "${REALCUT_REPO:?REALCUT_REPO is missing (template)}"
REF=${REALCUT_REF:-main}

# git reads the token from the environment (GIT_CONFIG_*), so it is not in ps, .git/config or the log
auth=$(printf 'x-access-token:%s' "$REALCUT_GIT_TOKEN" | base64 -w0)
export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.https://github.com/.extraheader
export GIT_CONFIG_VALUE_0="AUTHORIZATION: basic $auth"
export GIT_TERMINAL_PROMPT=0
[ -d "$R/.git" ] || git clone -q "$REALCUT_REPO" "$R"
git -C "$R" fetch -q origin "$REF"
git -C "$R" checkout -q --detach FETCH_HEAD
unset GIT_CONFIG_COUNT GIT_CONFIG_KEY_0 GIT_CONFIG_VALUE_0 auth
echo "realcut code: $(git -C "$R" rev-parse --short HEAD)"

# the base image runs this with its own /venv/main (Python 3.11) active: the system's 3.12 makes the venvs
PY=$(command -v /usr/bin/python3.12 || command -v /usr/bin/python3)
REALCUT_ROLE=worker REALCUT_WORKSPACE=$W REALCUT_PYTHON=$PY bash "$R/deploy/vast/setup.sh"

# a worker without every model would fail each batch: fail the provisioning instead (vast marks it)
missing=$(bash "$R/deploy/vast/download_models.sh" | grep -c "PC에서 올릴 파일\|실패" || true)
if [ "$missing" != 0 ]; then
  echo "models missing: $missing" >&2
  exit 1
fi
echo "realcut worker ready"
