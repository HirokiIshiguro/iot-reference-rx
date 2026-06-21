#ifndef AWS_IOT_CONFIG_H_
#define AWS_IOT_CONFIG_H_

#if defined(AWS_IOT_USE_LOCAL_CONFIG)
#include "aws_iot_config_local.h"
#endif

#ifndef AWS_IOT_MQTT_ENABLE
#define AWS_IOT_MQTT_ENABLE              (0)
#endif

#ifndef AWS_IOT_ENDPOINT
#define AWS_IOT_ENDPOINT                 ""
#endif

#ifndef AWS_IOT_THING_NAME
#define AWS_IOT_THING_NAME               "rx671-ek-type1yn"
#endif

#ifndef AWS_IOT_MQTT_PORT
#define AWS_IOT_MQTT_PORT                (8883U)
#endif

#ifndef AWS_IOT_PUBLISH_TOPIC
#define AWS_IOT_PUBLISH_TOPIC            AWS_IOT_THING_NAME "/smoke"
#endif

#ifndef AWS_IOT_CLIENT_CERT_PEM
#define AWS_IOT_CLIENT_CERT_PEM          ""
#endif

#ifndef AWS_IOT_CLIENT_PRIVATE_KEY_PEM
#define AWS_IOT_CLIENT_PRIVATE_KEY_PEM   ""
#endif

#endif /* AWS_IOT_CONFIG_H_ */
