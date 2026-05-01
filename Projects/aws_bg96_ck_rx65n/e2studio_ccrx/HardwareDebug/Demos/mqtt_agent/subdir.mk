################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/mqtt_agent/mqtt_agent_task.c

COMPILER_OBJS += \
Demos/mqtt_agent/mqtt_agent_task.obj

C_DEPS += \
Demos/mqtt_agent/mqtt_agent_task.d

# Each subdirectory must supply rules for building sources it contributes
Demos/mqtt_agent/%.obj: ../Demos/mqtt_agent/%.c Demos/mqtt_agent/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\mqtt_agent\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\mqtt_agent\cSubCommand.tmp" "$<"
