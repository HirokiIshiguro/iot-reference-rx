#!/bin/bash
set -euxo pipefail

PORT=5443
MBEDTLS_REPO_URL="https://gitlab.saffti.jp/oss/import/github/mbed-tls/mbedtls.git"
MBEDTLS_REF="v3.6.4"
MBEDTLS_DIR="/opt/lanbench-mbedtls-0rtt"
SERVICE_NAME="lanbench-tls13-0rtt"

dnf install -y git gcc make perl python3 diffutils

if [ ! -d "${MBEDTLS_DIR}/.git" ]; then
    rm -rf "${MBEDTLS_DIR}"
    git clone --depth 1 --branch "${MBEDTLS_REF}" --recursive "${MBEDTLS_REPO_URL}" "${MBEDTLS_DIR}"
fi

cd "${MBEDTLS_DIR}"
git fetch --depth 1 origin "refs/tags/${MBEDTLS_REF}:refs/tags/${MBEDTLS_REF}" || true
git checkout --detach "${MBEDTLS_REF}"
git submodule update --init --depth 1 framework

if ! grep -q '^#define MBEDTLS_SSL_EARLY_DATA' include/mbedtls/mbedtls_config.h; then
    python3 scripts/config.py set MBEDTLS_SSL_EARLY_DATA
fi

make -j2 programs/ssl/ssl_server2

cat >/etc/systemd/system/${SERVICE_NAME}.service <<UNIT
[Unit]
Description=LANBENCH Mbed TLS 1.3 resumption and 0-RTT server
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${MBEDTLS_DIR}
ExecStart=${MBEDTLS_DIR}/programs/ssl/ssl_server2 server_port=${PORT} min_version=tls13 max_version=tls13 early_data=1 max_early_data_size=1024 exchanges=1 tickets=1 auth_mode=optional ca_file=none debug_level=2
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable --now ${SERVICE_NAME}.service
