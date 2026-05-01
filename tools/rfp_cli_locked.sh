#!/bin/sh
set -eu

LOCK_DIR="${RFP_CLI_LOCK_DIR:-${RX72N_RFP_CLI_LOCK_DIR:-/tmp/rx72n-e2lite-rfp-cli.lock.d}}"
LOCK_FILE="${LOCK_DIR}/rfp-cli.lock"
REAL_RFP_CLI="${REAL_RFP_CLI:-${RX72N_REAL_RFP_CLI:-rfp-cli}}"

umask 000
mkdir -p "$LOCK_DIR"
chmod 1777 "$LOCK_DIR" 2>/dev/null || true
: >> "$LOCK_FILE"
chmod 666 "$LOCK_FILE" 2>/dev/null || true

exec flock "$LOCK_FILE" "$REAL_RFP_CLI" "$@"
