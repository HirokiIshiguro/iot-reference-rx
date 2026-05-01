################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/FreeRTOS-Kernel/croutine.c \
../Middleware/FreeRTOS/FreeRTOS-Kernel/event_groups.c \
../Middleware/FreeRTOS/FreeRTOS-Kernel/list.c \
../Middleware/FreeRTOS/FreeRTOS-Kernel/queue.c \
../Middleware/FreeRTOS/FreeRTOS-Kernel/stream_buffer.c \
../Middleware/FreeRTOS/FreeRTOS-Kernel/tasks.c \
../Middleware/FreeRTOS/FreeRTOS-Kernel/timers.c

COMPILER_OBJS += \
Middleware/FreeRTOS/FreeRTOS-Kernel/croutine.obj \
Middleware/FreeRTOS/FreeRTOS-Kernel/event_groups.obj \
Middleware/FreeRTOS/FreeRTOS-Kernel/list.obj \
Middleware/FreeRTOS/FreeRTOS-Kernel/queue.obj \
Middleware/FreeRTOS/FreeRTOS-Kernel/stream_buffer.obj \
Middleware/FreeRTOS/FreeRTOS-Kernel/tasks.obj \
Middleware/FreeRTOS/FreeRTOS-Kernel/timers.obj

C_DEPS += \
Middleware/FreeRTOS/FreeRTOS-Kernel/croutine.d \
Middleware/FreeRTOS/FreeRTOS-Kernel/event_groups.d \
Middleware/FreeRTOS/FreeRTOS-Kernel/list.d \
Middleware/FreeRTOS/FreeRTOS-Kernel/queue.d \
Middleware/FreeRTOS/FreeRTOS-Kernel/stream_buffer.d \
Middleware/FreeRTOS/FreeRTOS-Kernel/tasks.d \
Middleware/FreeRTOS/FreeRTOS-Kernel/timers.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/FreeRTOS-Kernel/%.obj: ../Middleware/FreeRTOS/FreeRTOS-Kernel/%.c Middleware/FreeRTOS/FreeRTOS-Kernel/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\FreeRTOS-Kernel\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\FreeRTOS-Kernel\cSubCommand.tmp" "$<"
