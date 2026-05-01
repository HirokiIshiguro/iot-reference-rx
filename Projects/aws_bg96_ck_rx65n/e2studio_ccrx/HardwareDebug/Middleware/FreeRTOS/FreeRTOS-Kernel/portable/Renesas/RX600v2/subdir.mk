################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/port.c

SRC_SRCS += \
../Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/port_asm.src

SRC_DEPS += \
Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/port_asm.d

ASSEMBLER_OBJS += \
Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/port_asm.obj

COMPILER_OBJS += \
Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/port.obj

C_DEPS += \
Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/port.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/%.obj: ../Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/%.c Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\FreeRTOS\FreeRTOS-Kernel\portable\Renesas\RX600v2\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\FreeRTOS\FreeRTOS-Kernel\portable\Renesas\RX600v2\cSubCommand.tmp" "$<"


Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/%.obj: ../Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/%.src Middleware/FreeRTOS/FreeRTOS-Kernel/portable/Renesas/RX600v2/Assembler.sub
	@echo 'Scanning and building file: $<'
	asrx -subcommand="Middleware\FreeRTOS\FreeRTOS-Kernel\portable\Renesas\RX600v2\srcDepSubCommand.tmp" -MF="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	asrx -subcommand="Middleware\FreeRTOS\FreeRTOS-Kernel\portable\Renesas\RX600v2\srcSubCommand.tmp" -output="$(@:%.d=%.obj)" "$<"
