"""Exercise the five-slot RX72N workload against real pinned littlefs in RAM."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
from tools.ci.tests import test_tsip_littlefs_capacity as capacity

ROOT = Path(__file__).resolve().parents[3]
BENCHMARK = r'''
/* Matches CLI begin/write/end with 64-byte append/close commands. Values are
 * synthetic; lengths come from public certificate/DER and TSIP type metadata. */
static int chunked_slot(const char *name,unsigned size) {
    uint8_t data[64];lfs_file_t file;unsigned offset,n,i;int result;
    lfs_ssize_t written;
    (void)lfs_remove(&fs,"tsipprov.tmp");
    for(offset=0;offset<size;offset+=n) {
        n=size-offset;if(n>sizeof(data))n=sizeof(data);
        for(i=0;i<n;i++)data[i]=(uint8_t)((offset+i)*7+1);
        result=lfs_file_open(&fs,&file,"tsipprov.tmp",LFS_O_WRONLY|LFS_O_APPEND|LFS_O_CREAT);
        if(result)return result;
        written=lfs_file_write(&fs,&file,data,n);
        /* Existing CLI checks write length and discards close's result. */
        (void)lfs_file_close(&fs,&file);
        if(written!=(lfs_ssize_t)n)return written<0 ? (int)written : LFS_ERR_IO;
    }
    (void)lfs_remove(&fs,name);return lfs_rename(&fs,"tsipprov.tmp",name);
}
#define PUT(name,size) do { error=wr(name,size);if(error)goto done; } while(0)
#define CHUNK(name,size) do { error=chunked_slot(name,size);if(error)goto done; } while(0)
static int replay_rx72n_benchmark(unsigned blocks) {
    struct lfs_config c={0};int error=0;
    memset(&fs,0,sizeof(fs));memset(disk,255,sizeof(disk));
    c.read=rd;c.prog=pr;c.erase=er;c.sync=sy;c.read_size=4;c.prog_size=4;
    c.block_size=128;c.block_count=blocks;c.cache_size=64;c.lookahead_size=16;c.block_cycles=500;
    assert(lfs_format(&fs,&c)==0 && lfs_mount(&fs,&c)==0);
    PUT("code_sign_cert_id",644);PUT("code_signer_public_key",178);
    /* Representative thing/endpoint; public client certificate861-byte DER
     * and AmazonRootCA1 1188-byte PEM+NUL from the failed build's public data. */
    PUT("thing_name",40);PUT("mqtt_endpoint",47);PUT("Device Cert",861);PUT("root_ca_id",1189);
    CHUNK("tsip_rootca_sig_id",256);CHUNK("tsip_rootca_der_id",837);
    CHUNK("tsip_rootca_pub_wrapped_id",340);CHUNK("tsip_client_pub_wrapped_id",340);
    CHUNK("tsip_client_pri_wrapped_id",580);
    PUT("tsip_rootca_pub_id",564);assert(lfs_remove(&fs,"tsip_rootca_pub_wrapped_id")==0);
    PUT("tsip_client_pub_id",564);PUT("tsip_client_pri_id",804);
    assert(lfs_remove(&fs,"tsip_client_pub_wrapped_id")==0);
    assert(lfs_remove(&fs,"tsip_client_pri_wrapped_id")==0);
    PUT("code_sign_cert_id",644);
    assert(lfs_unmount(&fs)==0 && lfs_mount(&fs,&c)==0);
    verify("code_sign_cert_id",644);verify("code_signer_public_key",178);
    verify("Device Cert",861);verify("root_ca_id",1189);verify("tsip_rootca_der_id",837);
    verify("tsip_rootca_pub_id",564);verify("tsip_client_pub_id",564);verify("tsip_client_pri_id",804);
done:
    assert(lfs_unmount(&fs)==0);return error;
}
'''


class Rx72nTsipCapacityTests(unittest.TestCase):
    compile_run = capacity.TsipLittlefsCapacityTests.compile_run

    def run_replay(self, app, main):
        self.assertTrue(capacity._host.GCC or capacity._host.MSVC, 'Host C compiler required')
        self.assertTrue((capacity.LFS / 'lfs.c').is_file(), 'Initialize pinned littlefs child')
        include = '#include "platform.h"\n' + f'#include "Projects/{app}/e2studio_ccrx/src/frtos_config/rm_littlefs_flash_config.h"\n'
        self.compile_run(include + capacity.REPLAY + BENCHMARK + main,
            headers={'platform.h':'#define BSP_DATA_FLASH_SIZE_BYTES 32768U\n','r_flash_rx_if.h':''},
            extra_sources=(capacity.LFS/'lfs.c',capacity.LFS/'lfs_util.c'),
            extra_includes=(capacity.LFS, ROOT/'Common/littlefs_common/rm_littlefs_df/targets/rx65n'))

    def test_old_eight_kib_fails_the_five_slot_workload(self):
        self.run_replay('aws_ether_rx72n_envision_kit_tsip',
            'int main(void){assert(replay_rx72n_benchmark(64)==LFS_ERR_NOSPC);return 0;}\n')

    def test_both_current_profiles_preserve_five_slots_and_boot_trust(self):
        for app in ('aws_ether_rx72n_envision_kit','aws_ether_rx72n_envision_kit_tsip'):
            with self.subTest(application=app):
                self.run_replay(app,
                    'int main(void){assert(replay_rx72n_benchmark(LFS_FLASH_BLOCK_COUNT)==0);return 0;}\n')

    def test_smart_configurator_retains_the_new_geometry(self):
        for app in ('aws_ether_rx72n_envision_kit','aws_ether_rx72n_envision_kit_tsip'):
            tree=ET.parse(ROOT/'Projects'/app/'e2studio_ccrx'/(app+'.scfg'))
            self.assertEqual(['128'],[n.get('selectedIndex') for n in tree.iter('gridItem')
                                      if n.get('id')=='LFS_FLASH_BLOCK_COUNT'])
