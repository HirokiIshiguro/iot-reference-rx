################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Common/FreeRTOS_common/entropy_hardware_poll.c \
../Common/FreeRTOS_common/unique_id.c

COMPILER_OBJS += \
Common/FreeRTOS_common/entropy_hardware_poll.obj \
Common/FreeRTOS_common/unique_id.obj

C_DEPS += \
Common/FreeRTOS_common/entropy_hardware_poll.d \
Common/FreeRTOS_common/unique_id.d

# Each subdirectory must supply rules for building sources it contributes
Common/FreeRTOS_common/%.obj: ../Common/FreeRTOS_common/%.c Common/FreeRTOS_common/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Common\FreeRTOS_common\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Common\FreeRTOS_common\cSubCommand.tmp" "$<"
