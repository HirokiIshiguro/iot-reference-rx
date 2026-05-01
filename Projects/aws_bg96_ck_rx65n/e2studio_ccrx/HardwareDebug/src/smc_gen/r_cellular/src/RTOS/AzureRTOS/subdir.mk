################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_cellular/src/RTOS/AzureRTOS/cellular_block_pool_control.c

COMPILER_OBJS += \
src/smc_gen/r_cellular/src/RTOS/AzureRTOS/cellular_block_pool_control.obj

C_DEPS += \
src/smc_gen/r_cellular/src/RTOS/AzureRTOS/cellular_block_pool_control.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_cellular/src/RTOS/AzureRTOS/%.obj: ../src/smc_gen/r_cellular/src/RTOS/AzureRTOS/%.c src/smc_gen/r_cellular/src/RTOS/AzureRTOS/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_cellular\src\RTOS\AzureRTOS\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_cellular\src\RTOS\AzureRTOS\cSubCommand.tmp" "$<"
