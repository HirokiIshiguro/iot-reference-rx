################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS-Plus-CLI/FreeRTOS_CLI.c

COMPILER_OBJS += \
Middleware/FreeRTOS-Plus-CLI/FreeRTOS_CLI.obj

C_DEPS += \
Middleware/FreeRTOS-Plus-CLI/FreeRTOS_CLI.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS-Plus-CLI/%.obj: ../Middleware/FreeRTOS-Plus-CLI/%.c Middleware/FreeRTOS-Plus-CLI/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS-Plus-CLI\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS-Plus-CLI\cSubCommand.tmp" "$<"
