################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/backoffAlgorithm/source/backoff_algorithm.c

COMPILER_OBJS += \
Middleware/FreeRTOS/backoffAlgorithm/source/backoff_algorithm.obj

C_DEPS += \
Middleware/FreeRTOS/backoffAlgorithm/source/backoff_algorithm.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/backoffAlgorithm/source/%.obj: ../Middleware/FreeRTOS/backoffAlgorithm/source/%.c Middleware/FreeRTOS/backoffAlgorithm/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\backoffAlgorithm\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\backoffAlgorithm\source\cSubCommand.tmp" "$<"
