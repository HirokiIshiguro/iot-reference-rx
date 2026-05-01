################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/coreMQTT/source/core_mqtt.c \
../Middleware/FreeRTOS/coreMQTT/source/core_mqtt_serializer.c \
../Middleware/FreeRTOS/coreMQTT/source/core_mqtt_state.c

COMPILER_OBJS += \
Middleware/FreeRTOS/coreMQTT/source/core_mqtt.obj \
Middleware/FreeRTOS/coreMQTT/source/core_mqtt_serializer.obj \
Middleware/FreeRTOS/coreMQTT/source/core_mqtt_state.obj

C_DEPS += \
Middleware/FreeRTOS/coreMQTT/source/core_mqtt.d \
Middleware/FreeRTOS/coreMQTT/source/core_mqtt_serializer.d \
Middleware/FreeRTOS/coreMQTT/source/core_mqtt_state.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/coreMQTT/source/%.obj: ../Middleware/FreeRTOS/coreMQTT/source/%.c Middleware/FreeRTOS/coreMQTT/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\coreMQTT\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\coreMQTT\source\cSubCommand.tmp" "$<"
