################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../lib/rx_bootloader/base64_decode.c \
../lib/rx_bootloader/rx_bootloader.c

COMPILER_OBJS += \
lib/rx_bootloader/base64_decode.obj \
lib/rx_bootloader/rx_bootloader.obj

C_DEPS += \
lib/rx_bootloader/base64_decode.d \
lib/rx_bootloader/rx_bootloader.d

# Each subdirectory must supply rules for building sources it contributes
lib/rx_bootloader/%.obj: ../lib/rx_bootloader/%.c lib/rx_bootloader/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="lib\rx_bootloader\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="lib\rx_bootloader\cSubCommand.tmp" "$<"
