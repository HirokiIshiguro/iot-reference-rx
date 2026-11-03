"""Execute the product store and CLI with public dummy flash/TSIP services."""
import importlib.util
from pathlib import Path
import unittest

_spec = importlib.util.spec_from_file_location(
    "tsip_host_compiler", Path(__file__).with_name("test_product_oss_api.py"))
_host = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_host)

HEADERS = {
    "FreeRTOS.h": """#pragma once
#include <stddef.h>
#include <stdint.h>
typedef int BaseType_t;
#define pdTRUE 1
#define pdFALSE 0
""",
    "lfs.h": """#pragma once
#include <stdint.h>
typedef int32_t lfs_ssize_t;
typedef int32_t lfs_soff_t;
typedef uint32_t lfs_size_t;
typedef struct { int index; } lfs_file_t;
struct lfs_info { uint32_t size; };
#define LFS_ERR_OK 0
#define LFS_O_RDONLY 1
#define LFS_O_WRONLY 2
#define LFS_O_CREAT 4
#define LFS_O_TRUNC 8
#define LFS_O_APPEND 16
""",
    "lfs_common_data.h": """#pragma once
#include "lfs.h"
void *LfsCommon_GetLfs(void);
int LfsCommon_FileOpen(void *,lfs_file_t *,const char *,int);
int LfsCommon_FileClose(void *,lfs_file_t *);
lfs_soff_t LfsCommon_FileSize(void *,lfs_file_t *);
lfs_ssize_t LfsCommon_FileRead(void *,lfs_file_t *,void *,lfs_size_t);
lfs_ssize_t LfsCommon_FileWrite(void *,lfs_file_t *,const void *,lfs_size_t);
int LfsCommon_Remove(void *,const char *);
int LfsCommon_Rename(void *,const char *,const char *);
int LfsCommon_Stat(void *,const char *,struct lfs_info *);
""",
    "r_tsip_rx_if.h": """#pragma once
#include <stdint.h>
typedef int e_tsip_err_t;
typedef struct { uint32_t dummy[8]; } tsip_tls_ca_certification_public_key_index_t;
typedef struct { uint32_t dummy[8]; } tsip_rsa2048_public_key_index_t;
typedef struct { uint32_t dummy[8]; } tsip_rsa2048_private_key_index_t;
#define TSIP_SUCCESS 0
#define TSIP_TLS_MODE_CLIENT 1
e_tsip_err_t R_TSIP_GenerateTlsRsaPublicKeyIndex(uint8_t *,uint8_t *,uint8_t *,tsip_tls_ca_certification_public_key_index_t *);
e_tsip_err_t R_TSIP_GenerateRsa2048PublicKeyIndex(uint8_t *,uint8_t *,uint8_t *,tsip_rsa2048_public_key_index_t *);
e_tsip_err_t R_TSIP_GenerateRsa2048PrivateKeyIndex(uint8_t *,uint8_t *,uint8_t *,tsip_rsa2048_private_key_index_t *);
e_tsip_err_t R_TSIP_TlsRegisterCaCertificationPublicKeyIndex(int,tsip_tls_ca_certification_public_key_index_t *);
""",
    "r_common_api_tsip.h": """#pragma once
#include "r_tsip_rx_if.h"
typedef int e_commonapi_err_t;
#define COMMONAPI_SUCCESS 0
e_commonapi_err_t R_Demo_Common_API_TSIP_Open(tsip_tls_ca_certification_public_key_index_t *,void *);
e_commonapi_err_t R_Demo_Common_API_TSIP_Close(void);
""",
    "FreeRTOS_CLI.h": """#pragma once
#include "FreeRTOS.h"
typedef struct { const char *name; const char *help; BaseType_t (*handler)(char *,size_t,const char *); int parameters; } CLI_Command_Definition_t;
const char *FreeRTOS_CLIGetParameter(const char *,unsigned,BaseType_t *);
void FreeRTOS_CLIRegisterCommand(const CLI_Command_Definition_t *);
""",
    "aws_clientcredential.h": '#define keyCLIENT_CERTIFICATE_PEM ((const char *)0)\n',
    "demo_config.h": """#define democonfigCLIENT_IDENTIFIER "fixture-thing"
#define democonfigMQTT_BROKER_ENDPOINT "example.test"
#define democonfigROOT_CA_PEM "PUBLIC_DUMMY_ROOT"
""",
    "store.h": "",
}

FIXTURE = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "Demos/tsip_provisioning/tsip_provisioning_store.c"
#include "Demos/tsip_provisioning/tsip_provisioning_cli.c"
tsip_rsa2048_private_key_index_t rsa2048_private_key;
tsip_rsa2048_public_key_index_t rsa2048_public_key;
static struct { const char *name; unsigned size; int present; unsigned char data[1024]; } files[8];
static const char *read_failure, *write_failure, *api_failure;
static unsigned generations, writes, closes;
static int find(const char *name) {
    int i; for(i=0;i<8;i++) if(!strcmp(files[i].name,name)) return i;
    assert(!"unexpected storage name"); return -1;
}
void *LfsCommon_GetLfs(void) { return NULL; }
int LfsCommon_FileOpen(void *fs,lfs_file_t *file,const char *name,int flags) {
    int i=find(name); (void)fs;
    if(flags & LFS_O_WRONLY) {
        if(write_failure && !strcmp(name,write_failure)) return -28;
        files[i].present=1;
    } else if(!files[i].present || (read_failure && !strcmp(name,read_failure))) return -5;
    file->index=i; return 0;
}
int LfsCommon_FileClose(void *fs,lfs_file_t *file) { (void)fs;(void)file;return 0; }
lfs_soff_t LfsCommon_FileSize(void *fs,lfs_file_t *file) { (void)fs;return (lfs_soff_t)files[file->index].size; }
lfs_ssize_t LfsCommon_FileRead(void *fs,lfs_file_t *file,void *data,lfs_size_t size) {
    (void)fs;memcpy(data,files[file->index].data,size);return (lfs_ssize_t)size;
}
lfs_ssize_t LfsCommon_FileWrite(void *fs,lfs_file_t *file,const void *data,lfs_size_t size) {
    (void)fs;assert(size<=1024);writes++;memcpy(files[file->index].data,data,size);
    files[file->index].size=size;return (lfs_ssize_t)size;
}
int LfsCommon_Remove(void *fs,const char *name) { (void)fs;files[find(name)].present=0;return 0; }
int LfsCommon_Rename(void *fs,const char *a,const char *b) { (void)fs;(void)a;(void)b;return 0; }
int LfsCommon_Stat(void *fs,const char *name,struct lfs_info *info) {
    int i=find(name);(void)fs;if(!files[i].present) return -2;info->size=files[i].size;return 0;
}
static int api(const char *name,int code) { return api_failure && !strcmp(api_failure,name) ? code : 0; }
e_commonapi_err_t R_Demo_Common_API_TSIP_Open(tsip_tls_ca_certification_public_key_index_t *index,void *unused) {
    (void)unused;return index ? api("open-with-root",-32) : api("open-plain",-31);
}
e_commonapi_err_t R_Demo_Common_API_TSIP_Close(void) { closes++;return 0; }
static int generate(uint8_t *w,uint8_t *iv,uint8_t *encrypted,void *index,const char *name,int code) {
    assert(iv==w+32 && encrypted==iv+16);generations++;
    memset(index,0xa5,32);return api(name,code);
}
e_tsip_err_t R_TSIP_GenerateTlsRsaPublicKeyIndex(uint8_t *w,uint8_t *i,uint8_t *e,tsip_tls_ca_certification_public_key_index_t *k) {
    return generate(w,i,e,k,"root-generate",101);
}
e_tsip_err_t R_TSIP_GenerateRsa2048PublicKeyIndex(uint8_t *w,uint8_t *i,uint8_t *e,tsip_rsa2048_public_key_index_t *k) {
    return generate(w,i,e,k,"client-pub-generate",102);
}
e_tsip_err_t R_TSIP_GenerateRsa2048PrivateKeyIndex(uint8_t *w,uint8_t *i,uint8_t *e,tsip_rsa2048_private_key_index_t *k) {
    return generate(w,i,e,k,"client-pri-generate",103);
}
e_tsip_err_t R_TSIP_TlsRegisterCaCertificationPublicKeyIndex(int mode,tsip_tls_ca_certification_public_key_index_t *k) {
    assert(mode==TSIP_TLS_MODE_CLIENT && k);return api("root-register",104);
}
const char *FreeRTOS_CLIGetParameter(const char *command,unsigned number,BaseType_t *length) {
    const char *p=command;unsigned i;
    for(i=0;i<number;i++) { while(*p && *p!=' ')p++;while(*p==' ')p++; }
    if(!*p) return NULL; *length=0;while(p[*length] && p[*length]!=' ')(*length)++;return p;
}
void FreeRTOS_CLIRegisterCommand(const CLI_Command_Definition_t *command) { (void)command; }
int32_t xprvWriteCacheEntry(size_t a,char *b,size_t c,char *d) { (void)a;(void)b;(void)c;(void)d;return 0; }
BaseType_t KVStore_xCommitChanges(void) { return pdTRUE; }
static void setup(void) {
    unsigned i;memset(files,0,sizeof(files));
    for(i=0;i<5;i++) { files[i].name=xSlotInfo[i].pcStorageName;memset(files[i].data,0x6d,1024); }
    files[5].name=TSIP_ROOT_SIGNER_KEY_INDEX_STORAGE_NAME;
    files[6].name=TSIP_CLIENT_PUBLIC_KEY_INDEX_STORAGE_NAME;
    files[7].name=TSIP_CLIENT_PRIVATE_KEY_INDEX_STORAGE_NAME;
    files[1].size=340;files[2].size=340;files[3].size=580;
    files[1].present=files[2].present=files[3].present=1;
    read_failure=write_failure=api_failure=NULL;generations=writes=closes=0;
    xRootCaTrustAnchorReady=pdFALSE;vTsipProvisioningClearPrepareError();
}
static void prepare(char *output,size_t size) {
    assert(prvTsipProvisioningCommand(output,size,"tsipprov prepare")==pdFALSE);
}
'''


class TsipPrepareDiagnosticsTests(unittest.TestCase):
    compile_run = _host.ProductApiTests.compile_run

    def run_fixture(self, main):
        self.assertTrue(_host.GCC or _host.MSVC, "Host C compiler is required")
        self.compile_run(FIXTURE + main, headers=HEADERS,
                         extra_defines=("TSIP_RUNTIME_PROVISIONING_ENABLE=1",))

    def test_all_fifteen_failure_stages_keep_numeric_status_and_failed_result(self):
        self.run_fixture(r'''
int main(void) {
    static const struct { const char *stage; int code; int slot; int kind; } cases[]={
        {"open-plain",-31,0,0},{"root-slot-read",-1,1,1},{"root-parse",339,1,2},
        {"root-generate",101,0,0},{"root-index-write",-1,5,3},
        {"open-with-root",-32,0,0},{"root-register",104,0,0},
        {"client-pub-slot-read",-1,2,1},{"client-pub-parse",339,2,2},
        {"client-pub-generate",102,0,0},{"client-pub-index-write",-1,6,3},
        {"client-pri-slot-read",-1,3,1},{"client-pri-parse",579,3,2},
        {"client-pri-generate",103,0,0},{"client-pri-index-write",-1,7,3}
    };
    unsigned i;char output[192],expected[96];
    for(i=0;i<sizeof(cases)/sizeof(cases[0]);i++) {
        setup();
        if(cases[i].kind==1) read_failure=files[cases[i].slot].name;
        else if(cases[i].kind==2) files[cases[i].slot].size=(unsigned)cases[i].code;
        else if(cases[i].kind==3) write_failure=files[cases[i].slot].name;
        else api_failure=cases[i].stage;
        prepare(output,sizeof(output));
        assert(!strncmp(output,"Error: TSIP runtime key prepare failed.",39));
        snprintf(expected,sizeof(expected),"stage=%s code=%d\r\n",cases[i].stage,cases[i].code);
        assert(strstr(output,expected));
        assert(!strcmp(pcTsipProvisioningPrepareErrorStage(),cases[i].stage));
        assert(lTsipProvisioningPrepareErrorCode()==cases[i].code);
    }
    return 0;
}
''')

    def test_success_preserves_import_cache_and_wrapped_slot_consumption(self):
        self.run_fixture(r'''
int main(void) {
    char output[192];unsigned cached,i;
    for(cached=0;cached<2;cached++) {
        setup();
        if(cached) for(i=5;i<8;i++) { files[i].present=1;files[i].size=32; }
        prepare(output,sizeof(output));
        assert(!strcmp(output,"OK: TSIP runtime keys prepared.\r\n"));
        assert(!strcmp(pcTsipProvisioningPrepareErrorStage(),"none"));
        assert(lTsipProvisioningPrepareErrorCode()==0 && closes==1);
        assert(generations==(cached ? 0U : 3U) && writes==(cached ? 0U : 3U));
        assert(!files[1].present && !files[2].present && !files[3].present);
    }
    return 0;
}
''')

    def test_cli_clears_previous_error_and_bounds_expanded_response(self):
        self.run_fixture(r'''
int main(void) {
    char output[192];struct { char text[16];char guard; } small;
    setup();api_failure="root-generate";prepare(output,sizeof(output));
    assert(strstr(output,"stage=root-generate code=101"));
    api_failure="open-plain";prepare(output,sizeof(output));
    assert(strstr(output,"stage=open-plain code=-31"));
    memset(&small,'G',sizeof(small));prepare(small.text,sizeof(small.text));
    assert(small.guard=='G' && small.text[15]==0);
    assert(!strncmp(small.text,"Error:",6));
    return 0;
}
''')
