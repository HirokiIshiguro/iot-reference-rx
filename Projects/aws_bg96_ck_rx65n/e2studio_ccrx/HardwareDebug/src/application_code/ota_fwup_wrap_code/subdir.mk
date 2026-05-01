################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/application_code/ota_fwup_wrap_code/ota_fwup_wrap_flash.c \
../src/application_code/ota_fwup_wrap_code/ota_fwup_wrap_verify.c

COMPILER_OBJS += \
src/application_code/ota_fwup_wrap_code/ota_fwup_wrap_flash.obj \
src/application_code/ota_fwup_wrap_code/ota_fwup_wrap_verify.obj

C_DEPS += \
src/application_code/ota_fwup_wrap_code/ota_fwup_wrap_flash.d \
src/application_code/ota_fwup_wrap_code/ota_fwup_wrap_verify.d

# Each subdirectory must supply rules for building sources it contributes
src/application_code/ota_fwup_wrap_code/%.obj: ../src/application_code/ota_fwup_wrap_code/%.c src/application_code/ota_fwup_wrap_code/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\application_code\ota_fwup_wrap_code\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\application_code\ota_fwup_wrap_code\cSubCommand.tmp" "$<"
