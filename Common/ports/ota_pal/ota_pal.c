/*
 * FreeRTOS OTA PAL for Renesas RX72N.
 *
 * This implementation writes OTA payloads directly to the inactive bank using
 * the Flash FIT BGO callback path. Incoming MQTT blocks are queued quickly and
 * a dedicated flash task serializes erase/write completion, so MQTT block
 * download can overlap with flash programming.
 *
 * SPDX-License-Identifier: MIT
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "FreeRTOS.h"
#include "queue.h"
#include "task.h"

#include "ota_pal.h"
#include "MQTTFileDownloader_config.h"

#include "platform.h"
#include "r_flash_rx_if.h"
#include "./src/targets/rx72n/r_flash_rx72n.h"
#include "r_fwup_config.h"
#include "r_common_api_flash.h"
#include "store.h"
#include "iot_crypto.h"

#include "mbedtls/asn1.h"
#include "mbedtls/ecdsa.h"
#include "mbedtls/error.h"

#define MAX_SIG_LENGTH              (64U)
#define HALF_SIG_LENGTH             (MAX_SIG_LENGTH / 2U)
#define OTA_FLASH_QUEUE_LENGTH      (2U)
#define OTA_PAYLOAD_BASE_OFFSET     (0x200U)
#define OTA_MAX_PAYLOAD_SIZE        (FWUP_CFG_AREA_SIZE - OTA_PAYLOAD_BASE_OFFSET)
#define OTA_FLASH_PAD_VALUE         (0xFFU)
#define OTA_HASH_READ_CHUNK_SIZE    (1024U)
#define OTA_IMAGE_FLAG_TESTING      (0xFEU)
#define OTA_MAGIC_CODE_LEN          (7U)
#define OTA_SIG_TYPE_LENGTH         (32U)
#define OTA_LEGACY_SIGNATURE_BYTES  (256U)
#define OTA_HEADER_RESERVED1_BYTES  (200U)
#define OTA_HEADER_RESERVED2_BYTES  (236U)
#define OTA_IMAGE_STATE_UNKNOWN_STR  ("unknown")
#define OTA_IMAGE_STATE_TESTING_STR  ("testing")
#define OTA_IMAGE_STATE_ACCEPTED_STR ("accepted")
#define OTA_IMAGE_STATE_REJECTED_STR ("rejected")
#define OTA_IMAGE_STATE_ABORTED_STR  ("aborted")

typedef struct OtaRsuHeader
{
    uint8_t magicCode[OTA_MAGIC_CODE_LEN];
    uint8_t imageFlag;
    uint8_t sigType[OTA_SIG_TYPE_LENGTH];
    uint32_t sigSize;
    uint8_t sig[OTA_LEGACY_SIGNATURE_BYTES];
    uint32_t dataflashFlag;
    uint32_t dataflashStartAddress;
    uint32_t dataflashEndAddress;
    uint8_t reserved1[OTA_HEADER_RESERVED1_BYTES];
    uint32_t sequenceNumber;
    uint32_t startAddress;
    uint32_t endAddress;
    uint32_t executionAddress;
    uint32_t hardwareId;
    uint8_t reserved2[OTA_HEADER_RESERVED2_BYTES];
} OtaRsuHeader_t;

typedef struct OtaFlashBlock
{
    uint32_t offset;
    uint32_t length;
    uint32_t paddedLength;
    uint8_t * pData;
} OtaFlashBlock_t;

const char OTA_JsonFileSignatureKey[OTA_FILE_SIG_KEY_STR_MAX_LENGTH] = "sig-sha256-ecdsa";

AfrOtaJobDocumentFields_t * pOTAFileContext = NULL;

extern volatile UPDATA_DATA_FLASH_CONTROL_BLOCK update_data_flash_control_block;

static OtaImageState_t OtaImageState = OtaImageStateUnknown;
static QueueHandle_t xOtaFlashQueue = NULL;
static TaskHandle_t xOtaFlashTask = NULL;
static volatile uint32_t ulOtaFlashPendingBlocks = 0U;
static volatile BaseType_t xOtaFlashError = pdFALSE;
static uint32_t ulOtaPayloadBytesReceived = 0U;

static int ExtractECDSASignature(const unsigned char * derSignature,
                                 size_t derSignatureLength,
                                 unsigned char * rawSignature);
static void prvOtaFlashTask(void * pvParameters);
static BaseType_t prvEnsureFlashResources(void);
static void prvResetDownloadState(void);
static void prvIncrementPendingBlocks(void);
static void prvDecrementPendingBlocks(void);
static BaseType_t prvWaitForFlashQueueDrained(void);
static BaseType_t prvGetPaddedLength(uint32_t length,
                                     uint32_t * pulPaddedLength);
static BaseType_t prvValidatePayloadRange(uint32_t offset,
                                          uint32_t length,
                                          uint32_t * pulPaddedLength);
static BaseType_t prvEraseBufferArea(void);
static BaseType_t prvWriteFlashBlocking(uint32_t destAddr,
                                        const uint8_t * pData,
                                        uint32_t length);
static BaseType_t prvWriteImageHeader(AfrOtaJobDocumentFields_t * pFileContext,
                                      const uint8_t * pRawSignature);
static OtaPalStatus_t prvVerifyReceivedPayload(AfrOtaJobDocumentFields_t * pFileContext);
static uint8_t * prvGetSignerCert(uint32_t * pulSignerCertSize);
static BaseType_t prvPersistImageState(OtaImageState_t eState);
static OtaImageState_t prvLoadPersistedImageState(void);
static const char * prvImageStateToString(OtaImageState_t eState);
static OtaImageState_t prvImageStateFromString(const char * pcState);
static void prvResetDevice(void);
static BaseType_t prvActivateBank(void);

OtaPalJobDocProcessingResult_t otaPal_CreateFileForRx(AfrOtaJobDocumentFields_t * const pFileContext)
{
    static uint8_t hdl = 0U;

    if (NULL == pFileContext)
    {
        return OtaPalJobDocFileCreateFailed;
    }

    if ((0U == pFileContext->fileSize) || (pFileContext->fileSize > OTA_MAX_PAYLOAD_SIZE))
    {
        LogError(("otaPal_CreateFileForRx: invalid payload size %u", (unsigned int)pFileContext->fileSize));
        return OtaPalJobDocFileCreateFailed;
    }

    if (pdTRUE != prvEnsureFlashResources())
    {
        LogError(("otaPal_CreateFileForRx: flash resource init failed"));
        return OtaPalJobDocFileCreateFailed;
    }

    (void)prvWaitForFlashQueueDrained();
    prvResetDownloadState();
    pFileContext->fileId = hdl++;
    OtaImageState = OtaImageStateUnknown;
    (void) prvPersistImageState(OtaImageState);

    if (pdTRUE != prvEraseBufferArea())
    {
        LogError(("otaPal_CreateFileForRx: buffer erase failed"));
        return OtaPalJobDocFileCreateFailed;
    }

    LogInfo(("otaPal_CreateFileForRx: direct queued flash path initialized"));
    return OtaPalJobDocFileCreated;
}

int16_t otaPal_WriteBlock(AfrOtaJobDocumentFields_t * const pFileContext,
                          uint32_t ulOffset,
                          uint8_t * const pData,
                          uint32_t ulBlockSize)
{
    OtaFlashBlock_t xBlock = {0};
    uint32_t paddedLength = 0U;

    if ((NULL == pFileContext) || (NULL == pData) || (0U == ulBlockSize) || (NULL == xOtaFlashQueue))
    {
        return 0;
    }

    if (pdTRUE == xOtaFlashError)
    {
        return 0;
    }

    if (ulBlockSize > mqttFileDownloader_CONFIG_BLOCK_SIZE)
    {
        xOtaFlashError = pdTRUE;
        LogError(("otaPal_WriteBlock: block too large: %u", (unsigned int)ulBlockSize));
        return 0;
    }

    if ((ulOffset > pFileContext->fileSize) || (ulBlockSize > (pFileContext->fileSize - ulOffset)))
    {
        xOtaFlashError = pdTRUE;
        LogError(("otaPal_WriteBlock: block exceeds job file size"));
        return 0;
    }

    if (pdTRUE != prvValidatePayloadRange(ulOffset, ulBlockSize, &paddedLength))
    {
        xOtaFlashError = pdTRUE;
        LogError(("otaPal_WriteBlock: block exceeds OTA flash buffer"));
        return 0;
    }

    xBlock.pData = pvPortMalloc(ulBlockSize);
    if (NULL == xBlock.pData)
    {
        LogError(("otaPal_WriteBlock: pvPortMalloc failed for %u bytes", (unsigned int)ulBlockSize));
        return 0;
    }

    (void)memcpy(xBlock.pData, pData, ulBlockSize);
    xBlock.offset = ulOffset;
    xBlock.length = ulBlockSize;
    xBlock.paddedLength = paddedLength;

    prvIncrementPendingBlocks();
    if (pdPASS != xQueueSend(xOtaFlashQueue, &xBlock, portMAX_DELAY))
    {
        prvDecrementPendingBlocks();
        vPortFree(xBlock.pData);
        LogError(("otaPal_WriteBlock: flash queue send failed"));
        return 0;
    }

    if ((ulOffset + ulBlockSize) > ulOtaPayloadBytesReceived)
    {
        ulOtaPayloadBytesReceived = ulOffset + ulBlockSize;
    }

    return (int16_t)ulBlockSize;
}

OtaPalStatus_t otaPal_CloseFile(AfrOtaJobDocumentFields_t * const pFileContext)
{
    OtaPalStatus_t eResult = OtaPalSuccess;
    unsigned char rawSignature[MAX_SIG_LENGTH] = {0};

    if (pdTRUE != prvWaitForFlashQueueDrained())
    {
        OtaImageState = OtaImageStateRejected;
        return OtaPalFileClose;
    }

    if ((NULL == pFileContext) || (NULL == pFileContext->signature) || (0 >= pFileContext->signatureLen))
    {
        OtaImageState = OtaImageStateRejected;
        return OtaPalSignatureCheckFailed;
    }

    pOTAFileContext = pFileContext;

    if (0 != ExtractECDSASignature((const unsigned char *)pFileContext->signature,
                                   pFileContext->signatureLen,
                                   rawSignature))
    {
        OtaImageState = OtaImageStateRejected;
        LogError(("otaPal_CloseFile: ECDSA signature extraction failed"));
        return OtaPalBadSignerCert;
    }

    if (pdTRUE != prvWriteImageHeader(pFileContext, rawSignature))
    {
        OtaImageState = OtaImageStateRejected;
        return OtaPalBadSignerCert;
    }

    eResult = prvVerifyReceivedPayload(pFileContext);
    OtaImageState = (OtaPalSuccess == eResult) ? OtaImageStateTesting : OtaImageStateRejected;
    (void) prvPersistImageState(OtaImageState);
    pFileContext->fileId = 0U;

    return eResult;
}

OtaPalStatus_t otaPal_CloseFileNoSignatureCheck(AfrOtaJobDocumentFields_t * const pFileContext)
{
    if (NULL != pFileContext)
    {
        pFileContext->fileId = 0U;
    }

    return (pdTRUE == prvWaitForFlashQueueDrained()) ? OtaPalSuccess : OtaPalFileClose;
}

OtaPalStatus_t otaPal_ResetDevice(AfrOtaJobDocumentFields_t * const pFileContext)
{
    (void) pFileContext;

    prvResetDevice();
    return OtaPalSuccess;
}

OtaPalStatus_t otaPal_ActivateNewImage(AfrOtaJobDocumentFields_t * const pFileContext)
{
    (void) pFileContext;

    if (pdTRUE != prvWaitForFlashQueueDrained())
    {
        return OtaPalActivateFailed;
    }

    if (pdTRUE != prvActivateBank())
    {
        return OtaPalActivateFailed;
    }

    prvResetDevice();
    return OtaPalSuccess;
}

OtaPalStatus_t otaPal_Abort(AfrOtaJobDocumentFields_t * const pFileContext)
{
    if (NULL != pFileContext)
    {
        pFileContext->fileId = 0U;
    }

    xOtaFlashError = pdTRUE;
    (void)prvWaitForFlashQueueDrained();

    OtaImageState = OtaImageStateAborted;
    (void) prvPersistImageState(OtaImageState);
    return OtaPalSuccess;
}

OtaPalStatus_t otaPal_SetPlatformImageState(AfrOtaJobDocumentFields_t * const pFileContext,
                                            OtaImageState_t eState)
{
    (void) pFileContext;

    OtaPalStatus_t eResult = OtaPalUninitialized;

    if (OtaImageStateTesting == OtaImageState)
    {
        switch (eState)
        {
            case OtaImageStateAccepted:
                LogInfo(("Accepted and committed final image."));
                eResult = OtaPalSuccess;
                break;

            case OtaImageStateRejected:
            case OtaImageStateAborted:
            case OtaImageStateTesting:
                eResult = OtaPalSuccess;
                break;

            default:
                eResult = OtaPalBadImageState;
                break;
        }
    }
    else
    {
        switch (eState)
        {
            case OtaImageStateAccepted:
                eResult = OtaPalCommitFailed;
                break;

            case OtaImageStateRejected:
            case OtaImageStateAborted:
            case OtaImageStateTesting:
                eResult = OtaPalSuccess;
                break;

            default:
                eResult = OtaPalBadImageState;
                break;
        }
    }

    OtaImageState = eState;
    (void) prvPersistImageState(OtaImageState);
    return eResult;
}

OtaPalImageState_t otaPal_GetPlatformImageState(AfrOtaJobDocumentFields_t * const pFileContext)
{
    (void) pFileContext;

    if (OtaImageStateUnknown == OtaImageState)
    {
        OtaImageState = prvLoadPersistedImageState();
    }

    switch (OtaImageState)
    {
        case OtaImageStateTesting:
            return OtaPalImageStatePendingCommit;
        case OtaImageStateAccepted:
        case OtaImageStateUnknown:
            return OtaPalImageStateValid;
        case OtaImageStateRejected:
        case OtaImageStateAborted:
        default:
            return OtaPalImageStateInvalid;
    }
}

OtaPalStatus_t otaPal_EraseArea(uint8_t area)
{
    if (1U != area)
    {
        LogError(("otaPal_EraseArea: only buffer area erase is supported in direct flash path"));
        return OtaPalEraseFailed;
    }

    return (pdTRUE == prvEraseBufferArea()) ? OtaPalSuccess : OtaPalEraseFailed;
}

static BaseType_t prvEnsureFlashResources(void)
{
    if (COMMONAPI_SUCCESS != R_Demo_Common_API_Flash_Open())
    {
        return pdFALSE;
    }

    if (NULL == xOtaFlashQueue)
    {
        xOtaFlashQueue = xQueueCreate(OTA_FLASH_QUEUE_LENGTH, sizeof(OtaFlashBlock_t));
        if (NULL == xOtaFlashQueue)
        {
            return pdFALSE;
        }
    }

    if (NULL == xOtaFlashTask)
    {
        if (pdPASS != xTaskCreate(prvOtaFlashTask,
                                  "OTA_FLASH",
                                  configMINIMAL_STACK_SIZE * 2U,
                                  NULL,
                                  configMAX_PRIORITIES - 1U,
                                  &xOtaFlashTask))
        {
            return pdFALSE;
        }
    }

    return pdTRUE;
}

static void prvResetDownloadState(void)
{
    ulOtaFlashPendingBlocks = 0U;
    xOtaFlashError = pdFALSE;
    ulOtaPayloadBytesReceived = 0U;
}

static void prvIncrementPendingBlocks(void)
{
    taskENTER_CRITICAL();
    ulOtaFlashPendingBlocks++;
    taskEXIT_CRITICAL();
}

static void prvDecrementPendingBlocks(void)
{
    taskENTER_CRITICAL();
    if (ulOtaFlashPendingBlocks > 0U)
    {
        ulOtaFlashPendingBlocks--;
    }
    taskEXIT_CRITICAL();
}

static BaseType_t prvWaitForFlashQueueDrained(void)
{
    while (ulOtaFlashPendingBlocks > 0U)
    {
        vTaskDelay(pdMS_TO_TICKS(1U));
    }

    return (pdTRUE == xOtaFlashError) ? pdFALSE : pdTRUE;
}

static BaseType_t prvGetPaddedLength(uint32_t length,
                                     uint32_t * pulPaddedLength)
{
    uint32_t paddedLength = length;
    uint32_t remainder;

    if ((0U == length) || (NULL == pulPaddedLength))
    {
        return pdFALSE;
    }

    remainder = paddedLength % FLASH_CF_MIN_PGM_SIZE;
    if (0U != remainder)
    {
        paddedLength += FLASH_CF_MIN_PGM_SIZE - remainder;
    }

    if (paddedLength < length)
    {
        return pdFALSE;
    }

    *pulPaddedLength = paddedLength;
    return pdTRUE;
}

static BaseType_t prvValidatePayloadRange(uint32_t offset,
                                          uint32_t length,
                                          uint32_t * pulPaddedLength)
{
    uint32_t paddedLength = 0U;

    if (pdTRUE != prvGetPaddedLength(length, &paddedLength))
    {
        return pdFALSE;
    }

    if ((offset > OTA_MAX_PAYLOAD_SIZE) || (paddedLength > (OTA_MAX_PAYLOAD_SIZE - offset)))
    {
        return pdFALSE;
    }

    *pulPaddedLength = paddedLength;
    return pdTRUE;
}

static BaseType_t prvEraseBufferArea(void)
{
    uint32_t numBlocks = FWUP_CFG_AREA_SIZE / FWUP_CFG_CF_BLK_SIZE;
    uint32_t eraseAddr = FWUP_CFG_BUF_AREA_ADDR_L + (FWUP_CFG_CF_BLK_SIZE * (numBlocks - 1U));
    flash_err_t flashError;

    if (pdTRUE != prvWaitForFlashQueueDrained())
    {
        return pdFALSE;
    }

    xSemaphoreTake(xSemaphoreFlashAccess, portMAX_DELAY);
    update_data_flash_control_block.status = DATA_FLASH_UPDATE_STATE_ERASE_WAIT_COMPLETE;
    flashError = R_FLASH_Erase((flash_block_address_t)eraseAddr, numBlocks);

    if (FLASH_SUCCESS == flashError)
    {
        xSemaphoreTake(xSemaphoreFlashAccess, portMAX_DELAY);
        xSemaphoreGive(xSemaphoreFlashAccess);
        return pdTRUE;
    }

    xSemaphoreGive(xSemaphoreFlashAccess);
    LogError(("prvEraseBufferArea: R_FLASH_Erase failed: %d", flashError));
    return pdFALSE;
}

static BaseType_t prvWriteFlashBlocking(uint32_t destAddr,
                                        const uint8_t * pData,
                                        uint32_t length)
{
    flash_err_t flashError;

    xSemaphoreTake(xSemaphoreFlashAccess, portMAX_DELAY);
    update_data_flash_control_block.status = DATA_FLASH_UPDATE_STATE_WRITE_WAIT_COMPLETE;
    flashError = R_FLASH_Write((uint32_t)pData, destAddr, length);

    if (FLASH_SUCCESS == flashError)
    {
        xSemaphoreTake(xSemaphoreFlashAccess, portMAX_DELAY);
        xSemaphoreGive(xSemaphoreFlashAccess);
        return pdTRUE;
    }

    xSemaphoreGive(xSemaphoreFlashAccess);
    LogError(("prvWriteFlashBlocking: R_FLASH_Write failed: %d at %08x", flashError, (unsigned int)destAddr));
    return pdFALSE;
}

static void prvOtaFlashTask(void * pvParameters)
{
    (void) pvParameters;

    static uint8_t flashWriteBuffer[mqttFileDownloader_CONFIG_BLOCK_SIZE + FLASH_CF_MIN_PGM_SIZE];
    OtaFlashBlock_t xBlock;

    for (;;)
    {
        if (pdPASS == xQueueReceive(xOtaFlashQueue, &xBlock, portMAX_DELAY))
        {
            uint32_t paddedLength = xBlock.paddedLength;

            if (paddedLength > sizeof(flashWriteBuffer))
            {
                xOtaFlashError = pdTRUE;
            }
            else
            {
                (void)memset(flashWriteBuffer, OTA_FLASH_PAD_VALUE, paddedLength);
                (void)memcpy(flashWriteBuffer, xBlock.pData, xBlock.length);

                if (pdTRUE != prvWriteFlashBlocking(FWUP_CFG_BUF_AREA_ADDR_L + OTA_PAYLOAD_BASE_OFFSET + xBlock.offset,
                                                    flashWriteBuffer,
                                                    paddedLength))
                {
                    xOtaFlashError = pdTRUE;
                }
            }

            vPortFree(xBlock.pData);
            prvDecrementPendingBlocks();
        }
    }
}

static BaseType_t prvWriteImageHeader(AfrOtaJobDocumentFields_t * pFileContext,
                                      const uint8_t * pRawSignature)
{
    OtaRsuHeader_t xHeader;

    (void)memset(&xHeader, 0, sizeof(xHeader));
    (void)memcpy(xHeader.magicCode, "RELFWV2", OTA_MAGIC_CODE_LEN);
    xHeader.imageFlag = OTA_IMAGE_FLAG_TESTING;
    (void)memcpy(xHeader.sigType, OTA_JsonFileSignatureKey, strlen(OTA_JsonFileSignatureKey));
    xHeader.sigSize = MAX_SIG_LENGTH;
    (void)memcpy(xHeader.sig, pRawSignature, MAX_SIG_LENGTH);
    (void)pFileContext;

    return prvWriteFlashBlocking(FWUP_CFG_BUF_AREA_ADDR_L,
                                 (const uint8_t *)&xHeader,
                                 sizeof(xHeader));
}

static OtaPalStatus_t prvVerifyReceivedPayload(AfrOtaJobDocumentFields_t * pFileContext)
{
    void * pCryptoContext = NULL;
    uint8_t * pSignerCert = NULL;
    uint32_t signerCertSize = 0U;
    uint32_t remaining = ulOtaPayloadBytesReceived;
    uint32_t offset = 0U;
    uint8_t * pReadAddr;
    BaseType_t xOk = pdTRUE;

    if (pdFALSE == CRYPTO_SignatureVerificationStart(&pCryptoContext,
                                                     cryptoASYMMETRIC_ALGORITHM_ECDSA,
                                                     cryptoHASH_ALGORITHM_SHA256))
    {
        return OtaPalSignatureCheckFailed;
    }

    while (remaining > 0U)
    {
        uint32_t chunkSize = (remaining > OTA_HASH_READ_CHUNK_SIZE) ? OTA_HASH_READ_CHUNK_SIZE : remaining;
        pReadAddr = (uint8_t *)(FWUP_CFG_BUF_AREA_ADDR_L + OTA_PAYLOAD_BASE_OFFSET + offset);
        CRYPTO_SignatureVerificationUpdate(pCryptoContext, (const uint8_t *)pReadAddr, chunkSize);
        offset += chunkSize;
        remaining -= chunkSize;
    }

    pSignerCert = prvGetSignerCert(&signerCertSize);
    if (NULL == pSignerCert)
    {
        (void)CRYPTO_SignatureVerificationFinal(pCryptoContext, NULL, 0U, NULL, 0U);
        xOk = pdFALSE;
    }
    else if (pdFALSE == CRYPTO_SignatureVerificationFinal(pCryptoContext,
                                                          (char *)pSignerCert,
                                                          signerCertSize,
                                                          (uint8_t *)pFileContext->signature,
                                                          pFileContext->signatureLen))
    {
        xOk = pdFALSE;
    }

    if (NULL != pSignerCert)
    {
        vPortFree(pSignerCert);
    }

    if (pdTRUE != xOk)
    {
        LogError(("prvVerifyReceivedPayload: signature verification failed"));
        return OtaPalSignatureCheckFailed;
    }

    LogInfo(("prvVerifyReceivedPayload: signature verification passed"));
    return OtaPalSuccess;
}

static uint8_t * prvGetSignerCert(uint32_t * pulSignerCertSize)
{
    uint8_t * pucCertData;
    uint8_t * pucSignerCert = NULL;
    size_t valueLength = prvGetCacheEntryLength(KVS_CODE_SIGN_CERT_ID);

    if (0U == valueLength)
    {
        LogError(("prvGetSignerCert: code signing certificate is not stored"));
        return NULL;
    }

    pucCertData = (uint8_t *)GetStringValue(KVS_CODE_SIGN_CERT_ID, valueLength);
    if (NULL == pucCertData)
    {
        return NULL;
    }

    pucSignerCert = pvPortMalloc(valueLength + 1U);
    if (NULL != pucSignerCert)
    {
        (void)memcpy(pucSignerCert, pucCertData, valueLength);
        pucSignerCert[valueLength] = 0U;
        *pulSignerCertSize = (uint32_t)valueLength + 1U;
    }

    vPortFree(pucCertData);
    return pucSignerCert;
}

static const char * prvImageStateToString(OtaImageState_t eState)
{
    switch (eState)
    {
        case OtaImageStateTesting:
            return OTA_IMAGE_STATE_TESTING_STR;

        case OtaImageStateAccepted:
            return OTA_IMAGE_STATE_ACCEPTED_STR;

        case OtaImageStateRejected:
            return OTA_IMAGE_STATE_REJECTED_STR;

        case OtaImageStateAborted:
            return OTA_IMAGE_STATE_ABORTED_STR;

        case OtaImageStateUnknown:
        default:
            return OTA_IMAGE_STATE_UNKNOWN_STR;
    }
}

static OtaImageState_t prvImageStateFromString(const char * pcState)
{
    if (NULL == pcState)
    {
        return OtaImageStateUnknown;
    }

    if (0 == strcmp(pcState, OTA_IMAGE_STATE_TESTING_STR))
    {
        return OtaImageStateTesting;
    }

    if (0 == strcmp(pcState, OTA_IMAGE_STATE_ACCEPTED_STR))
    {
        return OtaImageStateAccepted;
    }

    if (0 == strcmp(pcState, OTA_IMAGE_STATE_REJECTED_STR))
    {
        return OtaImageStateRejected;
    }

    if (0 == strcmp(pcState, OTA_IMAGE_STATE_ABORTED_STR))
    {
        return OtaImageStateAborted;
    }

    return OtaImageStateUnknown;
}

static BaseType_t prvPersistImageState(OtaImageState_t eState)
{
    const char * pcState = prvImageStateToString(eState);
    size_t xStateLength = strlen(pcState) + 1U;

    return (xprvWriteValueToImpl(KVS_OTA_IMAGE_STATE, (char *) pcState, (uint32_t) xStateLength) > 0) ? pdTRUE : pdFALSE;
}

static OtaImageState_t prvLoadPersistedImageState(void)
{
    size_t xStateLength = prvGetCacheEntryLength(KVS_OTA_IMAGE_STATE);
    char * pcState = NULL;
    OtaImageState_t eState = OtaImageStateUnknown;

    if (0U == xStateLength)
    {
        return OtaImageStateUnknown;
    }

    pcState = GetStringValue(KVS_OTA_IMAGE_STATE, xStateLength);
    if (NULL != pcState)
    {
        eState = prvImageStateFromString(pcState);
        vPortFree(pcState);
    }

    return eState;
}

static void prvResetDevice(void)
{
    R_BSP_SoftwareReset();
}

static BaseType_t prvActivateBank(void)
{
    flash_err_t err;

    R_BSP_SoftwareDelay(5000U, BSP_DELAY_MILLISECS);
    err = R_FLASH_Control(FLASH_CMD_BANK_TOGGLE, NULL);

    if (FLASH_SUCCESS != err)
    {
        LogError(("prvActivateBank: bank toggle failed: %d", err));
        return pdFALSE;
    }

    R_BSP_SoftwareDelay(500U, BSP_DELAY_MILLISECS);
    return pdTRUE;
}

static int ExtractECDSASignature(const unsigned char * derSignature,
                                 size_t derSignatureLength,
                                 unsigned char * rawSignature)
{
    unsigned char * p = (unsigned char *)derSignature;
    const unsigned char * end = derSignature + derSignatureLength;
    int ret = MBEDTLS_ERR_ERROR_CORRUPTION_DETECTED;
    size_t len;
    mbedtls_mpi r;
    mbedtls_mpi s;

    configASSERT(NULL != derSignature);
    mbedtls_mpi_init(&r);
    mbedtls_mpi_init(&s);

    if (0 != (ret = mbedtls_asn1_get_tag(&p, end, &len, MBEDTLS_ASN1_CONSTRUCTED | MBEDTLS_ASN1_SEQUENCE)))
    {
        ret += MBEDTLS_ERR_ECP_BAD_INPUT_DATA;
        goto cleanup;
    }

    if ((p + len) != end)
    {
        ret = MBEDTLS_ERROR_ADD(MBEDTLS_ERR_ECP_BAD_INPUT_DATA, MBEDTLS_ERR_ASN1_LENGTH_MISMATCH);
        goto cleanup;
    }

    if ((0 != (ret = mbedtls_asn1_get_mpi(&p, end, &r))) ||
        (0 != (ret = mbedtls_asn1_get_mpi(&p, end, &s))))
    {
        ret += MBEDTLS_ERR_ECP_BAD_INPUT_DATA;
        goto cleanup;
    }

    ret = mbedtls_mpi_write_binary(&r, &rawSignature[0], HALF_SIG_LENGTH);
    if (0 != ret)
    {
        goto cleanup;
    }

    ret = mbedtls_mpi_write_binary(&s, &rawSignature[HALF_SIG_LENGTH], HALF_SIG_LENGTH);
    if (0 != ret)
    {
        goto cleanup;
    }

    if (p != end)
    {
        ret = MBEDTLS_ERR_ECP_SIG_LEN_MISMATCH;
    }

cleanup:
    mbedtls_mpi_free(&r);
    mbedtls_mpi_free(&s);
    return ret;
}
