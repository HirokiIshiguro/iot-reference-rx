################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/network_transport/using_mbedtls_pkcs11/mbedtls_pk_pkcs11.c \
../Middleware/network_transport/using_mbedtls_pkcs11/transport_mbedtls_pkcs11.c

COMPILER_OBJS += \
Middleware/network_transport/using_mbedtls_pkcs11/mbedtls_pk_pkcs11.obj \
Middleware/network_transport/using_mbedtls_pkcs11/transport_mbedtls_pkcs11.obj

C_DEPS += \
Middleware/network_transport/using_mbedtls_pkcs11/mbedtls_pk_pkcs11.d \
Middleware/network_transport/using_mbedtls_pkcs11/transport_mbedtls_pkcs11.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/network_transport/using_mbedtls_pkcs11/%.obj: ../Middleware/network_transport/using_mbedtls_pkcs11/%.c Middleware/network_transport/using_mbedtls_pkcs11/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\network_transport\using_mbedtls_pkcs11\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\network_transport\using_mbedtls_pkcs11\cSubCommand.tmp" "$<"
