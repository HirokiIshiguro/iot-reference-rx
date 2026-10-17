"""Execute the actual OTA request and timeout branch for a lost final window."""
from pathlib import Path
import unittest
from tools.ci.tests import test_product_oss_api as host
from tools.ci.tests.test_public_signer_cli_commands import _function

ROOT = Path(__file__).resolve().parents[3]


@unittest.skipUnless(host.GCC or host.MSVC, "Host C compiler required")
class OtaRequestRetryTests(unittest.TestCase):
    def test_lost_request_window_restarts_at_first_unreceived_block(self):
        source = (ROOT / "Demos/OtaOverMqtt/OtaOverMqttDemo.c").read_text(encoding="utf-8")
        request = _function(source, r"static\s+void\s+requestDataBlock\s*\(\s*void\s*\)")
        timeout = _function(source, r"else\s+if\s*\(\s*OtaAgentEventRequestFileBlock\s*==\s*lastRecvEventId\s*\)")
        fixture = r'''
#ifdef NDEBUG
#error Assertions must remain enabled
#endif
#include <assert.h>
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#define GET_STREAM_REQUEST_BUFFER_SIZE 32
#define NUM_OF_BLOCKS_REQUESTED 2U
#define mqttFileDownloader_CONFIG_BLOCK_SIZE 4096U
#define pdMS_TO_TICKS(x) (x)
typedef int DataType_t;
enum {OtaAgentEventRequestFileBlock=1};
static int lastRecvEventId=1,recvEventId;
static uint32_t currentBlockOffset,nextBlockOffsetToRequest,totalNumOfBlocks,currentFileId;
static unsigned capturedOffset,capturedCount,publishes;
static struct {int dataType;const char *topicGetStream;size_t topicGetStreamLength;} mqttFileDownloaderContext;
static bool mqttWrapper_isConnected(void) { return true; }
static void vTaskDelay(unsigned ticks) { (void)ticks; }
static size_t mqttDownloader_createGetDataBlockRequest(DataType_t type,uint32_t file,unsigned size,uint16_t offset,uint32_t count,char *out,unsigned capacity) {
 (void)type;(void)file;(void)size;(void)out;(void)capacity;capturedOffset=offset;capturedCount=count;return 1;
}
static bool mqttWrapper_publish(const char *topic,size_t length,const uint8_t *data,size_t size) {
 (void)topic;(void)length;(void)data;(void)size;publishes++;return true;
}
''' + request + '\nstatic void timeout_event(void) {\n' + timeout.replace('else if', 'if', 1) + r'''
}
int main(void) {
 /* Publish the final window successfully but lose every response. */
 totalNumOfBlocks=10;currentBlockOffset=8;nextBlockOffsetToRequest=8;
 requestDataBlock();assert(publishes==1 && capturedOffset==8 && capturedCount==2 && nextBlockOffsetToRequest==10);
 timeout_event();assert(recvEventId==OtaAgentEventRequestFileBlock);
 requestDataBlock();assert(publishes==2 && capturedOffset==8 && capturedCount==2);
 /* An outstanding earlier hole also wins over the advanced request cursor. */
 currentBlockOffset=2;nextBlockOffsetToRequest=8;timeout_event();requestDataBlock();
 assert(publishes==3 && capturedOffset==2 && capturedCount==2);
 return 0;
}
'''
        host.ProductApiTests.compile_run(self, fixture)
        control = fixture.replace("nextBlockOffsetToRequest = currentBlockOffset;", "", 1)
        self.assertNotEqual(control, fixture)
        with self.assertRaises(AssertionError):
            host.ProductApiTests.compile_run(self, control)
