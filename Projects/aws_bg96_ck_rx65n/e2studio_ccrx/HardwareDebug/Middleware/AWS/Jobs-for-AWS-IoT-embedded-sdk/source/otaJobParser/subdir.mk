################################################################################
# Automatically-generated file. Do not edit!
################################################################################

# Add inputs and outputs from these tool invocations to the build variables
C_SRCS += \
../Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk/source/otaJobParser/job_parser.c \
../Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk/source/otaJobParser/ota_job_handler.c

COMPILER_OBJS += \
Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk/source/otaJobParser/job_parser.obj \
Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk/source/otaJobParser/ota_job_handler.obj

C_DEPS += \
Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk/source/otaJobParser/job_parser.d \
Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk/source/otaJobParser/ota_job_handler.d

# Each subdirectory must supply rules for building sources it contributes
Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk/source/otaJobParser/%.obj: ../Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk/source/otaJobParser/%.c Middleware/AWS/Jobs-for-AWS-IoT-embedded-sdk/source/otaJobParser/Compiler.sub
	@echo 'Scanning and building file: $<'
	ccrx -subcommand="Middleware\AWS\Jobs-for-AWS-IoT-embedded-sdk\source\otaJobParser\cDepSubCommand.tmp" -output=dep="$(@:%.obj=%.d)" -MT="$(@:%.d=%.obj)" -MT="$(@:%.obj=%.d)" "$<"
	ccrx -subcommand="Middleware\AWS\Jobs-for-AWS-IoT-embedded-sdk\source\otaJobParser\cSubCommand.tmp" "$<"
