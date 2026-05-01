################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/coreMQTT-Agent/source/core_mqtt_agent.c \
../Middleware/FreeRTOS/coreMQTT-Agent/source/core_mqtt_agent_command_functions.c

COMPILER_OBJS += \
Middleware/FreeRTOS/coreMQTT-Agent/source/core_mqtt_agent.obj \
Middleware/FreeRTOS/coreMQTT-Agent/source/core_mqtt_agent_command_functions.obj

C_DEPS += \
Middleware/FreeRTOS/coreMQTT-Agent/source/core_mqtt_agent.d \
Middleware/FreeRTOS/coreMQTT-Agent/source/core_mqtt_agent_command_functions.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/coreMQTT-Agent/source/%.obj: ../Middleware/FreeRTOS/coreMQTT-Agent/source/%.c Middleware/FreeRTOS/coreMQTT-Agent/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\coreMQTT-Agent\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\coreMQTT-Agent\source\cSubCommand.tmp" "$<"
