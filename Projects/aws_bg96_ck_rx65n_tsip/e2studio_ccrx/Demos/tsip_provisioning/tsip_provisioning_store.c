/*
 * Runtime accessors for TSIP provisioning blobs stored in littlefs.
 */

#include <stdint.h>
#include <string.h>

#include "FreeRTOS.h"
#include "lfs.h"
#include "lfs_util_config.h"
#include "r_common_api_tsip.h"
#include "r_tsip_rx_if.h"
#include "tsip_provisioning_store.h"

#define SKMT_WUFPK_SIZE                                (32U)
#define SKMT_IV_SIZE                                   (16U)
#define SKMT_CRC_SIZE                                  (4U)
#define SKMT_LEGACY_SCALAR_PLACEHOLDER_SIZE            (2U)

#define TSIP_TLS_RSA2048_PUBLIC_ENCRYPTED_KEY_SIZE     (288U)
#define TSIP_RSA2048_PUBLIC_ENCRYPTED_KEY_SIZE         (288U)
#define TSIP_RSA2048_PRIVATE_ENCRYPTED_KEY_SIZE        (528U)

#define TSIP_ROOT_SIGNER_KEY_INDEX_STORAGE_NAME        "tsip_rootca_pub_id"
#define TSIP_CLIENT_PUBLIC_KEY_INDEX_STORAGE_NAME      "tsip_client_pub_id"
#define TSIP_CLIENT_PRIVATE_KEY_INDEX_STORAGE_NAME     "tsip_client_pri_id"

#define ROOT_SIGNER_MAX_STORED_SIZE \
    (SKMT_LEGACY_SCALAR_PLACEHOLDER_SIZE + SKMT_WUFPK_SIZE + SKMT_IV_SIZE + \
     TSIP_TLS_RSA2048_PUBLIC_ENCRYPTED_KEY_SIZE + SKMT_CRC_SIZE)
#define CLIENT_PRIVATE_MAX_STORED_SIZE \
    (SKMT_LEGACY_SCALAR_PLACEHOLDER_SIZE + SKMT_WUFPK_SIZE + SKMT_IV_SIZE + \
     TSIP_RSA2048_PRIVATE_ENCRYPTED_KEY_SIZE + SKMT_CRC_SIZE)

typedef struct SkmtWrappedKeyView
{
    uint8_t * pucWufpk;
    uint8_t * pucIv;
    uint8_t * pucEncryptedKey;
} SkmtWrappedKeyView_t;

typedef struct TsipProvisioningSlotInfo
{
    const char * pcCliName;
    const char * pcStorageName;
    uint32_t ulExpectedSize;
} TsipProvisioningSlotInfo_t;

static BaseType_t prvReadFile(const char * pcStorageName,
                              uint8_t * pucBuffer,
                              uint32_t ulBufferSize,
                              uint32_t * pulActualSize);
static BaseType_t prvWriteFile(const char * pcStorageName,
                               const uint8_t * pucBuffer,
                               uint32_t ulBufferSize);
static BaseType_t prvParseSkmtWrappedKey(uint8_t * pucStoredData,
                                         uint32_t ulStoredLength,
                                         uint32_t ulEncryptedKeySize,
                                         SkmtWrappedKeyView_t * pxView);
static BaseType_t prvImportRootSignerPublicKey(void);
static BaseType_t prvLoadOrImportClientPublicKey(void);
static BaseType_t prvLoadOrImportClientPrivateKey(void);

static const TsipProvisioningSlotInfo_t xSlotInfo[TSIP_PROVISIONING_SLOT_COUNT] =
{
    { "rootca-sig", "tsip_rootca_sig_id", TSIP_PROVISIONING_ROOT_CA_SIGNATURE_SIZE },
    { "root-signer", "tsip_rootca_pub_wrapped_id", 0U },
    { "client-pub", "tsip_client_pub_wrapped_id", 0U },
    { "client-pri", "tsip_client_pri_wrapped_id", 0U },
    { "rootca-der", "tsip_rootca_der_id", 0U },
};

static tsip_tls_ca_certification_public_key_index_t xRootSignerPublicKeyIndex;
static BaseType_t xRootCaTrustAnchorReady = pdFALSE;
static uint8_t ucRootSignerBlob[ROOT_SIGNER_MAX_STORED_SIZE];
static uint8_t ucClientPrivateBlob[CLIENT_PRIVATE_MAX_STORED_SIZE];

extern lfs_t RM_STDIO_LITTLEFS_CFG_LFS;
extern tsip_rsa2048_private_key_index_t rsa2048_private_key;
extern tsip_rsa2048_public_key_index_t rsa2048_public_key;

const char * pcTsipProvisioningSlotCliName(TsipProvisioningSlot_t xSlot)
{
    if ((uint32_t)xSlot >= (uint32_t)TSIP_PROVISIONING_SLOT_COUNT)
    {
        return "";
    }

    return xSlotInfo[xSlot].pcCliName;
}

const char * pcTsipProvisioningSlotStorageName(TsipProvisioningSlot_t xSlot)
{
    if ((uint32_t)xSlot >= (uint32_t)TSIP_PROVISIONING_SLOT_COUNT)
    {
        return "";
    }

    return xSlotInfo[xSlot].pcStorageName;
}

uint32_t ulTsipProvisioningSlotExpectedSize(TsipProvisioningSlot_t xSlot)
{
    if ((uint32_t)xSlot >= (uint32_t)TSIP_PROVISIONING_SLOT_COUNT)
    {
        return 0U;
    }

    return xSlotInfo[xSlot].ulExpectedSize;
}

uint32_t ulTsipProvisioningGetStoredLength(TsipProvisioningSlot_t xSlot)
{
    struct lfs_info xFileInfo;

    if ((uint32_t)xSlot >= (uint32_t)TSIP_PROVISIONING_SLOT_COUNT)
    {
        return 0U;
    }

    if (LFS_ERR_OK == lfs_stat(&RM_STDIO_LITTLEFS_CFG_LFS, xSlotInfo[xSlot].pcStorageName, &xFileInfo))
    {
        return xFileInfo.size;
    }

    return 0U;
}

BaseType_t xTsipProvisioningReadSlot(TsipProvisioningSlot_t xSlot,
                                     uint8_t * pucBuffer,
                                     uint32_t ulBufferSize,
                                     uint32_t * pulActualSize)
{
    if ((uint32_t)xSlot >= (uint32_t)TSIP_PROVISIONING_SLOT_COUNT)
    {
        return pdFALSE;
    }

    return prvReadFile(xSlotInfo[xSlot].pcStorageName, pucBuffer, ulBufferSize, pulActualSize);
}

void vTsipProvisioningEraseSlot(TsipProvisioningSlot_t xSlot)
{
    if ((uint32_t)xSlot < (uint32_t)TSIP_PROVISIONING_SLOT_COUNT)
    {
        (void)lfs_remove(&RM_STDIO_LITTLEFS_CFG_LFS, xSlotInfo[xSlot].pcStorageName);
    }
}

BaseType_t xTsipProvisioningReadRootCaSignature(uint8_t * pucBuffer,
                                                uint32_t ulBufferSize,
                                                uint32_t * pulActualSize)
{
    BaseType_t xResult;
    uint32_t ulActualSize = 0U;

    xResult = xTsipProvisioningReadSlot(TSIP_PROVISIONING_SLOT_ROOT_CA_SIGNATURE,
                                        pucBuffer,
                                        ulBufferSize,
                                        &ulActualSize);
    if ((pdTRUE != xResult) || (TSIP_PROVISIONING_ROOT_CA_SIGNATURE_SIZE != ulActualSize))
    {
        return pdFALSE;
    }

    if (NULL != pulActualSize)
    {
        *pulActualSize = ulActualSize;
    }

    return pdTRUE;
}

BaseType_t xTsipProvisioningPrepareTlsRootCaTrustAnchor(void)
{
    BaseType_t xResult;
    uint32_t ulRootSignerSize = 0U;
    e_commonapi_err_t xCommonApiResult;
    e_tsip_err_t xTsipResult;

    if (pdTRUE == xRootCaTrustAnchorReady)
    {
        return pdTRUE;
    }

    xCommonApiResult = R_Demo_Common_API_TSIP_Open(NULL, NULL);
    if (COMMONAPI_SUCCESS != xCommonApiResult)
    {
        return pdFALSE;
    }

    xResult = prvReadFile(TSIP_ROOT_SIGNER_KEY_INDEX_STORAGE_NAME,
                          (uint8_t *)&xRootSignerPublicKeyIndex,
                          sizeof(xRootSignerPublicKeyIndex),
                          &ulRootSignerSize);
    if ((pdTRUE != xResult) || (sizeof(xRootSignerPublicKeyIndex) != ulRootSignerSize))
    {
        xResult = prvImportRootSignerPublicKey();
        if ((pdTRUE != xResult) ||
            (pdTRUE != prvWriteFile(TSIP_ROOT_SIGNER_KEY_INDEX_STORAGE_NAME,
                                    (const uint8_t *)&xRootSignerPublicKeyIndex,
                                    sizeof(xRootSignerPublicKeyIndex))))
        {
            (void)R_Demo_Common_API_TSIP_Close();
            return pdFALSE;
        }
    }

    (void)R_Demo_Common_API_TSIP_Close();

    xCommonApiResult = R_Demo_Common_API_TSIP_Open(&xRootSignerPublicKeyIndex, NULL);
    if (COMMONAPI_SUCCESS != xCommonApiResult)
    {
        return pdFALSE;
    }

    xTsipResult = R_TSIP_TlsRegisterCaCertificationPublicKeyIndex(TSIP_TLS_MODE_CLIENT, &xRootSignerPublicKeyIndex);
    if (TSIP_SUCCESS != xTsipResult)
    {
        return pdFALSE;
    }

    xRootCaTrustAnchorReady = pdTRUE;
    return pdTRUE;
}

BaseType_t xTsipProvisioningLoadClientRsa2048KeyPair(void)
{
    if (pdTRUE != xTsipProvisioningPrepareTlsRootCaTrustAnchor())
    {
        return pdFALSE;
    }

    return ((pdTRUE == prvLoadOrImportClientPublicKey()) &&
            (pdTRUE == prvLoadOrImportClientPrivateKey())) ? pdTRUE : pdFALSE;
}

static BaseType_t prvReadFile(const char * pcStorageName,
                              uint8_t * pucBuffer,
                              uint32_t ulBufferSize,
                              uint32_t * pulActualSize)
{
    lfs_file_t xFile;
    lfs_soff_t xFileSize;
    lfs_ssize_t xReadSize;

    if ((NULL == pcStorageName) || (NULL == pucBuffer) || (NULL == pulActualSize))
    {
        return pdFALSE;
    }

    if (LFS_ERR_OK != lfs_file_open(&RM_STDIO_LITTLEFS_CFG_LFS, &xFile, pcStorageName, LFS_O_RDONLY))
    {
        return pdFALSE;
    }

    xFileSize = lfs_file_size(&RM_STDIO_LITTLEFS_CFG_LFS, &xFile);
    if ((xFileSize < 0) || ((uint32_t)xFileSize > ulBufferSize))
    {
        (void)lfs_file_close(&RM_STDIO_LITTLEFS_CFG_LFS, &xFile);
        return pdFALSE;
    }

    xReadSize = lfs_file_read(&RM_STDIO_LITTLEFS_CFG_LFS, &xFile, pucBuffer, (lfs_size_t)xFileSize);
    (void)lfs_file_close(&RM_STDIO_LITTLEFS_CFG_LFS, &xFile);

    if (xReadSize != xFileSize)
    {
        return pdFALSE;
    }

    *pulActualSize = (uint32_t)xReadSize;
    return pdTRUE;
}

static BaseType_t prvWriteFile(const char * pcStorageName,
                               const uint8_t * pucBuffer,
                               uint32_t ulBufferSize)
{
    lfs_file_t xFile;
    lfs_ssize_t xWriteSize;

    if ((NULL == pcStorageName) || (NULL == pucBuffer) || (0U == ulBufferSize))
    {
        return pdFALSE;
    }

    (void)lfs_remove(&RM_STDIO_LITTLEFS_CFG_LFS, pcStorageName);

    if (LFS_ERR_OK != lfs_file_open(&RM_STDIO_LITTLEFS_CFG_LFS,
                                    &xFile,
                                    pcStorageName,
                                    LFS_O_WRONLY | LFS_O_TRUNC | LFS_O_CREAT))
    {
        return pdFALSE;
    }

    xWriteSize = lfs_file_write(&RM_STDIO_LITTLEFS_CFG_LFS, &xFile, pucBuffer, ulBufferSize);
    (void)lfs_file_close(&RM_STDIO_LITTLEFS_CFG_LFS, &xFile);

    return (xWriteSize == (lfs_ssize_t)ulBufferSize) ? pdTRUE : pdFALSE;
}

static BaseType_t prvParseSkmtWrappedKey(uint8_t * pucStoredData,
                                         uint32_t ulStoredLength,
                                         uint32_t ulEncryptedKeySize,
                                         SkmtWrappedKeyView_t * pxView)
{
    uint32_t ulOffset = 0U;
    uint32_t ulCompactLength = SKMT_WUFPK_SIZE + SKMT_IV_SIZE + ulEncryptedKeySize;
    uint32_t ulCompactLengthWithCrc = ulCompactLength + SKMT_CRC_SIZE;

    if ((NULL == pucStoredData) || (NULL == pxView))
    {
        return pdFALSE;
    }

    if (ulStoredLength == (ulCompactLengthWithCrc + SKMT_LEGACY_SCALAR_PLACEHOLDER_SIZE))
    {
        ulOffset = SKMT_LEGACY_SCALAR_PLACEHOLDER_SIZE;
    }
    else if ((ulStoredLength != ulCompactLengthWithCrc) && (ulStoredLength != ulCompactLength))
    {
        return pdFALSE;
    }

    pxView->pucWufpk = &pucStoredData[ulOffset];
    pxView->pucIv = &pucStoredData[ulOffset + SKMT_WUFPK_SIZE];
    pxView->pucEncryptedKey = &pucStoredData[ulOffset + SKMT_WUFPK_SIZE + SKMT_IV_SIZE];
    return pdTRUE;
}

static BaseType_t prvImportRootSignerPublicKey(void)
{
    BaseType_t xResult;
    uint32_t ulStoredLength = 0U;
    SkmtWrappedKeyView_t xWrappedKey;
    e_tsip_err_t xTsipResult;

    memset(&xRootSignerPublicKeyIndex, 0, sizeof(xRootSignerPublicKeyIndex));

    xResult = xTsipProvisioningReadSlot(TSIP_PROVISIONING_SLOT_ROOT_SIGNER_PUBLIC_KEY,
                                        ucRootSignerBlob,
                                        sizeof(ucRootSignerBlob),
                                        &ulStoredLength);
    if ((pdTRUE != xResult) ||
        (pdTRUE != prvParseSkmtWrappedKey(ucRootSignerBlob,
                                          ulStoredLength,
                                          TSIP_TLS_RSA2048_PUBLIC_ENCRYPTED_KEY_SIZE,
                                          &xWrappedKey)))
    {
        return pdFALSE;
    }

    xTsipResult = R_TSIP_GenerateTlsRsaPublicKeyIndex(xWrappedKey.pucWufpk,
                                                      xWrappedKey.pucIv,
                                                      xWrappedKey.pucEncryptedKey,
                                                      &xRootSignerPublicKeyIndex);

    return (TSIP_SUCCESS == xTsipResult) ? pdTRUE : pdFALSE;
}

static BaseType_t prvLoadOrImportClientPublicKey(void)
{
    BaseType_t xResult;
    uint32_t ulStoredLength = 0U;
    SkmtWrappedKeyView_t xWrappedKey;
    e_tsip_err_t xTsipResult;

    xResult = prvReadFile(TSIP_CLIENT_PUBLIC_KEY_INDEX_STORAGE_NAME,
                          (uint8_t *)&rsa2048_public_key,
                          sizeof(rsa2048_public_key),
                          &ulStoredLength);
    if ((pdTRUE == xResult) && (sizeof(rsa2048_public_key) == ulStoredLength))
    {
        return pdTRUE;
    }

    xResult = xTsipProvisioningReadSlot(TSIP_PROVISIONING_SLOT_CLIENT_PUBLIC_KEY,
                                        ucRootSignerBlob,
                                        sizeof(ucRootSignerBlob),
                                        &ulStoredLength);
    if ((pdTRUE != xResult) ||
        (pdTRUE != prvParseSkmtWrappedKey(ucRootSignerBlob,
                                          ulStoredLength,
                                          TSIP_RSA2048_PUBLIC_ENCRYPTED_KEY_SIZE,
                                          &xWrappedKey)))
    {
        return pdFALSE;
    }

    xTsipResult = R_TSIP_GenerateRsa2048PublicKeyIndex(xWrappedKey.pucWufpk,
                                                       xWrappedKey.pucIv,
                                                       xWrappedKey.pucEncryptedKey,
                                                       &rsa2048_public_key);
    if (TSIP_SUCCESS != xTsipResult)
    {
        return pdFALSE;
    }

    return prvWriteFile(TSIP_CLIENT_PUBLIC_KEY_INDEX_STORAGE_NAME,
                        (const uint8_t *)&rsa2048_public_key,
                        sizeof(rsa2048_public_key));
}

static BaseType_t prvLoadOrImportClientPrivateKey(void)
{
    BaseType_t xResult;
    uint32_t ulStoredLength = 0U;
    SkmtWrappedKeyView_t xWrappedKey;
    e_tsip_err_t xTsipResult;

    xResult = prvReadFile(TSIP_CLIENT_PRIVATE_KEY_INDEX_STORAGE_NAME,
                          (uint8_t *)&rsa2048_private_key,
                          sizeof(rsa2048_private_key),
                          &ulStoredLength);
    if ((pdTRUE == xResult) && (sizeof(rsa2048_private_key) == ulStoredLength))
    {
        return pdTRUE;
    }

    xResult = xTsipProvisioningReadSlot(TSIP_PROVISIONING_SLOT_CLIENT_PRIVATE_KEY,
                                        ucClientPrivateBlob,
                                        sizeof(ucClientPrivateBlob),
                                        &ulStoredLength);
    if ((pdTRUE != xResult) ||
        (pdTRUE != prvParseSkmtWrappedKey(ucClientPrivateBlob,
                                          ulStoredLength,
                                          TSIP_RSA2048_PRIVATE_ENCRYPTED_KEY_SIZE,
                                          &xWrappedKey)))
    {
        return pdFALSE;
    }

    xTsipResult = R_TSIP_GenerateRsa2048PrivateKeyIndex(xWrappedKey.pucWufpk,
                                                        xWrappedKey.pucIv,
                                                        xWrappedKey.pucEncryptedKey,
                                                        &rsa2048_private_key);
    if (TSIP_SUCCESS != xTsipResult)
    {
        return pdFALSE;
    }

    return prvWriteFile(TSIP_CLIENT_PRIVATE_KEY_INDEX_STORAGE_NAME,
                        (const uint8_t *)&rsa2048_private_key,
                        sizeof(rsa2048_private_key));
}
