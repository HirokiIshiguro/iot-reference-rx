################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/application_code/bg96_probe.c \
../src/application_code/main.c \
../src/application_code/user_init.c

COMPILER_OBJS += \
src/application_code/bg96_probe.obj \
src/application_code/main.obj \
src/application_code/user_init.obj

C_DEPS += \
src/application_code/bg96_probe.d \
src/application_code/main.d \
src/application_code/user_init.d

# Each subdirectory must supply rules for building sources it contributes
src/application_code/%.obj: ../src/application_code/%.c src/application_code/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\application_code\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\application_code\cSubCommand.tmp" "$<"
