################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/common/mqtt-agent-interface/freertos_agent_message.c \
../Demos/common/mqtt-agent-interface/freertos_command_pool.c

COMPILER_OBJS += \
Demos/common/mqtt-agent-interface/freertos_agent_message.obj \
Demos/common/mqtt-agent-interface/freertos_command_pool.obj

C_DEPS += \
Demos/common/mqtt-agent-interface/freertos_agent_message.d \
Demos/common/mqtt-agent-interface/freertos_command_pool.d

# Each subdirectory must supply rules for building sources it contributes
Demos/common/mqtt-agent-interface/%.obj: ../Demos/common/mqtt-agent-interface/%.c Demos/common/mqtt-agent-interface/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\common\mqtt-agent-interface\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\common\mqtt-agent-interface\cSubCommand.tmp" "$<"
