################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Demos/Fleet_Provisioning_With_CSR_Demo/FleetProvisioningDemoExample.c \
../Demos/Fleet_Provisioning_With_CSR_Demo/pkcs11_operations.c \
../Demos/Fleet_Provisioning_With_CSR_Demo/tinycbor_serializer.c

COMPILER_OBJS += \
Demos/Fleet_Provisioning_With_CSR_Demo/FleetProvisioningDemoExample.obj \
Demos/Fleet_Provisioning_With_CSR_Demo/pkcs11_operations.obj \
Demos/Fleet_Provisioning_With_CSR_Demo/tinycbor_serializer.obj

C_DEPS += \
Demos/Fleet_Provisioning_With_CSR_Demo/FleetProvisioningDemoExample.d \
Demos/Fleet_Provisioning_With_CSR_Demo/pkcs11_operations.d \
Demos/Fleet_Provisioning_With_CSR_Demo/tinycbor_serializer.d

# Each subdirectory must supply rules for building sources it contributes
Demos/Fleet_Provisioning_With_CSR_Demo/%.obj: ../Demos/Fleet_Provisioning_With_CSR_Demo/%.c Demos/Fleet_Provisioning_With_CSR_Demo/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Demos\Fleet_Provisioning_With_CSR_Demo\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Demos\Fleet_Provisioning_With_CSR_Demo\cSubCommand.tmp" "$<"
