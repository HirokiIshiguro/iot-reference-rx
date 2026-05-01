################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/SimplePubSub/simple_pub_sub_task.c

COMPILER_OBJS += \
Demos/SimplePubSub/simple_pub_sub_task.obj

C_DEPS += \
Demos/SimplePubSub/simple_pub_sub_task.d

# Each subdirectory must supply rules for building sources it contributes
Demos/SimplePubSub/%.obj: ../Demos/SimplePubSub/%.c Demos/SimplePubSub/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\SimplePubSub\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\SimplePubSub\cSubCommand.tmp" "$<"
