# Specification difference between CK-RX65N v1 board and v2 board

|#|Item|Change type|Content|V1 baseboard<br>[P/N:RTK5CK65N0S04000BE]<br>Cellular Cloud Kit<br>(RYZ014A Pmod)|V2 baseboard<br>[P/N:RTK5CK65N0S08001BE]<br>Wi-Fi Cloud Kit<br>(US159-DA16600EVZ Pmod)|
|----|----|----|----|----|----|
|1|PMOD I/F|Changed|IRQ of PMOD|Connect as IRQ|Connect as IRQ-DS (it can be used for Wake-up)
|2|PMOD I/F|Changed|Change default setting on PMOD to full flow control.<br>1. UART with full flow control.<br>2. I2C.<br>3. SPI.|Default: SPI/Control by either CTS or RTS for UART|Default: UART with full flow control|
|3|PMOD I/F|Added|UART full flow control (CTS & RTS) on Pmods|Not supported <br>(either CTS or RTS)|Supported <br>(it can ed changed by a jumper)|
|4|IIC I/F|Changed|Sensor Connection to RX65N|Sensors connect to 1 channel of IIC.<br>All sensors are conneted to channel 0.|Sensors connect to 3 channels of IIC.<br>Channel 0: HS3001, ICM-42605, and ICP-20100<br>Channel 1: ZMOD4510, and ZMOD4410<br>Channel 12: OB1203|
|5|IIC I/F|Added|IIC test pad (for waveform confirmation)|N/A|Supported|
|6|USB Serial Converter IC|Changed|USB to Serial conversion|RL78/G1C|FTDI (Improved throughput due to dropouts)|
|7|Sensor IC|Changed|Motion Tracking sensor|TDK 9-axis sensor (EOL) |6-axis sensor|
|8|Sensor IC|Changed|Barometric pressure sensor |ICP-10101|ICP-20100  w/o level shifter|
|9|ADC|Added|Fix short on both motion and pressure sensor on AD0 pin.<br>Connecting pin to GND gives the desired address. |N/A|Put a resister to DNF to allow users to fit to enable if needed.|
|10|USB|Changed|USB connecor type for USB Serial Converter|USB micro B|USB C|
|11|Ether|Added|Added resistors and capacitors on Ethernet pins (TP_AP, TP_AN, TP_BP, TP_BN)|N/A|Four 9.9ohm resistors and two 100nF caps to Ethernet connection|
|12|Ether|Changed|RX65N GPIO port# to connect the P0/LED0 pin(for Link Status) of EtherPHY|P54 port of RX65N|PA5 port of RX65N|
|13|Sub Clock capacitor|Changed|Changed capacitor for X2(Sub Clock)|27pF|15pF|
|14|Power Supply|Added|Power Supply from VBUS of the USB Serial Converter IC|It does NOT connect the VBUS power supply from USB/SCI to the MCU line|Connect the VBUS power line from the USB Serial Converter IC|
|15|Others|Changed|LED2, S2, ISL8002|Power-good output of ISL8002 is not supported|Power-good output of ISL8002 is supported. Change pin assignment|

# Details
![CK-RX65N_02](https://github.com/renesas/iot-reference-rx/assets/121073232/05600385-8251-4859-a033-3ea0dc0b0c0b)
![CK-RX65N_03](https://github.com/renesas/iot-reference-rx/assets/121073232/94350524-1a2c-4bbb-b183-6f9c965a57cd)
![CK-RX65N_04](https://github.com/renesas/iot-reference-rx/assets/121073232/445bfbe2-3a39-4b29-85a0-dc9a8fabcba5)
![CK-RX65N_05](https://github.com/renesas/iot-reference-rx/assets/121073232/d51f243a-0196-4145-8740-b723a81911c5)
![CK-RX65N_06](https://github.com/renesas/iot-reference-rx/assets/121073232/6fd0ee66-e41e-41dc-b084-23f6de925adc)
![CK-RX65N_07](https://github.com/renesas/iot-reference-rx/assets/121073232/7d0061d4-67cd-4ef0-a5d5-ce0672599891)
![CK-RX65N_08](https://github.com/renesas/iot-reference-rx/assets/121073232/a900f80e-a323-4828-b261-5b17e1c34f4a)
![CK-RX65N_09](https://github.com/renesas/iot-reference-rx/assets/121073232/b44091c2-22b3-4a63-bdcc-24d0913b0a22)
![CK-RX65N_10](https://github.com/renesas/iot-reference-rx/assets/121073232/0ff4b039-2005-42bf-a2cb-114d9d01f180)
![CK-RX65N_11](https://github.com/renesas/iot-reference-rx/assets/121073232/bfc9a47d-a683-4a59-a1ee-8267099845f8)
![CK-RX65N_12](https://github.com/renesas/iot-reference-rx/assets/121073232/2988d18d-6a32-4714-8e9a-72debe6e0381)
![CK-RX65N_13](https://github.com/renesas/iot-reference-rx/assets/121073232/74465956-c2b5-4ba9-95f0-da5f731a67c3)
![CK-RX65N_14](https://github.com/renesas/iot-reference-rx/assets/121073232/f1993762-261c-4992-9749-3d9e1a0f0b7b)
![CK-RX65N_15](https://github.com/renesas/iot-reference-rx/assets/121073232/f5da1841-5ced-496d-ac59-1a591d44e0e4)
