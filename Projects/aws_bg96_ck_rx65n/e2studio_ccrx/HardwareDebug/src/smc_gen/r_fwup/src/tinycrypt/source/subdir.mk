################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_fwup/src/tinycrypt/source/ecc.c \
../src/smc_gen/r_fwup/src/tinycrypt/source/ecc_dsa.c \
../src/smc_gen/r_fwup/src/tinycrypt/source/sha256.c \
../src/smc_gen/r_fwup/src/tinycrypt/source/utils.c

COMPILER_OBJS += \
src/smc_gen/r_fwup/src/tinycrypt/source/ecc.obj \
src/smc_gen/r_fwup/src/tinycrypt/source/ecc_dsa.obj \
src/smc_gen/r_fwup/src/tinycrypt/source/sha256.obj \
src/smc_gen/r_fwup/src/tinycrypt/source/utils.obj

C_DEPS += \
src/smc_gen/r_fwup/src/tinycrypt/source/ecc.d \
src/smc_gen/r_fwup/src/tinycrypt/source/ecc_dsa.d \
src/smc_gen/r_fwup/src/tinycrypt/source/sha256.d \
src/smc_gen/r_fwup/src/tinycrypt/source/utils.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_fwup/src/tinycrypt/source/%.obj: ../src/smc_gen/r_fwup/src/tinycrypt/source/%.c src/smc_gen/r_fwup/src/tinycrypt/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_fwup\src\tinycrypt\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_fwup\src\tinycrypt\source\cSubCommand.tmp" "$<"
