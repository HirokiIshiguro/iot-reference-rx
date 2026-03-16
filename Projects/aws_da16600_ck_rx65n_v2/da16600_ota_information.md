# Wi-Fi(DA16600), PubSub/MQTT with Over-the-air(OTA) update sample project

## Overview

This document provides information about the demo with the following specifications:

* Connection: Wi-Fi (DA16600)
* Demo Type: OTA update

> **Note:**  
> For information about the "*PubSub/MQTT sample project*", see [**"da16600_pubsub_information.md"**](da16600_pubsub_information.md).  
> For information about the "*PubSub/MQTT with Fleet Provisioning sample project*", see [**"da16600_fleet_information.md"**](da16600_fleet_information.md).  
> For more information about setting up and running the demo, see [**"Getting_Started_Guide.md"**](../../Getting_Started_Guide.md).

## About the Over-the-air(OTA) update Demo using Wi-Fi connection

In this demo, we will use Wi-Fi to connect to AWS and perform an OTA(Over-the-air) firmware update.

* **Improved OTA Update** (v202406.01-LTS-rx-1.1.0 later)
  * OTA firmware update via MQTT, with additional feature implementation such as firmware version checking, self-test, job cancellation and abrupt disconnect handling.

### Tasks performed

This demo performs the following tasks:

| Task Name                 | Detail | stack size<BR>(Byte) | Priority |
|---------------------------|--------|----------------------|----------|
| Logging task              | This task uses another task, such as UART, to actually perform the printing output.                              | 4608 | 2 |
| UART command console task | This task provides a command console function to realize CLI using UART.                                         | 4608 | 1 |
| main task                 | This task is the application entry point from power-on reset.                                                    | 512  | 1 |
| MQTT-agent task           | This task uses the MQTT agent API to communicate with the MQTT broker over the same MQTT connection.             | 6144 | 2 |
| PubSub task               | This task uses the MQTT Agent API to send a unique MQTT payload to a unique topic over the same MQTT connection. | 2048 | 1 |
| OTA Demo task             | This task connects to the MQTT broker, creates the MQTT Agent task and calls the Ota demo loop.                  | 2304 | 1 |
| OTA Agent task            | This task manages the OTA firmware updates for the device.                                                       | 8192 | 1 |

### Memory usage

* PubSub + OTA

  | Compiler | RAM size | ROM size |
  |----------|----------|----------|
  | CC-RX    | 381KB    | 375KB    |
  | GCC      | 386KB    | 355KB    |

* PubSub + OTA With Fleet Provisioning

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

* For common hardware setup instructions, see [**Getting Started Guide: step 2**](../../Getting_Started_Guide.md#step-2-hardware-setup).
* For DA16600 specific hardware setup instructions, please see [**da16600_pubsub_information.md: Hardware setup**](da16600_pubsub_information.md#hardware-setup).

### Software setup

* For common software setup instructions, see [**Getting Started Guide: step 4-3**](../../Getting_Started_Guide.md#step-4-3-run-pubsubmqtt-with-over-the-airota-update-sample-project).
* For DA16600 specific software setup instructions, please see [**da16600_pubsub_information.md: Software setup**](da16600_pubsub_information.md#software-setup).

## Troubleshooting

### 1. Troubleshooting for OTA project

* [OTA Troubleshooting](/Projects/aws_ether_ck_rx65n_v2/ether_ota_information.md#troubleshooting)
