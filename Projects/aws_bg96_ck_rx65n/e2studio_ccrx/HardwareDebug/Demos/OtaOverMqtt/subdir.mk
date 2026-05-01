################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/OtaOverMqtt/OtaOverMqttDemo.c

COMPILER_OBJS += \
Demos/OtaOverMqtt/OtaOverMqttDemo.obj

C_DEPS += \
Demos/OtaOverMqtt/OtaOverMqttDemo.d

# Each subdirectory must supply rules for building sources it contributes
Demos/OtaOverMqtt/%.obj: ../Demos/OtaOverMqtt/%.c Demos/OtaOverMqtt/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\OtaOverMqtt\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\OtaOverMqtt\cSubCommand.tmp" "$<"
