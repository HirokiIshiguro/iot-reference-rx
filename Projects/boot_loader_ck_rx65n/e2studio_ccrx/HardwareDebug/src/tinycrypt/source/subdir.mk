################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/tinycrypt/source/ecc.c \
../src/tinycrypt/source/ecc_dsa.c \
../src/tinycrypt/source/sha256.c \
../src/tinycrypt/source/utils.c

COMPILER_OBJS += \
src/tinycrypt/source/ecc.obj \
src/tinycrypt/source/ecc_dsa.obj \
src/tinycrypt/source/sha256.obj \
src/tinycrypt/source/utils.obj

C_DEPS += \
src/tinycrypt/source/ecc.d \
src/tinycrypt/source/ecc_dsa.d \
src/tinycrypt/source/sha256.d \
src/tinycrypt/source/utils.d

# Each subdirectory must supply rules for building sources it contributes
src/tinycrypt/source/%.obj: ../src/tinycrypt/source/%.c src/tinycrypt/source/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\tinycrypt\source\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\tinycrypt\source\cSubCommand.tmp" "$<"
