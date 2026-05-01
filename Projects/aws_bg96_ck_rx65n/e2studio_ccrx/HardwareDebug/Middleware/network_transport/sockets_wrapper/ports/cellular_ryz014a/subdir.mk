################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/TCP_socket_hook.c \
../Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/sockets_wrapper.c

COMPILER_OBJS += \
Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/TCP_socket_hook.obj \
Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/sockets_wrapper.obj

C_DEPS += \
Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/TCP_socket_hook.d \
Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/sockets_wrapper.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/%.obj: ../Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/%.c Middleware/network_transport/sockets_wrapper/ports/cellular_ryz014a/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\network_transport\sockets_wrapper\ports\cellular_ryz014a\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\network_transport\sockets_wrapper\ports\cellular_ryz014a\cSubCommand.tmp" "$<"
