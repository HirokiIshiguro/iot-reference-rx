################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_sci_rx/src/r_sci_rx.c \
../src/smc_gen/r_sci_rx/src/r_sci_rx_dmaca.c \
../src/smc_gen/r_sci_rx/src/r_sci_rx_dtc.c

COMPILER_OBJS += \
src/smc_gen/r_sci_rx/src/r_sci_rx.obj \
src/smc_gen/r_sci_rx/src/r_sci_rx_dmaca.obj \
src/smc_gen/r_sci_rx/src/r_sci_rx_dtc.obj

C_DEPS += \
src/smc_gen/r_sci_rx/src/r_sci_rx.d \
src/smc_gen/r_sci_rx/src/r_sci_rx_dmaca.d \
src/smc_gen/r_sci_rx/src/r_sci_rx_dtc.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_sci_rx/src/%.obj: ../src/smc_gen/r_sci_rx/src/%.c src/smc_gen/r_sci_rx/src/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_sci_rx\src\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_sci_rx\src\cSubCommand.tmp" "$<"
