"""Exercise the real TSIP entropy callback with a stub FIT driver."""
import unittest

from tools.ci.tests import test_product_oss_api as host


@unittest.skipUnless(host.GCC or host.MSVC, "Host C compiler required")
class TsipEntropyTests(unittest.TestCase):
    def test_reports_driver_errors_and_never_copies_failed_output(self):
        headers = {
            "platform.h": (
                "#include <stdbool.h>\n#include <stdint.h>\n"
                "#define BSP_CFG_MCU_PART_ENCRYPTION_INCLUDED true\n"
                "#define INTERNAL_NOT_USED(value) (void)(value)\n"
                "#define __LIT 1\n"
            ),
            "FreeRTOS.h": "",
            "task.h": "static inline uint32_t xTaskGetTickCount(void) { return 0; }\n",
            "r_tsip_rx_config.h": "",
            "r_tsip_rx_if.h": (
                "#include <stdint.h>\n"
                "typedef int e_tsip_err_t;\n"
                "#define TSIP_SUCCESS 0\n#define TSIP_ERR_RESOURCE_CONFLICT 1\n"
                "e_tsip_err_t R_TSIP_GenerateRandomNumber(uint32_t *random);\n"
            ),
            "r_common_api_tsip.h": (
                "typedef int tsip_tls_ca_certification_public_key_index_t;\n"
                "typedef int tsip_update_key_ring_t;\n"
                "#define COMMONAPI_SUCCESS 0\n#define COMMONAPI_ERR 1\n"
                "int R_Demo_Common_API_TSIP_Open(tsip_tls_ca_certification_public_key_index_t *, tsip_update_key_ring_t *);\n"
            ),
            "mbedtls/entropy.h": "#define MBEDTLS_ERR_ENTROPY_SOURCE_FAILED (-0x003C)\n",
        }
        host.ProductApiTests().compile_run(
            r"""
#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#include "r_tsip_rx_if.h"
#include "r_common_api_tsip.h"
#include "mbedtls/entropy.h"

int mbedtls_hardware_poll(void *, unsigned char *, size_t, size_t *);

static int open_result;
static int generate_result;
static unsigned int generate_calls;

int R_Demo_Common_API_TSIP_Open(tsip_tls_ca_certification_public_key_index_t *a,
                               tsip_update_key_ring_t *b)
{
    (void)a;
    (void)b;
    return open_result;
}

e_tsip_err_t R_TSIP_GenerateRandomNumber(uint32_t *random)
{
    generate_calls++;
    if (TSIP_SUCCESS == generate_result)
    {
        memset(random, 0x5a, 4 * sizeof(*random));
    }
    return generate_result;
}

static void expect_failure(void)
{
    unsigned char output[6] = {0, 1, 2, 3, 4, 5};
    const unsigned char untouched[6] = {0, 1, 2, 3, 4, 5};
    size_t written = sizeof(output);

    assert(mbedtls_hardware_poll(NULL, output, sizeof(output), &written)
           == MBEDTLS_ERR_ENTROPY_SOURCE_FAILED);
    assert(written == 0);
    assert(memcmp(output, untouched, sizeof(output)) == 0);
}

int main(void)
{
    unsigned char output[6] = {0};
    const unsigned char expected[6] = {0x5a, 0x5a, 0x5a, 0, 0, 0};
    size_t written = 0;

    open_result = COMMONAPI_ERR;
    expect_failure();
    assert(generate_calls == 0);

    open_result = COMMONAPI_SUCCESS;
    generate_result = TSIP_ERR_RESOURCE_CONFLICT;
    expect_failure();

    generate_result = TSIP_SUCCESS;
    assert(mbedtls_hardware_poll(NULL, output, 3, &written) == 0);
    assert(written == 3);
    assert(memcmp(output, expected, sizeof(output)) == 0);

    generate_result = TSIP_ERR_RESOURCE_CONFLICT;
    expect_failure();
    assert(generate_calls == 3);
    return 0;
}
""",
            headers=headers,
            extra_sources=[host.ROOT / "Common/FreeRTOS_common/entropy_hardware_poll.c"],
        )
