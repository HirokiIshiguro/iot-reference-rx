"""Execute each product maintenance entry with the post-open pin contract."""
from pathlib import Path
import re
import shlex
import unittest
from tools.ci.tests import test_product_oss_api as host

ROOT=Path(__file__).resolve().parents[3]


def main_task(text):
    match=re.search(r'^void main_task\(void \*pvParameters\)\s*\{',text,re.M)
    if match is None:raise AssertionError('Product maintenance entry missing')
    depth=1;opening=text.index('{',match.start())
    for end in range(opening+1,len(text)):
        depth+=(text[end]=='{')-(text[end]=='}')
        if not depth:return text[match.start():end+1]
    raise AssertionError('Product maintenance entry unclosed')


@unittest.skipUnless(host.GCC or host.MSVC,'requires host C compiler; no MCU access')
class Rx72MaintenancePinTests(unittest.TestCase):
    def test_both_product_entries_route_tx_after_sci_is_open(self):
        for project in ('aws_ether_rx72n_envision_kit','aws_ether_rx72n_envision_kit_tsip'):
            with self.subTest(project=project):
                body=main_task((ROOT/'Projects'/project/'e2studio_ccrx/src/application_code/main.c').read_text(encoding='utf-8'))
                host.ProductApiTests.compile_run(self,r'''
#include <assert.h>
#include <stddef.h>
#define PUBLIC_SIGNER_PROVISIONER_ENABLE 1
#define TRC_START 1
static int transmitter_enabled, pin_routed, source_witness;
static int xTraceEnable(int mode) { (void)mode; return 0; }
static void R_SCI_PinSet_SCI7(void) {
    assert(transmitter_enabled);
    pin_routed=1;
}
static void vRunPublicSignerProvisioner(void (*after_open)(void)) {
    transmitter_enabled=1;
    if (after_open) after_open();
    source_witness=pin_routed;
}
'''+body+r'''
int main(void) {
    main_task(NULL);
    return source_witness ? 0 : 7;
}
''')


class NormalMqttTrustTests(unittest.TestCase):
    def test_credential_update_keeps_the_signer_installed_with_the_normal_bundle(self):
        text=(ROOT/'.gitlab-ci.yml').read_text(encoding='utf-8')
        block=text.split('\ntest_rx72n_ether_mqtt:\n',1)[1]
        block=re.split(r'\n[^ \n][^\n]*:\n',block,maxsplit=1)[0]
        array=re.search(r'provision_args=\(\n(.*?)^\s*\)',block,re.M|re.S).group(1)
        args=shlex.split(array)
        self.assertIn('--cert',args)
        self.assertIn('--key',args)
        self.assertIn('--no-reset',args)
        self.assertNotIn('--format',args)
        self.assertNotIn('--codesigner-cert',args)
        self.assertNotIn('--codesigner-public-key',args)
        self.assertNotIn('--device-id',args)


if __name__=='__main__':unittest.main()
