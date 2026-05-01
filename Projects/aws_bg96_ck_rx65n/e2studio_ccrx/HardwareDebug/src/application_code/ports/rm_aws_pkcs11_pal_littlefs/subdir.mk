################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Common/ports/rm_aws_pkcs11_pal_littlefs/rm_aws_pkcs11_pal_littlefs.c

COMPILER_OBJS += \
src/application_code/ports/rm_aws_pkcs11_pal_littlefs/rm_aws_pkcs11_pal_littlefs.obj

C_DEPS += \
src/application_code/ports/rm_aws_pkcs11_pal_littlefs/rm_aws_pkcs11_pal_littlefs.d

# Each subdirectory must supply rules for building sources it contributes
src/application_code/ports/rm_aws_pkcs11_pal_littlefs/%.obj: ../Common/ports/rm_aws_pkcs11_pal_littlefs/%.c src/application_code/ports/rm_aws_pkcs11_pal_littlefs/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\application_code\ports\rm_aws_pkcs11_pal_littlefs\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\application_code\ports\rm_aws_pkcs11_pal_littlefs\cSubCommand.tmp" "$<"
