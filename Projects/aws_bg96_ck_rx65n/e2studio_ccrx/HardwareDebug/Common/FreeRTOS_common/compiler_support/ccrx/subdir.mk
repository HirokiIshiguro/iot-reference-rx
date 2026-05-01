################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Common/FreeRTOS_common/compiler_support/ccrx/exit.c \
../Common/FreeRTOS_common/compiler_support/ccrx/strnlen.c

COMPILER_OBJS += \
Common/FreeRTOS_common/compiler_support/ccrx/exit.obj \
Common/FreeRTOS_common/compiler_support/ccrx/strnlen.obj

C_DEPS += \
Common/FreeRTOS_common/compiler_support/ccrx/exit.d \
Common/FreeRTOS_common/compiler_support/ccrx/strnlen.d

# Each subdirectory must supply rules for building sources it contributes
Common/FreeRTOS_common/compiler_support/ccrx/%.obj: ../Common/FreeRTOS_common/compiler_support/ccrx/%.c Common/FreeRTOS_common/compiler_support/ccrx/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Common\FreeRTOS_common\compiler_support\ccrx\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Common\FreeRTOS_common\compiler_support\ccrx\cSubCommand.tmp" "$<"
