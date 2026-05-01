################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk/source/fleet_provisioning.c

COMPILER_OBJS += \
Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk/source/fleet_provisioning.obj

C_DEPS += \
Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk/source/fleet_provisioning.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk/source/%.obj: ../Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk/source/%.c Middleware/AWS/Fleet-Provisioning-for-AWS-IoT-embedded-sdk/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\AWS\Fleet-Provisioning-for-AWS-IoT-embedded-sdk\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\AWS\Fleet-Provisioning-for-AWS-IoT-embedded-sdk\source\cSubCommand.tmp" "$<"
