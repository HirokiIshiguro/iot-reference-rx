################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_pincfg/Pin.c \
../src/smc_gen/r_pincfg/r_irq_rx_pinset.c \
../src/smc_gen/r_pincfg/r_s12ad_rx_pinset.c \
../src/smc_gen/r_pincfg/r_sci_rx_pinset.c

COMPILER_OBJS += \
src/smc_gen/r_pincfg/Pin.obj \
src/smc_gen/r_pincfg/r_irq_rx_pinset.obj \
src/smc_gen/r_pincfg/r_s12ad_rx_pinset.obj \
src/smc_gen/r_pincfg/r_sci_rx_pinset.obj

C_DEPS += \
src/smc_gen/r_pincfg/Pin.d \
src/smc_gen/r_pincfg/r_irq_rx_pinset.d \
src/smc_gen/r_pincfg/r_s12ad_rx_pinset.d \
src/smc_gen/r_pincfg/r_sci_rx_pinset.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_pincfg/%.obj: ../src/smc_gen/r_pincfg/%.c src/smc_gen/r_pincfg/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_pincfg\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_pincfg\cSubCommand.tmp" "$<"
