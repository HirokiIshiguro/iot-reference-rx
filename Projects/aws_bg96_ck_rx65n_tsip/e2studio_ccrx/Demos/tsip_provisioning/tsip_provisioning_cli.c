/*
 * Runtime TSIP provisioning commands.
 *
 * The command writes TSIP provisioning blobs delivered over UART into the
 * littlefs-backed key-value store used by iot-reference-rx.
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "FreeRTOS.h"
#include "FreeRTOS_CLI.h"
#include "aws_clientcredential.h"
#include "demo_config.h"
#include "lfs.h"
#include "store.h"
#include "tsip_provisioning_cli.h"
#include "tsip_provisioning_store.h"

#define TSIPPROV_TEMP_FILE_NAME       "tsipprov.tmp"
#define TSIPPROV_MAX_CHUNK_BYTES      (1536U)

typedef struct TsipProvisioningCliSlot
{
    TsipProvisioningSlot_t xSlot;
    const char * pcCliName;
    const char * pcStorageName;
    uint32_t ulExpectedSize;
} TsipProvisioningCliSlot_t;

static BaseType_t prvTsipProvisioningCommand(char * pcWriteBuffer,
                                             size_t xWriteBufferLen,
                                             const char * pcCommandString);
static const TsipProvisioningCliSlot_t * prvFindSlot(const char * pcName,
                                                     BaseType_t xNameLength);
static BaseType_t prvParseUnsigned(const char * pcText,
                                   BaseType_t xTextLength,
                                   uint32_t * pulValue);
static BaseType_t prvParseHexBytes(const char * pcHex,
                                   BaseType_t xHexLength,
                                   uint8_t * pucOutput,
                                   uint32_t * pulOutputLength);
static int prvHexNibble(char c);
static BaseType_t prvWriteTempChunk(const uint8_t * pucData,
                                    uint32_t ulDataLength);
static BaseType_t prvCommitTempFile(const char * pcStorageName);
static uint32_t prvGetStoredLength(const char * pcStorageName);
static void prvEraseFileIfExists(const char * pcStorageName);
static BaseType_t prvRefreshAwsCredentialMetadata(void);
extern int32_t xprvWriteCacheEntry(size_t KeyLength,
                                   char * Key,
                                   size_t ValueLength,
                                   char * pvNewValue);
extern BaseType_t KVStore_xCommitChanges(void);

static const TsipProvisioningCliSlot_t xSlots[TSIP_PROVISIONING_SLOT_COUNT] =
{
    { TSIP_PROVISIONING_SLOT_ROOT_CA_SIGNATURE, "rootca-sig", "tsip_rootca_sig_id", 256U },
    { TSIP_PROVISIONING_SLOT_ROOT_SIGNER_PUBLIC_KEY, "root-signer", "tsip_rootca_pub_wrapped_id", 0U },
    { TSIP_PROVISIONING_SLOT_CLIENT_PUBLIC_KEY, "client-pub", "tsip_client_pub_wrapped_id", 0U },
    { TSIP_PROVISIONING_SLOT_CLIENT_PRIVATE_KEY, "client-pri", "tsip_client_pri_wrapped_id", 0U },
    { TSIP_PROVISIONING_SLOT_ROOT_CA_DER, "rootca-der", "tsip_rootca_der_id", 0U },
};

static const CLI_Command_Definition_t xTsipProvisioningCommand =
{
    "tsipprov",
    "\r\ntsipprov:\r\n"
    "    Provision TSIP blobs into littlefs.\r\n"
    "    Usage: tsipprov begin {rootca-sig|root-signer|client-pub|client-pri|rootca-der} <size>\r\n"
    "           tsipprov write <offset> <hex-bytes>\r\n"
    "           tsipprov end\r\n"
    "           tsipprov status\r\n"
    "           tsipprov prepare\r\n"
    "           tsipprov credentials\r\n"
    "           tsipprov erase <slot>\r\n",
    prvTsipProvisioningCommand,
    -1
};

static const TsipProvisioningCliSlot_t * pxActiveSlot = NULL;
static uint32_t ulExpectedLength = 0U;
static uint32_t ulReceivedLength = 0U;
static uint8_t ucChunkBuffer[TSIPPROV_MAX_CHUNK_BYTES];

void vRegisterTsipProvisioningCLICommands(void)
{
    FreeRTOS_CLIRegisterCommand(&xTsipProvisioningCommand);
}

static BaseType_t prvTsipProvisioningCommand(char * pcWriteBuffer,
                                             size_t xWriteBufferLen,
                                             const char * pcCommandString)
{
    const char * pcRequest;
    const char * pcParam1;
    const char * pcParam2;
    BaseType_t xRequestLength = 0;
    BaseType_t xParam1Length = 0;
    BaseType_t xParam2Length = 0;
    const TsipProvisioningCliSlot_t * pxSlot;
    uint32_t ulValue = 0U;
    uint32_t ulChunkLength = 0U;

    (void)xWriteBufferLen;
    pcWriteBuffer[0] = '\0';

    pcRequest = FreeRTOS_CLIGetParameter(pcCommandString, 1U, &xRequestLength);
    if (NULL == pcRequest)
    {
        sprintf(pcWriteBuffer, "Error: missing request.\r\n");
        return pdFALSE;
    }

    if (0 == strncmp(pcRequest, "begin", (size_t)xRequestLength))
    {
        pcParam1 = FreeRTOS_CLIGetParameter(pcCommandString, 2U, &xParam1Length);
        pcParam2 = FreeRTOS_CLIGetParameter(pcCommandString, 3U, &xParam2Length);
        pxSlot = prvFindSlot(pcParam1, xParam1Length);

        if ((NULL == pxSlot) || (pdTRUE != prvParseUnsigned(pcParam2, xParam2Length, &ulValue)) || (0U == ulValue))
        {
            sprintf(pcWriteBuffer, "Error: usage tsipprov begin <slot> <size>.\r\n");
            return pdFALSE;
        }

        if ((0U != pxSlot->ulExpectedSize) && (ulValue != pxSlot->ulExpectedSize))
        {
            sprintf(pcWriteBuffer, "Error: %s must be %lu bytes.\r\n",
                    pxSlot->pcCliName,
                    (unsigned long)pxSlot->ulExpectedSize);
            return pdFALSE;
        }

        prvEraseFileIfExists(TSIPPROV_TEMP_FILE_NAME);
        pxActiveSlot = pxSlot;
        ulExpectedLength = ulValue;
        ulReceivedLength = 0U;
        sprintf(pcWriteBuffer, "OK: begin %s %lu bytes.\r\n",
                pxActiveSlot->pcCliName,
                (unsigned long)ulExpectedLength);
    }
    else if (0 == strncmp(pcRequest, "write", (size_t)xRequestLength))
    {
        pcParam1 = FreeRTOS_CLIGetParameter(pcCommandString, 2U, &xParam1Length);
        pcParam2 = FreeRTOS_CLIGetParameter(pcCommandString, 3U, &xParam2Length);

        if ((NULL == pxActiveSlot) ||
            (pdTRUE != prvParseUnsigned(pcParam1, xParam1Length, &ulValue)) ||
            (ulValue != ulReceivedLength) ||
            (pdTRUE != prvParseHexBytes(pcParam2, xParam2Length, ucChunkBuffer, &ulChunkLength)) ||
            ((ulReceivedLength + ulChunkLength) > ulExpectedLength) ||
            (pdTRUE != prvWriteTempChunk(ucChunkBuffer, ulChunkLength)))
        {
            sprintf(pcWriteBuffer, "Error: write failed at %lu/%lu.\r\n",
                    (unsigned long)ulReceivedLength,
                    (unsigned long)ulExpectedLength);
            return pdFALSE;
        }

        ulReceivedLength += ulChunkLength;
        sprintf(pcWriteBuffer, "OK: write %lu/%lu.\r\n",
                (unsigned long)ulReceivedLength,
                (unsigned long)ulExpectedLength);
    }
    else if (0 == strncmp(pcRequest, "end", (size_t)xRequestLength))
    {
        if ((NULL == pxActiveSlot) ||
            (ulReceivedLength != ulExpectedLength) ||
            (pdTRUE != prvCommitTempFile(pxActiveSlot->pcStorageName)))
        {
            sprintf(pcWriteBuffer, "Error: end failed %lu/%lu.\r\n",
                    (unsigned long)ulReceivedLength,
                    (unsigned long)ulExpectedLength);
            return pdFALSE;
        }

        sprintf(pcWriteBuffer, "OK: stored %s %lu bytes.\r\n",
                pxActiveSlot->pcCliName,
                (unsigned long)ulReceivedLength);
        pxActiveSlot = NULL;
        ulExpectedLength = 0U;
        ulReceivedLength = 0U;
    }
    else if (0 == strncmp(pcRequest, "status", (size_t)xRequestLength))
    {
        size_t xOffset = 0U;
        int written;
        uint32_t i;

        written = snprintf(pcWriteBuffer,
                           xWriteBufferLen,
                           "active=%s %lu/%lu\r\n",
                           (NULL != pxActiveSlot) ? pxActiveSlot->pcCliName : "none",
                           (unsigned long)ulReceivedLength,
                           (unsigned long)ulExpectedLength);
        if (written > 0)
        {
            xOffset = (size_t)written;
        }

        for (i = 0U; (i < TSIP_PROVISIONING_SLOT_COUNT) && (xOffset < xWriteBufferLen); i++)
        {
            written = snprintf(&pcWriteBuffer[xOffset],
                               xWriteBufferLen - xOffset,
                               "%s=%lu\r\n",
                               xSlots[i].pcCliName,
                               (unsigned long)prvGetStoredLength(xSlots[i].pcStorageName));
            if (written <= 0)
            {
                break;
            }
            xOffset += (size_t)written;
        }
    }
    else if (0 == strncmp(pcRequest, "erase", (size_t)xRequestLength))
    {
        pcParam1 = FreeRTOS_CLIGetParameter(pcCommandString, 2U, &xParam1Length);
        pxSlot = prvFindSlot(pcParam1, xParam1Length);
        if (NULL == pxSlot)
        {
            sprintf(pcWriteBuffer, "Error: unknown slot.\r\n");
            return pdFALSE;
        }

        prvEraseFileIfExists(pxSlot->pcStorageName);
        sprintf(pcWriteBuffer, "OK: erased %s.\r\n", pxSlot->pcCliName);
    }
    else if (0 == strncmp(pcRequest, "prepare", (size_t)xRequestLength))
    {
        if ((pdTRUE == xTsipProvisioningPrepareTlsRootCaTrustAnchor()) &&
            (pdTRUE == xTsipProvisioningLoadClientRsa2048KeyPair()))
        {
            sprintf(pcWriteBuffer, "OK: TSIP runtime keys prepared.\r\n");
        }
        else
        {
            sprintf(pcWriteBuffer, "Error: TSIP runtime key prepare failed.\r\n");
        }
    }
    else if (0 == strncmp(pcRequest, "credentials", (size_t)xRequestLength))
    {
        if (pdTRUE == prvRefreshAwsCredentialMetadata())
        {
            sprintf(pcWriteBuffer, "OK: AWS credential metadata refreshed.\r\n");
        }
        else
        {
            sprintf(pcWriteBuffer, "Error: AWS credential metadata refresh failed.\r\n");
        }
    }
    else
    {
        sprintf(pcWriteBuffer, "Error: unknown request.\r\n");
    }

    return pdFALSE;
}

static BaseType_t prvRefreshAwsCredentialMetadata(void)
{
    BaseType_t xCommitResult;
    int32_t lStoreResult;
    char * pcValue;

    pcValue = (char *)democonfigCLIENT_IDENTIFIER;
    lStoreResult = xprvWriteCacheEntry(strlen("thingname"), "thingname", strlen(pcValue), pcValue);
    if (lStoreResult < 0)
    {
        return pdFALSE;
    }

    pcValue = (char *)democonfigMQTT_BROKER_ENDPOINT;
    lStoreResult = xprvWriteCacheEntry(strlen("endpoint"), "endpoint", strlen(pcValue), pcValue);
    if (lStoreResult < 0)
    {
        return pdFALSE;
    }

    if (NULL != keyCLIENT_CERTIFICATE_PEM)
    {
        pcValue = (char *)keyCLIENT_CERTIFICATE_PEM;
        lStoreResult = xprvWriteCacheEntry(strlen("cert"), "cert", strlen(pcValue), pcValue);
        if (lStoreResult < 0)
        {
            return pdFALSE;
        }
    }

    pcValue = (char *)otapalconfigCODE_SIGNING_CERTIFICATE;
    lStoreResult = xprvWriteCacheEntry(strlen("codesigncert"), "codesigncert", strlen(pcValue), pcValue);
    if (lStoreResult < 0)
    {
        return pdFALSE;
    }

    pcValue = (char *)democonfigROOT_CA_PEM;
    lStoreResult = xprvWriteCacheEntry(strlen("rootca"), "rootca", strlen(pcValue), pcValue);
    if (lStoreResult < 0)
    {
        return pdFALSE;
    }

    xCommitResult = KVStore_xCommitChanges();
    return xCommitResult;
}

static const TsipProvisioningCliSlot_t * prvFindSlot(const char * pcName,
                                                     BaseType_t xNameLength)
{
    uint32_t i;

    if (NULL == pcName)
    {
        return NULL;
    }

    for (i = 0U; i < TSIP_PROVISIONING_SLOT_COUNT; i++)
    {
        if ((strlen(xSlots[i].pcCliName) == (size_t)xNameLength) &&
            (0 == strncmp(pcName, xSlots[i].pcCliName, (size_t)xNameLength)))
        {
            return &xSlots[i];
        }
    }

    return NULL;
}

static BaseType_t prvParseUnsigned(const char * pcText,
                                   BaseType_t xTextLength,
                                   uint32_t * pulValue)
{
    uint32_t value = 0U;
    BaseType_t i;

    if ((NULL == pcText) || (xTextLength <= 0) || (NULL == pulValue))
    {
        return pdFALSE;
    }

    for (i = 0; i < xTextLength; i++)
    {
        if ((pcText[i] < '0') || (pcText[i] > '9'))
        {
            return pdFALSE;
        }
        value = (value * 10U) + (uint32_t)(pcText[i] - '0');
    }

    *pulValue = value;
    return pdTRUE;
}

static BaseType_t prvParseHexBytes(const char * pcHex,
                                   BaseType_t xHexLength,
                                   uint8_t * pucOutput,
                                   uint32_t * pulOutputLength)
{
    BaseType_t i;
    int high;
    int low;
    uint32_t outputLength;

    if ((NULL == pcHex) ||
        (NULL == pucOutput) ||
        (NULL == pulOutputLength) ||
        (xHexLength <= 0) ||
        (0 != (xHexLength & 1)) ||
        (((uint32_t)xHexLength / 2U) > TSIPPROV_MAX_CHUNK_BYTES))
    {
        return pdFALSE;
    }

    outputLength = (uint32_t)xHexLength / 2U;
    for (i = 0; i < xHexLength; i += 2)
    {
        high = prvHexNibble(pcHex[i]);
        low = prvHexNibble(pcHex[i + 1]);
        if ((high < 0) || (low < 0))
        {
            return pdFALSE;
        }
        pucOutput[i / 2] = (uint8_t)(((uint8_t)high << 4) | (uint8_t)low);
    }

    *pulOutputLength = outputLength;
    return pdTRUE;
}

static int prvHexNibble(char c)
{
    if ((c >= '0') && (c <= '9'))
    {
        return c - '0';
    }
    if ((c >= 'a') && (c <= 'f'))
    {
        return c - 'a' + 10;
    }
    if ((c >= 'A') && (c <= 'F'))
    {
        return c - 'A' + 10;
    }
    return -1;
}

static BaseType_t prvWriteTempChunk(const uint8_t * pucData,
                                    uint32_t ulDataLength)
{
    lfs_file_t file;
    lfs_ssize_t result;

    result = lfs_file_open(&RM_STDIO_LITTLEFS_CFG_LFS,
                           &file,
                           TSIPPROV_TEMP_FILE_NAME,
                           LFS_O_WRONLY | LFS_O_APPEND | LFS_O_CREAT);
    if (LFS_ERR_OK != result)
    {
        return pdFALSE;
    }

    result = lfs_file_write(&RM_STDIO_LITTLEFS_CFG_LFS, &file, pucData, ulDataLength);
    (void)lfs_file_close(&RM_STDIO_LITTLEFS_CFG_LFS, &file);

    return (result == (lfs_ssize_t)ulDataLength) ? pdTRUE : pdFALSE;
}

static BaseType_t prvCommitTempFile(const char * pcStorageName)
{
    prvEraseFileIfExists(pcStorageName);

    return (LFS_ERR_OK == lfs_rename(&RM_STDIO_LITTLEFS_CFG_LFS,
                                     TSIPPROV_TEMP_FILE_NAME,
                                     pcStorageName)) ? pdTRUE : pdFALSE;
}

static uint32_t prvGetStoredLength(const char * pcStorageName)
{
    struct lfs_info fileInfo;

    if (LFS_ERR_OK == lfs_stat(&RM_STDIO_LITTLEFS_CFG_LFS, pcStorageName, &fileInfo))
    {
        return fileInfo.size;
    }

    return 0U;
}

static void prvEraseFileIfExists(const char * pcStorageName)
{
    lfs_ssize_t result;

    result = lfs_remove(&RM_STDIO_LITTLEFS_CFG_LFS, pcStorageName);
    (void)result;
}
