################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/coreJSON/source/core_json.c

COMPILER_OBJS += \
Middleware/FreeRTOS/coreJSON/source/core_json.obj

C_DEPS += \
Middleware/FreeRTOS/coreJSON/source/core_json.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/coreJSON/source/%.obj: ../Middleware/FreeRTOS/coreJSON/source/%.c Middleware/FreeRTOS/coreJSON/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\coreJSON\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\coreJSON\source\cSubCommand.tmp" "$<"
