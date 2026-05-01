################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/frtos_startup/freertos_object_init.c \
../src/frtos_startup/freertos_start.c

COMPILER_OBJS += \
src/frtos_startup/freertos_object_init.obj \
src/frtos_startup/freertos_start.obj

C_DEPS += \
src/frtos_startup/freertos_object_init.d \
src/frtos_startup/freertos_start.d

# Each subdirectory must supply rules for building sources it contributes
src/frtos_startup/%.obj: ../src/frtos_startup/%.c src/frtos_startup/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\frtos_startup\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\frtos_startup\cSubCommand.tmp" "$<"
