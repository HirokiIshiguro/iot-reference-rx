"""Compile the real logger against a bounded FIFO and deterministic scheduler.

The consumer step models the logging task draining one record while a producer
waits. It exercises enqueue order and failure handling, not physical UART I/O.
"""
from pathlib import Path
import unittest

from tools.ci.tests import test_product_oss_api as host


ROOT = Path(__file__).resolve().parents[3]
LOGGING = ROOT / "Middleware/logging"

HEADERS = {
    "FreeRTOS.h": r"""
#ifndef INC_FREERTOS_H
#define INC_FREERTOS_H
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <assert.h>
typedef int BaseType_t;
typedef unsigned UBaseType_t;
typedef uint32_t TickType_t;
typedef void *TaskHandle_t;
#define pdPASS 1
#define pdFAIL 0
#define portMAX_DELAY UINT32_MAX
#define taskSCHEDULER_SUSPENDED 0
#define taskSCHEDULER_NOT_STARTED 1
#define taskSCHEDULER_RUNNING 2
#define configASSERT(x) assert(x)
#define configLOGGING_MAX_MESSAGE_LENGTH 192
#define configLOGGING_INCLUDE_TIME_AND_TASK_NAME 1
void capture(const char *text);
#define configPRINT_STRING(x) capture(x)
void *pvPortMalloc(size_t size);
void vPortFree(void *pointer);
void vLoggingPrint(const char *text);
#endif
""",
    "task.h": r"""
BaseType_t xTaskCreate(void (*task)(void *), const char *name, uint16_t stack,
                      void *argument, UBaseType_t priority, TaskHandle_t *handle);
BaseType_t xTaskGetSchedulerState(void);
TaskHandle_t xTaskGetCurrentTaskHandle(void);
const char *pcTaskGetName(TaskHandle_t task);
TickType_t xTaskGetTickCount(void);
""",
    "queue.h": r"""
typedef struct Queue *QueueHandle_t;
QueueHandle_t xQueueCreate(UBaseType_t count, UBaseType_t size);
BaseType_t xQueueSend(QueueHandle_t queue, const void *item, TickType_t wait);
BaseType_t xQueueReceive(QueueHandle_t queue, void *item, TickType_t wait);
void vQueueDelete(QueueHandle_t queue);
""",
    "semphr.h": "",
}

FIXTURE = r"""
#include "FreeRTOS.h"
#include "task.h"
#include "queue.h"
#include "iot_logging_task.h"
#include <stdio.h>
#include <string.h>
struct Queue { unsigned count, head; char *items[15]; };
static struct Queue fifo;
static unsigned allocated, released, drops, waited, emitted;
static int fail_allocation, scheduler=taskSCHEDULER_RUNNING, logging_caller;
static int logger_identity, producer_identity;
static char output[32][192];

void *pvPortMalloc(size_t size) {
    void *pointer=fail_allocation ? NULL : malloc(size);
    if(pointer) allocated++;
    return pointer;
}
void vPortFree(void *pointer) { if(pointer) released++; free(pointer); }
BaseType_t xTaskCreate(void (*task)(void *), const char *name, uint16_t stack,
                      void *argument, UBaseType_t priority, TaskHandle_t *handle) {
    (void)task; (void)name; (void)stack; (void)argument; (void)priority;
    if(handle) *handle=&logger_identity;
    return pdPASS;
}
BaseType_t xTaskGetSchedulerState(void) { return scheduler; }
TaskHandle_t xTaskGetCurrentTaskHandle(void) {
    return logging_caller ? &logger_identity : &producer_identity;
}
const char *pcTaskGetName(TaskHandle_t task) { (void)task; return "fixture"; }
TickType_t xTaskGetTickCount(void) { return 42; }
void capture(const char *text) {
    assert(emitted<32 && strlen(text)<sizeof(output[0]));
    strcpy(output[emitted++],text);
}
void vOutputString(const char *text) { capture(text); }
QueueHandle_t xQueueCreate(UBaseType_t count, UBaseType_t size) {
    assert(count==15 && size==sizeof(char *));
    memset(&fifo,0,sizeof(fifo)); return &fifo;
}
BaseType_t xQueueReceive(QueueHandle_t queue, void *item, TickType_t wait) {
    (void)wait;
    if(!queue->count) return pdFAIL;
    *(char **)item=queue->items[queue->head];
    queue->head=(queue->head+1)%15; queue->count--; return pdPASS;
}
static void consume_one(void) {
    char *text;
    assert(xQueueReceive(&fifo,&text,0)==pdPASS);
    capture(text); vPortFree(text);
}
BaseType_t xQueueSend(QueueHandle_t queue, const void *item, TickType_t wait) {
    assert(wait==0 || wait==portMAX_DELAY);
    if(queue->count==15 && wait==portMAX_DELAY) {
        /* Model the consumer running while the producer is blocked. */
        consume_one(); waited++;
    }
    if(queue->count==15) { drops++; return pdFAIL; }
    queue->items[(queue->head+queue->count)%15]=*(char *const *)item;
    queue->count++; return pdPASS;
}
void vQueueDelete(QueueHandle_t queue) { assert(queue==&fifo && !queue->count); }
static void drain(void) { while(fifo.count) consume_one(); }
static void fill(void) {
    unsigned index;
    for(index=0;index<15;index++) vLoggingPrintf("metric %u\r\n",index);
    assert(fifo.count==15 && emitted==0);
}
int main(void) {
    unsigned index, number;
    assert(xLoggingTaskInitialize(1024,2,15)==pdPASS);
#if LOG_TEST_CASE == 0
    fill();
    vLoggingPrintf("default"); vLoggingPrintfError("error");
    vLoggingPrintfWarn("warn"); vLoggingPrintfInfo("info");
    vLoggingPrintfDebug("debug");
    vLoggingPrintfWithFileAndLine("fixture.c",1,"location");
    vLoggingPrint("unformatted");
    assert(drops==7 && waited==0 && fifo.count==15);
    drain(); assert(emitted==15);
#elif LOG_TEST_CASE == 1
    fill();
    assert(xLoggingPrintfWait("[LANBENCH] DUAL_RESOURCE stage=done\r\n")==pdPASS);
    assert(xLoggingPrintfWait("[LANBENCH] PASS\r\n")==pdPASS);
    assert(waited==2 && drops==0 && emitted==2);
    drain(); assert(emitted==17);
    for(index=0;index<emitted;index++) {
        assert(sscanf(output[index],"%u",&number)==1 && number==index);
    }
    assert(strstr(output[15],"DUAL_RESOURCE stage=done"));
    assert(strstr(output[16],"[LANBENCH] PASS"));
#elif LOG_TEST_CASE == 2
    fail_allocation=1;
    assert(xLoggingPrintfWait("must not report success")==pdFAIL);
    assert(allocated==0 && fifo.count==0);
#elif LOG_TEST_CASE == 3
    scheduler=taskSCHEDULER_NOT_STARTED;
    assert(xLoggingPrintfWait("not started")==pdFAIL);
    scheduler=taskSCHEDULER_SUSPENDED;
    assert(xLoggingPrintfWait("suspended")==pdFAIL);
    assert(allocated==0 && fifo.count==0);
#elif LOG_TEST_CASE == 4
    logging_caller=1;
    assert(xLoggingPrintfWait("must not wait on self")==pdFAIL);
    assert(allocated==0 && fifo.count==0);
#else
#error Unknown fixture case
#endif
    assert(allocated==released);
    (void)index; (void)number;
    return 0;
}
"""


@unittest.skipUnless(host.GCC or host.MSVC, "Host C compiler required")
class LoggingDeliveryTests(unittest.TestCase):
    def compile_case(self, case):
        host.ProductApiTests.compile_run(
            self, FIXTURE, headers=HEADERS,
            extra_sources=(LOGGING / "iot_logging_task_dynamic_buffers.c",),
            extra_includes=(LOGGING / "include",),
            extra_defines=(f"LOG_TEST_CASE={case}",))

    def test_existing_apis_remain_nonblocking_when_fifo_is_full(self):
        self.compile_case(0)

    def test_waiting_producer_preserves_metrics_and_final_verdict_order(self):
        self.compile_case(1)

    def test_allocation_failure_does_not_report_enqueue_success(self):
        self.compile_case(2)

    def test_unstarted_or_suspended_scheduler_is_rejected(self):
        self.compile_case(3)

    def test_logging_task_cannot_wait_on_its_own_fifo(self):
        self.compile_case(4)


if __name__ == "__main__":
    unittest.main()
