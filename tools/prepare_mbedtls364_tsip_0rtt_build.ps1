param(
    [string]$ProjectRoot = $(if ($env:CI_PROJECT_DIR) { $env:CI_PROJECT_DIR } else { (Resolve-Path ".").Path }),
    [string]$ProjectName = "aws_ether_rx72n_envision_kit_tsip"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = (Resolve-Path $ProjectRoot).Path
$projectDir = Join-Path $projectRoot "Projects\$ProjectName\e2studio_ccrx"
if (-not (Test-Path -LiteralPath $projectDir)) {
    throw "TSIP project directory is missing: $projectDir"
}

$cproject = Join-Path $projectDir ".cproject"
$projectFile = Join-Path $projectDir ".project"
$projectLocalStagedMbedtls = Join-Path $projectDir "Middleware/3rdparty/mbedtls_with_TSIP"
$normalMbedtls = Join-Path $projectRoot "Middleware/3rdparty/mbedtls"
$stagedMbedtls = if (Test-Path -LiteralPath (Split-Path -Parent $projectLocalStagedMbedtls)) {
    $projectLocalStagedMbedtls
} else {
    Join-Path $projectRoot "Middleware/3rdparty/mbedtls_with_TSIP"
}

if (-not (Test-Path -LiteralPath $normalMbedtls)) {
    throw "Normal Mbed TLS submodule is missing: $normalMbedtls"
}
if (-not (Test-Path -LiteralPath $cproject)) {
    throw ".cproject is missing: $cproject"
}
if (-not (Test-Path -LiteralPath $projectFile)) {
    throw ".project is missing: $projectFile"
}

Write-Host "Staging normal Mbed TLS 3.6.x into mbedtls_with_TSIP path for TSIP 0-RTT build."
Write-Host "  source: $normalMbedtls"
Write-Host "  staged: $stagedMbedtls"
New-Item -ItemType Directory -Force -Path $stagedMbedtls | Out-Null
robocopy $normalMbedtls $stagedMbedtls /MIR /XD .git /XF .git | Out-Host
if ($LASTEXITCODE -ge 8) {
    throw "robocopy failed while staging normal Mbed TLS with exit code $LASTEXITCODE"
}
$global:LASTEXITCODE = 0

function Add-CompilerDefine {
    param(
        [string] $Text,
        [string] $Define,
        [string] $Anchor
    )

    if ($Text -match [regex]::Escape($Define)) {
        return $Text
    }

    $insert = $Anchor + "`r`n" + "`t`t`t`t`t`t`t`t`t<listOptionValue builtIn=`"false`" value=`"$Define`"/>"
    return $Text.Replace($Anchor, $insert)
}

function Set-LanbenchZeroRttHost {
    param(
        [string] $ProjectRoot,
        [string] $HostName
    )

    if ([string]::IsNullOrWhiteSpace($HostName)) {
        return
    }
    if ($HostName -notmatch '^[A-Za-z0-9._-]+$') {
        throw "LANBENCH_MBEDTLS_0RTT_HOST contains unsupported characters: $HostName"
    }

    $sourcePaths = @(
        (Join-Path $ProjectRoot "Demos/include/lanbench_tls13_0rtt_config.h"),
        (Join-Path $ProjectRoot "Demos/lanbench_tls13_0rtt/tls13_0rtt_smoke.c")
    )
    $pattern = '(?m)^(\s*#define\s+LANBENCH_TLS13_0RTT_HOST\s+)"[^"]+"'

    foreach ($sourcePath in $sourcePaths) {
        if (-not (Test-Path -LiteralPath $sourcePath)) {
            throw "0-RTT smoke source is missing: $sourcePath"
        }

        $sourceText = Get-Content -LiteralPath $sourcePath -Raw
        $replacement = "`${1}`"$HostName`""
        if ($sourceText -notmatch $pattern) {
            throw "LANBENCH_TLS13_0RTT_HOST default macro not found in $sourcePath"
        }

        $sourceText = [regex]::Replace($sourceText, $pattern, $replacement, 1)
        Set-Content -LiteralPath $sourcePath -Value $sourceText -Encoding UTF8
    }
}

$text = Get-Content -LiteralPath $cproject -Raw

$text = $text.Replace(
    'MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_with_tsip.h&quot;&gt;',
    'MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_with_tsip13_0rtt.h&quot;&gt;'
)
$text = $text.Replace(
    'MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_with_tsip13.h&quot;&gt;',
    'MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_with_tsip13_0rtt.h&quot;&gt;'
)

$configAnchor = '<listOptionValue builtIn="false" value="MBEDTLS_CONFIG_FILE=&lt;&quot;aws_mbedtls_config_with_tsip13_0rtt.h&quot;&gt;"/>'
if (-not $text.Contains($configAnchor)) {
    throw "TSIP 0-RTT mbed TLS config macro not found in $cproject"
}
$text = Add-CompilerDefine -Text $text -Define 'LANBENCH_TLS13_0RTT_ENABLE=1' -Anchor $configAnchor
$text = Add-CompilerDefine -Text $text -Define 'LANBENCH_TLS13_0RTT_TSIP_ENABLE=1' -Anchor $configAnchor

$lanbenchPort = if ($env:LANBENCH_MBEDTLS_0RTT_PORT) { $env:LANBENCH_MBEDTLS_0RTT_PORT } else { "" }
if (-not [string]::IsNullOrWhiteSpace($lanbenchPort)) {
    if ($lanbenchPort -notmatch '^\d+$') {
        throw "LANBENCH_MBEDTLS_0RTT_PORT must be numeric: $lanbenchPort"
    }
    $text = Add-CompilerDefine -Text $text -Define "LANBENCH_TLS_PORT=${lanbenchPort}U" -Anchor $configAnchor
}

$lanbenchHost = if ($env:LANBENCH_MBEDTLS_0RTT_HOST) { $env:LANBENCH_MBEDTLS_0RTT_HOST } else { "" }
Set-LanbenchZeroRttHost -ProjectRoot $projectRoot -HostName $lanbenchHost

$text = $text.Replace(
    'Middleware/network_transport/using_mbedtls_pkcs11/transport_mbedtls_pkcs11.c',
    'Middleware/network_transport/using_mbedtls_pkcs11_with_tsip/transport_mbedtls_pkcs11_with_tsip.c'
)

$text = $text.Replace(
    '.\Middleware/network_transport/using_mbedtls_pkcs11_with_tsip\transport_mbedtls_pkcs11_with_tsip.obj',
    '.\Middleware/network_transport/using_mbedtls_pkcs11\transport_mbedtls_pkcs11.obj'
)

$text = $text.Replace(
    '.\Middleware/3rdparty/mbedtls_with_TSIP/library\psa_crypto_driver_wrappers.obj',
    '.\Middleware/3rdparty/mbedtls_with_TSIP/library\psa_crypto_driver_wrappers_no_static.obj'
)

$extraObjects = @(
    'aesce',
    'ecp_curves_new',
    'pk_ecc',
    'pkcs7',
    'psa_crypto_ffdh',
    'psa_crypto_pake',
    'psa_util',
    'sha3',
    'x509write'
)

$anchorLine = '<listOptionValue builtIn="false" value="&quot;.\Middleware/3rdparty/mbedtls_with_TSIP/library\ripemd160.obj&quot;"/>'
$extraLines = foreach ($obj in $extraObjects) {
    "`t`t`t`t`t`t`t`t`t<listOptionValue builtIn=`"false`" value=`"&quot;.\Middleware/3rdparty/mbedtls_with_TSIP/library\$obj.obj&quot;`"/>"
}

foreach ($obj in $extraObjects) {
    if ($text -notmatch [regex]::Escape("mbedtls_with_TSIP/library\$obj.obj")) {
        $text = $text.Replace($anchorLine, (($extraLines -join "`r`n") + "`r`n" + "`t`t`t`t`t`t`t`t`t" + $anchorLine))
        break
    }
}

Set-Content -LiteralPath $cproject -Value $text -Encoding UTF8

$projectText = Get-Content -LiteralPath $projectFile -Raw
$projectText = [regex]::Replace(
    $projectText,
    '(?s)\r?\n\t\t<filter>\r?\n\t\t\t<id>\d+</id>\r?\n\t\t\t<name>Middleware/network_transport/using_mbedtls_pkcs11</name>\r?\n\t\t\t<type>6</type>\r?\n\t\t\t<matcher>\r?\n\t\t\t\t<id>org\.eclipse\.ui\.ide\.multiFilter</id>\r?\n\t\t\t\t<arguments>1\.0-name-matches-false-true-transport_mbedtls_pkcs11\.c\|transport_mbedtls_pkcs11\.h</arguments>\r?\n\t\t\t</matcher>\r?\n\t\t</filter>',
    ''
)
Set-Content -LiteralPath $projectFile -Value $projectText -Encoding UTF8

$sslTls13Generic = Join-Path $stagedMbedtls "library/ssl_tls13_generic.c"
$sslText = Get-Content -LiteralPath $sslTls13Generic -Raw

function Convert-NewLine {
    param(
        [string] $Text,
        [string] $NewLine
    )

    return (($Text -replace "`r`n", "`n") -replace "`r", "`n") -replace "`n", $NewLine
}

function Replace-RequiredRegex {
    param(
        [string] $Text,
        [string] $Pattern,
        [string] $Replacement,
        [string] $ErrorMessage
    )

    $regex = [regex]::new($Pattern)
    if (-not $regex.IsMatch($Text)) {
        throw $ErrorMessage
    }

    return $regex.Replace(
        $Text,
        [System.Text.RegularExpressions.MatchEvaluator] { param($match) $Replacement },
        1)
}

if ($sslText -notmatch 'R_TSIP_Tls13CertificateVerifyGenerate') {
    $sslNewLine = if ($sslText.Contains("`r`n")) { "`r`n" } else { "`n" }

    $includeAnchor = '#include "psa_util_internal.h"'
    $includeBlock = @'

#if defined(TSIP_TLS_API_ENABLE)
#include <stdint.h>
#include <platform.h>
#include "r_tsip_rx_if.h"
#if defined(MBEDTLS_THREADING_C)
#include "mbedtls/threading.h"
extern mbedtls_threading_mutex_t mutexUseTsip;
#endif /* MBEDTLS_THREADING_C */
extern tsip_rsa2048_private_key_index_t rsa2048_private_key;
extern tsip_ecc_private_key_index_t eccp256_private_key;
extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateAttempts;
extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateCalls;
extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateFailures;
extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus;
extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateLastScheme;
extern volatile uint32_t gTsipTlsProbeTls13CertificateVerifyGenerateLastBytes;
#define SSL_TLS13_TSIP_CERT_VERIFY_MAX_SIZE (4 + 256)
#define SSL_TLS13_TSIP_CERT_VERIFY_SKIP_HASH_LEN       (0x54534831U)
#define SSL_TLS13_TSIP_CERT_VERIFY_SKIP_OWN_CERT       (0x54534f43U)
#define SSL_TLS13_TSIP_CERT_VERIFY_SKIP_UNSUPPORTED    (0x54535553U)
#define SSL_TLS13_TSIP_CERT_VERIFY_SKIP_CERT_KEY       (0x5453434bU)
#endif /* TSIP_TLS_API_ENABLE */
'@
    $sslText = $sslText.Replace($includeAnchor, $includeAnchor + (Convert-NewLine -Text $includeBlock -NewLine $sslNewLine))

    $parseAnchor = "MBEDTLS_CHECK_RETURN_CRITICAL`r`nstatic int ssl_tls13_parse_certificate_verify"
    if ($sslText -notmatch [regex]::Escape($parseAnchor)) {
        $parseAnchor = "MBEDTLS_CHECK_RETURN_CRITICAL`nstatic int ssl_tls13_parse_certificate_verify"
    }
    $helperBlock = @'
#if defined(TSIP_TLS_API_ENABLE)
static int ssl_tls13_write_tsip_certificate_verify_body(mbedtls_ssl_context *ssl,
                                                        uint16_t algorithm,
                                                        const unsigned char *handshake_hash,
                                                        size_t handshake_hash_len,
                                                        unsigned char *buf,
                                                        unsigned char *end,
                                                        size_t *out_len,
                                                        int *handled)
{
    e_tsip_err_t tsip_ret;
    e_tsip_tls13_signature_scheme_type_t tsip_scheme;
    uint32_t *tsip_private_key_index = NULL;
    uint32_t tsip_certificate_verify_len = 0;
    const mbedtls_x509_crt *own_cert = mbedtls_ssl_own_cert(ssl);
    int ret = 0;

    *handled = 0;

    if (ssl->conf->endpoint != MBEDTLS_SSL_IS_CLIENT) {
        return 0;
    }

    gTsipTlsProbeTls13CertificateVerifyGenerateAttempts++;
    gTsipTlsProbeTls13CertificateVerifyGenerateLastScheme = (uint32_t) algorithm;
    gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = 0U;

    if (handshake_hash_len != R_TSIP_SHA256_HASH_LENGTH_BYTE_SIZE) {
        gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = SSL_TLS13_TSIP_CERT_VERIFY_SKIP_HASH_LEN;
        return 0;
    }

    if (own_cert == NULL) {
        gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = SSL_TLS13_TSIP_CERT_VERIFY_SKIP_OWN_CERT;
        return 0;
    }

    switch (algorithm) {
        case MBEDTLS_TLS1_3_SIG_RSA_PSS_RSAE_SHA256:
            if (!mbedtls_pk_can_do(&own_cert->pk, MBEDTLS_PK_RSA)) {
                gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = SSL_TLS13_TSIP_CERT_VERIFY_SKIP_CERT_KEY;
                return 0;
            }
            tsip_scheme = TSIP_TLS13_SIGNATURE_SCHEME_RSA_PSS_RSAE_SHA256;
            tsip_private_key_index = (uint32_t *) &rsa2048_private_key;
            break;

        case MBEDTLS_TLS1_3_SIG_ECDSA_SECP256R1_SHA256:
            if (!mbedtls_pk_can_do(&own_cert->pk, MBEDTLS_PK_ECDSA)) {
                gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = SSL_TLS13_TSIP_CERT_VERIFY_SKIP_CERT_KEY;
                return 0;
            }
            tsip_scheme = TSIP_TLS13_SIGNATURE_SCHEME_ECDSA_SECP256R1_SHA256;
            tsip_private_key_index = (uint32_t *) &eccp256_private_key;
            break;

        default:
            gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = SSL_TLS13_TSIP_CERT_VERIFY_SKIP_UNSUPPORTED;
            return 0;
    }

    MBEDTLS_SSL_CHK_BUF_PTR(buf, end, SSL_TLS13_TSIP_CERT_VERIFY_MAX_SIZE);

#if defined(MBEDTLS_THREADING_C)
    if ((ret = mbedtls_mutex_lock(&mutexUseTsip)) != 0) {
        return ret;
    }
#endif /* MBEDTLS_THREADING_C */

    gTsipTlsProbeTls13CertificateVerifyGenerateLastScheme = (uint32_t) tsip_scheme;

    tsip_ret = R_TSIP_Tls13CertificateVerifyGenerate(
        tsip_private_key_index,
        tsip_scheme,
        (uint8_t *) handshake_hash,
        buf,
        &tsip_certificate_verify_len);

#if defined(MBEDTLS_THREADING_C)
    mbedtls_mutex_unlock(&mutexUseTsip);
#endif /* MBEDTLS_THREADING_C */

    if (TSIP_SUCCESS != tsip_ret) {
        gTsipTlsProbeTls13CertificateVerifyGenerateFailures++;
        gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = (uint32_t) tsip_ret;
        MBEDTLS_SSL_DEBUG_MSG(1,
                              ("R_TSIP_Tls13CertificateVerifyGenerate failed: %d",
                               (int) tsip_ret));
        return MBEDTLS_ERR_SSL_HW_ACCEL_FAILED;
    }

    if (tsip_certificate_verify_len > SSL_TLS13_TSIP_CERT_VERIFY_MAX_SIZE) {
        gTsipTlsProbeTls13CertificateVerifyGenerateFailures++;
        gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = (uint32_t) MBEDTLS_ERR_SSL_BUFFER_TOO_SMALL;
        return MBEDTLS_ERR_SSL_BUFFER_TOO_SMALL;
    }

    gTsipTlsProbeTls13CertificateVerifyGenerateCalls++;
    gTsipTlsProbeTls13CertificateVerifyGenerateLastStatus = (uint32_t) TSIP_SUCCESS;
    gTsipTlsProbeTls13CertificateVerifyGenerateLastBytes = tsip_certificate_verify_len;

    *out_len = (size_t) tsip_certificate_verify_len;
    *handled = 1;
    return 0;
}
#endif /* TSIP_TLS_API_ENABLE */

'@
    $sslText = $sslText.Replace($parseAnchor, (Convert-NewLine -Text $helperBlock -NewLine $sslNewLine) + $parseAnchor)

    $loopReplacement = @'
    for (; *sig_alg != MBEDTLS_TLS1_3_SIG_NONE; sig_alg++) {
        psa_status_t status = PSA_ERROR_CORRUPTION_DETECTED;
        mbedtls_pk_type_t pk_type = MBEDTLS_PK_NONE;
        mbedtls_md_type_t md_alg = MBEDTLS_MD_NONE;
        psa_algorithm_t psa_algorithm = PSA_ALG_NONE;
        unsigned char verify_hash[PSA_HASH_MAX_SIZE];
        size_t verify_hash_len;
#if defined(TSIP_TLS_API_ENABLE)
        int tsip_cert_verify_handled = 0;
        size_t tsip_cert_verify_len = 0;
#endif /* TSIP_TLS_API_ENABLE */
'@
    $loopPattern = '    for \(; \*sig_alg != MBEDTLS_TLS1_3_SIG_NONE; sig_alg\+\+\) \{\r?\n' +
        '        psa_status_t status = PSA_ERROR_CORRUPTION_DETECTED;\r?\n' +
        '        mbedtls_pk_type_t pk_type = MBEDTLS_PK_NONE;\r?\n' +
        '        mbedtls_md_type_t md_alg = MBEDTLS_MD_NONE;\r?\n' +
        '        psa_algorithm_t psa_algorithm = PSA_ALG_NONE;\r?\n' +
        '        unsigned char verify_hash\[PSA_HASH_MAX_SIZE\];\r?\n' +
        '        size_t verify_hash_len;\r?\n'
    $sslText = Replace-RequiredRegex `
        -Text $sslText `
        -Pattern $loopPattern `
        -Replacement (Convert-NewLine -Text $loopReplacement -NewLine $sslNewLine) `
        -ErrorMessage "TLS 1.3 CertificateVerify loop anchor not found in $sslTls13Generic"

    $tsipCallBlock = @'
#if defined(TSIP_TLS_API_ENABLE)
        ret = ssl_tls13_write_tsip_certificate_verify_body(ssl,
                                                           *sig_alg,
                                                           handshake_hash,
                                                           handshake_hash_len,
                                                           p,
                                                           end,
                                                           &tsip_cert_verify_len,
                                                           &tsip_cert_verify_handled);
        if (ret != 0) {
            return ret;
        }
        if (tsip_cert_verify_handled != 0) {
            *out_len = tsip_cert_verify_len;
            return 0;
        }
#endif /* TSIP_TLS_API_ENABLE */

        if (!mbedtls_ssl_tls13_sig_alg_for_cert_verify_is_supported(*sig_alg)) {
            continue;
        }

'@
    $supportCheckPattern = '        if \(!mbedtls_ssl_tls13_sig_alg_for_cert_verify_is_supported\(\*sig_alg\)\) \{\r?\n' +
        '            continue;\r?\n' +
        '        \}\r?\n\r?\n'
    $sslText = Replace-RequiredRegex `
        -Text $sslText `
        -Pattern $supportCheckPattern `
        -Replacement (Convert-NewLine -Text $tsipCallBlock -NewLine $sslNewLine) `
        -ErrorMessage "TLS 1.3 CertificateVerify support-check anchor not found in $sslTls13Generic"

    $tsipCallCount = [regex]::Matches($sslText, 'ssl_tls13_write_tsip_certificate_verify_body\s*\(\s*ssl\s*,').Count
    if ($tsipCallCount -ne 1) {
        throw "Unexpected TSIP CertificateVerify hook count in ${sslTls13Generic}: $tsipCallCount"
    }

    Set-Content -LiteralPath $sslTls13Generic -Value $sslText -Encoding UTF8
}

Write-Host "Prepared TSIP Mbed TLS 3.6.x 0-RTT e2 studio build."
