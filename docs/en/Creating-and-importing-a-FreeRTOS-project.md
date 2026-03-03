# Introduction
This section shows how to use FreeRTOS projects in e² studio ported to the RX family.  
e² studio is the integrated development environment using Eclipse and please visit [here](https://www.renesas.com/jp/ja/software-tool/e-studio) to get the e² studio.  
The FreeRTOS projects can be created using e² studio's “Create New Project” function.  
You can also import the sample programs posted on the Renesas Website, or a cloned project from this repository.  

# How to develop a FreeRTOS project in e² studio
You can develop a FreeRTOS project using e² studio in the following ways.
When you want to start developing a FreeRTOS project from scratch, Renesas recommends to use [Create New Project Function](#create-a-new-freertos-project).  
For the latest information on using Free RTOS projects for RX, please refer to the [Getting Start Guide](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md).  
* [Create a new FreeRTOS project](#create-a-new-freertos-project) [Recommended]
	* Create a new project in e² studio 
* [Importing a FreeRTOS project](#importing-a-freertos-project)
	* Cloning projects from GitHub (hereafter Cloned project)
	* Unzipping sample program of APN zip file (hereafter sample project)

# Create a new FreeRTOS project
1.	Create an Executable project for CC-RX or GCC for Renesas RX.
2.	Select "FreeRTOS (with IoT libraries)" in the "RTOS" field to create a FreeRTOS project.<br>
    ![EN-1-STEP2-SelectRTOS](https://github.com/user-attachments/assets/70159247-2166-4c81-be83-9056902150e6)

    \*1: "FreeRTOS (with IoT libraries)(deprecated structure)" in the “RTOS” field is retained for compatibility. It is recommended to select "FreeRTOS (with IoT libraries)" for newly developed software.<br>
    \*2: If nothing is displayed in the "RTOS version" field, click "Manage RTOS versions" to download the newest version. <br>
    \*3: If a board that is not supported is selected in the "Target Board" field, the project cannot be created. If there is no "CK-RX65N-V2" in the board selection, click "Download additional boards..." to download the board description file.<br>
    ![EN-2-STEP2-Note3-TargetBoard](https://github.com/user-attachments/assets/d5a41329-83a7-43fb-8b00-16d3dcfd48b4)<br>

3.	Transition to the sample project selection dialog (in 202406-LTS-rx-1.0.1 below).<br>
    For details on the sample projects, refer to the following documents:
    - (Ethernet) Minimal sample project:
    Performs TCP/IP communication using FreeRTOS Kernel and FreeRTOS-Plus-TCP.<br>
    For use with RX Family MCUs other than RX65N, please refer to the [Porting Guide](FreeRTOS-Plus-TCP-Porting-Guide.md).<br>
    - (Ethernet) PubSub/MQTT sample project:
    Send PubSub message to the AWS IoT Core.<br>
    ![EN-3-STEP3-SlectMinimalSampleProject](https://github.com/user-attachments/assets/859b754e-2bab-41cd-850b-851bd8498704)

# Importing a FreeRTOS project
The following sections show you how to import the downloaded FreeRTOS project into e² studio.  
* The instructions in this section are mainly intended for importing such as sample programs in application note, and projects cloned from GitHub.
* The folder names and structures may differ depending on the project where you downloaded.
* Please replace environment specific words such as board name in the figures and description to match your environment.

# Base Folder Definition
* The root folder of Amazon FreeRTOS that was downloaded, unzipped, or cloned from GitHub with git is denoted as ${base_folder}.
* ${base_folder} contains demos and tests folders
* **Please put on the project in a place where the path can be shortened such as "c:\ ".**  
Note that total path length over 256 characters caused e² studio to output an error at Build.
* The figure below shows amazon-freertos cloned from GitHub and placed in c:\ws2. 
In this case, ${base_folder} becomes “C:\ws2\amazon-freertos” 

![00_folderpass](https://github.com/renesas/iot-reference-rx/assets/121073232/7bb386d2-88d6-4be8-91ca-fe7623f82f4f)

# Launch the e² studio and import the project
* Double-click the e² studio icon to launch
![02_FreeRTOSプロジェクトインポート_e2起動](https://user-images.githubusercontent.com/121073232/217969435-a934d9b9-d65a-4cd4-90af-9a3132ba6f55.png)

* Select workspace -> Launch  
When you have already selected the default folder, this window does not appear. 
![01_e2_launch](https://github.com/renesas/iot-reference-rx/assets/121073232/a2ba11fe-4e0a-4257-881a-6fa24ce6d255)

* Launch e² studio
![01_e2_launch](https://github.com/renesas/iot-reference-rx/assets/121073232/2fb802d3-266b-4e29-a3a7-fb3ecc276dca)

* Select the “import” menu from “File” tab.  
![03_e2_file_import](https://github.com/renesas/iot-reference-rx/assets/121073232/f70f8606-a82e-4677-b305-d4c9007c062b)

* Select “Existing Projects into Workspace” and press “next”.  
![04_e2_existingProject](https://github.com/renesas/iot-reference-rx/assets/121073232/485b580d-f7cb-4874-8e04-c8d971ff4fa9)

* Select the folder the project placed using "browse" button and press the “Select folder”.  
The folder depends on the compiler that you will use.

	* CC-RX
		* ${base_folder}/projects/renesas/Board name/e2studio/ 
	* GCC
		* ${base_folder}/projects/renesas/Board name/e2studio-gcc/
* This figure shows an example of using the following project  
Board　　　：CK-RX65N(with CAT.M1 module 'RYZ014A')  
Compiler　：GCC
![07_FreeRTOSプロジェクトインポート_フォルダーの選択](https://user-images.githubusercontent.com/121073232/217969551-8b44198f-92e0-43f8-9bd8-8e8f2067bfb1.png)

* Select the projects to import and press “Finish”
Project description:  

| Functions | Projects |
| ------ | ------ |
| For connection to AWS Cloud Services only | Select aws_demos |
| For OTA FW Update | Select aws_demos and boot_loader |

* This figure shows the case of selecting OTA function.  
![05_e2_select_projects](https://github.com/renesas/iot-reference-rx/assets/121073232/173b8f3b-fddd-4c6d-98e5-0d2810226c26)  
Note: Don’t select "Copy Projects into workspace" in both cases. 

* When close the "Welcome to e² studio" screen using the “Hide” button, the Project Explorer will appear.
![02_e2_welcome](https://github.com/renesas/iot-reference-rx/assets/121073232/186b4f2b-68c2-4245-bd4c-b69da7fddaee)<br>
 ↓↓↓<br><br>
![e2studio](https://github.com/renesas/iot-reference-rx/assets/121073232/3f0fb0ad-3cec-465d-8dfa-92e1906dc44e)

* Select “clean” from “Project” tab.
	* When you imported two projects, select "Clean all projects" check button.
	* Select “Start a build immediately” and “Build the entire workspace”, and press “Clean”.

![07_project_clean](https://github.com/renesas/iot-reference-rx/assets/121073232/41b4c443-ba25-42fb-88b3-7d7366c5b26f)

![08_Clean_allproject](https://github.com/renesas/iot-reference-rx/assets/121073232/65f5752c-010c-4bc3-83d4-2f9dde78d841)

* Check the build is finished successfully completed without any build errors.
![09_buildresult](https://github.com/renesas/iot-reference-rx/assets/121073232/f481fa5f-496c-46fa-8267-5bd8ac3ab615)

# Connecting to AWS
It is necessary to register “things” name to AWS IoT Core and register certificates and keys to the FreeRTOS program.  
Please configure settings according to the sample program/APN you are using before connecting to AWS.  

  
* When  you use a sample program/APN, please refer to the documentation of the sample program/APN how to proceed.
* Please check GettingStartGude for each board when you use AWS Partner Device certified sample programs.
* GettingStartGude and APN documents contain the screenshot and settings.
If the information or screenshot is different from your environment, please check the 
[Register device to AWS IoT](Register-device-to-AWS-IoT.md) page.