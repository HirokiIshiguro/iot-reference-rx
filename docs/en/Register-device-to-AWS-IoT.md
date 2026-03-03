# Introduction.
This section shows how to register a new device from the AWS IoT Core console.  
For the latest information on using Free RTOS projects for RX, please refer to the [Getting Start Guide](https://github.com/renesas/iot-reference-rx/blob/main/Getting_Started_Guide.md).  

# Get an AWS account
* [Get an AWS account](https://aws.amazon.com/free/?nc1=h_ls&all-free-tier.sort-by=item.additionalFields.SortRank&all-free-tier.sort-order=asc&awsf.Free%20Tier%20Types=*all&awsf.Free%20Tier%20Categories=*all) -> Click on the "Create a Free Account" button.
	* You can use the “AWS free tier” for your initial investigation.
![00_AWS_Get_an_account](https://github.com/renesas/iot-reference-rx/assets/121073232/57a4dee3-b201-478b-8309-a58d850a0bf2)

# Log in to the AWS Management Console
* [Amazon Web Services](https://aws.amazon.com/?nc2=h_lg) -> Account -> AWS Management Console

![01_AWS_ManagementConsol](https://github.com/renesas/iot-reference-rx/assets/121073232/8be86077-3ff4-4ebb-b399-d58ba18d573b)

# Go to the IoT Core control panel
* Type `IoT Core` in the search box at the top of the browser
* Press the link of “IoT Core” in the “Services”

![02_AWS_SerchIoTCore](https://github.com/renesas/iot-reference-rx/assets/121073232/e9855387-071f-46ba-9a2a-169114f45cf9)

# Create a Security Policy

* Security -> Policies -> Create Policy

![03_AWS_Policies](https://github.com/renesas/iot-reference-rx/assets/121073232/06078ac8-9b3b-4878-9a24-fab7465d2453)

* Enter "policy name" as you like.

![07_AWS_policy_name](https://github.com/renesas/iot-reference-rx/assets/121073232/933c7f9c-a32a-47fa-aeff-bdd60a57dd66)

* Policy statements -> Policy document -> Builder -> Add new statement  
* Click 'Add new statement' button three times, then four statement are shown. 
![08_AWS_policy_addstatements](https://github.com/renesas/iot-reference-rx/assets/121073232/36249db1-e9bf-40aa-b6b7-61ef8cdf39d9)

* "Allow" the following policy actions and set the wildcard `*` in the policy resource   

	| Policy effect  　　　　　| significance  　　　　　　　　　　　　　　　　　　　　　|
	| ------ | ------ |
	| iot:Connect | Connect to AWS IoT |
	| iot:Publish | Publish topics |
	| iot:Subscribe | Subscribe to topics |
	| iot:Receive| Receive messages from AWS IoT|

* Create
![09_AWS_policy_setstatements](https://github.com/renesas/iot-reference-rx/assets/121073232/e6c81225-e477-40e0-8a90-4d399e3525bf)


* When the setup is completed successfully, the following banner will appear at the top of the browser screen.
![10_AWS_policy_success_careate_Policy](https://github.com/renesas/iot-reference-rx/assets/121073232/0d6aa703-690e-4bd3-8962-db661a0d9208)


# Register devices (things) with AWS IoT

* Manege -> All devices -> Things -> Create things
![11_AWS_things_createthings](https://github.com/renesas/iot-reference-rx/assets/121073232/30ca0fa2-9ea7-4a2b-8270-fa98674f065c)

* Create things -> Create single thing
![12_AWS_things_create_single_thing](https://github.com/renesas/iot-reference-rx/assets/121073232/08aff87e-0875-4cf4-bec6-ad9b7e3d9c25)

* Thing properties -> Enter any name in the 'Thing name' field. -> Next
* Memorize the name of the thing in a text editor, etc. (to be used later)
![13_AWS_things_set_thing_name](https://github.com/renesas/iot-reference-rx/assets/121073232/14cec15c-8a54-44a8-87e4-2b61ebae36a3)

* Configure device certificate - optional -> Auto-generate a new certificate (recommended) -> Next
![14_AWS_things_config_device_cert](https://github.com/renesas/iot-reference-rx/assets/121073232/a3203376-262f-46d4-a599-eb94937268a7)

* Attach policies to certificate - optional -> Policy to be used☑ ->Create thing
![15_AWS_things_select_Policy](https://github.com/renesas/iot-reference-rx/assets/121073232/f87f7312-747d-4ba4-8771-2fcd7f337fed)

* Download the following files and press Done.
	* Note : The key file can be downloaded from only this browser screen.  
Also, once you press the "Done" button, you never be able to download this file again.  
Please make sure that you have downloaded the file before pressing the “Done” button.
		* **Device certificate**
		* **Public key file**
		* **Private key file**  
![16_AWS_things_download_cert](https://github.com/renesas/iot-reference-rx/assets/121073232/c7984aaf-a5e8-409f-9086-f4a4e6368c92)

* The following banner will appear when the procedure is successfully completed. 
![17_AWS_things_success_create](https://github.com/renesas/iot-reference-rx/assets/121073232/eef9568f-bd1e-43a4-9e57-ae67c7ba2663)

# Check the AWS IoT endpoints

* You will use the endpoint name later, so please make a note this name to the text editor etc.
![18_AWS_endpoint](https://github.com/renesas/iot-reference-rx/assets/121073232/bfe2008a-dc5b-4347-9a76-671fbb9b3a74)

# Summary of this section
You registered the device on the AWS IoT in this section.  
The data you made a note in this section will be used in the following steps.  
Please check following text data and files are prepared in your hand, again.  
* Text data:
	* Things name
	* endpoint name
* Files:
	* Device certification file
	* Public key file
	* Private key file
# Next Steps
The data you have memorized in the editor in this section will be used in the following steps.  
Please refer to the following page or the documentation of the sample program you are using for the procedure of registering information to the project.  
1. [Register device to AWS IoT](Register-device-to-AWS-IoT.md) [This page]
1. [Creating and importing a FreeRTOS project](Creating-and-importing-a-FreeRTOS-project.md)  
 [Importing a FreeRTOS project(zip)](Creating-and-importing-a-FreeRTOS-project.md#importing-a-freertos-project)  
 [Create a new FreeRTOS project](Creating-and-importing-a-FreeRTOS-project.md#create-a-new-freertos-project) 
1. [Configure the FreeRTOS project to connect to AWS IoT Core](Configure-the-FreeRTOS-project-to-connect-to-AWS-IoT-Core.md) 
1. [Execute Amazon FreeRTOS project and connect RX devices to AWS IoT](Execute-Amazon-FreeRTOS-project-and-connect-RX-devices-to-AWS-IoT.md)
