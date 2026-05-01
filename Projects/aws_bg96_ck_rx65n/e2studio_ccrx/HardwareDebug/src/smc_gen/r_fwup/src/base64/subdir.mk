################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_fwup/src/base64/base64_decode.c

COMPILER_OBJS += \
src/smc_gen/r_fwup/src/base64/base64_decode.obj

C_DEPS += \
src/smc_gen/r_fwup/src/base64/base64_decode.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_fwup/src/base64/%.obj: ../src/smc_gen/r_fwup/src/base64/%.c src/smc_gen/r_fwup/src/base64/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_fwup\src\base64\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_fwup\src\base64\cSubCommand.tmp" "$<"
