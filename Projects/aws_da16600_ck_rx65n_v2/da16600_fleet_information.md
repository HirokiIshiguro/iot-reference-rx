# Wi-Fi(DA16600), PubSub/MQTT with Fleet Provisioning sample project

## Overview

This document provides information about the demo with the following specifications:

* Connection: Wi-Fi(DA16600)
* Demo Type: Fleet Provisioning

> **Note:**  
> For information about the "*PubSub/MQTT sample project*", see [**"da16600_pubsub_information.md"**](da16600_pubsub_information.md).  
> For information about the "*PubSub/MQTT with Over-the-air(OTA) update sample project*", see [**"da16600_ota_information.md"**](da16600_ota_information.md).  
> For more information about setting up and running the demo, see [**"Getting_Started_Guide.md"**](../../Getting_Started_Guide.md).

## About the Fleet Provisioning Demo using Wi-Fi connection

In this demo, we will provision devices that connect to AWS using Fleet Provisioning over Ethernet.

### Tasks performed

This demo performs the following tasks:

| Task Name                 | Detail | stack size<BR>(Byte) | Priority |
|---------------------------|--------|----------------------|----------|
| Logging task              | This task uses another task, such as UART, to actually perform the printing output.                                                  | 4608 | 2 |
| UART command console task | This task provides a command console function to realize CLI using UART.                                                             | 4608 | 1 |
| main task                 | This task is the application entry point from power-on reset.                                                                        | 512  | 1 |
| MQTT-agent task           | This task uses the MQTT agent API to communicate with the MQTT broker over the same MQTT connection.                                 | 6144 | 2 |
| PubSub task               | This task uses the MQTT Agent API to send a unique MQTT payload to a unique topic over the same MQTT connection.                     | 2048 | 1 |
| Fleet Provisioning task   | In this task, you will use the Fleet Provisioning library to generate and sign certificates in AWS IoT to provision new IoT devices. | 2304 | 3 |

### Memory usage

* PubSub with Fleet Provisioning

  | Compiler | RAM size | ROM size |
  |----------|----------|----------|
  | CC-RX    | 367KB    | 355KB    |
  | GCC      | 372KB    | 358KB    |

* PubSub + OTA with Fleet Provisioning

  | Compiler | RAM size | ROM size |
  |----------|----------|----------|
  | CC-RX    | 390KB    | 397KB    |
  | GCC      | 395KB    | 388KB    |

### Confirmed Operation Environment

| Compiler | Version  | Details |
|----------|----------|---------|
| CC-RX    | V3.07.00 | Optimization: Level 2 |
| GCC      | GCC for Renesas RX v14.2.0.202505 | Optimization options:<br>&emsp;- Optimize for Debug<br>&emsp;- Function sections<br>&emsp;- Data sections<br>&emsp;- Enable garbage collection of unused input sections (-gc-sections) |

## Explanation specific to this demo

### Hardware setup

* For hardware setup instructions, see [**Getting Started Guide: step 2**](../../Getting_Started_Guide.md#step-2-hardware-setup).
* For DA16600 specific hardware setup instructions, please see [**da16600_pubsub_information.md: Hardware setup**](da16600_pubsub_information.md#hardware-setup).

### Software setup

* For software setup instructions, see [**Getting Started Guide: step 4-2**](../../Getting_Started_Guide.md#step-4-2-run-pubsubmqtt-with-fleet-provisioning-sample-project).
* For DA16600 specific software setup instructions, please see [**da16600_pubsub_information.md: Software setup**](da16600_pubsub_information.md#software-setup).

## Troubleshooting

N/A
