################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/common/pkcs11_helpers/pkcs11_helpers.c

COMPILER_OBJS += \
Demos/common/pkcs11_helpers/pkcs11_helpers.obj

C_DEPS += \
Demos/common/pkcs11_helpers/pkcs11_helpers.d

# Each subdirectory must supply rules for building sources it contributes
Demos/common/pkcs11_helpers/%.obj: ../Demos/common/pkcs11_helpers/%.c Demos/common/pkcs11_helpers/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\common\pkcs11_helpers\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\common\pkcs11_helpers\cSubCommand.tmp" "$<"
