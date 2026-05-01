################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/bootloader.c

COMPILER_OBJS += \
src/bootloader.obj

C_DEPS += \
src/bootloader.d

# Each subdirectory must supply rules for building sources it contributes
src/%.obj: ../src/%.c src/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\cSubCommand.tmp" "$<"
