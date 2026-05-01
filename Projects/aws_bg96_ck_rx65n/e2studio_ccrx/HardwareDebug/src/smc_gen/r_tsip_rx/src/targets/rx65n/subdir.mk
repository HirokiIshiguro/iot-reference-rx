################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_aes_rx.c \
../src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_arc4_rx.c \
../src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_ecc_rx.c \
../src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_hash_rx.c \
../src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_rsa_rx.c \
../src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_rx.c \
../src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_rx_private.c \
../src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_tdes_rx.c \
../src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_tls_rx.c

COMPILER_OBJS += \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_aes_rx.obj \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_arc4_rx.obj \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_ecc_rx.obj \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_hash_rx.obj \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_rsa_rx.obj \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_rx.obj \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_rx_private.obj \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_tdes_rx.obj \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_tls_rx.obj

C_DEPS += \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_aes_rx.d \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_arc4_rx.d \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_ecc_rx.d \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_hash_rx.d \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_rsa_rx.d \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_rx.d \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_rx_private.d \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_tdes_rx.d \
src/smc_gen/r_tsip_rx/src/targets/rx65n/r_tsip_tls_rx.d

# Each subdirectory must supply rules for building sources it contributes
src/smc_gen/r_tsip_rx/src/targets/rx65n/%.obj: ../src/smc_gen/r_tsip_rx/src/targets/rx65n/%.c src/smc_gen/r_tsip_rx/src/targets/rx65n/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="src\smc_gen\r_tsip_rx\src\targets\rx65n\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="src\smc_gen\r_tsip_rx\src\targets\rx65n\cSubCommand.tmp" "$<"
