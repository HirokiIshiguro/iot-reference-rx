# Ethernet, PubSub/MQTT with Over-the-air(OTA) update sample project

## Overview

This document provides information about the demo with the following specifications:

* Connection: Ethernet
* Demo Type: OTA update

> **Note:**  
> For information about the "*PubSub/MQTT sample project*", see [**"ether_pubsub_information.md"**](ether_pubsub_information.md).  
> For information about the "*PubSub/MQTT with Fleet Provisioning sample project*", see [**"ether_fleet_information.md"**](ether_fleet_information.md).  
> For more information about setting up and running the demo, see [**"Getting_Started_Guide.md"**](../../Getting_Started_Guide.md).

## About the Over-the-air(OTA) update Demo using Ethernet connection

In this demo, we will use Ethernet to connect to AWS and perform an OTA(Over-the-air) firmware update.

* **Improved OTA Update** (v202406.01-LTS-rx-1.1.0 later)
  * OTA firmware update via MQTT, with additional feature implementation such as firmware version checking, self-test, job cancellation and abrupt disconnect handling.

### Tasks performed

This demo performs the following tasks:

| Task Name                 | Detail | stack size<BR>(Byte) | Priority |
|---------------------------|--------|----------------------|----------|
| Logging task              | This task uses another task, such as UART, to actually perform the printing output.                              | 4608 | 2 |
| UART command console task | This task provides a command console function to realize CLI using UART.                                         | 4608 | 1 |
| Ether Receive check task  | This task checks for incoming data from the Ethernet.                                                            | 512  | 6 |
| IP task                   | This task handles the Ethernet communication.                                                                    | 768  | 5 |
| main task                 | This task is the application entry point from power-on reset.                                                    | 512  | 1 |
| MQTT-agent task           | This task uses the MQTT agent API to communicate with the MQTT broker over the same MQTT connection.             | 6144 | 2 |
| PubSub task               | This task uses the MQTT Agent API to send a unique MQTT payload to a unique topic over the same MQTT connection. | 2048 | 1 |
| OTA Demo task             | This task connects to the MQTT broker, creates the MQTT Agent task and calls the Ota demo loop.                  | 2304 | 1 |
| OTA Agent task            | This task manages the OTA firmware updates for the device.                                                       | 8192 | 1 |

### Memory usage

* pubSub + OTA

  | Compiler | RAM size | ROM size |
  |----------|----------|----------|
  | CC-RX    | 350KB    | 407KB    |
  | GCC      | 358KB    | 390KB    |

* PubSub + OTA with Fleet Provisioning

  | Compiler | RAM size | ROM size |
  |----------|----------|----------|
  | CC-RX    | 358KB    | 428KB    |
  | GCC      | 366KB    | 423KB    |

### Confirmed Operation Environment

| Compiler | Version  | Details |
|----------|----------|---------|
| CC-RX    | V3.07.00 | Optimization: Level 2 |
| GCC      | GCC for Renesas RX v14.2.0.202505 | Optimization options:<br>&emsp;- Optimize for Debug<br>&emsp;- Function sections<br>&emsp;- Data sections<br>&emsp;- Enable garbage collection of unused input sections (-gc-sections) |

## Explanation specific to this demo

### Hardware setup

For hardware setup instructions, see [**Getting Started Guide: step 2**](../../Getting_Started_Guide.md#step-2-hardware-setup).

### Software setup

For software setup instructions, see [**Getting Started Guide: step 4-3**](../../Getting_Started_Guide.md#step-4-3-run-pubsubmqtt-with-over-the-airota-update-sample-project).

## Troubleshooting

### 1. Operation when OTA update firmware is abnormal

If the device cannot connect to the network when running the updated firmware, the self-test will not be performed and the updated firmware will be executed as is.  
In this case, the old firmware will remain in the flash memory, so please consider measures such as rollback to the old firmware.

### 2. Differences in behavior depending on LTS version after running OTA demo

Please note that the behavior when launching the OTA demo differs depending on the LTS version.  

  | LTS version    | detail |
  |----------------|--------|
  | v202210.01-LTS | After the *OTA demo starts running*, an OTA request message will be sent once.<BR>The *demo* will wait for the preconfigured *duration* to *poll for an OTA job*.<BR>After the preconfigured duration has elapsed, the device will enter suspended state. |
  | v202406.01-LTS | After the OTA demo *starts running*, OTA request messages *will be* sent to AWS periodically until an OTA job is *detected*.<BR>(There is no *configuration* value to specify the duration to wait for an OTA job.)|
  | v202406.04-LTS | After the *OTA demo starts running*, publish a `start-next` message to poll for existing OTA job.<BR>When no pending job is found, subscribe to the reserved topic *../jobs/notify* and wait for job notification.  |

### 3. Enable job cancellation events for OTA

This demo supports OTA update job cancellation.  
In order to use this feature, please check the following:

* Open IoT Core in the AWS Management Console.  
* Click **Settings** and check the **Event-based messages** section.
* Confirm that events such as `Job completed, canceled` are registered as shown below.  
  ![trouble-01](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/ota_trouble_01.png?raw=true)
* If the event is not registered, click the `Manage events` button, check the event, and add it.  
  ![trouble-02](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/ota_trouble_02.png?raw=true)
