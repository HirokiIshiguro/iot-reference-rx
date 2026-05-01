################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/logging/iot_logging_task_dynamic_buffers.c

COMPILER_OBJS += \
Middleware/logging/iot_logging_task_dynamic_buffers.obj

C_DEPS += \
Middleware/logging/iot_logging_task_dynamic_buffers.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/logging/%.obj: ../Middleware/logging/%.c Middleware/logging/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\logging\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\logging\cSubCommand.tmp" "$<"
