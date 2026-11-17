# Getting Start Guide
The following tables shows the boards  certified by AWS Partner Device.  
You can start developing IoT products immediately using Getting Start Guide or Application Notes (APN).  
The supported FreeRTOS version is different by each board.  
[Renesas GitHub](https://github.com/renesas/iot-reference-rx) will post the latest FreeRTOS program for RX.  
Also, when the device that you use is not listed in this table, please check the old GitHub.

| MCU | Boards | Wi-Fi | Ether | LTE CAT-M1 | AWS Partner Device Catalog | Getting Start Gude | Startup APN for IoT development |
| ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ |
| RX65N | [CK-RX65N v1](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/ck-rx65n-cloud-kit-based-rx65n-mcu-group) | - | Supported| Supported| [Link](https://devices.amazonaws.com/detail/a3G8a00000Et8xUEAR/Renesas-CK-RX65N) | [Link](https://www.renesas.com/document/qsg/rx65n-connecting-aws-cloud-freertos-getting-started-guide-ck-rx65n) | [Link](https://www.renesas.com/document/qsg/ck-rx65n-sim-activation-creating-trial-account-and-using-dashboard-getting-started-guide-ck-rx65n) |
| RX65N | [CK-RX65N v2](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/ck-rx65n-cloud-kit-based-rx65n-mcu-group)（*1） | Supported| Supported| - | - | - | [Link](https://www.renesas.com/document/qsg/aws-cloud-connectivity-ck-rx65n-v2-wi-fi-da16600-getting-started-guide) |
| RX65N | [RX65N CloudKit](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/rx65n-cloud-kit-renesas-rx65n-cloud-kit) | Supported | - | - | [Link](https://devices.amazonaws.com/detail/a3G0h000000P0lFEAS/RX65N-Cloud-Kit) |  [Link](https://www.renesas.com/document/qsg/connecting-aws-cloud-freertos-getting-started-guide-renesas-rx65n-cloud-kit-rev100) | <- |
| RX65N | [Renesas Starter Kit+ for RX65N-2MB](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/rx65n-2mb-starter-kit-plus-renesas-starter-kit-rx65n-2mb) | - | Supported | - | [Link](https://devices.amazonaws.com/detail/a3G0L00000AAOkeUAH/Renesas-Starter-Kit-for-RX65N-2MB) |  [Link](https://www.renesas.com/document/qsg/connecting-aws-cloud-freertos-getting-started-guide-renesas-starter-kit-rx65n-2mb-rev100) | <- |
| RX72N | [RX72N Envision Kit](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/rx72n-envision-kit-rx72n-envision-kit) | Supported(*2) | - | - | [Link](https://devices.amazonaws.com/detail/a3G0h00000E1zpfEAB/RX72N-Envision-Kit) |  [Link](https://www.renesas.com/document/qsg/connecting-aws-cloud-freertos-getting-started-guide-renesas-rx72n-envision-kit-rev100) | <- |
| RX671 | [Renesas Starter Kit+ for RX671](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/rx671-starter-kit-plus-renesas-starter-kit-rx671) | Supported(*2) | - | - | [Link](https://devices.amazonaws.com/detail/a3G0h00000E20zqEAB/Renesas-Starter-Kit-for-RX671) |  [Link](https://www.renesas.com/document/qsg/getting-started-renesas-starter-kit-rx671) | <- |

Note1: For specification differences between CK-RX65N v1 and v2, please [click here](../ja/CK-RX65N_Specification.md).  
Note2: Requires [Wi-Fi Pmod expansion board](https://www.renesas.com/products/microcontrollers-microprocessors/ra-cortex-m-mcus/wi-fi-pmod-expansion-board-80211bgn-24g-wi-fi-pmod-expansion-board)(Requires purchase addtionally)

# Data visualization in the cloud
Renesas provides an APN that the board collects sensor data and sends it to AWS cloud service, then visualizes it as a graph.  

- [RX65N CloudKit(Wi-Fi)](https://www.renesas.com/document/apn/visualizing-and-controlling-sensor-information-using-amazon-web-services-rx65n-cloud-kit-and?r=1471546)

- [RX72N EnvisionKit(Wi-Fi)](https://www.renesas.com/document/apn/rx72n-group-using-quick-connect-iot-send-sensor-information-amazon-web-services-rx72n-envision-kit?r=1471546)*

- [CK-RX65N(Cellular / Ethernet)](https://www.renesas.com/document/scd/ck-rx65n-sim-activation-creating-trial-account-and-using-dashboard-getting-started-guide-ck-rx65n?r=1471546)

Note: It needs to use [Wi-Fi Pmod Expansion Board](https://www.renesas.com/products/microcontrollers-microprocessors/ra-cortex-m-mcus/wi-fi-pmod-expansion-board-80211bgn-24g-wi-fi-pmod-expansion-board)


# Remote firmware update via OTA
RX Family has solutions for OTA firmware updates remotely using the AWS cloud service.
- [Renesas MCU Firmware Update Design Policy](https://www.renesas.com/document/apn/renesas-mcu-firmware-update-design-policy-rev100?r=1471546&r=1471546)  
This APN introduces the design principles of firmware update in Renesas MCUs.  
It includes mechanisms for security features, bootloader implementation, and so on.  

- [FW Update FIT* module v1.06](https://www.renesas.com/document/scd/rx-family-firmware-update-module-using-firmware-integration-technology-sample-code?r=1499716&r=1471546) / [FW Update FIT* module v2.01](https://www.renesas.com/document/scd/rx-family-firmware-update-module-using-firmware-integration-technology-application-notes-rev200)  
This is a Fit module to assists in the implementation of firmware update.  
If you are using e² studio, this Fit module can be downloaded directly from the IDE.  
Note: [Firmware Integration Technology](https://www.renesas.com/software-tool/fit). Refer to the link for more detail.

- [How to implement FreeRTOS OTA by using Amazon Web Services](https://www.renesas.com/document/apn/rx-family-how-implement-freertos-ota-using-amazon-web-services-rx65n-rev102?r=1471546&r=1471546)  
This APN shows how to apply OTA features on AWS cloud service with the FreeRTOS for RX family.  

- [Development Assistance QE for OTA](https://www.renesas.com/software-tool/qe-ota-development-assistance-cloud-technical-preview-edition)  
The “QE for OTA” is an assistant tool makes it easier with to implement OTA in e² studio's GUI.  
This tool integrates the all of the procedures regarding OTA from inputting to AWS console to checking the result of OTA.

- [Secondary Device OTA FW Update](https://www.renesas.com/document/scd/rx65n-group-sample-code-ota-update-secondary-device-amazon-web-service-using-freertos-rev110-sample?r=1471546)  
This APN presents a way to achieve OTA for devices connected to a gateway device (secondry devices).  
This APN can be utilized to enable OTA firmware updates for devices that are not directly connected to the network.
<img src="https://github.com/renesas/iot-reference-rx/assets/121073232/45db0efb-1578-4fd7-a3c7-303b583f8cac" width="600">

# Fleet Provisioning
- [Provisioning Procedure for IoT Devices](https://www.renesas.com/document/apn/rx-family-provisioning-procedure-iot-devices-rev100)  
This sample program allows you to easily run AWS Fleet Provisioning, which automatically handles the provisioning of multiple devices, a challenge in mass production.    
The Fleet Provisioning sample program is also available from e² studio's project generation function.
