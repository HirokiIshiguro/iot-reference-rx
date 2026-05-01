################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Common/patches/Jobs-for-AWS-IoT-embedded-sdk/source/jobs.c

COMPILER_OBJS += \
Common/patches/Jobs-for-AWS-IoT-embedded-sdk/source/jobs.obj

C_DEPS += \
Common/patches/Jobs-for-AWS-IoT-embedded-sdk/source/jobs.d

# Each subdirectory must supply rules for building sources it contributes
Common/patches/Jobs-for-AWS-IoT-embedded-sdk/source/%.obj: ../Common/patches/Jobs-for-AWS-IoT-embedded-sdk/source/%.c Common/patches/Jobs-for-AWS-IoT-embedded-sdk/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Common\patches\Jobs-for-AWS-IoT-embedded-sdk\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Common\patches\Jobs-for-AWS-IoT-embedded-sdk\source\cSubCommand.tmp" "$<"
