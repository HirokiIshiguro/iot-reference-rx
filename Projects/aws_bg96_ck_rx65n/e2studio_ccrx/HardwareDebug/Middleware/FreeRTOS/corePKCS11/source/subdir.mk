################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/corePKCS11/source/core_pkcs11.c \
../Middleware/FreeRTOS/corePKCS11/source/core_pki_utils.c

COMPILER_OBJS += \
Middleware/FreeRTOS/corePKCS11/source/core_pkcs11.obj \
Middleware/FreeRTOS/corePKCS11/source/core_pki_utils.obj

C_DEPS += \
Middleware/FreeRTOS/corePKCS11/source/core_pkcs11.d \
Middleware/FreeRTOS/corePKCS11/source/core_pki_utils.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/corePKCS11/source/%.obj: ../Middleware/FreeRTOS/corePKCS11/source/%.c Middleware/FreeRTOS/corePKCS11/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\corePKCS11\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\corePKCS11\source\cSubCommand.tmp" "$<"
