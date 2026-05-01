################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Common/littlefs_common/lfs_common_data.c

COMPILER_OBJS += \
Common/littlefs_common/lfs_common_data.obj

C_DEPS += \
Common/littlefs_common/lfs_common_data.d

# Each subdirectory must supply rules for building sources it contributes
Common/littlefs_common/%.obj: ../Common/littlefs_common/%.c Common/littlefs_common/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Common\littlefs_common\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Common\littlefs_common\cSubCommand.tmp" "$<"
