param(
    [string]$ProjectRoot = $(if ($env:CI_PROJECT_DIR) { $env:CI_PROJECT_DIR } else { (Resolve-Path ".").Path }),
    [string]$ProjectName = "aws_ether_rx72n_envision_kit_tsip"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# The former experiment copied software Mbed TLS 3.6.4 over the TSIP gitlink
# and rewrote ssl_tls13_generic.c in the consumer. Keep all sources unchanged.
# A future TSIP 0-RTT implementation must live in the purpose-specific fork
# and be referenced by a reviewed fixed submodule commit.
throw 'TSIP 0-RTT is unavailable with the common 3.2.1 backend. Consumer-side OSS copies and patches are prohibited. Implement and verify it in the TSIP Mbed TLS fork before enabling this option.'
