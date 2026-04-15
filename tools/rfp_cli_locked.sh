#!/bin/sh
set -eu

LOCK_FILE="${RX72N_RFP_CLI_LOCK_FILE:-/tmp/rx72n-e2lite-rfp-cli.lock}"
REAL_RFP_CLI="${RX72N_REAL_RFP_CLI:-rfp-cli}"

exec flock "$LOCK_FILE" "$REAL_RFP_CLI" "$@"
