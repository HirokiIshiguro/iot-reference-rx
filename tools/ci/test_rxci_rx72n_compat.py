"""Host checks for the RX72N TSIP compatibility record adapter."""
import unittest

from tools.ci.tests import test_product_oss_api as host


@unittest.skipUnless(host.GCC or host.MSVC, "Host C compiler required")
class Rx72nCompatTests(unittest.TestCase):
    def test_record_chunks_authentication_and_tail(self):
        app = (host.ROOT / "Projects/aws_ether_rx72n_envision_kit_tsip_compat"
               / "e2studio_ccrx/src/application_code")
        headers = {
            "FreeRTOS.h": (
                "typedef int BaseType_t;\n#define pdTRUE 1\n#define pdFALSE 0\n"
            ),
            "mbedtls/error.h": "#define MBEDTLS_ERR_PLATFORM_HW_ACCEL_FAILED (-5)\n",
            "mbedtls/gcm.h": (
                '#include <stddef.h>\n#include "gcm_alt.h"\n'
                "typedef int mbedtls_cipher_id_t;\n#define MBEDTLS_CIPHER_ID_AES 1\n"
                "#define MBEDTLS_ERR_GCM_BAD_INPUT (-3)\n#define MBEDTLS_ERR_GCM_AUTH_FAILED (-4)\n"
                "#define MBEDTLS_GCM_ENCRYPT 1\n#define MBEDTLS_GCM_DECRYPT 0\n"
            ),
            "mbedtls/platform.h": (
                "#include <stdlib.h>\n#define mbedtls_calloc calloc\n#define mbedtls_free free\n"
                "#define MBEDTLS_ERR_CIPHER_ALLOC_FAILED (-6)\n"
            ),
            "mbedtls/platform_util.h": (
                "#include <string.h>\n"
                "static inline void mbedtls_platform_zeroize(void *p, size_t n) { memset(p, 0, n); }\n"
            ),
            "mbedtls/threading.h": (
                "typedef int mbedtls_threading_mutex_t;\n"
                "int mbedtls_platform_mutex_lock(mbedtls_threading_mutex_t *mutex);\n"
                "int mbedtls_platform_mutex_unlock(mbedtls_threading_mutex_t *mutex);\n"
            ),
            "r_tsip_rx_if.h": r"""
#ifndef TEST_TSIP_H
#define TEST_TSIP_H
#include <stdint.h>
typedef int e_tsip_err_t;
typedef struct tsip_aes_key_index { int index; } tsip_aes_key_index_t;
typedef int tsip_update_key_ring_t;
typedef int tsip_aes_handle_t;
typedef int tsip_gcm_handle_t;
#define TSIP_SUCCESS 0
#define TSIP_ERR_FAIL 1
#define TSIP_ERR_AUTHENTICATION 2
e_tsip_err_t R_TSIP_GenerateAes128KeyIndex(uint8_t *, uint8_t *, uint8_t *, tsip_aes_key_index_t *);
e_tsip_err_t R_TSIP_GenerateUpdateKeyRingKeyIndex(uint8_t *, uint8_t *, uint8_t *, tsip_update_key_ring_t *);
e_tsip_err_t R_TSIP_UpdateAes128KeyIndex(uint8_t *, uint8_t *, tsip_aes_key_index_t *);
e_tsip_err_t R_TSIP_GenerateRandomNumber(uint32_t *);
e_tsip_err_t R_TSIP_Aes128EcbEncryptInit(tsip_aes_handle_t *, tsip_aes_key_index_t *);
e_tsip_err_t R_TSIP_Aes128EcbEncryptUpdate(tsip_aes_handle_t *, uint8_t *, uint8_t *, uint32_t);
e_tsip_err_t R_TSIP_Aes128EcbEncryptFinal(tsip_aes_handle_t *, uint8_t *, uint32_t *);
e_tsip_err_t R_TSIP_Aes128CbcEncryptInit(tsip_aes_handle_t *, tsip_aes_key_index_t *, uint8_t *);
e_tsip_err_t R_TSIP_Aes128CbcEncryptUpdate(tsip_aes_handle_t *, uint8_t *, uint8_t *, uint32_t);
e_tsip_err_t R_TSIP_Aes128CbcEncryptFinal(tsip_aes_handle_t *, uint8_t *, uint32_t *);
e_tsip_err_t R_TSIP_Aes128GcmEncryptInit(tsip_gcm_handle_t *, tsip_aes_key_index_t *, uint8_t *, uint32_t);
e_tsip_err_t R_TSIP_Aes128GcmEncryptUpdate(tsip_gcm_handle_t *, uint8_t *, uint8_t *, uint32_t, uint8_t *, uint32_t);
e_tsip_err_t R_TSIP_Aes128GcmEncryptFinal(tsip_gcm_handle_t *, uint8_t *, uint32_t *, uint8_t *);
e_tsip_err_t R_TSIP_Aes128GcmDecryptInit(tsip_gcm_handle_t *, tsip_aes_key_index_t *, uint8_t *, uint32_t);
e_tsip_err_t R_TSIP_Aes128GcmDecryptUpdate(tsip_gcm_handle_t *, uint8_t *, uint8_t *, uint32_t, uint8_t *, uint32_t);
e_tsip_err_t R_TSIP_Aes128GcmDecryptFinal(tsip_gcm_handle_t *, uint8_t *, uint32_t *, uint8_t *, uint32_t);
#endif
""",
            "r_common_api_tsip.h": (
                '#include "r_tsip_rx_if.h"\n'
                "#define COMMONAPI_SUCCESS 0\n"
                "int R_Demo_Common_API_TSIP_Open(void *, tsip_update_key_ring_t *);\n"
                "int R_Demo_Common_API_TSIP_Close(void);\n"
            ),
        }
        host.ProductApiTests().compile_run(
            r"""
#include <assert.h>
#include <string.h>
#include "tsip_gcm_alt.c"

mbedtls_threading_mutex_t mutexUseTsip;
static unsigned mutex_locked, parts, bytes, calls;
static int auth;

int mbedtls_platform_mutex_lock(mbedtls_threading_mutex_t *mutex)
{ (void)mutex; assert(mutex_locked++ == 0); return 0; }
int mbedtls_platform_mutex_unlock(mbedtls_threading_mutex_t *mutex)
{ (void)mutex; assert(mutex_locked-- == 1); return 0; }

BaseType_t xTsipProvisioningReadSlot(TsipProvisioningSlot_t slot, uint8_t *buffer,
                                    uint32_t size, uint32_t *actual)
{
    assert(mutex_locked);
    assert(size == (slot == TSIP_PROVISIONING_SLOT_KEY_UPDATE_KEY ? 108 : 92));
    for (uint32_t i = 0; i < size; ++i) buffer[i] = (uint8_t)i;
    *actual = size;
    parts |= 1u << slot;
    return pdTRUE;
}
static int check_blob(uint8_t *w, uint8_t *iv, uint8_t *e, int *index)
{ assert(w[0] == 8 && iv[0] == 40 && e[0] == 56); *index = 1; return 0; }
e_tsip_err_t R_TSIP_GenerateAes128KeyIndex(uint8_t *w, uint8_t *v, uint8_t *e, tsip_aes_key_index_t *k)
{ return check_blob(w, v, e, &k->index); }
e_tsip_err_t R_TSIP_GenerateUpdateKeyRingKeyIndex(uint8_t *w, uint8_t *v, uint8_t *e, int *k)
{ return check_blob(w, v, e, k); }
int R_Demo_Common_API_TSIP_Open(void *root, int *ring)
{ assert(mutex_locked && root == NULL && (!ring || *ring == 1)); return 0; }
int R_Demo_Common_API_TSIP_Close(void) { assert(mutex_locked); return 0; }
e_tsip_err_t R_TSIP_UpdateAes128KeyIndex(uint8_t *v, uint8_t *e, tsip_aes_key_index_t *k)
{ (void)v; (void)e; (void)k; return TSIP_ERR_FAIL; }
e_tsip_err_t R_TSIP_GenerateRandomNumber(uint32_t *words)
{ (void)words; return TSIP_ERR_FAIL; }
e_tsip_err_t R_TSIP_Aes128EcbEncryptInit(int *h, tsip_aes_key_index_t *k)
{ (void)h; (void)k; return TSIP_ERR_FAIL; }
e_tsip_err_t R_TSIP_Aes128EcbEncryptUpdate(int *h, uint8_t *p, uint8_t *c, uint32_t n)
{ (void)h; (void)p; (void)c; (void)n; return TSIP_ERR_FAIL; }
e_tsip_err_t R_TSIP_Aes128EcbEncryptFinal(int *h, uint8_t *b, uint32_t *n)
{ (void)h; (void)b; (void)n; return TSIP_ERR_FAIL; }
e_tsip_err_t R_TSIP_Aes128CbcEncryptInit(int *h, tsip_aes_key_index_t *k, uint8_t *v)
{ (void)h; (void)k; (void)v; return TSIP_ERR_FAIL; }
e_tsip_err_t R_TSIP_Aes128CbcEncryptUpdate(int *h, uint8_t *p, uint8_t *c, uint32_t n)
{ return R_TSIP_Aes128EcbEncryptUpdate(h,p,c,n); }
e_tsip_err_t R_TSIP_Aes128CbcEncryptFinal(int *h, uint8_t *b, uint32_t *n)
{ return R_TSIP_Aes128EcbEncryptFinal(h,b,n); }
e_tsip_err_t R_TSIP_Aes128GcmEncryptInit(int *h, tsip_aes_key_index_t *k, uint8_t *v, uint32_t n)
{ assert(mutex_locked && n == 12 && v && k->index == 1); *h = 1; bytes = calls = 0; return 0; }
e_tsip_err_t R_TSIP_Aes128GcmDecryptInit(int *h, tsip_aes_key_index_t *k, uint8_t *v, uint32_t n)
{ return R_TSIP_Aes128GcmEncryptInit(h,k,v,n); }
e_tsip_err_t R_TSIP_Aes128GcmEncryptUpdate(int *h, uint8_t *p, uint8_t *c, uint32_t n,
                                          uint8_t *ad, uint32_t na)
{
    assert(mutex_locked && *h && p == c && (uintptr_t)c % 4 == 0);
    assert(calls++ ? na == 0 : na == 13 && ad[0] == 7);
    memset(c, 0x55, n - n % 16);
    bytes += n;
    return 0;
}
e_tsip_err_t R_TSIP_Aes128GcmDecryptUpdate(int *h, uint8_t *p, uint8_t *c, uint32_t n,
                                          uint8_t *ad, uint32_t na)
{ return R_TSIP_Aes128GcmEncryptUpdate(h,p,c,n,ad,na); }
e_tsip_err_t R_TSIP_Aes128GcmEncryptFinal(int *h, uint8_t *c, uint32_t *n, uint8_t *tag)
{ assert(mutex_locked && *h); memset(c, 0x33, 16); memset(tag, 0x10, 16); *n=bytes; return 0; }
e_tsip_err_t R_TSIP_Aes128GcmDecryptFinal(int *h, uint8_t *c, uint32_t *n, uint8_t *tag, uint32_t len)
{ assert(len == 16 && tag[0] == 0x10); R_TSIP_Aes128GcmEncryptFinal(h,c,n,tag); return auth; }

int main(void)
{
    mbedtls_gcm_context ctx;
    unsigned char record[276] = {0}, nonce[12] = {0}, aad[13] = {7}, tag[16] = {0};

    assert(xRx72nTsipCompatPrepare() == pdTRUE && !mutex_locked);
    assert(parts == ((1u << TSIP_PROVISIONING_SLOT_KEY_UPDATE_KEY) |
                     (1u << TSIP_PROVISIONING_SLOT_KEY_UPDATE_CBC_AES128) |
                     (1u << TSIP_PROVISIONING_SLOT_KEY_UPDATE_CBC_MAC_AES128)));
    mbedtls_gcm_init(&ctx);
    assert(mbedtls_gcm_setkey(&ctx, MBEDTLS_CIPHER_ID_AES, record, 128) != 0);
    assert(ctx.key_index == NULL && !mutex_locked);
    ctx.key_index = calloc(1, sizeof(*ctx.key_index));
    assert(ctx.key_index != NULL);
    ctx.key_index->index = 1;
    assert(mbedtls_gcm_crypt_and_tag(&ctx, MBEDTLS_GCM_ENCRYPT, 275, nonce, 12,
                                     aad, 13, record, record, 16, tag) == 0);
    assert(calls == 2 && bytes == 275 && tag[0] == 0x10);
    assert(record[271] == 0x55 && record[272] == 0x33 && record[274] == 0x33 && record[275] == 0);
    auth = TSIP_ERR_AUTHENTICATION;
    assert(mbedtls_gcm_auth_decrypt(&ctx, 275, nonce, 12, aad, 13, tag, 16,
                                    record, record) == MBEDTLS_ERR_GCM_AUTH_FAILED);
    for (unsigned i = 0; i < sizeof(record); ++i) assert(record[i] == 0);
    mbedtls_gcm_free(&ctx);
    assert(!mutex_locked && ctx.key_index == NULL);
    return 0;
}
""",
            headers=headers,
            extra_includes=[app, host.ROOT / "Demos/tsip_provisioning"],
        )
