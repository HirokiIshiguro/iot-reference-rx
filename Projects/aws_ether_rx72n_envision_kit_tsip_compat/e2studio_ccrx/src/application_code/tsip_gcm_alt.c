/* RX72N experimental one-shot TLS 1.2 AES-128-GCM backend. */
#include <stdint.h>
#include <string.h>

#include "FreeRTOS.h"
#include "mbedtls/error.h"
#include "mbedtls/gcm.h"
#include "mbedtls/platform.h"
#include "mbedtls/platform_util.h"
#include "mbedtls/threading.h"
#include "r_common_api_tsip.h"
#include "tsip_provisioning_store.h"

#define AES_BLOCK_BYTES       (16U)
#define GCM_IV_BYTES          (12U)
#define GCM_CHUNK_BYTES       (256U)
#define TLS_RECORD_BYTES      (16384U)
/* SKMT binary layout including its 8-byte header. */
#define SKMT_WUFPK_OFFSET      (8U)
#define SKMT_IV_OFFSET         (40U)
#define SKMT_ENCRYPTED_OFFSET  (56U)
#define SKMT_KUK_BYTES         (108U)
#define SKMT_AES_BYTES         (92U)

typedef union TsipBuffer
{
    uint32_t words[GCM_CHUNK_BYTES / sizeof(uint32_t)];
    uint8_t bytes[GCM_CHUNK_BYTES];
} TsipBuffer_t;

extern mbedtls_threading_mutex_t mutexUseTsip;
static tsip_aes_key_index_t xCbcIndex;
static tsip_aes_key_index_t xMacIndex;
static BaseType_t xProvisioned = pdFALSE;

static BaseType_t prvReadBlob(TsipProvisioningSlot_t slot, TsipBuffer_t *blob, uint32_t size)
{
    uint32_t actual = 0;
    return (xTsipProvisioningReadSlot(slot, blob->bytes, size, &actual) == pdTRUE &&
            actual == size) ? pdTRUE : pdFALSE;
}

static e_tsip_err_t prvImportAesIndex(TsipBuffer_t *blob, tsip_aes_key_index_t *index)
{
    return R_TSIP_GenerateAes128KeyIndex(blob->bytes + SKMT_WUFPK_OFFSET,
                                       blob->bytes + SKMT_IV_OFFSET,
                                       blob->bytes + SKMT_ENCRYPTED_OFFSET, index);
}

BaseType_t xRx72nTsipCompatPrepare(void)
{
    TsipBuffer_t blob;
    tsip_update_key_ring_t key_ring;
    e_tsip_err_t status = TSIP_ERR_FAIL;

    /* Called after LittleFS is mounted and before the network or PKCS#11 starts. */
    if (mbedtls_platform_mutex_lock(&mutexUseTsip) != 0)
    {
        return pdFALSE;
    }
    if (prvReadBlob(TSIP_PROVISIONING_SLOT_KEY_UPDATE_CBC_AES128, &blob, SKMT_AES_BYTES) == pdTRUE &&
        R_Demo_Common_API_TSIP_Open(NULL, NULL) == COMMONAPI_SUCCESS &&
        prvImportAesIndex(&blob, &xCbcIndex) == TSIP_SUCCESS &&
        prvReadBlob(TSIP_PROVISIONING_SLOT_KEY_UPDATE_CBC_MAC_AES128, &blob, SKMT_AES_BYTES) == pdTRUE &&
        prvImportAesIndex(&blob, &xMacIndex) == TSIP_SUCCESS &&
        prvReadBlob(TSIP_PROVISIONING_SLOT_KEY_UPDATE_KEY, &blob, SKMT_KUK_BYTES) == pdTRUE)
    {
        status = R_TSIP_GenerateUpdateKeyRingKeyIndex(blob.bytes + SKMT_WUFPK_OFFSET,
                                                     blob.bytes + SKMT_IV_OFFSET,
                                                     blob.bytes + SKMT_ENCRYPTED_OFFSET, &key_ring);
        if (status == TSIP_SUCCESS &&
            (R_Demo_Common_API_TSIP_Close() != COMMONAPI_SUCCESS ||
             R_Demo_Common_API_TSIP_Open(NULL, &key_ring) != COMMONAPI_SUCCESS))
        {
            status = TSIP_ERR_FAIL;
        }
    }

    xProvisioned = (status == TSIP_SUCCESS) ? pdTRUE : pdFALSE;
    mbedtls_platform_zeroize(&key_ring, sizeof(key_ring));
    mbedtls_platform_zeroize(&blob, sizeof(blob));
    (void)mbedtls_platform_mutex_unlock(&mutexUseTsip);
    return xProvisioned;
}

void mbedtls_gcm_init(mbedtls_gcm_context *ctx)
{
    memset(ctx, 0, sizeof(*ctx));
}

void mbedtls_gcm_free(mbedtls_gcm_context *ctx)
{
    if (ctx != NULL && ctx->key_index != NULL)
    {
        mbedtls_platform_zeroize(ctx->key_index, sizeof(*ctx->key_index));
        mbedtls_free(ctx->key_index);
        ctx->key_index = NULL;
    }
}

int mbedtls_gcm_setkey(mbedtls_gcm_context *ctx, mbedtls_cipher_id_t cipher,
                       const unsigned char *key, unsigned int keybits)
{
    tsip_aes_handle_t aes;
    tsip_aes_key_index_t *key_index;
    uint32_t iv_words[4];
    uint32_t plain_words[8];
    uint32_t encrypted_words[8];
    uint32_t tail_words[4];
    uint32_t tail_length;
    uint8_t *plain = (uint8_t *)plain_words;
    e_tsip_err_t status;
    e_tsip_err_t final_status;

    mbedtls_gcm_free(ctx);
    if (cipher != MBEDTLS_CIPHER_ID_AES || keybits != 128U || key == NULL)
    {
        return MBEDTLS_ERR_GCM_BAD_INPUT;
    }
    if (xProvisioned != pdTRUE || mbedtls_platform_mutex_lock(&mutexUseTsip) != 0)
    {
        return MBEDTLS_ERR_PLATFORM_HW_ACCEL_FAILED;
    }

    key_index = mbedtls_calloc(1, sizeof(*key_index));
    if (key_index == NULL)
    {
        (void)mbedtls_platform_mutex_unlock(&mutexUseTsip);
        return MBEDTLS_ERR_CIPHER_ALLOC_FAILED;
    }

    /* R20AN0371 §7.5: for a one-block key, CBC-MAC is one ECB encryption
     * from a zero MAC. CBC encrypts the key followed by that MAC. */
    status = R_TSIP_GenerateRandomNumber(iv_words);
    if (status == TSIP_SUCCESS)
    {
        status = R_TSIP_Aes128EcbEncryptInit(&aes, &xMacIndex);
    }
    if (status == TSIP_SUCCESS)
    {
        memcpy(plain, key, AES_BLOCK_BYTES);
        status = R_TSIP_Aes128EcbEncryptUpdate(&aes, plain, plain + AES_BLOCK_BYTES, AES_BLOCK_BYTES);
        final_status = R_TSIP_Aes128EcbEncryptFinal(&aes, (uint8_t *)tail_words, &tail_length);
        if (status == TSIP_SUCCESS)
        {
            status = final_status;
        }
    }
    if (status == TSIP_SUCCESS)
    {
        status = R_TSIP_Aes128CbcEncryptInit(&aes, &xCbcIndex, (uint8_t *)iv_words);
    }
    if (status == TSIP_SUCCESS)
    {
        status = R_TSIP_Aes128CbcEncryptUpdate(&aes, plain, (uint8_t *)encrypted_words, sizeof(plain_words));
        final_status = R_TSIP_Aes128CbcEncryptFinal(&aes, (uint8_t *)tail_words, &tail_length);
        if (status == TSIP_SUCCESS)
        {
            status = final_status;
        }
    }
    mbedtls_platform_zeroize(plain_words, sizeof(plain_words));
    mbedtls_platform_zeroize(tail_words, sizeof(tail_words));

    if (status == TSIP_SUCCESS)
    {
        status = R_TSIP_UpdateAes128KeyIndex((uint8_t *)iv_words, (uint8_t *)encrypted_words, key_index);
    }
    mbedtls_platform_zeroize(encrypted_words, sizeof(encrypted_words));
    mbedtls_platform_zeroize(iv_words, sizeof(iv_words));
    mbedtls_platform_zeroize(&aes, sizeof(aes));
    (void)mbedtls_platform_mutex_unlock(&mutexUseTsip);

    if (status != TSIP_SUCCESS)
    {
        mbedtls_platform_zeroize(key_index, sizeof(*key_index));
        mbedtls_free(key_index);
        return MBEDTLS_ERR_PLATFORM_HW_ACCEL_FAILED;
    }
    ctx->key_index = key_index;
    return 0;
}

static int prvGcmRecord(mbedtls_gcm_context *ctx, int mode, size_t length,
                        const unsigned char *iv, size_t iv_len,
                        const unsigned char *add, size_t add_len,
                        const unsigned char *input, unsigned char *output, size_t tag_len,
                        unsigned char *tag)
{
    tsip_gcm_handle_t handle;
    TsipBuffer_t chunk;
    uint32_t iv_words[3];
    uint32_t aad_words[4];
    uint32_t final_words[4];
    uint32_t tag_words[4];
    uint32_t final_length;
    e_tsip_err_t status;
    int result = MBEDTLS_ERR_PLATFORM_HW_ACCEL_FAILED;
    size_t offset = 0;
    size_t tail = length % AES_BLOCK_BYTES;
    const int encrypt = (mode == MBEDTLS_GCM_ENCRYPT);

    if (ctx->key_index == NULL || iv == NULL || iv_len != GCM_IV_BYTES ||
        add_len > 13U || (add_len != 0 && add == NULL) ||
        tag == NULL || tag_len != AES_BLOCK_BYTES || length > TLS_RECORD_BYTES ||
        (length != 0 && (input == NULL || output == NULL)) ||
        (input != output && length != 0 &&
         ((uintptr_t)input < (uintptr_t)output ?
           (uintptr_t)output - (uintptr_t)input : (uintptr_t)input - (uintptr_t)output) < length))
    {
        return MBEDTLS_ERR_GCM_BAD_INPUT;
    }
    if (mbedtls_platform_mutex_lock(&mutexUseTsip) != 0)
    {
        return result;
    }

    memcpy(iv_words, iv, iv_len);
    if (add_len != 0)
    {
        memcpy(aad_words, add, add_len);
    }
    if (!encrypt)
    {
        memcpy(tag_words, tag, tag_len);
    }
    status = encrypt ?
        R_TSIP_Aes128GcmEncryptInit(&handle, ctx->key_index, (uint8_t *)iv_words, GCM_IV_BYTES) :
        R_TSIP_Aes128GcmDecryptInit(&handle, ctx->key_index, (uint8_t *)iv_words, GCM_IV_BYTES);
    if (status == TSIP_SUCCESS)
    {
        e_tsip_err_t final_status;
        /* FIT accepts identical input/output addresses. Stage aligned blocks
         * because the TLS record buffer need not be word aligned. */
        do
        {
            size_t count = length - offset;
            if (count > sizeof(chunk.bytes))
            {
                count = sizeof(chunk.bytes);
            }
            if (count != 0)
            {
                memcpy(chunk.bytes, input + offset, count);
            }
            status = encrypt ?
                R_TSIP_Aes128GcmEncryptUpdate(&handle, chunk.bytes, chunk.bytes, (uint32_t)count,
                                              (uint8_t *)aad_words, (uint32_t)add_len) :
                R_TSIP_Aes128GcmDecryptUpdate(&handle, chunk.bytes, chunk.bytes, (uint32_t)count,
                                              (uint8_t *)aad_words, (uint32_t)add_len);
            if (status == TSIP_SUCCESS && count >= AES_BLOCK_BYTES)
            {
                memcpy(output + offset, chunk.bytes, count - count % AES_BLOCK_BYTES);
            }
            offset += count;
            add_len = 0;
        } while (status == TSIP_SUCCESS && offset < length);

        final_status = encrypt ?
            R_TSIP_Aes128GcmEncryptFinal(&handle, (uint8_t *)final_words, &final_length, (uint8_t *)tag_words) :
            R_TSIP_Aes128GcmDecryptFinal(&handle, (uint8_t *)final_words, &final_length, (uint8_t *)tag_words,
                                         AES_BLOCK_BYTES);
        if (status == TSIP_SUCCESS)
        {
            if (final_status == TSIP_SUCCESS)
            {
                if (tail != 0)
                {
                    memcpy(output + length - tail, final_words, tail);
                }
                if (encrypt)
                {
                    memcpy(tag, tag_words, tag_len);
                }
                result = 0;
            }
            else if (!encrypt && final_status == TSIP_ERR_AUTHENTICATION)
            {
                result = MBEDTLS_ERR_GCM_AUTH_FAILED;
            }
        }
    }
    if (result != 0 && length != 0)
    {
        mbedtls_platform_zeroize(output, length);
    }
    mbedtls_platform_zeroize(&chunk, sizeof(chunk));
    mbedtls_platform_zeroize(final_words, sizeof(final_words));
    mbedtls_platform_zeroize(tag_words, sizeof(tag_words));
    mbedtls_platform_zeroize(&handle, sizeof(handle));
    (void)mbedtls_platform_mutex_unlock(&mutexUseTsip);
    return result;
}

int mbedtls_gcm_crypt_and_tag(mbedtls_gcm_context *ctx, int mode, size_t length,
                              const unsigned char *iv, size_t iv_len,
                              const unsigned char *add, size_t add_len,
                              const unsigned char *input, unsigned char *output,
                              size_t tag_len, unsigned char *tag)
{
    if (mode != MBEDTLS_GCM_ENCRYPT)
    {
        return MBEDTLS_ERR_GCM_BAD_INPUT;
    }
    return prvGcmRecord(ctx, mode, length, iv, iv_len, add, add_len, input, output, tag_len, tag);
}

int mbedtls_gcm_auth_decrypt(mbedtls_gcm_context *ctx, size_t length,
                             const unsigned char *iv, size_t iv_len,
                             const unsigned char *add, size_t add_len,
                             const unsigned char *tag, size_t tag_len,
                             const unsigned char *input, unsigned char *output)
{
    unsigned char expected_tag[AES_BLOCK_BYTES];
    if (tag == NULL || tag_len != sizeof(expected_tag))
    {
        return MBEDTLS_ERR_GCM_BAD_INPUT;
    }
    memcpy(expected_tag, tag, sizeof(expected_tag));
    return prvGcmRecord(ctx, MBEDTLS_GCM_DECRYPT, length, iv, iv_len, add, add_len,
                        input, output, tag_len, expected_tag);
}

/* The generic cipher wrapper links these functions. The TLS 1.2 AEAD
 * record path uses only the one-shot functions above. */
int mbedtls_gcm_starts(mbedtls_gcm_context *ctx, int mode, const unsigned char *iv, size_t iv_len)
{
    (void)ctx;
    (void)mode;
    (void)iv;
    (void)iv_len;
    return MBEDTLS_ERR_GCM_BAD_INPUT;
}

int mbedtls_gcm_update_ad(mbedtls_gcm_context *ctx, const unsigned char *add, size_t add_len)
{
    (void)ctx;
    (void)add;
    (void)add_len;
    return MBEDTLS_ERR_GCM_BAD_INPUT;
}

int mbedtls_gcm_update(mbedtls_gcm_context *ctx, const unsigned char *input, size_t input_length,
                       unsigned char *output, size_t output_size, size_t *output_length)
{
    (void)ctx;
    (void)input;
    (void)input_length;
    (void)output;
    (void)output_size;
    *output_length = 0;
    return MBEDTLS_ERR_GCM_BAD_INPUT;
}

int mbedtls_gcm_finish(mbedtls_gcm_context *ctx, unsigned char *output, size_t output_size,
                       size_t *output_length, unsigned char *tag, size_t tag_len)
{
    (void)ctx;
    (void)output;
    (void)output_size;
    *output_length = 0;
    (void)tag;
    (void)tag_len;
    return MBEDTLS_ERR_GCM_BAD_INPUT;
}
