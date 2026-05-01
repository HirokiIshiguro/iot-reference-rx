################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_cellular/src/private/private_api/cellular_at_cmd_res_ctrl.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_closesocket.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_disconnect.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_execute_at_cmd.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_getpdpaddr.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_irq_ctrl.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_module_reset.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_power_down.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_psm_config.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_rts_ctrl.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_sci_ctrl.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_semaphore_ctrl.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_shutdownsocket.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_smcwrx.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_smcwtx.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_task_ctrl.c \
../src/smc_gen/r_cellular/src/private/private_api/cellular_timeout_ctrl.c

COMPILER_OBJS += \
src/smc_gen/r_cellular/src/private/private_api/cellular_at_cmd_res_ctrl.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_closesocket.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_disconnect.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_execute_at_cmd.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_getpdpaddr.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_irq_ctrl.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_module_reset.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_power_down.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_psm_config.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_rts_ctrl.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_sci_ctrl.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_semaphore_ctrl.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_shutdownsocket.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_smcwrx.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_smcwtx.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_task_ctrl.obj \
src/smc_gen/r_cellular/src/private/private_api/cellular_timeout_ctrl.obj

C_DEPS += \
src/smc_gen/r_cellular/src/private/private_api/cellular_at_cmd_res_ctrl.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_closesocket.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_disconnect.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_execute_at_cmd.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_getpdpaddr.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_irq_ctrl.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_module_reset.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_power_down.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_psm_config.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_rts_ctrl.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_sci_ctrl.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_semaphore_ctrl.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_shutdownsocket.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_smcwrx.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_smcwtx.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_task_ctrl.d \
src/smc_gen/r_cellular/src/private/private_api/cellular_timeout_ctrl.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_cellular/src/private/private_api/%.obj: ../src/smc_gen/r_cellular/src/private/private_api/%.c src/smc_gen/r_cellular/src/private/private_api/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_cellular\src\private\private_api\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_cellular\src\private\private_api\cSubCommand.tmp" "$<"
