################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/3rdparty/mbedtls_utils/mbedtls_bio_freertos_plus_cellular.c \
../Middleware/3rdparty/mbedtls_utils/mbedtls_freertos_port.c

COMPILER_OBJS += \
Middleware/3rdparty/mbedtls_utils/mbedtls_bio_freertos_plus_cellular.obj \
Middleware/3rdparty/mbedtls_utils/mbedtls_freertos_port.obj

C_DEPS += \
Middleware/3rdparty/mbedtls_utils/mbedtls_bio_freertos_plus_cellular.d \
Middleware/3rdparty/mbedtls_utils/mbedtls_freertos_port.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/3rdparty/mbedtls_utils/%.obj: ../Middleware/3rdparty/mbedtls_utils/%.c Middleware/3rdparty/mbedtls_utils/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\3rdparty\mbedtls_utils\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\3rdparty\mbedtls_utils\cSubCommand.tmp" "$<"
