################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/common/mqtt-wrapper/mqtt_wrapper.c

COMPILER_OBJS += \
Demos/common/mqtt-wrapper/mqtt_wrapper.obj

C_DEPS += \
Demos/common/mqtt-wrapper/mqtt_wrapper.d

# Each subdirectory must supply rules for building sources it contributes
Demos/common/mqtt-wrapper/%.obj: ../Demos/common/mqtt-wrapper/%.c Demos/common/mqtt-wrapper/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\common\mqtt-wrapper\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\common\mqtt-wrapper\cSubCommand.tmp" "$<"
