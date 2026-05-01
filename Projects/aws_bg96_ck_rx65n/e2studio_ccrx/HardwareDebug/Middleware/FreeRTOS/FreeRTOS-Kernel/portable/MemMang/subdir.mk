################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/FreeRTOS-Kernel/portable/MemMang/heap_4.c

COMPILER_OBJS += \
Middleware/FreeRTOS/FreeRTOS-Kernel/portable/MemMang/heap_4.obj

C_DEPS += \
Middleware/FreeRTOS/FreeRTOS-Kernel/portable/MemMang/heap_4.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/FreeRTOS-Kernel/portable/MemMang/%.obj: ../Middleware/FreeRTOS/FreeRTOS-Kernel/portable/MemMang/%.c Middleware/FreeRTOS/FreeRTOS-Kernel/portable/MemMang/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\FreeRTOS-Kernel\portable\MemMang\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\FreeRTOS-Kernel\portable\MemMang\cSubCommand.tmp" "$<"
