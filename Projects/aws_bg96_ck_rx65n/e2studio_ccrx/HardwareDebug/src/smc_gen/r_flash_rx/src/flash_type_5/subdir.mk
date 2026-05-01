################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_flash_rx/src/flash_type_5/r_flash_type5.c

COMPILER_OBJS += \
src/smc_gen/r_flash_rx/src/flash_type_5/r_flash_type5.obj

C_DEPS += \
src/smc_gen/r_flash_rx/src/flash_type_5/r_flash_type5.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_flash_rx/src/flash_type_5/%.obj: ../src/smc_gen/r_flash_rx/src/flash_type_5/%.c src/smc_gen/r_flash_rx/src/flash_type_5/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_flash_rx\src\flash_type_5\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_flash_rx\src\flash_type_5\cSubCommand.tmp" "$<"
