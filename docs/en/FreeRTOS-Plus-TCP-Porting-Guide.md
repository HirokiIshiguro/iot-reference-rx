# What is FreeRTOS-Plus-TCP minimal sample project?
Provides basic TCP/IP functionality using FreeRTOS Kernel and FreeRTOS-Plus-TCP
  - Acquisition of IP address by DHCP
  - IP address search of URLs by DNS
  - Send ping to the specified IP Address

For the latest support information, please refer to [README](https://github.com/renesas/iot-reference-rx?tab=readme-ov-file#list-of-demos-supported-by-each-release-tag).

# Guide to porting FreeRTOS-Plus-TCP minimal sample to other device
How to create FreeRTOS-Plus-TCP minimal sample project on the other MCUs other than RX65N

1.	Create **Minimal sample project** specifying CK-RX65N-V2 as **Target Board**.
2.	Double-click <project name>.scfg in **Project Explorer**, and then click **Board** tab.
3.	Change **Target Board** or **Target Device**.
    -	Please select the device with sufficient ROM/RAM size.
    -	The size of **Minimal sample project** is as follows.
        | ROM | RAM |
        |-----|------|
        | 58KB | 52KB |

        \* Compiler: CC-RX v3.07.00<br>
        \* Note: Optimization: -optimize=2, -size<br>
4.	Click **Next** -> **Finish**
5.	Confirm that the board or device are changed as you specified in previous step and click **Generate Code** button.
6.	Change the following settings as needed.
    -	FreeRTOS kernel portable layer (port)：The default port is RX600v2.
    Please download the suitable port from [FreeRTOS-Kernel GitHub](https://github.com/FreeRTOS/FreeRTOS-Kernel/tree/main/portable/Renesas) and add it to the project.<br>
    \* If you are porting to RXv3 core device, you cannot currently use the RX700v3_DPFPU port.
    Please use the RX600v2 port instead. Please note that the RX600v2 port doesn’t support DPFPU instruction.
    -	Ethernet FIT：<project name>.scfg -> **Components** tab -> **r_ether_rx**
    -	Pin Settings：<project name>.scfg -> **Pins** tab -> **Ethernet controller**