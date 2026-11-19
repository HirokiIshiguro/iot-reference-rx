#ifndef CORE_MQTT_AGENT_CONFIG_H_
#define CORE_MQTT_AGENT_CONFIG_H_

#ifdef __cplusplus
extern "C" {
#endif

#include "logging_levels.h"

#ifndef LIBRARY_LOG_NAME
#define LIBRARY_LOG_NAME    "MQTT_Agent"
#endif

#ifndef LIBRARY_LOG_LEVEL
#define LIBRARY_LOG_LEVEL   LOG_INFO
#endif

#include "logging_stack.h"

#define MQTT_AGENT_MAX_EVENT_QUEUE_WAIT_TIME    (50U)

#ifdef __cplusplus
}
#endif

#endif /* CORE_MQTT_AGENT_CONFIG_H_ */
