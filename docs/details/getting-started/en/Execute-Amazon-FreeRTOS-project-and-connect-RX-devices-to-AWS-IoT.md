# Introduction
This section shows how to connect to AWS IoT Core and subscribe to topics in a FreeRTOS project for the RX family.  
The precondition of this section:  
The FreeRTOS project has been successfully built, including certification of things information registration with AWS.When you have not finished above preparation, please set up your environment referring the following link in advance.  
For the latest information on using Free RTOS projects for RX, please refer to the [Getting Start Guide](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md).  
  
1. [Register device to AWS IoT](Register-device-to-AWS-IoT.md)
1. [Creating and importing a FreeRTOS project](Creating-and-importing-a-FreeRTOS-project.md)  
 [Importing a FreeRTOS project(zip)](Creating-and-importing-a-FreeRTOS-project.md#importing-a-freertos-project)  
 [Create a new FreeRTOS project](Creating-and-importing-a-FreeRTOS-project.md#create-a-new-freertos-project) 
1. [Configure the FreeRTOS project to connect to AWS IoT Core](Configure-the-FreeRTOS-project-to-connect-to-AWS-IoT-Core.md) 
1. [Execute Amazon FreeRTOS project and connect RX devices to AWS IoT](Execute-Amazon-FreeRTOS-project-and-connect-RX-devices-to-AWS-IoT.md) [This page]

# Configure the IoT Core control panel to check the messages from devices

* Subscribe to Topics in the IoT Core Control Panel
	* [Move to the IoT Core control panel](Register-device-to-AWS-IoT.md#log-in-to-the-aws-management-console)
	* Test -> MQTT test client -> Subscribe to a topic  
-> Set "#" as a topic filter (wildcard) -> Subscribe

![01_test_mqtt](https://github.com/renesas/iot-reference-rx/assets/121073232/cc0b8793-989b-4403-9772-0bb3dbc44ae3)

The sample program for Renesas evaluation boards with AWS Partner Device certification outputs debug logs.  
The output UART channel depends on the evaluation board, 7please refer the getting started guide.   
See GettingStartGude on the evaluation board for details.
* Connect the evaluation board to the PC with a USB cable (see GettingStartGude for each board for the USB port to be connected)  
The output UART channel depends on the evaluation board, 7please refer the getting started guide.
* Launch terminal software like TeraTerm on the PC and set the serial port settings as follows

| Setting | Value |
| ------ | ------ |
| Speed | 115200bps |
| Data length | 8bit |
| Parity bit | none |
| Stop bits | 1bit |
| Flow control | none |

# Download FreeRTOS project to RX MCU
* Press the "bug" icon in the upper left corner of the e2 studio screen

![debug_button](https://github.com/renesas/iot-reference-rx/assets/121073232/31c9bfb6-50ea-4883-9930-122d1695489e)

* Select "Switch" in the "Confirm Perspective Switch" window.

![switch](https://github.com/renesas/iot-reference-rx/assets/121073232/73663545-c171-42d4-9324-77aed847ef7c)

# Execute program

* Press "Resume" button

![02_resume](https://github.com/renesas/iot-reference-rx/assets/121073232/6b64837f-9f1f-4c1c-b07d-105b55689905)

* Check the breakpoint is set in the main() routine.

![03_main](https://github.com/renesas/iot-reference-rx/assets/121073232/b8276f52-0887-4e50-ae29-fc6db4f859b9)


* Press "Resume" button

![02_resume](https://github.com/renesas/iot-reference-rx/assets/121073232/b52de873-5451-4b4a-9255-e537f1ca6203)

# Check messages from devices in the IoT Core control panel
* Check that the messages defined by source code in the FreeRTOS project are displayed.  
Note: Output messages are deferent from by the project.   
e.g., "Hello World" "Task X publishing message XX"  
![test_mqtt_subsc](https://github.com/renesas/iot-reference-rx/assets/121073232/0e241db3-8bc5-4386-a934-95c7acfa7d5b)


