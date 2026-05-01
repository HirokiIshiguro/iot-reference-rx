################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Common/ports/ota_pal/ota_pal.c

COMPILER_OBJS += \
src/application_code/ports/ota_pal/ota_pal.obj

C_DEPS += \
src/application_code/ports/ota_pal/ota_pal.d

# Each subdirectory must supply rules for building sources it contributes
src/application_code/ports/ota_pal/%.obj: ../Common/ports/ota_pal/%.c src/application_code/ports/ota_pal/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\application_code\ports\ota_pal\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\application_code\ports\ota_pal\cSubCommand.tmp" "$<"
