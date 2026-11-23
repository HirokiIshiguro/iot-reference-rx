"""RX65 CLI storage remains independent from the r_cellular driver's buffers."""
from pathlib import Path
import unittest
from tools.ci.tests import test_product_oss_api as product_api

ROOT=Path(__file__).resolve().parents[3]


@unittest.skipUnless(product_api.GCC or product_api.MSVC,"Host C compiler required")
class Rx65LinkSupportTests(unittest.TestCase):
    def test_both_rx65_init_objects_provide_independent_zeroed_cli_storage(self):
        for project in ("aws_bg96_ck_rx65n","aws_bg96_ck_rx65n_tsip"):
            with self.subTest(project=project):
                config=f"Projects/{project}/e2studio_ccrx/src/smc_gen/r_config/r_sci_rx_config.h"
                product_api.ProductApiTests.compile_run(self,r'''
#include <assert.h>
#include <stddef.h>
extern char *txBuffer;
extern void UserInitialization(void);
static unsigned pins;
void R_Pins_Create(void) { ++pins; }
int main(void) {
    unsigned i;assert(txBuffer);
    for(i=0;i<400;i++)assert(!txBuffer[i]);
    UserInitialization();assert(pins==1);
    txBuffer[399]='x';UserInitialization();assert(pins==2 && txBuffer[399]=='x');
    return 0;
}
''',headers={"platform.h":"", "r_pinset.h":"", "r_flash_rx_if.h":"",
             "Pin.h":"void R_Pins_Create(void);\n", "r_sci_rx_if.h":'#include "'+config+'"\n'},
                    extra_sources=(ROOT/f"Projects/{project}/e2studio_ccrx/src/application_code/user_init.c",))


if __name__=="__main__":unittest.main()
