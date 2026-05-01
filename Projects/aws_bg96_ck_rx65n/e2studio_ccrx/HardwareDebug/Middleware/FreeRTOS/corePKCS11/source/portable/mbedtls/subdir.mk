################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/corePKCS11/source/portable/mbedtls/core_pkcs11_mbedtls.c

COMPILER_OBJS += \
Middleware/FreeRTOS/corePKCS11/source/portable/mbedtls/core_pkcs11_mbedtls.obj

C_DEPS += \
Middleware/FreeRTOS/corePKCS11/source/portable/mbedtls/core_pkcs11_mbedtls.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/corePKCS11/source/portable/mbedtls/%.obj: ../Middleware/FreeRTOS/corePKCS11/source/portable/mbedtls/%.c Middleware/FreeRTOS/corePKCS11/source/portable/mbedtls/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\corePKCS11\source\portable\mbedtls\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\corePKCS11\source\portable\mbedtls\cSubCommand.tmp" "$<"
