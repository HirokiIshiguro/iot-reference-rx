/*
 * Tracealyzer Recorder configuration for EK-RX671 + Type 1YN.
 *
 * The recorder sources are not copied into this project. They are pulled from
 * Projects/aws_wifi_rx671_ek/external/TraceRecorderSource and compiled through
 * small wrappers under src/tracealyzer_recorder/upstream.
 */
#ifndef TRC_CONFIG_H
#define TRC_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

#include "platform.h"

#define TRC_CFG_HARDWARE_PORT              TRC_HARDWARE_PORT_Renesas_RX600
#define TRC_CFG_SCHEDULING_ONLY            0
#define TRC_CFG_INCLUDE_MEMMANG_EVENTS     0
#define TRC_CFG_INCLUDE_USER_EVENTS        1
#define TRC_CFG_INCLUDE_ISR_TRACING        1
#define TRC_CFG_INCLUDE_READY_EVENTS       1
#define TRC_CFG_INCLUDE_OSTICK_EVENTS      0

#define TRC_CFG_ENTRY_SLOTS                80
#define TRC_CFG_ENTRY_SYMBOL_MAX_LENGTH    28

#define TRC_CFG_ENABLE_TASK_MONITOR        0
#define TRC_CFG_TASK_MONITOR_MAX_TASKS     10
#define TRC_CFG_ENABLE_STACK_MONITOR       0
#define TRC_CFG_STACK_MONITOR_MAX_TASKS    10
#define TRC_CFG_STACK_MONITOR_MAX_REPORTS  1

#define TRC_CFG_CTRL_TASK_PRIORITY         1
#define TRC_CFG_CTRL_TASK_DELAY            10
#define TRC_CFG_CTRL_TASK_STACK_SIZE       512

#define TRC_CFG_RECORDER_BUFFER_ALLOCATION TRC_RECORDER_BUFFER_ALLOCATION_STATIC
#define TRC_CFG_MAX_ISR_NESTING            8
#define TRC_CFG_ISR_TAILCHAINING_THRESHOLD 0
#define TRC_CFG_RECORDER_DATA_INIT         1
#define TRC_CFG_RECORDER_DATA_ATTRIBUTE
#define TRC_CFG_USE_TRACE_ASSERT           0

#ifdef __cplusplus
}
#endif

#endif /* TRC_CONFIG_H */
