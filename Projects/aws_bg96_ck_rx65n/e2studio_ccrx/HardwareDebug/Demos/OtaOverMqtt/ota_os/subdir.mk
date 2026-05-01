################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/OtaOverMqtt/ota_os/ota_os_freertos.c

COMPILER_OBJS += \
Demos/OtaOverMqtt/ota_os/ota_os_freertos.obj

C_DEPS += \
Demos/OtaOverMqtt/ota_os/ota_os_freertos.d

# Each subdirectory must supply rules for building sources it contributes
Demos/OtaOverMqtt/ota_os/%.obj: ../Demos/OtaOverMqtt/ota_os/%.c Demos/OtaOverMqtt/ota_os/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\OtaOverMqtt\ota_os\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\OtaOverMqtt\ota_os\cSubCommand.tmp" "$<"
