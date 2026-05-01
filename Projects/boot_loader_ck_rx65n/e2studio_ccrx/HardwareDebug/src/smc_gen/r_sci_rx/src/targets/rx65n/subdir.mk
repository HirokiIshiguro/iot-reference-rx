################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_sci_rx/src/targets/rx65n/r_sci_rx65n.c \
../src/smc_gen/r_sci_rx/src/targets/rx65n/r_sci_rx65n_data.c

COMPILER_OBJS += \
src/smc_gen/r_sci_rx/src/targets/rx65n/r_sci_rx65n.obj \
src/smc_gen/r_sci_rx/src/targets/rx65n/r_sci_rx65n_data.obj

C_DEPS += \
src/smc_gen/r_sci_rx/src/targets/rx65n/r_sci_rx65n.d \
src/smc_gen/r_sci_rx/src/targets/rx65n/r_sci_rx65n_data.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_sci_rx/src/targets/rx65n/%.obj: ../src/smc_gen/r_sci_rx/src/targets/rx65n/%.c src/smc_gen/r_sci_rx/src/targets/rx65n/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_sci_rx\src\targets\rx65n\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_sci_rx\src\targets\rx65n\cSubCommand.tmp" "$<"
