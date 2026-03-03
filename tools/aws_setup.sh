#!/bin/bash
# =============================================================
# AWS IoT Core setup for iot-reference-rx (CK-RX65N)
#
# Prerequisites:
#   - AWS CLI installed and configured (aws configure)
#   - IAM user with IoT admin permissions
#
# Usage:
#   ./tools/aws_setup.sh [THING_NAME] [POLICY_NAME]
#
# This script:
#   1. Creates an IoT Thing
#   2. Generates certificate + private key
#   3. Creates an IoT Policy
#   4. Attaches policy to certificate
#   5. Attaches certificate to thing
#   6. Outputs the endpoint URL
#
# Output files are saved to certs/ directory.
# =============================================================

set -euo pipefail

# Detect python command (python3 on Linux/macOS, python on Windows)
if command -v python3 &>/dev/null; then
    PYTHON=python3
else
    PYTHON=python
fi

THING_NAME="${1:-ck-rx65n-01}"
POLICY_NAME="${2:-ck-rx65n-policy}"
CERTS_DIR="certs"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
POLICY_FILE="${SCRIPT_DIR}/iot_policy.json"

echo "============================================================"
echo "AWS IoT Core Setup"
echo "============================================================"
echo "Thing Name:  ${THING_NAME}"
echo "Policy Name: ${POLICY_NAME}"
echo "Certs Dir:   ${CERTS_DIR}"
echo "============================================================"

# Create output directory
mkdir -p "${CERTS_DIR}"

# --- Step 1: Create Thing ---
echo ""
echo "=== Step 1: Create Thing ==="
aws iot create-thing --thing-name "${THING_NAME}" || {
    echo "WARNING: Thing may already exist. Continuing..."
}
echo "Thing created: ${THING_NAME}"

# --- Step 2: Create certificate + keys ---
echo ""
echo "=== Step 2: Create certificate and keys ==="
CERT_OUTPUT=$(aws iot create-keys-and-certificate \
    --set-as-active \
    --certificate-pem-outfile "${CERTS_DIR}/${THING_NAME}-cert.pem" \
    --private-key-outfile "${CERTS_DIR}/${THING_NAME}-privkey.pem" \
    --public-key-outfile "${CERTS_DIR}/${THING_NAME}-pubkey.pem")

CERT_ARN=$(echo "${CERT_OUTPUT}" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['certificateArn'])")
CERT_ID=$(echo "${CERT_OUTPUT}" | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['certificateId'])")

echo "Certificate ARN: ${CERT_ARN}"
echo "Certificate ID:  ${CERT_ID}"
echo "Files saved:"
echo "  - ${CERTS_DIR}/${THING_NAME}-cert.pem"
echo "  - ${CERTS_DIR}/${THING_NAME}-privkey.pem"
echo "  - ${CERTS_DIR}/${THING_NAME}-pubkey.pem"

# --- Step 3: Create IoT Policy ---
echo ""
echo "=== Step 3: Create IoT Policy ==="
if [ ! -f "${POLICY_FILE}" ]; then
    echo "ERROR: Policy file not found: ${POLICY_FILE}"
    exit 1
fi
aws iot create-policy \
    --policy-name "${POLICY_NAME}" \
    --policy-document "file://${POLICY_FILE}" || {
    echo "WARNING: Policy may already exist. Continuing..."
}
echo "Policy created: ${POLICY_NAME}"

# --- Step 4: Attach policy to certificate ---
echo ""
echo "=== Step 4: Attach policy to certificate ==="
aws iot attach-policy \
    --policy-name "${POLICY_NAME}" \
    --target "${CERT_ARN}"
echo "Policy attached to certificate"

# --- Step 5: Attach certificate to thing ---
echo ""
echo "=== Step 5: Attach certificate to thing ==="
aws iot attach-thing-principal \
    --thing-name "${THING_NAME}" \
    --principal "${CERT_ARN}"
echo "Certificate attached to thing"

# --- Step 6: Get endpoint ---
echo ""
echo "=== Step 6: Get IoT endpoint ==="
ENDPOINT=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS \
    | $PYTHON -c "import sys,json; print(json.load(sys.stdin)['endpointAddress'])")
echo "Endpoint: ${ENDPOINT}"

# --- Summary ---
echo ""
echo "============================================================"
echo "AWS IoT Core Setup Complete"
echo "============================================================"
echo ""
echo "Thing Name:      ${THING_NAME}"
echo "Policy Name:     ${POLICY_NAME}"
echo "Certificate ARN: ${CERT_ARN}"
echo "Certificate ID:  ${CERT_ID}"
echo "Endpoint:        ${ENDPOINT}"
echo ""
echo "Next steps:"
echo "  1. Register CI/CD Variables in iot-reference-rx project:"
echo "     AWS_IOT_ENDPOINT  = ${ENDPOINT}"
echo "     AWS_IOT_THING_NAME = ${THING_NAME}"
echo "     AWS_IOT_CERT       = (File) ${CERTS_DIR}/${THING_NAME}-cert.pem"
echo "     AWS_IOT_PRIVKEY    = (File) ${CERTS_DIR}/${THING_NAME}-privkey.pem"
echo ""
echo "  2. Provision device via UART:"
echo "     python tools/provision.py --port COM9 --baud 115200 \\"
echo "       --thing-name ${THING_NAME} \\"
echo "       --endpoint ${ENDPOINT} \\"
echo "       --cert ${CERTS_DIR}/${THING_NAME}-cert.pem \\"
echo "       --key ${CERTS_DIR}/${THING_NAME}-privkey.pem"
echo "============================================================"
