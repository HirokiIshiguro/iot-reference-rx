"""Application storage ports compile against the pristine RX and littlefs APIs."""
import unittest
from pathlib import Path
from tools.ci.tests import test_product_oss_api as product_api

ROOT = Path(__file__).resolve().parents[3]
RX = ROOT / "Middleware/Renesas/rm_littlefs_rx/rm_littlefs_rx_vx.xx/rm_littlefs_rx"
LFS = RX / "third_party/littlefs"
RTOS = ROOT / "Middleware/Renesas/rm_rtos_abstraction_rx/rm_rtos_abstraction_rx_vx.xx/rm_rtos_abstraction_rx"
APP = ROOT / "Projects/aws_ether_rx72n_envision_kit/e2studio_ccrx/src"

@unittest.skipUnless(product_api.GCC or product_api.MSVC, "Host C compiler required")
class ProductLittlefsTests(unittest.TestCase):
    def test_all_application_and_bootloader_partition_headers_match(self):
        pairs = [
            ("aws_wifi_rx671_ek", "boot_loader_rx671_ek"),
            ("aws_bg96_ck_rx65n", "boot_loader_ck_rx65n"),
            ("aws_bg96_ck_rx65n_tsip", "boot_loader_ck_rx65n"),
            ("aws_ether_rx72n_envision_kit", "boot_loader_rx72n_envision_kit"),
            ("aws_ether_rx72n_envision_kit_tsip", "boot_loader_rx72n_envision_kit"),
        ]
        for application, bootloader in pairs:
            with self.subTest(application=application):
                self_path = f"Projects/{application}/e2studio_ccrx/src"
                boot_path = f"Projects/{bootloader}/e2studio_ccrx/src"
                source = f'''
#include <assert.h>
#include "platform.h"
#include "{self_path}/frtos_config/rm_littlefs_flash_config.h"
#include "{self_path}/smc_gen/r_config/rm_littlefs_rx_config.h"
#include "{boot_path}/rx_bootloader_config.h"
int main(void) {{
    assert(RM_LITTLEFS_FLASH_DATA_START == 0x00100000UL);
    assert(RX_BOOTLOADER_LITTLEFS_KEY_STORE_BASE_ADDRESS == RM_LITTLEFS_FLASH_DATA_START);
    assert(LFS_FLASH_BLOCK_SIZE == 128 && LFS_FLASH_BLOCK_COUNT == 64);
    assert(RX_BOOTLOADER_LITTLEFS_KEY_STORE_REGION_SIZE == LFS_FLASH_BLOCK_SIZE*LFS_FLASH_BLOCK_COUNT);
    assert(LFS_FLASH_READ_SIZE == 4 && LFS_FLASH_READ_SIZE == RM_LITTLEFS_CFG_READ_SIZE);
    assert(LFS_FLASH_PROGRAM_SIZE == 4 && LFS_FLASH_PROGRAM_SIZE == RM_LITTLEFS_CFG_PROG_SIZE);
    assert(LFS_FLASH_BLOCK_SIZE == RM_LITTLEFS_CFG_BLOCK_SIZE);
    assert(RM_LITTLEFS_CFG_CACHE_SIZE == 64 && RM_LITTLEFS_CFG_LOOKAHEAD_SIZE == 16);
    assert(RM_LITTLEFS_CFG_BLOCK_CYCLES == 500);
    return 0;
}}
'''
                product_api.ProductApiTests.compile_run(self, source,
                    headers={"platform.h":"#define BSP_DATA_FLASH_SIZE_BYTES 32768U\n",
                             "rx65n.h":"", "rx671.h":"", "rx72n.h":"", "r_flash_rx_if.h":""},
                    extra_includes=(ROOT/"Common/littlefs_common/rm_littlefs_df/targets/rx65n",))

    def test_real_filesystem_roundtrip_geometry_mutex_and_retry(self):
        headers = {
            "FreeRTOS.h": "#include <stdint.h>\n#include <stddef.h>\ntypedef int BaseType_t;\ntypedef unsigned TickType_t;\n#define pdTRUE 1\n#define portMAX_DELAY 0xffffffffU\n",
            "semphr.h": "typedef struct { int unused; } StaticSemaphore_t;\ntypedef void *SemaphoreHandle_t;\nSemaphoreHandle_t xSemaphoreCreateMutexStatic(StaticSemaphore_t *);\nint xSemaphoreTake(SemaphoreHandle_t, unsigned);\nint xSemaphoreGive(SemaphoreHandle_t);\n",
            "task.h": "#define taskSCHEDULER_RUNNING 2\nint xTaskGetSchedulerState(void);\nvoid vTaskDelay(unsigned);\n",
            "r_common_api_flash.h": "#define COMMONAPI_SUCCESS 0\nint R_Demo_Common_API_Flash_Open(void);\n",
            "platform.h": "#define BSP_DATA_FLASH_SIZE_BYTES 32768U\n",
        }
        # Use the actual application partition and adapter configuration headers.
        product_api.ProductApiTests.compile_run(self, r'''
#include <assert.h>
#include <string.h>
#include "FreeRTOS.h"
#include "semphr.h"
#include "lfs_common_data.h"
#include "rm_rtos_abstraction_rx_if.h"
static unsigned char flash[8192];
static int held, created, common_open_count, adapter_open_count, format_count, yield_count;
static int common_open_error=1, mount_error=1, read_error;
static rm_rtos_abstraction_sleep_task_t sleep_task;
static rm_littlefs_ctrl_t *controller;
SemaphoreHandle_t xSemaphoreCreateMutexStatic(StaticSemaphore_t *buffer) { assert(buffer); created++; return buffer; }
int xSemaphoreTake(SemaphoreHandle_t mutex, unsigned ticks) { assert(mutex && !held && ticks==0xffffffffU); held=1; return 1; }
int xSemaphoreGive(SemaphoreHandle_t mutex) { assert(mutex && held); held=0; return 1; }
int xTaskGetSchedulerState(void) { return 2; }
void vTaskDelay(unsigned ticks) { assert(ticks==1U && held); ++yield_count; }
int R_Demo_Common_API_Flash_Open(void) { assert(held); ++common_open_count; return common_open_error?-1:0; }
rm_rtos_abstraction_err_t RM_RTOS_ABSTRACTION_SetSleepTask(rm_rtos_abstraction_sleep_task_t function) {
    assert(held && function); sleep_task=function; return RM_RTOS_ABSTRACTION_SUCCESS;
}
static int read_block(const struct lfs_config *cfg, lfs_block_t block, lfs_off_t offset, void *buffer, lfs_size_t size) {
    assert(held && block<64 && offset+size<=128 && !(offset%4) && !(size%4));
    if(read_error) return LFS_ERR_IO;
    memcpy(buffer, flash+block*cfg->block_size+offset,size); return 0;
}
static int program_block(const struct lfs_config *cfg, lfs_block_t block, lfs_off_t offset, const void *buffer, lfs_size_t size) {
    unsigned i; unsigned char *destination=flash+block*cfg->block_size+offset;
    const unsigned char *bytes=buffer;
    assert(held && block<64 && offset+size<=128 && !(offset%4) && !(size%4));
    for(i=0;i<size;i++) { assert((destination[i]&bytes[i])==bytes[i]); destination[i]&=bytes[i]; }
    assert(sleep_task); sleep_task(0); return 0;
}
static int erase_block(const struct lfs_config *cfg, lfs_block_t block) {
    assert(held && block<64); memset(flash+block*cfg->block_size,255,cfg->block_size); return 0;
}
static int sync_block(const struct lfs_config *cfg) { (void)cfg; assert(held); return 0; }
lfs_t *RM_LITTLEFS_GetLfs(rm_littlefs_ctrl_t *ctrl) { return ctrl->opened?&ctrl->lfs:NULL; }
rm_littlefs_err_t RM_LITTLEFS_Open(rm_littlefs_ctrl_t *ctrl, const rm_littlefs_cfg_t *cfg) {
    int result;
    assert(held); ++adapter_open_count;
    assert(cfg->base_address==0x00100000 && cfg->region_size==8192);
    assert(cfg->read_size==4 && cfg->prog_size==4 && cfg->block_size==128);
    assert(cfg->cache_size==64 && cfg->lookahead_size==16 && cfg->block_cycles==500);
    assert(cfg->format_if_mount_failed==1);
    if(mount_error) return RM_LITTLEFS_ERR_MOUNT;
    memset(ctrl,0,sizeof(*ctrl)); controller=ctrl;
    ctrl->lfs_cfg.context=ctrl; ctrl->base_address=cfg->base_address; ctrl->region_size=cfg->region_size;
    ctrl->lfs_cfg.read=read_block; ctrl->lfs_cfg.prog=program_block; ctrl->lfs_cfg.erase=erase_block; ctrl->lfs_cfg.sync=sync_block;
    ctrl->lfs_cfg.read_size=4; ctrl->lfs_cfg.prog_size=4; ctrl->lfs_cfg.block_size=128; ctrl->lfs_cfg.block_count=64;
    ctrl->lfs_cfg.cache_size=64; ctrl->lfs_cfg.lookahead_size=16; ctrl->lfs_cfg.block_cycles=500;
    ctrl->lfs_cfg.read_buffer=ctrl->read_buffer; ctrl->lfs_cfg.prog_buffer=ctrl->prog_buffer;
    ctrl->lfs_cfg.lookahead_buffer=ctrl->lookahead_buffer;
    result=lfs_mount(&ctrl->lfs,&ctrl->lfs_cfg);
    if(result) { assert(!lfs_format(&ctrl->lfs,&ctrl->lfs_cfg)); ++format_count; result=lfs_mount(&ctrl->lfs,&ctrl->lfs_cfg); }
    assert(!result); ctrl->opened=1; return RM_LITTLEFS_SUCCESS;
}
rm_littlefs_err_t RM_LITTLEFS_Format(rm_littlefs_ctrl_t *ctrl) {
    assert(held && ctrl->opened); assert(!lfs_unmount(&ctrl->lfs)); ctrl->opened=0;
    assert(!lfs_format(&ctrl->lfs,&ctrl->lfs_cfg)); ++format_count;
    assert(!lfs_mount(&ctrl->lfs,&ctrl->lfs_cfg)); ctrl->opened=1; return RM_LITTLEFS_SUCCESS;
}
int main(void) {
    const char key[]="PUBLIC-SIGNER-KEY"; char output[32]={0}; lfs_file_t file={0}; struct lfs_info info;
    lfs_t *lfs;
    memset(flash,255,sizeof(flash));
    assert(LfsCommon_Remove(NULL,"none")==LFS_ERR_IO && !held);
    assert(littlFs_init()==LFS_ERR_IO && !held && created==1 && adapter_open_count==0);
    common_open_error=0;
    assert(littlFs_init()==LFS_ERR_CORRUPT && !held && adapter_open_count==1);
    mount_error=0;
    assert(!littlFs_init() && !held && adapter_open_count==2 && format_count==1);
    assert(!littlFs_init() && !held && adapter_open_count==2 && created==1);
    lfs=LfsCommon_GetLfs(); assert(lfs && controller);
    assert(LfsCommon_Stat(NULL,"key",&info)==LFS_ERR_BADF && !held);
    assert(!LfsCommon_FileOpen(lfs,&file,"code_signer_public_key",LFS_O_CREAT|LFS_O_RDWR));
    assert(LfsCommon_FileWrite(lfs,&file,key,sizeof(key))==sizeof(key));
    assert(!LfsCommon_FileSync(lfs,&file)); assert(LfsCommon_FileSize(lfs,&file)==sizeof(key));
    assert(LfsCommon_FileSeek(lfs,&file,0,LFS_SEEK_SET)==0);
    assert(LfsCommon_FileRead(lfs,&file,output,sizeof(key))==sizeof(key) && !memcmp(output,key,sizeof(key)));
    assert(!LfsCommon_FileClose(lfs,&file));
    assert(!LfsCommon_Stat(lfs,"code_signer_public_key",&info) && info.size==sizeof(key));
    assert(!LfsCommon_Rename(lfs,"code_signer_public_key","code_sign_cert_id"));
    read_error=1; assert(LfsCommon_FileOpen(lfs,&file,"code_sign_cert_id",LFS_O_RDONLY)==LFS_ERR_IO && !held);
    read_error=0; assert(!LfsCommon_Remove(lfs,"code_sign_cert_id") && !held);
    assert(LfsCommon_Stat(lfs,"code_sign_cert_id",&info)==LFS_ERR_NOENT && !held);
    assert(!littlFs_format() && !held && format_count==2 && adapter_open_count==2);
    assert(yield_count>0 && common_open_count==3);
    return 0;
}
''', headers=headers, extra_sources=(ROOT/"Common/littlefs_common/lfs_common_data.c",LFS/"lfs.c",LFS/"lfs_util.c"),
            extra_includes=(ROOT/"Common/littlefs_common",RX,LFS,RTOS,APP/"smc_gen/r_config",
                            APP/"frtos_config",ROOT/"Common/littlefs_common/rm_littlefs_df/targets/rx65n"))

    def test_application_callers_cannot_bypass_product_lock(self):
        import re
        paths = ["Demos/cli/store.c", "Demos/cli/CLIcommands.c", "Demos/tsip_provisioning/tsip_provisioning_store.c",
                 "Demos/tsip_provisioning/tsip_provisioning_cli.c", "Common/littlefs_common/rm_stdio_littlefs.h",
                 "Common/ports/rm_aws_pkcs11_pal_littlefs/rm_aws_pkcs11_pal_littlefs.c"]
        for name in paths:
            source=(ROOT/name).read_text(encoding="utf-8")
            self.assertNotRegex(source,r"\blfs_(?:file_\w+|remove|rename|stat|format|mount|unmount)\s*\(",name)
            self.assertNotIn("RM_LITTLEFS_FLASH_Open",source,name)
            self.assertNotIn("fsp_common_api.h",source,name)
        for name in ("Common/littlefs_common/rm_littlefs_api.h", "Common/littlefs_common/rm_littlefs_flash.h",
                     "Common/ports/rm_littlefs_flash/rm_littlefs_flash.c"):
            self.assertFalse((ROOT/name).exists(),name)

if __name__ == "__main__":
    unittest.main()
