################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_fwup/src/r_fwup.c \
../src/smc_gen/r_fwup/src/r_fwup_wrap_com.c \
../src/smc_gen/r_fwup/src/r_fwup_wrap_flash.c \
../src/smc_gen/r_fwup/src/r_fwup_wrap_verify.c

COMPILER_OBJS += \
src/smc_gen/r_fwup/src/r_fwup.obj \
src/smc_gen/r_fwup/src/r_fwup_wrap_com.obj \
src/smc_gen/r_fwup/src/r_fwup_wrap_flash.obj \
src/smc_gen/r_fwup/src/r_fwup_wrap_verify.obj

C_DEPS += \
src/smc_gen/r_fwup/src/r_fwup.d \
src/smc_gen/r_fwup/src/r_fwup_wrap_com.d \
src/smc_gen/r_fwup/src/r_fwup_wrap_flash.d \
src/smc_gen/r_fwup/src/r_fwup_wrap_verify.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_fwup/src/%.obj: ../src/smc_gen/r_fwup/src/%.c src/smc_gen/r_fwup/src/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_fwup\src\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_fwup\src\cSubCommand.tmp" "$<"
