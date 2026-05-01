################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/freertos_plus/standard/crypto/src/iot_crypto.c

COMPILER_OBJS += \
Middleware/freertos_plus/standard/crypto/src/iot_crypto.obj

C_DEPS += \
Middleware/freertos_plus/standard/crypto/src/iot_crypto.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/freertos_plus/standard/crypto/src/%.obj: ../Middleware/freertos_plus/standard/crypto/src/%.c Middleware/freertos_plus/standard/crypto/src/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\freertos_plus\standard\crypto\src\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\freertos_plus\standard\crypto\src\cSubCommand.tmp" "$<"
