"""Keep registered RX72N application rings/pool synchronized through SC."""
from pathlib import Path
import re,unittest,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3]
class Rx72nNetworkDefaultsTests(unittest.TestCase):
    def test_normal_software_and_tsip_have_2x2_rings_and_pool8(self):
        for name in ('aws_ether_rx72n_envision_kit','aws_ether_rx72n_envision_kit_tsip'):
            with self.subTest(project=name):
                project=ROOT/'Projects'/name/'e2studio_ccrx'
                ether=(project/'src/smc_gen/r_config/r_ether_rx_config.h').read_text(encoding='utf-8')
                ip=(project/'src/frtos_config/FreeRTOSIPConfig.h').read_text(encoding='utf-8')
                sc=ET.parse(project/(name+'.scfg'));qe=ET.parse(project/'.settings/com.renesas.smc.e2studio.qe.xml')
                for direction in ('RX','TX'):
                    key='ETHER_CFG_EMAC_'+direction+'_DESCRIPTORS'
                    self.assertRegex(ether,r'#define\s+'+key+r'\s+\(2\)')
                    self.assertEqual(['2'],[n.get('selectedIndex') for n in sc.findall('.//gridItem[@id="'+key+'"]')])
                    self.assertEqual(['2'],[n.get('value') for n in qe.findall('.//Setting[@id="'+key+'"]')])
                self.assertRegex(ip,r'#define\s+ipconfigNUM_NETWORK_BUFFER_DESCRIPTORS\s+\(8\)')
                self.assertEqual(['8'],[n.get('selectedIndex') for n in sc.findall('.//gridItem[@id="ipconfigNUM_NETWORK_BUFFER_DESCRIPTORS"]')])
if __name__=='__main__':unittest.main()
