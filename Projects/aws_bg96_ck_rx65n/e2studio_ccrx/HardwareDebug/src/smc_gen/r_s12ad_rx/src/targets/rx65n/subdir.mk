################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_s12ad_rx/src/targets/rx65n/r_s12ad_rx65n.c

COMPILER_OBJS += \
src/smc_gen/r_s12ad_rx/src/targets/rx65n/r_s12ad_rx65n.obj

C_DEPS += \
src/smc_gen/r_s12ad_rx/src/targets/rx65n/r_s12ad_rx65n.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_s12ad_rx/src/targets/rx65n/%.obj: ../src/smc_gen/r_s12ad_rx/src/targets/rx65n/%.c src/smc_gen/r_s12ad_rx/src/targets/rx65n/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_s12ad_rx\src\targets\rx65n\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_s12ad_rx\src\targets\rx65n\cSubCommand.tmp" "$<"
