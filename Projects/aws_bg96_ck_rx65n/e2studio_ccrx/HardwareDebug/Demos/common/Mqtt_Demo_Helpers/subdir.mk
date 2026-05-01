################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/common/Mqtt_Demo_Helpers/mqtt_pkcs11_demo_helpers.c

COMPILER_OBJS += \
Demos/common/Mqtt_Demo_Helpers/mqtt_pkcs11_demo_helpers.obj

C_DEPS += \
Demos/common/Mqtt_Demo_Helpers/mqtt_pkcs11_demo_helpers.d

# Each subdirectory must supply rules for building sources it contributes
Demos/common/Mqtt_Demo_Helpers/%.obj: ../Demos/common/Mqtt_Demo_Helpers/%.c Demos/common/Mqtt_Demo_Helpers/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\common\Mqtt_Demo_Helpers\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\common\Mqtt_Demo_Helpers\cSubCommand.tmp" "$<"
