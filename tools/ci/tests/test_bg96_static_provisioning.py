"""Static product key import and MQTT selection replace the retired text writer.

Real product routines, original public CorePKCS11 headers and both original
Mbed TLS libraries are used. Synthetic keys exist only inside the host process;
no private key or environment credential is read, printed, or embedded here.
"""
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import os
import re
import subprocess
from types import SimpleNamespace
import unittest
from unittest import mock

from tools import bg96_bootloader_integration as bg96
from tools.ci.tests import test_product_oss_api as host

ROOT = Path(__file__).resolve().parents[3]
DEV = ROOT / "Demos/dev_mode_key_provisioning/src/aws_dev_mode_key_provisioning.c"
FLEET = ROOT / "Demos/Fleet_Provisioning_With_CSR_Demo/pkcs11_operations.c"
MQTT = ROOT / "Demos/mqtt_agent/mqtt_agent_task.c"
PORT = ROOT / "Middleware/network_transport/using_mbedtls_pkcs11"
PKCS = ROOT / "Middleware/FreeRTOS/corePKCS11/source"


def function(text, name):
    """Select the verbatim product definition, excluding forward declarations."""
    match = re.search(r"^(?:static\s+)?CK_RV\s+" + name + r"\([^;]*?\)\s*\{", text, re.M)
    if match is None:
        raise AssertionError("Missing product definition: " + name)
    start = match.start()
    opening = text.index("{", start)
    depth = 1
    for end in range(opening + 1, len(text)):
        depth += (text[end] == "{") - (text[end] == "}")
        if not depth:
            return text[start:end + 1]
    raise AssertionError("Unclosed product definition: " + name)


class StaticProvisioningContractTests(unittest.TestCase):
    def provision_store(self, action, *, skip_private_key=False):
        """Model the CLI cache/commit boundary, including destructive format."""
        original = {
            "codesigncert": "fixture boot certificate",
            "codesignpubkey": "fixture boot public key",
            "cert": "old device certificate",
            "key": "old device key",
            "claimcert": "old claim certificate",
            "claimkey": "old claim key",
        }
        persisted = dict(original)
        cache = dict(original)
        commands = []

        def send_command(port, command, **kwargs):
            commands.append(command)
            if command == "format":
                persisted.clear()
                cache.clear()
            elif command == "conf commit":
                persisted.clear()
                persisted.update(cache)
            elif command.startswith("conf set "):
                _, _, name, value = command.split(" ", 3)
                cache[name] = value
            else:
                raise AssertionError("Unexpected fixture CLI command")

        def send_pem(port, name, value, **kwargs):
            cache[name] = value

        environment = {
            "BG96_AWS_IOT_ENDPOINT": "fixture.invalid",
            "RX65N_BG96_AWS_IOT_THING_NAME": "fixture-thing",
            "AWS_IOT_CERT": "new device certificate",
            "AWS_IOT_PRIVKEY": "new device key",
            "BG96_FLEET_PROVISIONING_TEMPLATE": "fixture-template",
            "BG96_FLEET_CLAIM_CERT": "new claim certificate",
            "BG96_FLEET_CLAIM_PRIVATE_KEY": "new claim key",
            "BG96_CELLULAR_APN": "fixture-apn",
        }
        args = SimpleNamespace(skip_private_key=skip_private_key,
            provision_cli_timeout=1, provision_char_delay=0,
            provision_line_delay=0, no_reset_after_provision=True)
        port = mock.Mock()
        with mock.patch.dict(os.environ, environment, clear=True), \
             mock.patch.object(bg96, "enter_cli_mode"), \
             mock.patch.object(bg96, "send_cli_command", side_effect=send_command), \
             mock.patch.object(bg96, "send_cli_pem", side_effect=send_pem), \
             mock.patch.object(bg96, "run_rfp") as reset, \
             redirect_stdout(StringIO()):
            action(args, port)
        reset.assert_not_called()
        self.assertEqual(commands[-1], "conf commit")
        self.assertEqual(persisted["apn"], "fixture-apn")
        for name in ("codesigncert", "codesignpubkey"):
            self.assertEqual(persisted.get(name), original[name], name)
        return persisted, original

    def test_mqtt_update_preserves_boot_trust_and_updates_device_credentials(self):
        store, _ = self.provision_store(bg96.provision_mqtt_credentials)
        self.assertEqual(store["endpoint"], "fixture.invalid")
        self.assertEqual(store["thingname"], "fixture-thing")
        self.assertEqual(store["cert"], "new device certificate")
        self.assertEqual(store["key"], "new device key")

    def test_tsip_mqtt_update_preserves_boot_trust_and_skips_plaintext_key(self):
        store, original = self.provision_store(bg96.provision_mqtt_credentials,
                                               skip_private_key=True)
        self.assertEqual(store["endpoint"], "fixture.invalid")
        self.assertEqual(store["thingname"], "fixture-thing")
        self.assertEqual(store["cert"], "new device certificate")
        self.assertEqual(store["key"], original["key"])

    def test_fleet_update_preserves_boot_trust_and_updates_claim_credentials(self):
        store, _ = self.provision_store(bg96.provision_fleet_credentials)
        self.assertEqual(store["endpoint"], "fixture.invalid")
        self.assertEqual(store["template"], "fixture-template")
        self.assertEqual(store["claimcert"], "new claim certificate")
        self.assertEqual(store["claimkey"], "new claim key")

    def test_no_active_build_or_ci_path_invokes_the_retired_source_writer(self):
        legacy = "patch_bg96_aws_iot_mcu.py"
        self.assertFalse((ROOT / "tools" / legacy).exists())
        tracked = subprocess.check_output(
            ["git", "ls-files", "-z", "--", ".gitlab-ci.yml", "tools"], cwd=ROOT
        ).decode("utf-8").split("\0")
        files = [ROOT / name for name in tracked if name
            and (name == ".gitlab-ci.yml" or Path(name).suffix in (".py", ".ps1", ".bat", ".sh"))
            and "tests" not in Path(name).parts and (ROOT / name).is_file()]
        for path in files:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertFalse(legacy in path.read_text(encoding="utf-8"),
                                 "Retired writer reference in " + path.relative_to(ROOT).as_posix())
        builder = (ROOT / "tools/build_headless_rx65n_bg96.ps1").read_text(encoding="utf-8")
        self.assertNotIn("$patchApplied", builder)
        self.assertNotIn("$patchBackup", builder)
        for path, names in ((DEV, ("xProvisionPrivateKey", "xProvisionPublicKey")),
                            (FLEET, ("provisionPrivateKey",))):
            text = path.read_text(encoding="utf-8")
            for name in names:
                body = function(text, name)
                self.assertIn("lPKCS11RandomCallback", body)
                self.assertNotIn("mbedtls_ctr_drbg_seed", body)
                self.assertNotIn("mbedtls_entropy_init", body)


@unittest.skipUnless(host.GCC or host.MSVC, "Host C compiler required; no MCU operation")
class StaticProvisioningRuntimeTests(unittest.TestCase):
    def test_private_key_parse_uses_session_rng_and_never_stores_on_rng_error_both_backends(self):
        dev = DEV.read_text(encoding="utf-8")
        fleet = FLEET.read_text(encoding="utf-8")
        declarations = "\n".join(re.findall(r"^#define\s+(?:MODULUS_LENGTH|E_LENGTH|D_LENGTH|PRIME_1_LENGTH|PRIME_2_LENGTH|EXPONENT_1_LENGTH|EXPONENT_2_LENGTH|COEFFICIENT_LENGTH)\s+[^\n]+", dev, re.M))
        rsa = re.search(r"typedef struct RsaParams_t\s*\{.*?\} RsaParams_t;", dev, re.S).group()
        routines = "\n".join(function(dev, n) for n in (
            "prvProvisionPrivateECKey", "prvProvisionPrivateRSAKey", "xProvisionPrivateKey", "xProvisionPublicKey"))
        routines += "\n" + "\n".join(function(fleet, n) for n in (
            "provisionPrivateECKey", "provisionPrivateRSAKey", "provisionPrivateKey"))
        headers = {
            "logging_levels.h": "#define LOG_ERROR 1\n",
            "logging_stack.h": "#define LogError(...) ((void)0)\n#define LogInfo(...) ((void)0)\n#define LogDebug(...) ((void)0)\n",
            "core_pkcs11_config.h": "#ifndef TEST_PKCS_CONFIG\n#define TEST_PKCS_CONFIG\n#include <stdlib.h>\n#include <assert.h>\n#define configASSERT(x) assert(x)\n#define pvPortMalloc malloc\n#define vPortFree free\n#define LogError(...) ((void)0)\n#define LogInfo(...) ((void)0)\n#define LogDebug(...) ((void)0)\n#endif\n",
            "static_provision_mbedtls_config.h": """#ifndef TEST_MBED_CONFIG
#define TEST_MBED_CONFIG
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
#define MBEDTLS_PK_PARSE_C
#define MBEDTLS_PK_WRITE_C
#define MBEDTLS_MD_C
#define MBEDTLS_SHA256_C
#define MBEDTLS_SHA224_C
#define MBEDTLS_OID_C
#endif
""",
        }
        source = r'''
#include <assert.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#define MBEDTLS_ALLOW_PRIVATE_ACCESS
#include "mbedtls_pk_pkcs11.h"
#include "mbedtls/ecdsa.h"
#include "mbedtls/oid.h"
#include "mbedtls/version.h"
#include "core_pkcs11_config_defaults.h"
#define DEV_MODE_KEY_PROVISIONING_PRINT(...) ((void)0)
static CK_FUNCTION_LIST functions;
static mbedtls_pk_context synthetic;
static unsigned state=17, random_calls, creates;
static int list_error, random_error;
static CK_OBJECT_CLASS expected_class;
static unsigned char public_point[67];
static int entropy(void *ctx,unsigned char *output,size_t length) {
    size_t i;(void)ctx;
    for(i=0;i<length;i++){state=state*1664525U+1013904223U;output[i]=(unsigned char)(state>>24);}
    return 0;
}
void vOutputString(const char *text){(void)text;}
CK_RV C_GetFunctionList(CK_FUNCTION_LIST_PTR_PTR output) {
    *output=list_error?NULL:&functions;return list_error?CKR_GENERAL_ERROR:CKR_OK;
}
static CK_RV random_bytes(CK_SESSION_HANDLE session,CK_BYTE_PTR output,CK_ULONG size) {
    ++random_calls;
    if(session!=9)return CKR_SESSION_HANDLE_INVALID;
    if(random_error)return CKR_GENERAL_ERROR;
    return entropy(NULL,output,size)?CKR_GENERAL_ERROR:CKR_OK;
}
static CK_RV create_object(CK_SESSION_HANDLE session,CK_ATTRIBUTE_PTR attrs,CK_ULONG count,CK_OBJECT_HANDLE_PTR object) {
    CK_ULONG i;unsigned seen=0;unsigned char scalar[32];
    const unsigned char oid[]={6,8,42,134,72,206,61,3,1,7};
    assert(session==9);
    assert(!mbedtls_mpi_write_binary(&mbedtls_pk_ec(synthetic)->d,scalar,sizeof(scalar)));
    for(i=0;i<count;i++) {
        assert(attrs[i].pValue);
        if(attrs[i].type==CKA_CLASS){assert(*(CK_OBJECT_CLASS *)attrs[i].pValue==expected_class);seen|=1;}
        else if(attrs[i].type==CKA_KEY_TYPE){assert(*(CK_KEY_TYPE *)attrs[i].pValue==CKK_EC);seen|=2;}
        else if(attrs[i].type==CKA_LABEL){assert(attrs[i].ulValueLen==4 && !memcmp(attrs[i].pValue,"host",4));seen|=4;}
        else if(attrs[i].type==CKA_EC_PARAMS){assert(attrs[i].ulValueLen==sizeof(oid) && !memcmp(attrs[i].pValue,oid,sizeof(oid)));seen|=8;}
        else if(attrs[i].type==CKA_VALUE){assert(expected_class==CKO_PRIVATE_KEY && attrs[i].ulValueLen==32 && !memcmp(attrs[i].pValue,scalar,32));seen|=16;}
        else if(attrs[i].type==CKA_EC_POINT){assert(expected_class==CKO_PUBLIC_KEY && attrs[i].ulValueLen==67 && !memcmp(attrs[i].pValue,public_point,67));seen|=16;}
    }
    memset(scalar,0,sizeof(scalar));assert(seen==31);++creates;if(object)*object=7;return CKR_OK;
}
CK_RV C_CreateObject(CK_SESSION_HANDLE session,CK_ATTRIBUTE_PTR attrs,CK_ULONG count,CK_OBJECT_HANDLE_PTR object) {
    return create_object(session,attrs,count,object);
}
''' + declarations + "\n" + rsa + "\n" + routines + r'''
static CK_RV import_key(unsigned route,CK_SESSION_HANDLE session,unsigned char *data,size_t size) {
    CK_OBJECT_HANDLE object=CK_INVALID_HANDLE;
    if(route==0)return xProvisionPrivateKey(session,data,size,(uint8_t *)"host",&object);
    if(route==1)return xProvisionPublicKey(session,data,size,CKK_EC,(uint8_t *)"host",&object);
    return provisionPrivateKey(session,(const char *)data,size,"host");
}
int main(void) {
    unsigned char der[51]={0x30,0x31,0x02,0x01,0x01,0x04,0x20};
    const unsigned char curve[]={0xa0,0x0a,0x06,0x08,0x2a,0x86,0x48,0xce,0x3d,0x03,0x01,0x07};
    unsigned char public_der[160];int length;size_t point_length;unsigned route;
    functions.C_GenerateRandom=random_bytes;functions.C_CreateObject=create_object;
    mbedtls_pk_init(&synthetic);
    assert(!mbedtls_pk_setup(&synthetic,mbedtls_pk_info_from_type(MBEDTLS_PK_ECKEY)));
    assert(!mbedtls_ecp_gen_key(MBEDTLS_ECP_DP_SECP256R1,mbedtls_pk_ec(synthetic),entropy,NULL));
    /* SEC1 without optional Q forces the actual parser to derive Q using f_rng. */
    assert(!mbedtls_mpi_write_binary(&mbedtls_pk_ec(synthetic)->d,der+7,32));
    memcpy(der+39,curve,sizeof(curve));
    public_point[0]=4;public_point[1]=65;
    assert(!mbedtls_ecp_point_write_binary(&mbedtls_pk_ec(synthetic)->grp,&mbedtls_pk_ec(synthetic)->Q,
        MBEDTLS_ECP_PF_UNCOMPRESSED,&point_length,public_point+2,65));assert(point_length==65);
    for(route=0;route<3;route++) {
        expected_class=route==1?CKO_PUBLIC_KEY:CKO_PRIVATE_KEY;
        creates=random_calls=0;assert(import_key(route,9,der,sizeof(der))==CKR_OK);
        assert(creates==1 && random_calls>0);
        creates=random_calls=0;random_error=1;assert(import_key(route,9,der,sizeof(der))!=CKR_OK);
        assert(!creates && random_calls>0);random_error=0;
        creates=random_calls=0;list_error=1;assert(import_key(route,9,der,sizeof(der))!=CKR_OK);
        assert(!creates && !random_calls);list_error=0;
        creates=random_calls=0;functions.C_GenerateRandom=NULL;assert(import_key(route,9,der,sizeof(der))!=CKR_OK);
        assert(!creates && !random_calls);functions.C_GenerateRandom=random_bytes;
        creates=random_calls=0;assert(import_key(route,CK_INVALID_HANDLE,der,sizeof(der))!=CKR_OK);
        assert(!creates && random_calls>0);
    }
    /* SPKI public-only parsing retains the existing fallback without session RNG. */
    length=mbedtls_pk_write_pubkey_der(&synthetic,public_der,sizeof(public_der));assert(length>0);
    creates=random_calls=0;expected_class=CKO_PUBLIC_KEY;random_error=1;
    assert(import_key(1,9,public_der+sizeof(public_der)-length,(size_t)length)==CKR_OK);
    assert(creates==1 && !random_calls);
    memset(der,0,sizeof(der));mbedtls_pk_free(&synthetic);return 0;
}
'''
        for name, version in (("mbedtls", "3.6.4"), ("mbedtls_with_TSIP", "3.2.1")):
            with self.subTest(backend=name, version=version):
                library = ROOT / "Middleware/3rdparty" / name
                host.ProductApiTests.compile_run(self, source, headers=headers,
                    extra_sources=(PORT / "mbedtls_pk_pkcs11.c", *sorted((library / "library").glob("*.c"))),
                    extra_includes=(PORT, library / "include", library / "library", PKCS / "include",
                        PKCS / "dependency/3rdparty/pkcs11/published/2-40-errata-1"),
                    extra_defines=('MBEDTLS_CONFIG_FILE="static_provision_mbedtls_config.h"',))

    def test_actual_mqtt_preprocessor_selection_keeps_kvs_and_unit_test_precedence(self):
        text = MQTT.read_text(encoding="utf-8")
        begin = text.index("#if defined(__TEST__)\n")
        end = text.index("#endif", begin) + len("#endif")
        selected = text[begin:end]
        source = r'''
#include <assert.h>
#include <string.h>
#define clientcredentialIOT_THING_NAME "legacy-test-id"
#define clientcredentialMQTT_BROKER_ENDPOINT "legacy-test.example.invalid"
#define democonfigCLIENT_IDENTIFIER "ci-demo-id"
#define democonfigMQTT_BROKER_ENDPOINT "ci.example.invalid"
#define democonfigROOT_CA_PEM "default-ca"
#define KVS_CORE_THING_NAME 1
#define KVS_CORE_MQTT_ENDPOINT 2
#define KVS_ROOT_CA_ID 3
#define LogInfo(...) ((void)0)
static unsigned length_calls, value_calls, without_ca;
static int prvGetCacheEntryLength(int key){++length_calls;return key==3 && without_ca?0:8;}
static char *GetStringValue(int key,int size){(void)size;++value_calls;return key==1?"kvs-id":key==2?"kvs.example.invalid":"kvs-ca";}
static void select_credentials(void) {
    char *pcThingName=NULL,*pcBrokerEndpoint=NULL,*pcRootCA=NULL;
    int thingnameLength,endpointLength,rootCALength;
''' + selected + r'''
#if EXPECTED_ROUTE==0
    assert(!strcmp(pcThingName,"kvs-id") && !strcmp(pcBrokerEndpoint,"kvs.example.invalid"));
    assert(!strcmp(pcRootCA,without_ca?"default-ca":"kvs-ca"));
    assert(length_calls==3 && value_calls==(without_ca?2U:3U));
#elif EXPECTED_ROUTE==1
    assert(!strcmp(pcThingName,"legacy-test-id") && !strcmp(pcBrokerEndpoint,"legacy-test.example.invalid"));
    assert(!strcmp(pcRootCA,"default-ca") && !length_calls && !value_calls);
#else
    assert(!strcmp(pcThingName,"ci-demo-id") && !strcmp(pcBrokerEndpoint,"ci.example.invalid"));
    assert(!strcmp(pcRootCA,"default-ca") && !length_calls && !value_calls);
#endif
}
int main(void) {
    select_credentials();length_calls=value_calls=0;without_ca=1;select_credentials();return 0;
}
'''
        for defines in (("EXPECTED_ROUTE=0",), ("__TEST__=1", "EXPECTED_ROUTE=1"),
                        ("BG96_CI_MQTT_CREDENTIALS=1", "EXPECTED_ROUTE=2"),
                        ("BG96_CI_MQTT_CREDENTIALS=1", "__TEST__=1", "EXPECTED_ROUTE=1")):
            with self.subTest(defines=defines):
                host.ProductApiTests.compile_run(self, source, extra_defines=defines)


if __name__ == "__main__":
    unittest.main()
