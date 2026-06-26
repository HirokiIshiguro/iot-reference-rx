/*
 * Tracealyzer FreeRTOS kernel-port configuration.
 */
#ifndef TRC_KERNEL_PORT_CONFIG_H
#define TRC_KERNEL_PORT_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

#define TRC_CFG_FREERTOS_VERSION               TRC_FREERTOS_VERSION_11_1_0
#define TRC_CFG_INCLUDE_EVENT_GROUP_EVENTS     0
#define TRC_CFG_INCLUDE_TIMER_EVENTS           0
#define TRC_CFG_INCLUDE_PEND_FUNC_CALL_EVENTS  0
#define TRC_CFG_INCLUDE_STREAM_BUFFER_EVENTS   0
#define TRC_CFG_ACKNOWLEDGE_QUEUE_SET_SEND     0
#define TRC_CFG_KERNEL_PORT_TASK_MONITOR_TLS_INDEX 0

#ifdef __cplusplus
}
#endif

#endif /* TRC_KERNEL_PORT_CONFIG_H */
