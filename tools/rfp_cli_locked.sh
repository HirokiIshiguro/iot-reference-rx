#!/bin/sh
set -eu

LOCK_DIR="${RFP_CLI_LOCK_DIR:-${RX72N_RFP_CLI_LOCK_DIR:-/tmp/rx72n-e2lite-rfp-cli.lock.d}}"
LOCK_FILE="${LOCK_DIR}/rfp-cli.lock"
REAL_RFP_CLI="${REAL_RFP_CLI:-${RX72N_REAL_RFP_CLI:-rfp-cli}}"

if [ -e "$LOCK_FILE.unsafe.json" ] || [ -L "$LOCK_FILE.unsafe.json" ]; then
    echo "RFP termination is unverified; manual recovery is required" >&2
    exit 1
fi

umask 000
mkdir -p "$LOCK_DIR"
chmod 1777 "$LOCK_DIR" 2>/dev/null || true
: >> "$LOCK_FILE"
chmod 666 "$LOCK_FILE" 2>/dev/null || true

# Keep flock's supervising parent and recheck after waiting for the lock.
# This also protects after_script callers when before_script rejected reuse.
exec flock "$LOCK_FILE" sh -c '
    lock_file=$1
    shift
    if [ -e "$lock_file.unsafe.json" ] || [ -L "$lock_file.unsafe.json" ]; then
        echo "RFP termination is unverified; manual recovery is required" >&2
        exit 1
    fi
    exec "$@"
' sh "$LOCK_FILE" "$REAL_RFP_CLI" "$@"
