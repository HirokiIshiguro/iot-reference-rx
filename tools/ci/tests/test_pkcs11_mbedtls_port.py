"""The product PKCS11 adapter links against both pristine Mbed TLS backends."""
from pathlib import Path
import unittest
from tools.ci.tests import test_product_oss_api as product_api

ROOT=Path(__file__).resolve().parents[3]
PORT=ROOT/"Middleware/network_transport/using_mbedtls_pkcs11"
PKCS=ROOT/"Middleware/FreeRTOS/corePKCS11/source"


@unittest.skipUnless(product_api.GCC or product_api.MSVC,"Host C compiler required")
class Pkcs11MbedtlsPortTests(unittest.TestCase):
    def test_rng_failure_and_ecdsa_public_context_signature_roundtrip_both_versions(self):
        headers={
            "logging_levels.h":"#define LOG_ERROR 1\n",
            "logging_stack.h":"#define LogError(...) ((void)0)\n#define LogInfo(...) ((void)0)\n#define LogDebug(...) ((void)0)\n",
            "core_pkcs11_config.h":"#ifndef PORT_PKCS_CONFIG\n#define PORT_PKCS_CONFIG\n#include <stdlib.h>\n#include <assert.h>\n#define configASSERT(x) assert(x)\n#define pvPortMalloc malloc\n#define vPortFree free\n#endif\n",
            "port_mbedtls_config.h":"""#ifndef PORT_MBED_CONFIG
#define PORT_MBED_CONFIG
#define MBEDTLS_ALLOW_PRIVATE_ACCESS
#define MBEDTLS_FUNC_ENABLE
#define APP_ALL_PRINT(...) ((void)0)
#define MBEDTLS_PLATFORM_C
#define MBEDTLS_KEY_EXCHANGE_PSK_ENABLED
#define MBEDTLS_ASN1_PARSE_C
#define MBEDTLS_ASN1_WRITE_C
#define MBEDTLS_BIGNUM_C
#define MBEDTLS_ECP_C
#define MBEDTLS_ECDSA_C
#define MBEDTLS_ECP_DP_SECP256R1_ENABLED
#define MBEDTLS_RSA_C
#define MBEDTLS_PKCS1_V15
#define MBEDTLS_PK_C
#define MBEDTLS_MD_C
#define MBEDTLS_SHA256_C
#define MBEDTLS_SHA224_C
#define MBEDTLS_OID_C
#endif
""",
        }
        source=r'''
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#define MBEDTLS_ALLOW_PRIVATE_ACCESS
#include "mbedtls_pk_pkcs11.h"
#include "mbedtls/ecdsa.h"
#include "mbedtls/version.h"
static CK_FUNCTION_LIST functions;
static mbedtls_ecdsa_context synthetic;
static unsigned state=17;
static int list_error, random_error, sign_error;
static unsigned char point[67];
static int entropy(void *ctx,unsigned char *output,size_t length) {
    size_t i;(void)ctx;for(i=0;i<length;i++){state=state*1664525U+1013904223U;output[i]=(unsigned char)(state>>24);}return 0;
}
void vOutputString(const char *text){(void)text;}
CK_RV C_GetFunctionList(CK_FUNCTION_LIST_PTR_PTR output) {
    if(list_error)return CKR_GENERAL_ERROR;*output=&functions;return CKR_OK;
}
static CK_RV random_bytes(CK_SESSION_HANDLE session,CK_BYTE_PTR output,CK_ULONG size) {
    assert(session==9);if(random_error)return CKR_GENERAL_ERROR;return entropy(NULL,output,size)?CKR_GENERAL_ERROR:CKR_OK;
}
static CK_RV attribute(CK_SESSION_HANDLE session,CK_OBJECT_HANDLE handle,CK_ATTRIBUTE_PTR values,CK_ULONG count) {
    CK_ULONG i;static const unsigned char parameters[]={6,8,42,134,72,206,61,3,1,7};
    assert(session==9 && handle==7);
    for(i=0;i<count;i++) {
        if(values[i].type==CKA_KEY_TYPE){assert(values[i].pValue);*(CK_KEY_TYPE *)values[i].pValue=CKK_ECDSA;}
        else if(values[i].type==CKA_EC_PARAMS){if(values[i].pValue)memcpy(values[i].pValue,parameters,sizeof(parameters));values[i].ulValueLen=sizeof(parameters);}
        else if(values[i].type==CKA_EC_POINT){if(values[i].pValue)memcpy(values[i].pValue,point,sizeof(point));values[i].ulValueLen=sizeof(point);}
        else return CKR_ATTRIBUTE_TYPE_INVALID;
    }return CKR_OK;
}
static CK_RV sign_init(CK_SESSION_HANDLE session,CK_MECHANISM_PTR mechanism,CK_OBJECT_HANDLE handle) {
    assert(session==9 && handle==7 && mechanism->mechanism==CKM_ECDSA);return sign_error?CKR_GENERAL_ERROR:CKR_OK;
}
static CK_RV sign_bytes(CK_SESSION_HANDLE session,CK_BYTE_PTR hash,CK_ULONG hash_size,CK_BYTE_PTR output,CK_ULONG_PTR size) {
    mbedtls_mpi r,s;int result;assert(session==9 && hash_size==32 && *size>=64);
    mbedtls_mpi_init(&r);mbedtls_mpi_init(&s);
    result=mbedtls_ecdsa_sign(&synthetic.grp,&r,&s,&synthetic.d,hash,hash_size,entropy,NULL);
    if(!result)result=mbedtls_mpi_write_binary(&r,output,32);
    if(!result)result=mbedtls_mpi_write_binary(&s,output+32,32);
    mbedtls_mpi_free(&r);mbedtls_mpi_free(&s);*size=64;return result?CKR_GENERAL_ERROR:CKR_OK;
}
int main(void) {
    unsigned char bytes[32],hash[32]={1},signature[80];size_t length=0,point_length=0;
    CK_SESSION_HANDLE session=9;mbedtls_pk_context private_context,public_context;
    functions.C_GenerateRandom=random_bytes;functions.C_GetAttributeValue=attribute;
    functions.C_SignInit=sign_init;functions.C_Sign=sign_bytes;
    assert(lPKCS11RandomCallback(NULL,bytes,sizeof(bytes))==-1);
    assert(lPKCS11RandomCallback(&session,NULL,sizeof(bytes))==-1);
    list_error=1;assert(lPKCS11RandomCallback(&session,bytes,sizeof(bytes))==-1);list_error=0;
    random_error=1;assert(lPKCS11RandomCallback(&session,bytes,sizeof(bytes))!=0);random_error=0;
    assert(!lPKCS11RandomCallback(&session,bytes,sizeof(bytes)));
    mbedtls_pk_init(&private_context);mbedtls_pk_init(&public_context);
    assert(xPKCS11_initMbedtlsPkContext(NULL,session,7)==CKR_ARGUMENTS_BAD);
    assert(xPKCS11_initMbedtlsPkContext(&private_context,CK_INVALID_HANDLE,7)==CKR_SESSION_HANDLE_INVALID);
    mbedtls_ecdsa_init(&synthetic);
    assert(!mbedtls_ecdsa_genkey(&synthetic,MBEDTLS_ECP_DP_SECP256R1,entropy,NULL));
    point[0]=4;point[1]=65;
    assert(!mbedtls_ecp_point_write_binary(&synthetic.grp,&synthetic.Q,MBEDTLS_ECP_PF_UNCOMPRESSED,&point_length,point+2,65));
    assert(point_length==65);
    assert(xPKCS11_initMbedtlsPkContext(&private_context,session,7)==CKR_OK);
    assert(mbedtls_pk_get_bitlen(&private_context)==256);
    assert(!mbedtls_pk_setup(&public_context,mbedtls_pk_info_from_type(MBEDTLS_PK_ECKEY)));
    assert(!mbedtls_ecp_group_copy(&mbedtls_pk_ec(public_context)->grp,&synthetic.grp));
    assert(!mbedtls_ecp_copy(&mbedtls_pk_ec(public_context)->Q,&synthetic.Q));
    assert(!mbedtls_pk_sign(&private_context,MBEDTLS_MD_SHA256,hash,sizeof(hash),signature,sizeof(signature),&length,entropy,NULL));
    assert(length>64 && length<=sizeof(signature));
    assert(!mbedtls_pk_verify(&public_context,MBEDTLS_MD_SHA256,hash,sizeof(hash),signature,length));
    signature[length-1]^=1;
    assert(mbedtls_pk_verify(&public_context,MBEDTLS_MD_SHA256,hash,sizeof(hash),signature,length)!=0);
    sign_error=1;
    assert(mbedtls_pk_sign(&private_context,MBEDTLS_MD_SHA256,hash,sizeof(hash),signature,sizeof(signature),&length,entropy,NULL)!=0);
    mbedtls_pk_free(&private_context);mbedtls_pk_free(&public_context);mbedtls_ecdsa_free(&synthetic);
    return 0;
}
'''
        for name,version in (("mbedtls","3.6.4"),("mbedtls_with_TSIP","3.2.1")):
            with self.subTest(backend=name,version=version):
                library=ROOT/"Middleware/3rdparty"/name
                product_api.ProductApiTests.compile_run(self,source,headers=headers,
                    extra_sources=(PORT/"mbedtls_pk_pkcs11.c",*sorted((library/"library").glob("*.c"))),
                    extra_includes=(PORT,library/"include",library/"library",PKCS/"include",
                        PKCS/"dependency/3rdparty/pkcs11/published/2-40-errata-1"),
                    extra_defines=('MBEDTLS_CONFIG_FILE="port_mbedtls_config.h"',))


if __name__=="__main__":unittest.main()
