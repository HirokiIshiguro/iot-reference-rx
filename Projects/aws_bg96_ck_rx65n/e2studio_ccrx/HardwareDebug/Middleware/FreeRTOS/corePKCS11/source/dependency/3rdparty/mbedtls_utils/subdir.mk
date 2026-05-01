################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/corePKCS11/source/dependency/3rdparty/mbedtls_utils/mbedtls_utils.c

COMPILER_OBJS += \
Middleware/FreeRTOS/corePKCS11/source/dependency/3rdparty/mbedtls_utils/mbedtls_utils.obj

C_DEPS += \
Middleware/FreeRTOS/corePKCS11/source/dependency/3rdparty/mbedtls_utils/mbedtls_utils.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/corePKCS11/source/dependency/3rdparty/mbedtls_utils/%.obj: ../Middleware/FreeRTOS/corePKCS11/source/dependency/3rdparty/mbedtls_utils/%.c Middleware/FreeRTOS/corePKCS11/source/dependency/3rdparty/mbedtls_utils/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\corePKCS11\source\dependency\3rdparty\mbedtls_utils\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\corePKCS11\source\dependency\3rdparty\mbedtls_utils\cSubCommand.tmp" "$<"
