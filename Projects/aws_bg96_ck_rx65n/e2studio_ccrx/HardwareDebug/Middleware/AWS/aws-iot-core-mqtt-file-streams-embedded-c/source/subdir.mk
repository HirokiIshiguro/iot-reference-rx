################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/MQTTFileDownloader.c \
../Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/MQTTFileDownloader_base64.c \
../Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/MQTTFileDownloader_cbor.c

COMPILER_OBJS += \
Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/MQTTFileDownloader.obj \
Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/MQTTFileDownloader_base64.obj \
Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/MQTTFileDownloader_cbor.obj

C_DEPS += \
Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/MQTTFileDownloader.d \
Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/MQTTFileDownloader_base64.d \
Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/MQTTFileDownloader_cbor.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/%.obj: ../Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/%.c Middleware/AWS/aws-iot-core-mqtt-file-streams-embedded-c/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\AWS\aws-iot-core-mqtt-file-streams-embedded-c\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\AWS\aws-iot-core-mqtt-file-streams-embedded-c\source\cSubCommand.tmp" "$<"
