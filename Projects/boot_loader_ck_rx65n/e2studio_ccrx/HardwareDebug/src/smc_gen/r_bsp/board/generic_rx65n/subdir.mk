################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_bsp/board/generic_rx65n/hwsetup.c

COMPILER_OBJS += \
src/smc_gen/r_bsp/board/generic_rx65n/hwsetup.obj

C_DEPS += \
src/smc_gen/r_bsp/board/generic_rx65n/hwsetup.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_bsp/board/generic_rx65n/%.obj: ../src/smc_gen/r_bsp/board/generic_rx65n/%.c src/smc_gen/r_bsp/board/generic_rx65n/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_bsp\board\generic_rx65n\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_bsp\board\generic_rx65n\cSubCommand.tmp" "$<"
