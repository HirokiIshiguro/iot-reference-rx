/*
 * Copyright Amazon.com, Inc. and its affiliates. All Rights Reserved.
 * Modifications Copyright (C) 2025 Renesas Electronics Corporation or its affiliates.
 * SPDX-License-Identifier: MIT
 *
 * Licensed under the MIT License. See the LICENSE accompanying this file
 * for the specific language governing permissions and limitations under
 * the License.
 */

#ifndef MQTT_WRAPPER_H
#define MQTT_WRAPPER_H

#include "FreeRTOS.h"
#include "task.h"

#include "core_mqtt.h"
#include "core_mqtt_agent.h"
#include "mqtt_agent_task.h"

/**********************************************************************************************************************
 * Function Name: mqttWrapper_setCoreMqttContext
 * Description  : .
 * Argument     : mqttContext
 * Return Value : .
 *********************************************************************************************************************/
void mqttWrapper_setCoreMqttContext (MQTTContext_t * mqttContext);

/**********************************************************************************************************************
 * Function Name: mqttWrapper_setThingName
 * Description  : .
 * Arguments    : thingName
 *              : thingNameLength
 * Return Value : .
 *********************************************************************************************************************/
void mqttWrapper_setThingName (char * thingName,
                            size_t thingNameLength);

/**********************************************************************************************************************
 * Function Name: mqttWrapper_getThingName
 * Description  : .
 * Arguments    : thingNameBuffer
 *              : thingNameLength
 * Return Value : .
 *********************************************************************************************************************/
void mqttWrapper_getThingName (char *   thingNameBuffer,
                            size_t * thingNameLength );

/**********************************************************************************************************************
 * Function Name: mqttWrapper_isConnected
 * Description  : .
 * Return Value : .
 *********************************************************************************************************************/
bool mqttWrapper_isConnected (void);

/**********************************************************************************************************************
 * Function Name: mqttWrapper_publish
 * Description  : .
 * Arguments    : topic
 *              : topicLength
 *              : message
 *              : messageLength
 * Return Value : .
 *********************************************************************************************************************/
bool mqttWrapper_publish (char *    topic,
                        size_t    topicLength,
                        uint8_t * message,
                        size_t    messageLength );

/**********************************************************************************************************************
 * Function Name: mqttWrapper_subscribe
 * Description  : .
 * Arguments    : topic
 *              : topicLength
 * Return Value : .
 *********************************************************************************************************************/
bool mqttWrapper_subscribe (char * topic,
                        size_t topicLength);

/**********************************************************************************************************************
 * Function Name: mqttWrapper_unsubscribe
 * Description  : .
 * Arguments    : topic
 *              : topicLength
 * Return Value : .
 *********************************************************************************************************************/
bool mqttWrapper_unsubscribe (char * topic,
                            size_t topicLength);

#endif /* ifndef MQTT_WRAPPER_H */
