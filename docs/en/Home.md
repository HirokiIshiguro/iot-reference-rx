# Welcome to the AWS IoT Reference for Renesas RX MCUs
[English](../ja/Home.md)(This page) / [日本語](../ja/Home.md)  
1. [Tutorial](#tutorial)
1. [TroubleShooting](#TroubleShooting)

The Renesas RX family prepares evaluation boards and FreeRTOS projects certified by AWS Partner Device.  
Please refer to the figure below for the various solutions offered by the RX Family in conjunction with the AWS Cloud.


```mermaid
flowchart TB
classDef blue fill:#06418c,stroke:#fff,stroke-width:2px,color:#fff
    Start(Development of IoT devices using RX)
    Start -->|Step1|CK
subgraph CK[Trial connection to AWS]
direction TB
    KitPage[Learn about and purchase<br>the CK-RX65N<br> - Wi-Fi and Ethernet -]:::blue
        click KitPage "https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/ck-rx65n-cloud-kit-based-rx65n-mcu-group"
    KitPage --> Step1[Trial connecting to AWS<br>with a dashboard demo for CK-RX65N]:::blue
        click Step1 "https://www.renesas.com/document/qsg/aws-cloud-connectivity-ck-rx65n-v2-wi-fi-da16600-getting-started-guide"
end
    CK --> |Step2|FreeRTOS
subgraph FreeRTOS[IoT device development]
direction TB
subgraph iotref[ ]
direction TB
style iotref fill-opacity:0, stroke-opacity:0;
    GSG[Getting Start Guide]:::blue
        click GSG "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md"
end
subgraph with[Demo projects that connected to AWS cloud using AWS libraries]
direction TB
subgraph dummy[ ]
style dummy fill-opacity:0, stroke-opacity:0;
    GSG --- MQTT[MQTT]:::blue-.-MQTT_Video[Video]:::blue
        click MQTT "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md#step-4-run-demos"
        click MQTT_Video "https://www.renesas.com/ajax/show-video/25570839"
    GSG --- OTA[OTA]:::blue-.-OTA_Video[Video]:::blue
        click OTA "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md#step-4-3-run-pubsubmqtt-with-over-the-airota-update-sample-project"
        click OTA_Video "https://www.renesas.com/video/freertos-ota-tutorial-ck-rx65n-13-cloud-operation"
    GSG --- Fleet[Fleet<br>Provisioning]:::blue-.-Fleet_Video[Video]:::blue
        click Fleet "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md#step-4-2-run-pubsubmqtt-with-fleet-provisioning-sample-project"
        click Fleet_Video "https://www.renesas.com/video/freertos-fleet-provisioning-tutorial-ck-rx65n-12-iot-devices-cloud-operation"
    GSG --- TSIP[TLS with<br>TSIP]:::blue-.-TSIP_Video[Video]:::blue
        click TSIP "https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md#step-4-4-run-pubsubmqtt-with-over-the-airota-update-sample-project-tls-with-tsip"
        click TSIP_Video "https://www.renesas.com/ajax/show-video/25566619"
end
end

subgraph minimalproject[Demo project that does not include AWS libraries]
direction TB
style Comment fill-opacity:0, stroke-opacity:0;
    GSG --- minimal[Free RTOS TCP minimal]:::blue
    click minimal "https://github.com/renesas/iot-reference-rx/blob/accf243603b068bf6e8d88be76c433f8b9125da5/Configuration/samples/minimal_tcp/README.md"
    Comment[Provides basic TCP/IP<br>functionaly using<br>Free RTOS Kernel<br>and FreeRTOS-Plus-TCP]
end
end
    FreeRTOS --- |Various solutions to support development|items

subgraph items[Collateral]
direction RL
    subgraph APN
        2nd[2ndry Device<br>Update]:::blue
            click 2nd "https://www.renesas.com/document/scd/rx65n-group-sample-code-ota-update-secondary-device-amazon-web-services-use-freertos-rev200"
        FWUP[FW Update FIT]:::blue
            click FWUP "https://www.renesas.com/document/apn/rx-family-firmware-update-module-using-firmware-integration-technology-application-notes"
    end
    subgraph Tool
        QE[QE for OTA]:::blue
            click QE "https://www.renesas.com/software-tool/qe-ota-development-assistance-cloud"
    end
    subgraph Wiki[This Wiki]
        Tutorial
        TroubleShooting
        info[Useful Information]
    end
end
```

# Reference
* The latest Application Note(APN), seminar and related information : [Renesas Official Web](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/cloudsolutions)  

# Tutorial
For the latest information on using Free RTOS projects for RX, please refer to the [Getting Start Guide](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md).  
If you would like to learn more about the various settings in AWS and operating procedures in e² studio, please also check the following tutorials.    
1. [Register device to AWS IoT](Register-device-to-AWS-IoT.md)
1. [Creating and importing a FreeRTOS project](Creating-and-importing-a-FreeRTOS-project.md)  
 [Importing a FreeRTOS project(zip)](Creating-and-importing-a-FreeRTOS-project.md#importing-a-freertos-project)  
 [Create a new FreeRTOS project](Creating-and-importing-a-FreeRTOS-project.md#create-a-new-freertos-project) 
1. [Configure the FreeRTOS project to connect to AWS IoT Core](Configure-the-FreeRTOS-project-to-connect-to-AWS-IoT-Core.md) 
1. [Execute Amazon FreeRTOS project and connect RX devices to AWS IoT](Execute-Amazon-FreeRTOS-project-and-connect-RX-devices-to-AWS-IoT.md)

# TroubleShooting
Please refer to the [TroubleShooting](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md#troubleshooting).

# FreeRTOS Related External Links(aws.com)
1. [Amazon FreeRTOS](https://aws.amazon.com/freertos/)
1. [Getting Started with FreeRTOS](https://docs.aws.amazon.com/freertos/latest/userguide/freertos-getting-started.html)
1. [Amazon FreeRTOS Documents](https://docs.aws.amazon.com/freertos/)
	1. [Amazon FreeRTOS UserGuide](https://docs.aws.amazon.com/freertos/latest/userguide/index.html)
	1. [Amazon FreeRTOS API Reference](https://docs.aws.amazon.com/freertos/latest/lib-ref/index.html)
	1. [FreeRTOS kernel fundamentals](https://docs.aws.amazon.com/freertos/latest/userguide/dev-guide-freertos-kernel.html)
