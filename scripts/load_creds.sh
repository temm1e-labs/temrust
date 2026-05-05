#!/bin/bash
# Source this from any script that needs credentials.
# All four env files live at ~/.config/temllm/ with chmod 600.
# Never commit these files; never echo their values.

CREDS_DIR="${HOME}/.config/temllm"

if [ ! -d "$CREDS_DIR" ]; then
    echo "ERROR: ${CREDS_DIR} does not exist. See AUTOMATION.md §1." >&2
    return 1 2>/dev/null || exit 1
fi

for f in hf.env together.env gh.env runpod.env; do
    if [ ! -f "${CREDS_DIR}/${f}" ]; then
        echo "ERROR: missing ${CREDS_DIR}/${f}" >&2
        return 1 2>/dev/null || exit 1
    fi
    set -a
    source "${CREDS_DIR}/${f}"
    set +a
done

# Sanity check that everything got set without echoing values
[ -z "$HF_TOKEN" ]          && { echo "ERROR: HF_TOKEN not set" >&2; return 1 2>/dev/null || exit 1; }
[ -z "$TOGETHER_API_KEY" ]  && { echo "ERROR: TOGETHER_API_KEY not set" >&2; return 1 2>/dev/null || exit 1; }
[ -z "$GH_TOKEN" ]          && { echo "ERROR: GH_TOKEN not set" >&2; return 1 2>/dev/null || exit 1; }
[ -z "$RUNPOD_API_KEY" ]    && { echo "ERROR: RUNPOD_API_KEY not set" >&2; return 1 2>/dev/null || exit 1; }
