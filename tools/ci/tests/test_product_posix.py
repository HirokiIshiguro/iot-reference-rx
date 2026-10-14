"""The product byte-order port emits network bytes without a TCP/IP dependency."""
import unittest
from tools.ci.tests import test_product_oss_api as product_api

@unittest.skipUnless(product_api.GCC or product_api.MSVC, 'Host C compiler required')
class ProductPosixTests(unittest.TestCase):
    def test_wire_byte_order_and_roundtrip(self):
        product_api.ProductApiTests.compile_run(self, r'''
#include <assert.h>
#include <stdint.h>
#include "Common/FreeRTOS_common/posix/include/arpa/inet.h"
int main(void) {
    const uint16_t values16[] = {0U, 1U, 0x1234U, 0xFFFFU};
    const uint32_t values32[] = {0UL, 1UL, 0x12345678UL, 0xDEADBEEFUL, 0xFFFFFFFFUL};
    uint16_t word16 = htons(0x1234U);
    uint32_t word32 = htonl(0x12345678UL);
    const unsigned char *bytes16 = (const unsigned char *)&word16;
    const unsigned char *bytes32 = (const unsigned char *)&word32;
    unsigned int i;
    assert(bytes16[0] == 0x12U && bytes16[1] == 0x34U);
    assert(bytes32[0] == 0x12U && bytes32[1] == 0x34U && bytes32[2] == 0x56U && bytes32[3] == 0x78U);
    for (i = 0; i < sizeof(values16)/sizeof(values16[0]); ++i) assert(ntohs(htons(values16[i])) == values16[i]);
    for (i = 0; i < sizeof(values32)/sizeof(values32[0]); ++i) assert(ntohl(htonl(values32[i])) == values32[i]);
    return 0;
}
''')

if __name__ == '__main__':
    unittest.main()
