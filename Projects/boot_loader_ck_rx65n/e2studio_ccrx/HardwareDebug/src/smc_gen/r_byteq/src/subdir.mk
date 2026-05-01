################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_byteq/src/r_byteq.c

COMPILER_OBJS += \
src/smc_gen/r_byteq/src/r_byteq.obj

C_DEPS += \
src/smc_gen/r_byteq/src/r_byteq.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_byteq/src/%.obj: ../src/smc_gen/r_byteq/src/%.c src/smc_gen/r_byteq/src/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_byteq\src\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_byteq\src\cSubCommand.tmp" "$<"
