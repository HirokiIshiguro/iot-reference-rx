# FreeRTOS LTS IoT Reference for RX72N Envision Kit

## Introduction

This repository is currently maintained as an RX72N Envision Kit focused FreeRTOS/AWS IoT reference.  
The original upstream covered multiple RX boards, but this fork now keeps only the RX72N projects because the boot loader mechanism differs from the other targets.

The RX family is a kind of MCUs provided by [Renesas](https://www.renesas.com), and this repository uses [AWS](https://aws.amazon.com) and [FreeRTOS](https://www.freertos.org/RTOS.html) as the software stack.

## Product Specifications

This reference is consist of demo applications, FreeRTOS kernel, middleware provided by AWS and 3rd party, middleware and drivers for RX family provided as the [RX Driver Package](https://github.com/renesas/rx-driver-package) by the Renesas, files to collaborate Renesas tools such as the IDE [e2 studio](https://www.renesas.com/software-tool/e-studio), and etc.
Summary of specifications explains in the following chapters.

### Using AWS Services

* [AWS IoT core](https://aws.amazon.com/iot-core/)

### Supported Board

* RX72N Envision Kit

### Current Scope

The current maintained projects in `Projects/` are:

* `boot_loader_rx72n_envision_kit`
* `aws_ether_rx72n_envision_kit`

Historical documentation for CK-RX65N v2 and its variants may remain in this repository, but those projects are no longer shipped in `Projects/`.

| Tags | Connectivity | Compiler  | Import project | Project generation (PG) | PubSub | OTA update | Fleet Provisioning | TLS with TSIP |TCP minimal |
|------|--------------|-----------|----------------|-------------------------|--------|-----|-------------------|-------------|-------------|
| [v202406.04-LTS-rx-1.2.0](https://github.com/renesas/iot-reference-rx/tree/v202406.04-LTS-rx-1.2.0)<br>* This Version | Ethernet, Cellular, Wi-Fi | CC-RX, GCC | Yes | No   | Yes  | Yes | Yes  | No  | No |
| [v202406.01-LTS-rx-1.1.1](https://github.com/renesas/iot-reference-rx/tree/v202406.01-LTS-rx-1.1.1) | Ethernet, Cellular, Wi-Fi | CC-RX, GCC | Yes | Yes  | Yes  | Yes<BR>(Not supported for Wi-Fi)  | No  | No  | Yes |
| [v202406.01-LTS-rx-1.1.0](https://github.com/renesas/iot-reference-rx/tree/v202406.01-LTS-rx-1.1.0) | Ethernet, Cellular, Wi-Fi | CC-RX, GCC | Yes | No  | Yes  | Yes<BR>(Not supported for Wi-Fi)  | No  | No  | No  |
| [v202406.01-LTS-rx-1.0.1](https://github.com/renesas/iot-reference-rx/tree/v202406.01-LTS-rx-1.0.1) | Ethernet | CC-RX, GCC | Yes | Yes | Yes | No  | No | No | Yes |
| [v202210.01-LTS-rx-1.3.2](https://github.com/renesas/iot-reference-rx/tree/v202210.01-LTS-rx-1.3.2) | Ethernet, Wi-Fi | CC-RX, GCC | Yes | Yes | Yes | Yes | Yes | Yes<BR>(PubSub and OTA for CC-RX) | Yes |

> note 1: demo:
>
> * PubSub  
>   Simple MQTT communication with AWS CLI or AWS Management Console
> * OTA (Over-the-air) update  
>   Update device firmware using AWS
> * Fleet Provisioning  
>   Generating and securely delivering device certificates and private keys to your devices by AWS when they connect to AWS IoT for the first time
> * TCP minimal(Ethernet Only)
>   * Provides basic TCP/IP functionality using FreeRTOS Kernel and FreeRTOS-Plus-TCP
>   * Acquisition of IP address by DHCP
>   * IP address search of URLs by DNS

> note 2: TLS with TSIP:
>
> * It uses the RX Family's built-in security hardware, [Trusted Secure IP (TSIP)](https://www.renesas.com/products/microcontrollers-microprocessors/rx-32-bit-performance-efficiency-mcus/rx-security-solutions).
> * This enables secure key management and high-speed encryption and decryption for TLS communications.

> note3 : The preceding demos use the following technical elements of the AWS IoT:
>
> * [AWS IoT Jobs](https://docs.aws.amazon.com/iot/latest/developerguide/iot-jobs.html)
> * [MQTT File Delivery](https://docs.aws.amazon.com/iot/latest/developerguide/mqtt-based-file-delivery.html) 

> note 4: From v202406.01-LTS-rx-1.1.1, the PG feature also supports RX65N group custom user boards.

### Open Source Software (OSS) Components

The following table indicates name and version of OSS which are used in this reference. The column *LTS Until* indicates the support period as LTS.

| Library                          | Version       | LTS Until  | LTS Repo URL                                                         | Remarks |
|----------------------------------|---------------|------------|----------------------------------------------------------------------|---------|
| FreeRTOS Cellular Interface      | 1.4.0         | 06/30/2026 | <https://github.com/FreeRTOS/FreeRTOS-Cellular-Interface>            | Unused  |
| FreeRTOS Kernel                  | 11.1.0        | 06/30/2026 | <https://github.com/FreeRTOS/FreeRTOS-Kernel>                        |         |
| FreeRTOS-Plus-TCP                | 4.2.5         | 06/30/2026 | <https://github.com/FreeRTOS/FreeRTOS-Plus-TCP>                      |         |
| backoffAlgorithm                 | 1.4.1         | 06/30/2026 | <https://github.com/FreeRTOS/backoffAlgorithm>                       |         |
| coreHTTP Client                  | 3.1.1         | 06/30/2026 | <https://github.com/FreeRTOS/coreHTTP>                               | Unused  |
| coreJSON                         | 3.3.0         | 06/30/2026 | <https://github.com/FreeRTOS/coreJSON>                               |         |
| coreMQTT Client                  | 2.3.1         | 06/30/2026 | <https://github.com/FreeRTOS/coreMQTT>                               |         |
| coreMQTT Agent                   | 1.3.1         | --         | <https://github.com/FreeRTOS/coreMQTT-Agent>                         |         |
| corePKCS11                       | 3.6.3         | 06/30/2026 | <https://github.com/FreeRTOS/corePKCS11>                             |         |
| coreSNTP                         | 1.3.1         | 06/30/2026 | <https://github.com/FreeRTOS/coreSNTP>                               | Unused  |
| AWS IoT Device Defender          | 1.4.0         | 06/30/2026 | <https://github.com/aws/Device-Defender-for-AWS-IoT-embedded-sdk>    | Unused  |
| AWS IoT Device Shadow            | 1.4.1         | 06/30/2026 | <https://github.com/aws/Device-Shadow-for-AWS-IoT-embedded-sdk>      | Unused  |
| AWS IoT Fleet Provisioning       | 1.2.1         | 06/30/2026 | <https://github.com/aws/Fleet-Provisioning-for-AWS-IoT-embedded-sdk> |         |
| AWS IoT Jobs                     | 1.5.1         | 06/30/2026 | <https://github.com/aws/Jobs-for-AWS-IoT-embedded-sdk>               |         |
| AWS SigV4                        | 1.3.0         | 06/30/2026 | <https://github.com/aws/SigV4-for-AWS-IoT-embedded-sdk>              | Unused  |
| AWS IoT MQTT File Streams        | 1.1.0         | 06/30/2026 | <https://github.com/aws/aws-iot-core-mqtt-file-streams-embedded-c>   |         |
| tinycbor                         | 0.5.2         | --         | <https://github.com/intel/tinycbor>                                    |         |
| mbedtls                          | 3.6.4         | --         | <https://github.com/Mbed-TLS/mbedtls>                                     |         |
| mbedtls_config                   | 3.6.4         | --         | --                                           |         |
| mbedtls_utils                    | --            | --         | --                                           |         |
| littlefs                         | 2.5.1         | --         | <https://github.com/littlefs-project/littlefs>                   |         |
| FreeRTOS-Plus network_transport  | --            | --         | <https://github.com/FreeRTOS/FreeRTOS/tree/main/FreeRTOS-Plus/Source/Application-Protocols/network_transport> |         |
| FreeRTOS-Plus-CLI                | 1.0.4         | --         | <https://github.com/FreeRTOS/FreeRTOS/tree/main/FreeRTOS-Plus/Source/FreeRTOS-Plus-CLI>                       |         |
| FreeRTOS crypto                  | 1.1.2         | --         | <https://github.com/aws/amazon-freertos/tree/main/libraries/freertos_plus/standard/crypto>                    |         |
| Logging Interface                | 1.1.3         | --         | <https://github.com/aws/amazon-freertos/tree/main/libraries/logging> |         |
| pkcs11                           | 2-40-errata-1 | --         | <https://github.com/amazon-freertos/pkcs11>                          |         |

### FIT Modules and RX Driver Package

The following table indicates name and version of [FIT modules](https://www.renesas.com/software-tool/fit) which are used in this reference and version of [RX Driver Package](https://www.renesas.com/software-tool/rx-driver-package) in which each FIT module is packaged.

#### FIT module List

| FIT module   | Revision of FIT module | Version of RX Driver Package |
|--------------|---------|------------|
|r_bsp         |7.54     | -          |
|r_s12ad_rx    |5.41     |1.47        |
|r_byteq       |2.11     |1.47        |
|r_cellular    |1.13     |1.47        |
|r_ether_rx    |1.24     |1.47        |
|r_flash_rx    |5.22     |1.47        |
|r_sci_rx      |5.41     |1.47        |
|r_tsip_rx     |1.22     |1.47        |
|r_irq_rx      |4.71     |1.47        |
|r_fwup        |2.04     |1.45 - 1.47 |
|r_wifi_da16xxx|1.40     |1.48        |

### Data Flash Usage

RX family of MCU has internal Data Flash Memory, and this references are using the Data Flash to store the data for connecting to the Cloud service.  

| Area | Description | Contents |Start address<br>[Size] | Section name |
|------|-------------|----------|--------------|--------------|
|LittleFS management area|It's consist of the filesystem LittleFS,<br>default size is 8960 bytes.<br>You can change size by `LFS_FLASH_BLOCK_COUNT`.|IoT const data<br><ul><li>thingname</li><li>endpoint</li><li>claim credentials</li><li>device credentials</li><li>provisioning template</li><li>codesigncert</li><li>root ca</li>|0x00100000<br><br>[8960 bytes<br>(*Default*)]|C_LITTLEFS_MANAGEMENT_AREA|
|Free area|It's not used by the demo.<br>Therefore, it's free area for user application.|User application data|0x00102300<br>(*Default*)<br><br>[23808 bytes<br>(*Default*)]|C_USER_APPLICATION_AREA|

* LittleFS management area
  * The demo project uses a maximum of 8960 bytes of Data Flash from address 0x00100000 to 0x001022FF using LittleFS.
    * If this area is less than 8960 bytes, the demo will not work properly.
  * You must **NOT** overwrite other data against IoT const data in this area.
  * If you intend to read/write user application data in this area, incrsease the value of `LFS_FLASH_BLOCK_COUNT` in the "Projects\\...\\frtos_config\\rm_littlefs_flash_config.h".
    * `LFS_FLASH_BLOCK_COUNT` must be specified 71 ( == 9088 bytes) or more and 256 (32768 bytes, it is Data Flash size) or less.
    * You must use LittleFS's API to read/write this area.
  * When increasing `LFS_FLASH_BLOCK_COUNT`, you must also reset the address of the section for free area(C_USER_APPLICATION_AREA) considering the increased LittleFS management area.  
    **Open the project by e2 studio of IDE** --> **Right-click on the project at the project explore** --> **properties** --> **C/C++ Build** --> **Settings** --> **Section**
    * If you do not set up a section, the demo may not work properly.
* Free area
  * The remaining area on Data Flash, 23808 bytes of Data Flash area at address 0x00102300 or above, can be used as user application area.
    * You must use FLASH FIT module's API to write this area.

#### Data Flash Memory Map

The following figure indicates how memory in Data Flash in CK-RX65N v2 is used for each example of `LFS_FLASH_BLOCK_COUNT` value.

```text
In case of `LFS_FLASH_BLOCK_COUNT` == 70 (8960 bytes)
 +----------------------------+-------------------------+ <- 0x00100000
 |  LittleFS management area  |  IoT const data         |    <8960 bytes>
 +----------------------------+-------------------------+ <- 0x00102300
 |  Free area                 |  User application data  |    <23808 bytes>
 |                            |                         |
 +----------------------------+-------------------------+ <- 0x00107FFF

In case of `LFS_FLASH_BLOCK_COUNT` == 170 (21760 bytes)
 +----------------------------+-------------------------+ <- 0x00100000
 |  LittleFS management area  |  IoT const data         |    <21760 bytes>
 |                            |  User application data  |
 +----------------------------+-------------------------+ <- 0x00105500
 |  Free area                 |  User application data  |    <11008 bytes>
 +----------------------------+-------------------------+ <- 0x00107FFF
```

### SubModule Patches

The following submodules have been modified by Renesas.  
These changes will be saved in the `\Common\patches` folder and will be incorporated into the project until they are merged into the FreeRTOS LTS.

* FreeRTOS-Plus-TCP  
  * It will be stored in the following folder.  
    `\Common\patches\FreeRTOS-Plus-TCP`
  * The FreeRTOS-Plus-TCP submodule code NetworkInterface.c was missing `pxFillInterfaceDescriptor`.  
    As a temporary workaround, the missing `pxFillInterfaceDescriptor` function was added.
* Jobs-for-AWS-IoT-embedded-sdk
  * It will be stored in the following folder.  
    `\Common\patches\Jobs-for-AWS-IoT-embedded-sdk`
  * The AWS IoT Jobs  packaged in LTS_v202406.01 lacks "custom version string" support.  
    So as a temporary workaround, we have modified the Jobs_UpdateMsg API to allow the custom version to be used.  
* aws-iot-core-mqtt-file-streams-embedded-c
  * It will be stored in the following folder.  
    `\Common\patches\aws-iot-core-mqtt-file-streams-embedded-c`
  * This fixes a build error that occurs when building the following AWS IoT MQTT File Streams source code with GCC v14.2.0.202505 or later.  
    `MQTTFileDownloader_cbor.c`

### Configuration values changed from the default in the FIT Modules

* The configuration values of the FIT modules that have been changed from the default values are listed in the table below.
* However, each projects is evaluated only with preset values, including configuration values that have not been changed from the default values.
* If changed, the program may not work properly.

<details>
<summary>CK-RX65N v2 Ethernet Projects</summary>

  | FIT module | Config name | Default Value | Project value | Reason for change |
  |------------|-------------|---------------|---------------|-------------------|
  | r_bsp      | BSP_CFG_HEAP_BYTES | 0x400 | 0x2000 | Because LittleFS and fleet provisioning demo uses malloc which is not an OS feature.<br>Also, because the default value cannot secure enough heap memory. |
  |            | BSP_CFG_CODE_FLASH_BANK_MODE | 1 | 0 | This project uses the Dual bank function. |
  |            | BSP_CFG_RTOS_USED | 0 | 1 | This project uses FreeRTOS. |
  |            | BSP_CFG_SCI_UART_TERMINAL_ENABLE | 0 | 1 | This project uses SCI UART terminals. |
  |            | BSP_CFG_SCI_UART_TERMINAL_CHANNEL | 8 | 5 | This project uses SCI CH5 as the SCI UART terminal. |
  |            | BSP_CFG_EXPANSION_RAM_ENABLE | 1 | 1\* | *This macro is set to "1" by default.<BR>It is included in this table as a note, we used EXRAM area in GCC project to avoid overflow of RAM area. |
  | r_ether_rx | ETHER_CFG_MODE_SEL | 0 | 1 | This value depends on the CK-RX65N v2 PHY-LSI and circuit specifications. |
  |            | ETHER_CFG_CH0_PHY_ADDRESS | 0 | 5 | This value depends on the CK-RX65N v2 PHY-LSI and circuit specifications. |
  |            | ETHER_CFG_EMAC_RX_DESCRIPTORS | 1 | 6 | Settings to prevent descriptor exhaustion when sending and receiving Ethernet frames. |
  |            | ETHER_CFG_EMAC_TX_DESCRIPTORS | 1 | 3 | Settings to prevent descriptor exhaustion when sending and receiving Ethernet frames |
  |            | ETHER_CFG_CH0_PHY_ACCESS | 1 | 0 | This value depends on the CK-RX65N v2 PHY-LSI and circuit specifications. |
  |            | ETHER_CFG_LINK_PRESENT | 0 | 1 | This value depends on the CK-RX65N v2 PHY-LSI and circuit specifications. |
  |            | ETHER_CFG_USE_PHY_ICS1894_32 | 0 | 1 | This value depends on the CK-RX65N v2 PHY-LSI and circuit specifications. |
  | r_flash_rx | FLASH_CFG_CODE_FLASH_ENABLE | 0 | 1 | OTA library rewrites code flash. |
  |            | FLASH_CFG_DATA_FLASH_BGO | 0 | 1 | LittleFS is implemented to rewrite data flash using BGO functionality. |
  |            | FLASH_CFG_CODE_FLASH_BGO | 0 | 1 | OTA library is implemented to rewrite code flash using BGO functionality. |
  |            | FLASH_CFG_CODE_FLASH_RUN_FROM_ROM | 0 | 1 | OTA library is implemented to execute code that rewrites the code flash from another bank. |
  | r_sci_rx   | SCI_CFG_CH1_INCLUDED | 1 | 0 | Because CH1 is not used. |
  |            | SCI_CFG_CH5_INCLUDED | 0 | 1 | SCI CH5 is used as the SCI UART terminal. |
  |            | SCI_CFG_TEI_INCLUDED | 0 | 1 | Transmit end interrupt is used. |
  | r_s12ad_rx | *No change*          |   |   |   |
  | r_tsip_rx  | *No change*          |   |   |   |
  | r_byteq    | *No change*          |   |   |   |
  | r_fwup     | FWUP_CFG_UPDATE_MODE | 1 | 0 | This project uses Dual bank function. |
  |            | FWUP_CFG_FUNCTION_MODE | 0 | 1 | This project is user program. |
  |            | FWUP_CFG_MAIN_AREA_ADDR_L | 0xFFE00000U | 0xFFF00000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_BUF_AREA_ADDR_L | 0xFFEF8000U | 0xFFE00000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_AREA_SIZE | 0xF8000U | 0xF0000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_USER_SHA256_INIT_ENABLED | 0 | 1 | Because custom function for SHA256 context initialization is used |
  |            | FWUP_CFG_USER_SHA256_INIT_FUNCTION | my_sha256_init_function | ota_sha256_init_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_SHA256_UPDATE_ENABLED | 0 | 1 | Because custom function for SHA256 context update is used |
  |            | FWUP_CFG_USER_SHA256_UPDATE_FUNCTION | my_sha256_update_function | ota_sha256_update_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_SHA256_FINAL_ENABLED | 0 | 1 | Because custom function for SHA256 context finalization is used |
  |            | FWUP_CFG_USER_SHA256_FINAL_FUNCTION | my_sha256_final_function | ota_sha256_final_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_VERIFY_ECDSA_ENABLED | 0 | 1 | Because custom function for ECC key verification is used |
  |            | FWUP_CFG_USER_VERIFY_ECDSA_FUNCTION | my_verify_ecdsa_function | ota_verify_ecdsa_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_GET_CRYPT_CONTEXT_ENABLED | 0 | 1 | Because custom function for cryptography encryption (iot-crypto) is used |
  |            | FWUP_CFG_USER_GET_CRYPT_CONTEXT_FUNCTION | my_get_crypt_context_function | ota_get_crypt_context_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_OPEN_ENABLED | 0 | 1 | Because custom FWUP flash wrapper  open function is used |
  |            | FWUP_CFG_USER_FLASH_ERASE_FUNCTION | my_flash_open_function | ota_flash_open_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_CLOSE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper close  function is used |
  |            | FWUP_CFG_USER_FLASH_CLOSE_FUNCTION | my_flash_close_function | ota_flash_close_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_ERASE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper erase function is used |
  |            | FWUP_CFG_USER_FLASH_ERASE_FUNCTION | my_flash_erase_function | ota_flash_erase_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_WRITE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper write function is used |
  |            | FWUP_CFG_USER_FLASH_WRITE_FUNCTION | my_flash_write_function | ota_flash_write_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_READ_ENABLED | 0 | 1 | Because custom FWUP flash wrapper read function is used |
  |            | FWUP_CFG_USER_FLASH_READ_FUNCTION | my_flash_read_function | ota_flash_read_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_BANK_SWAP_ENABLED | 0 | 1 | Because custom FWUP flash wrapper bank swap function is used |
  |            | FWUP_CFG_USER_BANK_SWAP_FUNCTION | my_bank_swap_function | ota_bank_swap_function | Define custom wrapper function name for OTA use case |

</details>

<details>
<summary>CK-RX65N v2 Cellular(RYZ014A) Projects</summary>

  | FIT module | Config name | Default Value | Project value | Reason for change |
  |------------|-------------|---------------|---------------|-------------------|
  | r_bsp      | BSP_CFG_HEAP_BYTES | 0x400 | 0x2000 | Because LittleFS and fleet provisioning demo uses malloc which is not an OS feature.<br>Also, because the default value cannot secure enough heap memory. |
  |            | BSP_CFG_CODE_FLASH_BANK_MODE | 1 | 0 | This project uses the Dual bank function. |
  |            | BSP_CFG_RTOS_USED | 0 | 1 | This project uses FreeRTOS. |
  |            | BSP_CFG_SCI_UART_TERMINAL_ENABLE	| 0 | 1 | This project uses SCI UART terminals. |
  |            | BSP_CFG_SCI_UART_TERMINAL_CHANNEL | 8 | 5 | This project uses SCI CH5 as the SCI UART terminal. |
  |            | BSP_CFG_EXPANSION_RAM_ENABLE | 1 | 1\* | *This macro is set to "1" by default.<BR>It is included in this table as a note, we used EXRAM area in GCC project to avoid overflow of RAM area. |
  |  r_cellular | CELLULAR_CFG_DEBUGLOG | 0 | 4 | Enable debug logging to facilitate problem resolution. |
  | r_flash_rx | FLASH_CFG_CODE_FLASH_ENABLE | 0 | 1 | OTA library rewrites code flash. |
  |            | FLASH_CFG_DATA_FLASH_BGO | 0 | 1 | LittleFS is implemented to rewrite data flash using BGO functionality. |
  |            | FLASH_CFG_CODE_FLASH_BGO | 0 | 1 | OTA library is implemented to rewrite code flash using BGO functionality. |
  |            | FLASH_CFG_CODE_FLASH_RUN_FROM_ROM | 0 | 1 | OTA library is implemented to execute code that rewrites the code flash from another bank. |
  | r_sci_rx   | SCI_CFG_CH1_INCLUDED | 1 | 0 | Because CH1 is not used. |
  |            | SCI_CFG_CH5_INCLUDED | 0 | 1 | SCI CH5 is used as the SCI UART terminal. |
  |            | SCI_CFG_CH6_INCLUDED | 0 | 1 | SCI CH6 is used to communicate with the RYZ014A module. |
  |            | SCI_CFG_CH6_TX_BUFSIZ | 80 | 2180 | The TX buffer size needs to be increased to communicate with RYZ014A. |
  |            | SCI_CFG_CH6_RX_BUFSIZ | 80 | 8192 | The RX buffer size needs to be increased to communicate with RYZ014A. |
  |            | SCI_CFG_TEI_INCLUDED | 0 | 1 | Transmit end interrupt is used. |
  |            | SCI_CFG_CH6_EN_TXI_NESTED_INT<BR>SCI_CFG_CH6_EN_RXI_NESTED_INT<BR>SCI_CFG_CH6_EN_TEI_NESTED_INT<BR>SCI_CFG_CH6_EN_ERI_NESTED_INT | 0\* | 1\* | (*In test project only*)<BR>Because RYZ014A module requires flow control in case data  is transmit/received too fast.<BR>Enable this macro as workaround for testing. |
  | r_fwup     | FWUP_CFG_UPDATE_MODE | 1 | 0 | This project uses Dual bank function. |
  |            | FWUP_CFG_FUNCTION_MODE | 0 | 1 | This project is user program. |
  |            | FWUP_CFG_MAIN_AREA_ADDR_L | 0xFFE00000U | 0xFFF00000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_BUF_AREA_ADDR_L | 0xFFEF8000U | 0xFFE00000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_AREA_SIZE | 0xF8000U | 0xF0000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_USER_SHA256_INIT_ENABLED | 0 | 1 | Because custom function for SHA256 context initialization is used |
  |            | FWUP_CFG_USER_SHA256_INIT_FUNCTION | my_sha256_init_function | ota_sha256_init_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_SHA256_UPDATE_ENABLED | 0 | 1 | Because custom function for SHA256 context update is used |
  |            | FWUP_CFG_USER_SHA256_UPDATE_FUNCTION | my_sha256_update_function | ota_sha256_update_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_SHA256_FINAL_ENABLED | 0 | 1 | Because custom function for SHA256 context finalization is used |
  |            | FWUP_CFG_USER_SHA256_FINAL_FUNCTION | my_sha256_final_function | ota_sha256_final_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_VERIFY_ECDSA_ENABLED | 0 | 1 | Because custom function for ECC key verification is used |
  |            | FWUP_CFG_USER_VERIFY_ECDSA_FUNCTION | my_verify_ecdsa_function | ota_verify_ecdsa_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_GET_CRYPT_CONTEXT_ENABLED | 0 | 1 | Because custom function for cryptography encryption (iot-crypto) is used |
  |            | FWUP_CFG_USER_GET_CRYPT_CONTEXT_FUNCTION | my_get_crypt_context_function | ota_get_crypt_context_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_OPEN_ENABLED | 0 | 1 | Because custom FWUP flash wrapper  open function is used |
  |            | FWUP_CFG_USER_FLASH_ERASE_FUNCTION | my_flash_open_function | ota_flash_open_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_CLOSE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper close  function is used |
  |            | FWUP_CFG_USER_FLASH_CLOSE_FUNCTION | my_flash_close_function | ota_flash_close_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_ERASE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper erase function is used |
  |            | FWUP_CFG_USER_FLASH_ERASE_FUNCTION | my_flash_erase_function | ota_flash_erase_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_WRITE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper write function is used |
  |            | FWUP_CFG_USER_FLASH_WRITE_FUNCTION | my_flash_write_function | ota_flash_write_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_READ_ENABLED | 0 | 1 | Because custom FWUP flash wrapper read function is used |
  |            | FWUP_CFG_USER_FLASH_READ_FUNCTION | my_flash_read_function | ota_flash_read_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_BANK_SWAP_ENABLED | 0 | 1 | Because custom FWUP flash wrapper bank swap function is used |
  |            | FWUP_CFG_USER_BANK_SWAP_FUNCTION | my_bank_swap_function | ota_bank_swap_function | Define custom wrapper function name for OTA use case |

</details>

<details>
<summary>CK-RX65N v2 Wi-Fi(DA16600) Projects</summary>

  | FIT module | Config name | Default Value | Project value | Reason for change |
  |------------|-------------|---------------|---------------|-------------------|
  | r_bsp      | BSP_CFG_HEAP_BYTES | 0x400 | 0x2000 | Because LittleFS and fleet provisioning demo uses malloc which is not an OS feature.<br>Also, because the default value cannot secure enough heap memory. |
  |            | BSP_CFG_CODE_FLASH_BANK_MODE | 1 | 0 | This project uses the Dual bank function. |
  |            | BSP_CFG_RTOS_USED | 0 | 1 | This project uses FreeRTOS. |
  |            | BSP_CFG_SCI_UART_TERMINAL_ENABLE | 0 | 1 | This project uses SCI UART terminals. |
  |            | BSP_CFG_SCI_UART_TERMINAL_CHANNEL | 8 | 5 | This project uses SCI CH5 as the SCI UART terminal. |
  |            | BSP_CFG_EXPANSION_RAM_ENABLE | 1 | 1\* | *This macro is set to "1" by default.<BR>It is included in this table as a note, we used EXRAM area in GCC project to avoid overflow of RAM area. |
  | r_flash_rx | FLASH_CFG_CODE_FLASH_ENABLE | 0 | 1 | OTA library rewrites code flash. |
  |            | FLASH_CFG_DATA_FLASH_BGO | 0 | 1 | LittleFS is implemented to rewrite data flash using BGO functionality. |
  |            | FLASH_CFG_CODE_FLASH_BGO | 0 | 1 | OTA library is implemented to rewrite code flash using BGO functionality. |
  |            | FLASH_CFG_CODE_FLASH_RUN_FROM_ROM | 0 | 1 | OTA library is implemented to execute code that rewrites the code flash from another bank. |
  | r_wifi_da16xxx | WIFI_CFG_DA16600_SUPPORT | 0 | 1 | Enable support for DA16600 |
  |                | WIFI_CFG_AT_CMD_TX_BUFFER_SIZE | 512 | 1500 | Because the buffer size is insufficient with the default value. |
  |                | WIFI_CFG_AT_CMD_RX_BUFFER_SIZE | 3000| 2048<BR>(GCC only) | Because the buffer size is insufficient with the default value. |
  |                | WIFI_CFG_SNTP_ENABLE | 0 | 1 | Enable SNTP client service. |
  |                | WIFI_CFG_COUNTRY_CODE | "" | "VN" | Configure this value based on the location of the users.<BR> (Please refer to [Settings of Country code and GMT timezone](Getting_Started_Guide.md#settings-of-country-code-and-gmt-timezone-only-using-wi-fi) for settings) |
  |                | WIFI_CFG_USE_FREERTOS_LOGGING | 0 | 1 | Using FreeRTOS logging. |
  |                | WIFI_CFG_DEBUG_LOG | 3 | 4 | Print all debug log. |
  |                | WIFI_CFG_TCP_CREATABLE_SOCKETS| 1 | 4 | Because the socket number is insufficient with the default value. |
  |                | WIFI_CFG_TCP_SOCKET_RECEIVE_BUFFER_SIZE | 4096 | 8192 | Because the buffer size is insufficient with the default value. |
  | r_sci_rx   | SCI_CFG_CH1_INCLUDED | 1 | 0 | Because CH1 is not used. |
  |            | SCI_CFG_CH5_INCLUDED | 0 | 1 | SCI CH5 is used as the SCI UART terminal. |
  |            | SCI_CFG_CH6_INCLUDED | 0 | 1 | SCI CH6 is used to communicate with the DA16600 module. |
  |            | SCI_CFG_CH6_TX_BUFSIZ | 80 | 2180 | The TX buffer size needs to be increased to communicate with DA16600. |
  |            | SCI_CFG_CH6_RX_BUFSIZ | 80 | 8192 | The RX buffer size needs to be increased to communicate with DA16600. |
  |            | SCI_CFG_TEI_INCLUDED | 0 | 1 | Transmit end interrupt is used. |
  | r_fwup     | FWUP_CFG_UPDATE_MODE | 1 | 0 | This project uses Dual bank function. |
  |            | FWUP_CFG_FUNCTION_MODE | 0 | 1 | This project is user program. |
  |            | FWUP_CFG_MAIN_AREA_ADDR_L | 0xFFE00000U | 0xFFF00000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_BUF_AREA_ADDR_L | 0xFFEF8000U | 0xFFE00000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_AREA_SIZE | 0xF8000U | 0xF0000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_USER_SHA256_INIT_ENABLED | 0 | 1 | Because custom function for SHA256 context initialization is used |
  |            | FWUP_CFG_USER_SHA256_INIT_FUNCTION | my_sha256_init_function | ota_sha256_init_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_SHA256_UPDATE_ENABLED | 0 | 1 | Because custom function for SHA256 context update is used |
  |            | FWUP_CFG_USER_SHA256_UPDATE_FUNCTION | my_sha256_update_function | ota_sha256_update_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_SHA256_FINAL_ENABLED | 0 | 1 | Because custom function for SHA256 context finalization is used |
  |            | FWUP_CFG_USER_SHA256_FINAL_FUNCTION | my_sha256_final_function | ota_sha256_final_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_VERIFY_ECDSA_ENABLED | 0 | 1 | Because custom function for ECC key verification is used |
  |            | FWUP_CFG_USER_VERIFY_ECDSA_FUNCTION | my_verify_ecdsa_function | ota_verify_ecdsa_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_GET_CRYPT_CONTEXT_ENABLED | 0 | 1 | Because custom function for cryptography encryption (iot-crypto) is used |
  |            | FWUP_CFG_USER_GET_CRYPT_CONTEXT_FUNCTION | my_get_crypt_context_function | ota_get_crypt_context_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_OPEN_ENABLED | 0 | 1 | Because custom FWUP flash wrapper  open function is used |
  |            | FWUP_CFG_USER_FLASH_ERASE_FUNCTION | my_flash_open_function | ota_flash_open_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_CLOSE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper close  function is used |
  |            | FWUP_CFG_USER_FLASH_CLOSE_FUNCTION | my_flash_close_function | ota_flash_close_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_ERASE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper erase function is used |
  |            | FWUP_CFG_USER_FLASH_ERASE_FUNCTION | my_flash_erase_function | ota_flash_erase_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_WRITE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper write function is used |
  |            | FWUP_CFG_USER_FLASH_WRITE_FUNCTION | my_flash_write_function | ota_flash_write_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_FLASH_READ_ENABLED | 0 | 1 | Because custom FWUP flash wrapper read function is used |
  |            | FWUP_CFG_USER_FLASH_READ_FUNCTION | my_flash_read_function | ota_flash_read_function | Define custom wrapper function name for OTA use case |
  |            | FWUP_CFG_USER_BANK_SWAP_ENABLED | 0 | 1 | Because custom FWUP flash wrapper bank swap function is used |
  |            | FWUP_CFG_USER_BANK_SWAP_FUNCTION | my_bank_swap_function | ota_bank_swap_function | Define custom wrapper function name for OTA use case |

</details>

<details>
<summary>CK-RX65N v2 Bootloader Project</summary>

  | FIT module | Config name | Default Value | Project value | Reason for change |
  |------------|-------------|---------------|---------------|-------------------|
  | r_bsp      | BSP_CFG_USER_CHARPUT_ENABLED | 0 | 1 | Use with log output function. |
  |            | BSP_CFG_CODE_FLASH_BANK_MODE | 1 | 0 | This project uses the Dual bank function. |
  |            | BSP_CFG_SCI_UART_TERMINAL_ENABLE | 0 | 1 | This is to use SCI UART Terminal |
  |            | BSP_CFG_SCI_UART_TERMINAL_CHANNEL | 8 | 5 | This is to use SCI UART Terminal |
  |            | BSP_CFG_BOOTLOADER_PROJECT | 0 | 1 | This is to enable clock setting for Bootloader |
  | r_flash_rx | FLASH_CFG_CODE_FLASH_ENABLE | 0 | 1 | Bootloader rewrites the code flash. |
  |            | FLASH_CFG_CODE_FLASH_RUN_FROM_ROM | 0 | 1 | Bootloader is implemented to execute code that rewrites the code flash from another bank. |
  | r_sci_rx   | SCI_CFG_CH1_INCLUDED | 1 | 0 | Because CH1 is not used. |
  |            | SCI_CFG_CH5_INCLUDED | 0 | 1 | SCI CH5 is used to write firmware and output log information. |
  | r_fwup     | FWUP_CFG_UPDATE_MODE | 1 | 0 | This project uses the Dual bank function. |
  |            | FWUP_CFG_MAIN_AREA_ADDR_L | 0xFFE00000U | 0xFFF00000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_BUF_AREA_ADDR_L | 0xFFEF8000U | 0xFFE00000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_AREA_SIZE | 0xF8000U | 0xF0000U | This value is set according to the RX65N ROM 2MB product. |
  |            | FWUP_CFG_USER_FLASH_OPEN_ENABLED | 0 | 1 | Because custom FWUP flash wrapper open function is used |
  |            | FWUP_CFG_USER_FLASH_CLOSE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper close function is used |
  |            | FWUP_CFG_USER_FLASH_ERASE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper erase function is used |
  |            | FWUP_CFG_USER_FLASH_WRITE_ENABLED | 0 | 1 | Because custom FWUP flash wrapper write function is used |
  |            | FWUP_CFG_USER_FLASH_READ_ENABLED | 0 | 1 | Because custom FWUP flash wrapper read function is used |
  |            | FWUP_CFG_USER_BANK_SWAP_ENABLED | 0 | 1 | Because custom FWUP flash wrapper bank swap function is used |

* The macros defined in `boot_loader.h` are shown below.

| File Name     | Config name | Config value | Project value | Description |
| ------------- | ----------- | ------------ | ------------- | ----------- |
| boot_loader.h | BL_UPDATE_MODE | 0:Disable<BR>1:Enable | 0 |If only the bootloader is written to the device, pressing the switch will install the initial firmware.  |
|               | BL_INITIAL_IMAGE_INSTALL | 0:Disable<BR>1:Enable | 0 | If the execution plane is empty, initial FW is installed. |
|               | BL_ERASE_BUFFER_AREA_AFTER_VERIFIED | 0:Disable<BR>1:Enable | 0 | After the firmware update is completed, the old firmware written on the Buffer side is deleted after the verification of new firmware. |
|               | BL_UPDATE_DATA_FLASH | 0:Disable<BR>1:Enable | 0 | Update data flash area.|
|               | BL_ENABLE_ROOLBACK | 0:Disable<BR>1:Enable | 1 | Enable rollback to old image if signature verification fails. |

> note 1: If both `BL_UPDATE_MODE` and `BL_INITIAL_IMAGE_INSTALL` above are disabled (Disable), the definition `BL_UART_RTS` for UART flow control is disabled.
In this sample, both `BL_UPDATE_MODE` and `BL_INITIAL_IMAGE_INSTALL` are set to Disable, so the default `BL_UART_RTS` is disabled.  

> note 2: In this demo, `BL_ERASE_BUFFER_AREA_AFTER_VERIFIED` is set to 0 so that the buffer area will be erased on the user application side when OTA is executed.  
Also, `BL_ENABLE_ROOLBACK` is set to 1 so that the bootloader will revert to the old firmware if signature verification of the new firmware fails.

</details>

## Limitation

<details>
<summary>Click here to check Limitation</summary>

* CLI task cannot run after starting the demo to avoid the SCI conflict.  
* OTA demo will not work properly unless `mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST` is set to "1".  
  If `mqttFileDownloader_MAX_NUM_BLOCKS_REQUEST` is set to anything other than 1, a build error will occur.  
* The following macros are not supported by this source code.  
  If you build the macros below, a build error will occur.  
  `LFS_NO_MALLOC`  
  `LFS_THREADSAFE`  
* Limitations on the xGetMQTTAgentState() function  
  In the following case, the xGetMQTTAgentState() function for monitoring the communication status returns the state of established MQTT connection with AWS (`MQTT_AGENT_STATE_CONNECTED`) without detecting the disconnection:  
The hook function *1 is called by occurring an error of a TCP_Sockets API *2 (disconnection with AWS) inner the xGetMQTTAgentState(), then this hook restores the connection to established state.  
  *1 The hook function defined in USER_TCP_HOOK_FUNCTION macro in src/frtos_config/user_tcp_hook_config.h  
  *2 TCP_Sockets API is a function defined in TCP_Sockets_xxxx
* Notes on redundant linker section after generating code with Smart Configurator.  
  After generating code with Smart Configurator, sections `C_FIRMWARE_UPDATE_CONTROL_BLOCK` and `C_FIRMWARE_UPDATE_CONTROL_BLOCK_MIRROR` will be created at address 0x00100000.  
  These sections are redundant, it does not impact memory usage of the project.  
  This behavior is according to the specification of r_tsip_rx FIT module (from version 1.17.l).  
* Notes on bootloader to application transition.  
  When transitioning from the bootloader sample program to the application, the settings of the bootloader's peripheral functions are taken over by the application.  
  For more information, check chapter 7 of the following document.  
  [RX Family Firmware Update module Using Firmware Integration Technology Application Notes.](https://www.renesas.com/document/apn/rx-family-firmware-update-module-using-firmware-integration-technology-application-notes)
* Limitations on transmission with multiple sockets
  If using multiple sockets and one of socket happens error, `Reset Hook` function is executed. In this case, all socket information is removed, while the remaining socket attempts to send or receive data. The communication in this socket will not work properly.
  Do not use multiple sockets with Reset Hook function.

* Socket wrapper/TCP_socket_hook works in single thread. Do not trigger `TCP_socket_hook` in multiple threads.  

* Limitations on using the LittleFS module  
  The LittleFS is not thread-safe.  
  Calling the LittleFS API from multiple tasks is prohibited.

* This connection protocol used in this demo requires SNI (Server Name Indication).  
  For this reason, if you set the following macro to pdTRUE (disable SNI) and build, a build error will occur.
  * democonfigDISABLE_SNI(demo_config.h)  

  If you want to disable SNI, set `democonfigDISABLE_SNI` to 1 in `demo_config.h` and comment out the following three lines.

  ```c
  #if ( democonfigDISABLE_SNI == 1 )
    #error "It is strongly recommended to implement SNI authentication, this requirement is enforced in mbedTLS library (mbedtls_ssl_handshake). Furthermore, SNI is required for connection to AWS IoT Core MQTT broker."
  #endif
  ```

* If you are using GCC as a compiler, please use `e2 studio 2025-04` or later.  
  If you are using a version earlier than e2 studio 2025-01, the optimization setting `-gc-sections` may be disabled when generating code.

* In `e2 studio 2025-07` or older, there is a known issue where the `FreeRTOSIPConfig.h` file will be removed when changing the package version of an import project.  
  Please manually recover the `FreeRTOSIPConfig.h` from the `/trash` folder in e2 studio Project Explorer.  
  Please make sure to click the "Generate Code" button again after the recovery, to ensure the latest settings are applied.  

* Fleet Provisioning may fail if a network disconnection occurs at specific points during the provisioning process.
  * This issue occurs under the following conditions:
    * Before receiving the certificate from AWS
    * Immediately after publishing
  * A temporary workaround has been implemented to allow recovery if the same condition occurs twice in succession.
  * This may be related to a bug currently under discussion in the [GitHub Issue#1206](https://github.com/FreeRTOS/FreeRTOS/issues/1206).  
    (However, it has not been verified whether applying this fix will fix the problem.)  

* Close Socket Function in the Cellular Project's Socket Wrapper  
The error‑handling logic in the `CloseSocket()` function is intentionally commented out when a socket‑close error occurs.  
File: `\Middleware\network_transport\sockets_wrapper\ports\cellular_ryz014a\TCP_socket_hook.c`  
Users may uncomment or extend this logic as needed for their specific use cases.
This behavior is intentional for the following reasons:
  * To prevent excessive resets of the RYZ014A module
  * To allow users to determine whether other sockets that are operating normally should be closed

* Default Value of the Root CA Certificate  
Projects prior to `v202406.01-LTS-rx-1.1.1` use the Starfield Cross‑signing CA as the default root CA certificate.  
However, Starfield's CA is no longer part of the AWS certificate chain.  
Therefore, update the project's default root CA to Amazon's root CA (`Amazon Root CA 1`) as shown below:  
File: `\src\frtos_config\demo_config.h`  

  ```c
  #define democonfigROOT_CA_PEM    (tlsATS1_ROOT_CERTIFICATE_PEM)
  ```

* Code Generation Issue in GCC Projects When Using e2 studio 2025-12  
If you are using e2 studio 2025-12, a build error may occur under the following conditions:  
Projects older than `v202406.01-LTS-rx-1.1.1` may encounter this issue.
  * When using a GCC project with code generation via the Smart Configurator  
  * When generating a GCC project using PG  

  **Required Fix**  
    The linker script file (`\src\linker_script.ld`) must be corrected at lines 140 and 141.  
    ![limitation1](https://github.com/renesas/iot-reference-rx/wiki/getting_started_guide_image/readme_lim_01.png?raw=true)  
  **After correction:**  

    ```c
    *MqttDemoExample.o(.bss.**)
    ```

</details>

## License

* Source code located in the *Projects*, *Common*, *Middleware/AWS*, and *Middleware/FreeRTOS* directories are available under the terms of the MIT License. See the LICENSE file for more details.
* Other libraries located in the *Middleware* directories are available under the terms specified in each source file.
* Each Renesas FIT Modules in RX driver package located in the *Projects/xxx/xxx/src/smc_gen* are available under the terms of the basically BSD3-Clause License. See the doc/license of following URL for more details.
[https://github.com/renesas/rx-driver-package](https://github.com/renesas/rx-driver-package)

## Support

Visit the following official webpage if having any technical questions.

* [English window](https://en-support.renesas.com/dashboard)
* [Japanese window](https://ja-support.renesas.com/dashboard)
* [Chinese window](https://zh-support.renesas.com/dashboard)
