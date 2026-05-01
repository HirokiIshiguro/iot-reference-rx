################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/dev_mode_key_provisioning/src/aws_dev_mode_key_provisioning.c

COMPILER_OBJS += \
Demos/dev_mode_key_provisioning/src/aws_dev_mode_key_provisioning.obj

C_DEPS += \
Demos/dev_mode_key_provisioning/src/aws_dev_mode_key_provisioning.d

# Each subdirectory must supply rules for building sources it contributes
Demos/dev_mode_key_provisioning/src/%.obj: ../Demos/dev_mode_key_provisioning/src/%.c Demos/dev_mode_key_provisioning/src/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\dev_mode_key_provisioning\src\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\dev_mode_key_provisioning\src\cSubCommand.tmp" "$<"
