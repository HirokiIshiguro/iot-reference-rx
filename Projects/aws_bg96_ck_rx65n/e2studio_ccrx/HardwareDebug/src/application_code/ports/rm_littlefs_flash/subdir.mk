################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Common/ports/rm_littlefs_flash/rm_littlefs_flash.c

COMPILER_OBJS += \
src/application_code/ports/rm_littlefs_flash/rm_littlefs_flash.obj

C_DEPS += \
src/application_code/ports/rm_littlefs_flash/rm_littlefs_flash.d

# Each subdirectory must supply rules for building sources it contributes
src/application_code/ports/rm_littlefs_flash/%.obj: ../Common/ports/rm_littlefs_flash/%.c src/application_code/ports/rm_littlefs_flash/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\application_code\ports\rm_littlefs_flash\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\application_code\ports\rm_littlefs_flash\cSubCommand.tmp" "$<"
