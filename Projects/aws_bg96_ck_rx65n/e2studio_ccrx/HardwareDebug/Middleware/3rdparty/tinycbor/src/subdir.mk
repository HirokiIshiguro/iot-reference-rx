################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/3rdparty/tinycbor/src/cborencoder.c \
../Middleware/3rdparty/tinycbor/src/cborencoder_close_container_checked.c \
../Middleware/3rdparty/tinycbor/src/cborerrorstrings.c \
../Middleware/3rdparty/tinycbor/src/cborparser.c \
../Middleware/3rdparty/tinycbor/src/cborparser_dup_string.c \
../Middleware/3rdparty/tinycbor/src/cborpretty.c \
../Middleware/3rdparty/tinycbor/src/cborpretty_stdio.c \
../Middleware/3rdparty/tinycbor/src/cborvalidation.c

COMPILER_OBJS += \
Middleware/3rdparty/tinycbor/src/cborencoder.obj \
Middleware/3rdparty/tinycbor/src/cborencoder_close_container_checked.obj \
Middleware/3rdparty/tinycbor/src/cborerrorstrings.obj \
Middleware/3rdparty/tinycbor/src/cborparser.obj \
Middleware/3rdparty/tinycbor/src/cborparser_dup_string.obj \
Middleware/3rdparty/tinycbor/src/cborpretty.obj \
Middleware/3rdparty/tinycbor/src/cborpretty_stdio.obj \
Middleware/3rdparty/tinycbor/src/cborvalidation.obj

C_DEPS += \
Middleware/3rdparty/tinycbor/src/cborencoder.d \
Middleware/3rdparty/tinycbor/src/cborencoder_close_container_checked.d \
Middleware/3rdparty/tinycbor/src/cborerrorstrings.d \
Middleware/3rdparty/tinycbor/src/cborparser.d \
Middleware/3rdparty/tinycbor/src/cborparser_dup_string.d \
Middleware/3rdparty/tinycbor/src/cborpretty.d \
Middleware/3rdparty/tinycbor/src/cborpretty_stdio.d \
Middleware/3rdparty/tinycbor/src/cborvalidation.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/3rdparty/tinycbor/src/%.obj: ../Middleware/3rdparty/tinycbor/src/%.c Middleware/3rdparty/tinycbor/src/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\3rdparty\tinycbor\src\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\3rdparty\tinycbor\src\cSubCommand.tmp" "$<"
