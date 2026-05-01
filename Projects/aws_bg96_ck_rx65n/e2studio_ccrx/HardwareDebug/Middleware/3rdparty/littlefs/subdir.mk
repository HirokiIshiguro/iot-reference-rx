################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/3rdparty/littlefs/lfs.c \
../Middleware/3rdparty/littlefs/lfs_util.c

COMPILER_OBJS += \
Middleware/3rdparty/littlefs/lfs.obj \
Middleware/3rdparty/littlefs/lfs_util.obj

C_DEPS += \
Middleware/3rdparty/littlefs/lfs.d \
Middleware/3rdparty/littlefs/lfs_util.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/3rdparty/littlefs/%.obj: ../Middleware/3rdparty/littlefs/%.c Middleware/3rdparty/littlefs/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\3rdparty\littlefs\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\3rdparty\littlefs\cSubCommand.tmp" "$<"
