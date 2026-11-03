"""Replay signed-boot/TSIP storage with real pinned littlefs and dummy bytes."""
import importlib.util
from pathlib import Path
import subprocess
import unittest
import xml.etree.ElementTree as ET

_spec = importlib.util.spec_from_file_location(
    "capacity_host_compiler", Path(__file__).with_name("test_product_oss_api.py"))
_host = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_host)
ROOT = Path(__file__).resolve().parents[3]
LFS = ROOT / "Middleware/Renesas/rm_littlefs_rx/rm_littlefs_rx_vx.xx/rm_littlefs_rx/third_party/littlefs"

# Derived from the public RAM replay in issue188 note51976. Filenames follow
# store.h/tsip_provisioning_store.c. Index lengths follow the registered
# rx-driver-package bcc409d3 r_tsip_rx_if.h (140/140/200 words plus type).
# The 862-byte DER certificate and 40-byte thing name are representative dummy
# inputs, not a copy of a device credential. Every callback touches RAM only.
REPLAY = r'''
#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "lfs.h"
static uint8_t disk[32768];
static lfs_t fs;
static int rd(const struct lfs_config *c,lfs_block_t b,lfs_off_t o,void *p,lfs_size_t n) {
    assert(b<c->block_count && o+n<=c->block_size);
    memcpy(p,disk+b*c->block_size+o,n);return 0;
}
static int pr(const struct lfs_config *c,lfs_block_t b,lfs_off_t o,const void *p,lfs_size_t n) {
    const uint8_t *in=p; lfs_size_t i;
    assert(b<c->block_count && o+n<=c->block_size);
    for(i=0;i<n;i++) {
        uint8_t *out=&disk[b*c->block_size+o+i];
        assert((*out & in[i])==in[i]); *out=in[i];
    }
    return 0;
}
static int er(const struct lfs_config *c,lfs_block_t b) {
    assert(b<c->block_count);memset(disk+b*c->block_size,255,c->block_size);return 0;
}
static int sy(const struct lfs_config *c) { (void)c;return 0; }
static int wr(const char *name,unsigned size) {
    uint8_t data[2048];lfs_file_t file;int open,close;lfs_ssize_t written;unsigned i;
    assert(size<=sizeof(data));for(i=0;i<size;i++)data[i]=(uint8_t)(i*7+1);
    (void)lfs_remove(&fs,name);
    open=lfs_file_open(&fs,&file,name,LFS_O_WRONLY|LFS_O_CREAT|LFS_O_TRUNC);
    if(open)return open;
    written=lfs_file_write(&fs,&file,data,size);close=lfs_file_close(&fs,&file);
    if(written<0)return (int)written;
    if(close)return close;
    return written==(lfs_ssize_t)size ? 0 : LFS_ERR_IO;
}
static int slot(const char *name,unsigned size) {
    int result=wr("tsipprov.tmp",size);
    return result ? result : lfs_rename(&fs,"tsipprov.tmp",name);
}
#define WRITE(name,size) do { error=wr(name,size);if(error)goto done; } while(0)
#define SLOT(name,size) do { error=slot(name,size);if(error)goto done; } while(0)
static void verify(const char *name,unsigned size) {
    uint8_t data[2048];lfs_file_t file;unsigned i;
    assert(lfs_file_open(&fs,&file,name,LFS_O_RDONLY)==0);
    assert(lfs_file_size(&fs,&file)==(lfs_soff_t)size);
    assert(lfs_file_read(&fs,&file,data,size)==(lfs_ssize_t)size);
    assert(lfs_file_close(&fs,&file)==0);
    for(i=0;i<size;i++)assert(data[i]==(uint8_t)(i*7+1));
}
static int replay(unsigned blocks,int apn) {
    struct lfs_config c={0};struct lfs_info info;int error=0;
    assert(blocks*LFS_FLASH_BLOCK_SIZE<=sizeof(disk));
    memset(&fs,0,sizeof(fs));memset(disk,255,sizeof(disk));
    c.read=rd;c.prog=pr;c.erase=er;c.sync=sy;
    c.read_size=4;c.prog_size=4;c.block_size=LFS_FLASH_BLOCK_SIZE;c.block_count=blocks;
    c.cache_size=64;c.lookahead_size=16;c.block_cycles=500;
    assert(lfs_format(&fs,&c)==0 && lfs_mount(&fs,&c)==0);
    WRITE("code_sign_cert_id",644);WRITE("code_signer_public_key",178);
    WRITE("thing_name",40);WRITE("mqtt_endpoint",47);WRITE("Device Cert",862);
    if(apn) {
        WRITE("cellular_ap_name",10);WRITE("cellular_ap_userid",4);
        WRITE("cellular_ap_password",4);WRITE("cellular_ap_auth_type",1);
    }
    SLOT("tsip_rootca_sig_id",256);SLOT("tsip_rootca_pub_wrapped_id",340);
    SLOT("tsip_client_pub_wrapped_id",340);SLOT("tsip_client_pri_wrapped_id",580);
    WRITE("tsip_rootca_pub_id",564);assert(lfs_remove(&fs,"tsip_rootca_pub_wrapped_id")==0);
    WRITE("tsip_client_pub_id",564);assert(lfs_remove(&fs,"tsip_client_pub_wrapped_id")==0);
    WRITE("tsip_client_pri_id",804);assert(lfs_remove(&fs,"tsip_client_pri_wrapped_id")==0);
    /* OTA signer replacement must work after provisioning and preserve trust. */
    WRITE("code_sign_cert_id",644);
    assert(lfs_unmount(&fs)==0 && lfs_mount(&fs,&c)==0);
    verify("code_sign_cert_id",644);verify("code_signer_public_key",178);
    verify("Device Cert",862);verify("tsip_rootca_sig_id",256);
    verify("tsip_rootca_pub_id",564);verify("tsip_client_pub_id",564);verify("tsip_client_pri_id",804);
    assert(lfs_stat(&fs,"tsip_rootca_pub_wrapped_id",&info)==LFS_ERR_NOENT);
    assert(lfs_stat(&fs,"tsip_client_pub_wrapped_id",&info)==LFS_ERR_NOENT);
    assert(lfs_stat(&fs,"tsip_client_pri_wrapped_id",&info)==LFS_ERR_NOENT);
done:
    assert(lfs_unmount(&fs)==0);return error;
}
'''


class TsipLittlefsCapacityTests(unittest.TestCase):
    compile_run = _host.ProductApiTests.compile_run

    def run_capacity(self, application, main):
        self.assertTrue(_host.GCC or _host.MSVC, "Host C compiler required")
        self.assertTrue((LFS / "lfs.c").is_file(), "Initialize pinned littlefs child")
        include = '#include "platform.h"\n' + f'#include "Projects/{application}/e2studio_ccrx/src/frtos_config/rm_littlefs_flash_config.h"\n'
        self.compile_run(include + REPLAY + main,
                         headers={"platform.h": "#define BSP_DATA_FLASH_SIZE_BYTES 32768U\n",
                                  "r_flash_rx_if.h": ""},
                         extra_sources=(LFS / "lfs.c", LFS / "lfs_util.c"),
                         extra_includes=(LFS, ROOT / "Common/littlefs_common/rm_littlefs_df/targets/rx65n"))

    def test_both_rx65n_profiles_preserve_tsip_and_boot_trust_after_ota_rewrite(self):
        for app in ("aws_bg96_ck_rx65n", "aws_bg96_ck_rx65n_tsip"):
            with self.subTest(application=app):
                self.run_capacity(app, "int main(void) { assert(replay(LFS_FLASH_BLOCK_COUNT,1)==0);return 0;}\n")

    def test_old_eight_kib_geometry_fails_the_same_storage_sequence(self):
        self.run_capacity("aws_bg96_ck_rx65n_tsip", "int main(void) { assert(replay(64,1)==LFS_ERR_NOSPC);return 0;}\n")

    def test_rx72n_legacy_four_slot_profile_fits_eight_kib(self):
        self.run_capacity("aws_ether_rx72n_envision_kit_tsip", "int main(void) { assert(replay(64,0)==0);return 0;}\n")

    def test_smart_configurator_retains_the_application_geometry(self):
        for app in ("aws_bg96_ck_rx65n", "aws_bg96_ck_rx65n_tsip"):
            base = ROOT / "Projects" / app / "e2studio_ccrx"
            tree = ET.parse(base / (app + ".scfg"))
            selected = [n.attrib["selectedIndex"] for n in tree.iter("gridItem")
                        if n.get("id") == "LFS_FLASH_BLOCK_COUNT"]
            self.assertEqual(["128"], selected)

    def test_index_size_fixture_is_bound_to_the_registered_driver_pin(self):
        value = subprocess.check_output(["git", "ls-tree", "HEAD", "--", "Middleware/Renesas/rx-driver-package"], cwd=ROOT).decode().strip()
        self.assertEqual("160000 commit bcc409d331b0bff68d4b09bf6fc41376f75d42bc\tMiddleware/Renesas/rx-driver-package", value)
