################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_cellular/src/RTOS/cellular_create_event_group.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_create_semaphore.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_create_task.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_delay_task.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_delete_event_group.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_delete_semaphore.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_delete_task.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_free.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_get_event_flg.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_get_tickcount.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_give_semaphore.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_interrupt_ctrl.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_malloc.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_set_event_flg.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_synchro_event_group.c \
../src/smc_gen/r_cellular/src/RTOS/cellular_take_semaphore.c

COMPILER_OBJS += \
src/smc_gen/r_cellular/src/RTOS/cellular_create_event_group.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_create_semaphore.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_create_task.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_delay_task.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_delete_event_group.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_delete_semaphore.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_delete_task.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_free.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_get_event_flg.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_get_tickcount.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_give_semaphore.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_interrupt_ctrl.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_malloc.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_set_event_flg.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_synchro_event_group.obj \
src/smc_gen/r_cellular/src/RTOS/cellular_take_semaphore.obj

C_DEPS += \
src/smc_gen/r_cellular/src/RTOS/cellular_create_event_group.d \
src/smc_gen/r_cellular/src/RTOS/cellular_create_semaphore.d \
src/smc_gen/r_cellular/src/RTOS/cellular_create_task.d \
src/smc_gen/r_cellular/src/RTOS/cellular_delay_task.d \
src/smc_gen/r_cellular/src/RTOS/cellular_delete_event_group.d \
src/smc_gen/r_cellular/src/RTOS/cellular_delete_semaphore.d \
src/smc_gen/r_cellular/src/RTOS/cellular_delete_task.d \
src/smc_gen/r_cellular/src/RTOS/cellular_free.d \
src/smc_gen/r_cellular/src/RTOS/cellular_get_event_flg.d \
src/smc_gen/r_cellular/src/RTOS/cellular_get_tickcount.d \
src/smc_gen/r_cellular/src/RTOS/cellular_give_semaphore.d \
src/smc_gen/r_cellular/src/RTOS/cellular_interrupt_ctrl.d \
src/smc_gen/r_cellular/src/RTOS/cellular_malloc.d \
src/smc_gen/r_cellular/src/RTOS/cellular_set_event_flg.d \
src/smc_gen/r_cellular/src/RTOS/cellular_synchro_event_group.d \
src/smc_gen/r_cellular/src/RTOS/cellular_take_semaphore.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_cellular/src/RTOS/%.obj: ../src/smc_gen/r_cellular/src/RTOS/%.c src/smc_gen/r_cellular/src/RTOS/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_cellular\src\RTOS\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_cellular\src\RTOS\cSubCommand.tmp" "$<"
