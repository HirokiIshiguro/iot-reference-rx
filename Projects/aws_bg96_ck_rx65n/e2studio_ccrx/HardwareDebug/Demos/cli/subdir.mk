################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/cli/CLIcommands.c \
../Demos/cli/UARTCommandConsole.c \
../Demos/cli/serial.c \
../Demos/cli/store.c

COMPILER_OBJS += \
Demos/cli/CLIcommands.obj \
Demos/cli/UARTCommandConsole.obj \
Demos/cli/serial.obj \
Demos/cli/store.obj

C_DEPS += \
Demos/cli/CLIcommands.d \
Demos/cli/UARTCommandConsole.d \
Demos/cli/serial.d \
Demos/cli/store.d

# Each subdirectory must supply rules for building sources it contributes
Demos/cli/%.obj: ../Demos/cli/%.c Demos/cli/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\cli\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\cli\cSubCommand.tmp" "$<"
