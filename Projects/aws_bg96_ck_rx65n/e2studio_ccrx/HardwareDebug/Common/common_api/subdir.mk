################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Common/common_api/r_common_api_flash.c \
../Common/common_api/r_common_api_tsip.c

COMPILER_OBJS += \
Common/common_api/r_common_api_flash.obj \
Common/common_api/r_common_api_tsip.obj

C_DEPS += \
Common/common_api/r_common_api_flash.d \
Common/common_api/r_common_api_tsip.d

# Each subdirectory must supply rules for building sources it contributes
Common/common_api/%.obj: ../Common/common_api/%.c Common/common_api/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Common\common_api\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Common\common_api\cSubCommand.tmp" "$<"
