/***********************************************************************
*
*  FILE        : rx_bootloader.c
*  DESCRIPTION : RX family secure boot loader (generic).
*
*                Based on the RX65N-RSK amazon-freertos boot_loader reference
*                (projects/renesas/rx65n-rsk/e2studio/boot_loader/src/boot_loader.c),
*                with RX72N Envision Kit extensions available behind config switches.
*
*                MCU-dependent flash addresses are declared in config/<mcu>.h and
*                selected via config/rx_bootloader_config.h.
*
***********************************************************************/
#include <stdio.h>
#include <string.h>

#include "r_smc_entry.h"
#include "r_flash_rx_if.h"
#include "r_sci_rx_if.h"
#include "r_sci_rx_pinset.h"

#include "rx_bootloader.h"
#include "rx_bootloader_private.h"
#include "base64_decode.h"
#include "code_signer_public_key.h"

/* tinycrypt */
#include "tinycrypt/sha256.h"
#include "tinycrypt/ecc.h"
#include "tinycrypt/ecc_dsa.h"
#include "tinycrypt/constants.h"

#if RX_BOOTLOADER_USE_LCD
#include "r_simple_graphic_if.h"
#include "r_simple_glcdc_config_rx_if.h"
#endif

#if RX_BOOTLOADER_USE_PERF_COUNTER
#include "r_cmt_rx_if.h"
#endif

#if RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE
#include "r_simple_filesystem_on_dataflash_if.h"
#endif

/*---------------------------------------------------------------------------------------------------------------------*
 * Derived flash layout values (computed from the per-MCU config)
 *---------------------------------------------------------------------------------------------------------------------*/
#define RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS FLASH_CF_LO_BANK_LO_ADDR
#define RX_BOOTLOADER_UPDATE_EXECUTE_AREA_LOW_ADDRESS   FLASH_CF_HI_BANK_LO_ADDR
#define RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER        \
    (FLASH_NUM_BLOCKS_CF - RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL - RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM)
#define USER_RESET_VECTOR_ADDRESS                       (RX_BOOTLOADER_LOW_ADDRESS - 4)

/*---------------------------------------------------------------------------------------------------------------------*
 * Module state
 *---------------------------------------------------------------------------------------------------------------------*/
__STATIC FIRMWARE_UPDATE_CONTROL_BLOCK *firmware_update_control_block_bank0 =
    (FIRMWARE_UPDATE_CONTROL_BLOCK*)RX_BOOTLOADER_UPDATE_EXECUTE_AREA_LOW_ADDRESS;
__STATIC FIRMWARE_UPDATE_CONTROL_BLOCK *firmware_update_control_block_bank1 =
    (FIRMWARE_UPDATE_CONTROL_BLOCK*)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS;
__STATIC LOAD_FIRMWARE_CONTROL_BLOCK   load_firmware_control_block;
__STATIC LOAD_CONST_DATA_CONTROL_BLOCK load_const_data_control_block;

__STATIC uint32_t secure_boot_state = BOOT_LOADER_STATE_INITIALIZING;
__STATIC uint32_t flash_error_code;

/* Handle storage. */
sci_hdl_t                 my_sci_handle;
SCI_RECEIVE_CONTROL_BLOCK sci_receive_control_block;
SCI_BUFFER_CONTROL        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_TOTAL_NUM];

__STATIC int32_t firmware_verification_sha256_ecdsa(const uint8_t *pucData,
                                                    uint32_t       ulSize,
                                                    const uint8_t *pucSignature,
                                                    uint32_t       ulSignatureSize,
                                                    const uint8_t *local_code_signer_public_key);
__CONST uint8_t  code_signer_public_key[]      = CODE_SIGNER_PUBLIC_KEY_PEM;
__CONST uint32_t code_signer_public_key_length = sizeof(code_signer_public_key);

#if RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE
__CONST uint8_t  code_signer_public_key_label[] = "code signer public key";
#endif

#if RX_BOOTLOADER_USE_PERF_COUNTER
__STATIC uint32_t s_10us_counter;
__STATIC uint32_t s_10us_counter_start_flag;
__STATIC uint32_t sha256_time;
__STATIC uint32_t ecdsa_time;

__STATIC void     reset_10us_counter(void);
__STATIC void     start_10us_counter(void);
__STATIC void     stop_10us_counter(void);
__STATIC uint32_t read_10us_counter(void);

void bootloader_software_timer_handler(void *arg);
#endif

/*---------------------------------------------------------------------------------------------------------------------*
 * Forward declarations
 *---------------------------------------------------------------------------------------------------------------------*/
__STATIC int32_t             secure_boot(void);
__STATIC int32_t             firm_block_read(uint32_t *firmware, uint32_t offset);
__STATIC int32_t             const_data_block_read(uint32_t *const_data, uint32_t offset);
__STATIC uint32_t            sci_expected_receive_size(void);
__STATIC void                bank_swap_with_software_reset(void);
__STATIC void                software_reset(void);
__STATIC const uint8_t      *get_status_string(uint8_t status);
__STATIC void                my_sci_callback(void *pArgs);
__STATIC void                my_flash_callback(void *event);

/***********************************************************************************************************************
* Function Name: rx_bootloader_main
***********************************************************************************************************************/
void rx_bootloader_main(void)
{
    int32_t result_secure_boot;
    nop();

#if RX_BOOTLOADER_USE_LCD
    R_SIMPLE_GLCDC_CONFIG_Open();
    R_SIMPLE_GRAPHIC_Open();
#endif

    while (1)
    {
        result_secure_boot = secure_boot();
        if (BOOT_LOADER_SUCCESS == result_secure_boot)
        {
            /* stop all interrupt completely */
            set_psw(0);
#if RX_BOOTLOADER_USE_LCD
            R_SIMPLE_GRAPHIC_Close();
            R_SIMPLE_GLCDC_CONFIG_Close();
#endif
            R_SCI_Close(my_sci_handle);
            uint32_t addr;
            addr = *(uint32_t *)USER_RESET_VECTOR_ADDRESS;
            ((void (*)())addr)();
            while (1); /* infinite loop */
        }
        else if (BOOT_LOADER_FAIL == result_secure_boot)
        {
            while (1) { /* infinity loop */ }
        }
        else if (BOOT_LOADER_IN_PROGRESS == result_secure_boot)
        {
            continue;
        }
        else
        {
            while (1) { /* infinite loop */ }
        }
    }
}

/***********************************************************************************************************************
* Function Name: secure_boot
* Description  : Bootloader state machine. Called repeatedly from rx_bootloader_main() until it returns
*                BOOT_LOADER_SUCCESS (jump to user program) or BOOT_LOADER_FAIL (halt).
***********************************************************************************************************************/
__STATIC int32_t secure_boot(void)
{
    flash_err_t flash_api_error_code = FLASH_SUCCESS;
    int32_t     secure_boot_error_code = BOOT_LOADER_IN_PROGRESS;
    uint32_t    bank_info = 255;
    flash_interrupt_config_t cb_func_info;
    FIRMWARE_UPDATE_CONTROL_BLOCK *firmware_update_control_block_tmp =
        (FIRMWARE_UPDATE_CONTROL_BLOCK *)load_firmware_control_block.flash_buffer;
    int32_t verification_result = -1;

#if RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE
    uint8_t *local_code_signer_public_key;
    uint32_t local_code_signer_public_key_size;
#else
    const uint8_t *local_code_signer_public_key = code_signer_public_key;
#endif

    switch (secure_boot_state)
    {
        case BOOT_LOADER_STATE_INITIALIZING:
            R_SCI_PinSet_serial_term();

            sci_cfg_t my_sci_config;
            sci_err_t my_sci_err;
#if RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE
            SFD_HANDLE sfd_handle;
#endif
#if RX_BOOTLOADER_USE_PERF_COUNTER
            uint32_t my_cmt_channel;
#endif

            my_sci_config.async.baud_rate    = BSP_CFG_SCI_UART_TERMINAL_BITRATE;
            my_sci_config.async.clk_src      = SCI_CLK_INT;
            my_sci_config.async.data_size    = SCI_DATA_8BIT;
            my_sci_config.async.parity_en    = SCI_PARITY_OFF;
            my_sci_config.async.parity_type  = SCI_EVEN_PARITY;
            my_sci_config.async.stop_bits    = SCI_STOPBITS_1;
            my_sci_config.async.int_priority = BSP_CFG_SCI_UART_TERMINAL_INTERRUPT_PRIORITY;

            my_sci_err = R_SCI_Open(SCI_CH_serial_term, SCI_MODE_ASYNC, &my_sci_config, my_sci_callback, &my_sci_handle);
            if (SCI_SUCCESS != my_sci_err)
            {
                nop();
                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                secure_boot_error_code = BOOT_LOADER_FAIL;
                break;
            }

            load_firmware_control_block.progress = 0;
            load_firmware_control_block.offset   = 0;

            flash_api_error_code = R_FLASH_Open();
            if (FLASH_SUCCESS != flash_api_error_code)
            {
                printf("R_FLASH_Open() returns error. %d.\r\n", flash_error_code);
                printf("system error.\r\n");
                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                secure_boot_error_code = BOOT_LOADER_FAIL;
            }

            printf("-------------------------------------------------\r\n");
            printf("RX secure boot program\r\n");
            printf("-------------------------------------------------\r\n");

#if RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE
            printf("Checking data flash ROM status.\r\n");
            R_SFD_Open();

            printf("Loading user code signer public key: ");
            sfd_handle = R_SFD_FindObject((uint8_t *)code_signer_public_key_label,
                                          sizeof(code_signer_public_key_label));
            if (sfd_handle != SFD_HANDLE_INVALID)
            {
                printf("found.\r\n");
                R_SFD_GetObjectValue(sfd_handle,
                                     (uint8_t **)&local_code_signer_public_key,
                                     &local_code_signer_public_key_size);
            }
            else
            {
                printf("not found.\r\n");
                printf("provision the user code signer public key: ");
                R_SFD_Open();
                sfd_handle = R_SFD_SaveObject((uint8_t *)code_signer_public_key_label,
                                              sizeof(code_signer_public_key_label),
                                              (uint8_t *)code_signer_public_key,
                                              code_signer_public_key_length);
                if (sfd_handle != SFD_HANDLE_INVALID)
                {
                    printf("OK.\r\n");
                    R_SFD_GetObjectValue(sfd_handle,
                                         (uint8_t **)&local_code_signer_public_key,
                                         &local_code_signer_public_key_size);
                }
                else
                {
                    printf("NG.\r\n");
                }
                R_SFD_Close();
            }
            R_SFD_Close();
#endif /* RX_BOOTLOADER_USE_DATAFLASH_KEY_STORE */

            printf("Checking code flash ROM status.\r\n");
            printf("bank 0 status = 0x%x [%s]\r\n", firmware_update_control_block_bank0->image_flag, get_status_string(firmware_update_control_block_bank0->image_flag));
            printf("bank 1 status = 0x%x [%s]\r\n", firmware_update_control_block_bank1->image_flag, get_status_string(firmware_update_control_block_bank1->image_flag));

            R_FLASH_Control(FLASH_CMD_BANK_GET, &bank_info);
            printf("bank info = %d. (start bank = %d)\r\n", bank_info, (bank_info ^ 0x01));

            cb_func_info.pcallback    = my_flash_callback;
            cb_func_info.int_priority = RX_BOOTLOADER_FLASH_INT_PRIORITY;
            R_FLASH_Control(FLASH_CMD_SET_BGO_CALLBACK, (void *)&cb_func_info);

#if RX_BOOTLOADER_USE_PERF_COUNTER
            R_CMT_CreatePeriodic(100000, bootloader_software_timer_handler, &my_cmt_channel);
            printf("started 10us software timer using CMT channel %d.\r\n", my_cmt_channel);
#endif

            secure_boot_state = BOOT_LOADER_STATE_BANK1_CHECK;
            break;

        case BOOT_LOADER_STATE_BANK1_CHECK:
            if (firmware_update_control_block_bank1->image_flag == LIFECYCLE_STATE_TESTING)
            {
                memcpy(load_firmware_control_block.flash_buffer,
                       (void *)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS,
                       FLASH_CF_MEDIUM_BLOCK_SIZE);

                printf("integrity check scheme = %-.32s\r\n", firmware_update_control_block_bank1->signature_type);
                printf("bank1(temporary area) on code flash integrity check...");

                if (!strcmp((const char *)firmware_update_control_block_bank1->signature_type,
                            INTEGRITY_CHECK_SCHEME_HASH_SHA256_STANDALONE))
                {
                    uint8_t hash_sha256[TC_SHA256_DIGEST_SIZE];
                    struct tc_sha256_state_struct xCtx;
                    tc_sha256_init(&xCtx);
                    tc_sha256_update(&xCtx,
                        (uint8_t *)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS + RX_BOOTLOADER_FW_HEADER_LENGTH,
                        (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER) - RX_BOOTLOADER_FW_HEADER_LENGTH);
                    tc_sha256_final(hash_sha256, &xCtx);
                    verification_result = memcmp(firmware_update_control_block_bank1->signature, hash_sha256, sizeof(hash_sha256));
                }
                else if (!strcmp((const char *)firmware_update_control_block_bank1->signature_type,
                                 INTEGRITY_CHECK_SCHEME_SIG_SHA256_ECDSA_STANDALONE))
                {
                    verification_result = firmware_verification_sha256_ecdsa(
                        (const uint8_t *)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS + RX_BOOTLOADER_FW_HEADER_LENGTH,
                        (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER) - RX_BOOTLOADER_FW_HEADER_LENGTH,
                        firmware_update_control_block_bank1->signature,
                        firmware_update_control_block_bank1->signature_size,
                        local_code_signer_public_key);
                }
                else
                {
                    verification_result = -1;
                }

                if (0 == verification_result)
                {
                    printf("OK\r\n");
                    firmware_update_control_block_tmp->image_flag = LIFECYCLE_STATE_VALID;
                }
                else
                {
                    printf("NG\r\n");
                    firmware_update_control_block_tmp->image_flag = LIFECYCLE_STATE_INVALID;
                }
                printf("update LIFECYCLE_STATE from [%s] to [%s]\r\n",
                       get_status_string(firmware_update_control_block_bank1->image_flag),
                       get_status_string(firmware_update_control_block_tmp->image_flag));
                printf("bank1(temporary area) block0 erase (to update LIFECYCLE_STATE)...");
                flash_api_error_code = R_FLASH_Erase((flash_block_address_t)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS, 1);
                if (FLASH_SUCCESS != flash_api_error_code)
                {
                    printf("R_FLASH_Erase() returns error. %d.\r\n", flash_error_code);
                    printf("system error.\r\n");
                    secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                    secure_boot_error_code = BOOT_LOADER_FAIL;
                    break;
                }
                secure_boot_state = BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_ERASE_WAIT;
            }
            else
            {
                if (firmware_update_control_block_bank0->image_flag == LIFECYCLE_STATE_VALID)
                {
                    secure_boot_state = BOOT_LOADER_STATE_BANK0_UPDATE_CHECK;
                }
                else
                {
                    secure_boot_state = BOOT_LOADER_STATE_BANK0_CHECK;
                }
            }
            break;

        case BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_ERASE_WAIT:
            /* this state will be updated by flash callback */
            break;

        case BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_ERASE_COMPLETE:
            if (FLASH_SUCCESS == flash_error_code)
            {
                printf("OK\r\n");
            }
            else
            {
                printf("R_FLASH_Erase() callback error. %d.\r\n", flash_error_code);
                printf("system error.\r\n");
                secure_boot_state = BOOT_LOADER_STATE_FATAL_ERROR;
                break;
            }
            printf("bank1(temporary area) block0 write (to update LIFECYCLE_STATE)...");
            flash_api_error_code = R_FLASH_Write((uint32_t)firmware_update_control_block_tmp,
                                                 (uint32_t)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS,
                                                 FLASH_CF_MEDIUM_BLOCK_SIZE);
            if (FLASH_SUCCESS != flash_api_error_code)
            {
                printf("R_FLASH_Write() returns error. %d.\r\n", flash_error_code);
                printf("system error.\r\n");
                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                secure_boot_error_code = BOOT_LOADER_FAIL;
                break;
            }
            secure_boot_state = BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_WRITE_WAIT;
            break;

        case BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_WRITE_WAIT:
            /* this state will be updated by flash callback */
            break;

        case BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_WRITE_COMPLETE:
            if (FLASH_SUCCESS == flash_error_code)
            {
                printf("OK\r\n");
            }
            else
            {
                printf("R_FLASH_Write() callback error. %d.\r\n", flash_error_code);
                printf("system error.\r\n");
                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                secure_boot_error_code = BOOT_LOADER_FAIL;
                break;
            }
            printf("refresh bank1 secure boot mirror area before swap...");
            flash_api_error_code = R_FLASH_Erase(RX_BOOTLOADER_MIRROR_HIGH_ADDRESS,
                                                 RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL + RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM);
            if (FLASH_SUCCESS != flash_api_error_code)
            {
                printf("NG\r\n");
                printf("R_FLASH_Erase() returns error code = %d.\r\n", flash_error_code);
                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                secure_boot_error_code = BOOT_LOADER_FAIL;
                break;
            }
            secure_boot_state = BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_ERASE_WAIT;
            break;

        case BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_ERASE_WAIT:
            /* this state will be updated by flash callback */
            break;

        case BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_ERASE_COMPLETE:
            if (FLASH_SUCCESS == flash_error_code)
            {
                printf("OK\r\n");
            }
            else
            {
                printf("R_FLASH_Erase() callback error. %d.\r\n", flash_error_code);
                printf("system error.\r\n");
                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                secure_boot_error_code = BOOT_LOADER_FAIL;
                break;
            }
            printf("copy secure boot (part1) from bank0 to bank1...");
            flash_api_error_code = R_FLASH_Write((uint32_t)RX_BOOTLOADER_LOW_ADDRESS,
                                                 (uint32_t)RX_BOOTLOADER_MIRROR_LOW_ADDRESS,
                                                 ((uint32_t)RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM) * FLASH_CF_MEDIUM_BLOCK_SIZE);
            if (FLASH_SUCCESS != flash_api_error_code)
            {
                printf("NG\r\n");
                printf("R_FLASH_Write() returns error code = %d.\r\n", flash_error_code);
                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                secure_boot_error_code = BOOT_LOADER_FAIL;
                break;
            }
            secure_boot_state = BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_WAIT1;
            break;

        case BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_WAIT1:
            /* this state will be updated by flash callback */
            break;

        case BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_COMPLETE1:
            if (FLASH_SUCCESS == flash_error_code)
            {
                printf("OK\r\n");
            }
            else
            {
                printf("R_FLASH_Write() callback error. %d.\r\n", flash_error_code);
                printf("system error.\r\n");
                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                secure_boot_error_code = BOOT_LOADER_FAIL;
                break;
            }
            printf("copy secure boot (part2) from bank0 to bank1...");
            if (RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM > 0)
            {
                flash_api_error_code = R_FLASH_Write((uint32_t)RX_BOOTLOADER_SMALL_BLOCK_SRC,
                                                     (uint32_t)RX_BOOTLOADER_SMALL_BLOCK_DST,
                                                     RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL * FLASH_CF_SMALL_BLOCK_SIZE);
                if (FLASH_SUCCESS != flash_api_error_code)
                {
                    printf("NG\r\n");
                    printf("R_FLASH_Write() returns error code = %d.\r\n", flash_error_code);
                    secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                    secure_boot_error_code = BOOT_LOADER_FAIL;
                    break;
                }
                secure_boot_state = BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_WAIT2;
            }
            else
            {
                secure_boot_state = BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_COMPLETE2;
            }
            break;

        case BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_WAIT2:
            /* this state will be updated by flash callback */
            break;

        case BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_COMPLETE2:
            if (FLASH_SUCCESS == flash_error_code)
            {
                printf("OK\r\n");
            }
            else
            {
                printf("R_FLASH_Write() callback error. %d.\r\n", flash_error_code);
                printf("system error.\r\n");
                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                secure_boot_error_code = BOOT_LOADER_FAIL;
                break;
            }
            printf("swap bank...\r\n");
            R_BSP_SoftwareDelay(3000, BSP_DELAY_MILLISECS);
            bank_swap_with_software_reset();
            while (1);
            break;

        case BOOT_LOADER_STATE_BANK0_CHECK:
        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_WAIT:
        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_COMPLETE:
        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT1:
        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_COMPLETE1:
        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT2:
        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_COMPLETE2:
        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_ERASE_WAIT:
        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_ERASE_COMPLETE:
        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_ERASE_WAIT:
        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_ERASE_COMPLETE:
        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_READ_WAIT:
        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_READ_COMPLETE:
        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_WRITE_WAIT:
        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_WRITE_COMPLETE:
        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_WAIT:
        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_COMPLETE:
        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_WAIT:
        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_COMPLETE:
        case BOOT_LOADER_STATE_BANK0_UPDATE_CHECK:
        case BOOT_LOADER_STATE_BANK1_UPDATE_CODE_FLASH_ERASE_WAIT:
        case BOOT_LOADER_STATE_BANK1_UPDATE_CODE_FLASH_ERASE_COMPLETE:
        case BOOT_LOADER_STATE_FINALIZE:
            switch (firmware_update_control_block_bank0->image_flag)
            {
                case LIFECYCLE_STATE_BLANK:
                    switch (secure_boot_state)
                    {
                        case BOOT_LOADER_STATE_BANK0_CHECK:
                            if (firmware_update_control_block_bank1->image_flag == LIFECYCLE_STATE_VALID)
                            {
                                printf("bank0 is blank and bank1 is valid. swap bank...\r\n");
                                R_BSP_SoftwareDelay(3000, BSP_DELAY_MILLISECS);
                                bank_swap_with_software_reset();
                                while (1);
                            }
                            printf("start installing user program.\r\n");
                            if (firmware_update_control_block_bank1->image_flag == LIFECYCLE_STATE_INSTALLING)
                            {
                                secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_COMPLETE;
                            }
                            else
                            {
                                printf("erase bank1 secure boot mirror area...");
                                flash_api_error_code = R_FLASH_Erase(RX_BOOTLOADER_MIRROR_HIGH_ADDRESS,
                                                                     RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL + RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM);
                                if (FLASH_SUCCESS != flash_api_error_code)
                                {
                                    printf("NG\r\n");
                                    printf("R_FLASH_Erase() returns error code = %d.\r\n", flash_error_code);
                                    secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                    secure_boot_error_code = BOOT_LOADER_FAIL;
                                    break;
                                }
                                secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_WAIT;
                            }
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_WAIT:
                            /* this state will be updated by flash callback */
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_COMPLETE:
                            if (firmware_update_control_block_bank1->image_flag != LIFECYCLE_STATE_INSTALLING)
                            {
                                if (FLASH_SUCCESS == flash_error_code)
                                {
                                    printf("OK\r\n");
                                }
                                else
                                {
                                    printf("R_FLASH_Erase() callback error. %d.\r\n", flash_error_code);
                                    printf("system error.\r\n");
                                    secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                    secure_boot_error_code = BOOT_LOADER_FAIL;
                                    break;
                                }
                            }
                            printf("copy secure boot (part1) from bank0 to bank1...");
                            flash_api_error_code = R_FLASH_Write((uint32_t)RX_BOOTLOADER_LOW_ADDRESS,
                                                                 (uint32_t)RX_BOOTLOADER_MIRROR_LOW_ADDRESS,
                                                                 ((uint32_t)RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM) * FLASH_CF_MEDIUM_BLOCK_SIZE);
                            if (FLASH_SUCCESS != flash_api_error_code)
                            {
                                printf("NG\r\n");
                                printf("R_FLASH_Write() returns error code = %d.\r\n", flash_error_code);
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                                break;
                            }
                            secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT1;
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT1:
                            /* this state will be updated by flash callback */
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_COMPLETE1:
                            if (FLASH_SUCCESS == flash_error_code)
                            {
                                printf("OK\r\n");
                            }
                            else
                            {
                                printf("R_FLASH_Write() callback error. %d.\r\n", flash_error_code);
                                printf("system error.\r\n");
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                                break;
                            }
                            printf("copy secure boot (part2) from bank0 to bank1...");
                            if (RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM > 0)
                            {
                                flash_api_error_code = R_FLASH_Write((uint32_t)RX_BOOTLOADER_SMALL_BLOCK_SRC,
                                                                     (uint32_t)RX_BOOTLOADER_SMALL_BLOCK_DST,
                                                                     RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL * FLASH_CF_SMALL_BLOCK_SIZE);
                                if (FLASH_SUCCESS != flash_api_error_code)
                                {
                                    printf("NG\r\n");
                                    printf("R_FLASH_Write() returns error code = %d.\r\n", flash_error_code);
                                    secure_boot_error_code = BOOT_LOADER_FAIL;
                                    break;
                                }
                            }
                            else
                            {
                                secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_COMPLETE2;
                            }
                            secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT2;
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT2:
                            /* this state will be updated by flash callback */
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_COMPLETE2:
                            if (FLASH_SUCCESS == flash_error_code)
                            {
                                printf("OK\r\n");
                            }
                            else
                            {
                                printf("R_FLASH_Write() callback error. %d.\r\n", flash_error_code);
                                printf("system error.\r\n");
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                                break;
                            }
                            if (firmware_update_control_block_bank1->image_flag == LIFECYCLE_STATE_INSTALLING)
                            {
                                memcpy(load_firmware_control_block.flash_buffer,
                                       (void *)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS,
                                       FLASH_CF_MEDIUM_BLOCK_SIZE);
                                firmware_update_control_block_tmp->image_flag = LIFECYCLE_STATE_VALID;
                                printf("update LIFECYCLE_STATE from [%s] to [%s]\r\n",
                                       get_status_string(firmware_update_control_block_bank1->image_flag),
                                       get_status_string(firmware_update_control_block_tmp->image_flag));
                                printf("bank1(temporary area) block0 erase (to update LIFECYCLE_STATE)...");
                                flash_api_error_code = R_FLASH_Erase((flash_block_address_t)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS, 1);
                                if (FLASH_SUCCESS != flash_api_error_code)
                                {
                                    printf("R_FLASH_Erase() returns error. %d.\r\n", flash_error_code);
                                    printf("system error.\r\n");
                                    secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                    secure_boot_error_code = BOOT_LOADER_FAIL;
                                    break;
                                }
                                secure_boot_state = BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_ERASE_WAIT;
                            }
                            else
                            {
                                printf("========== install user program phase ==========\r\n");
                                printf("erase install area (data flash): ");
                                flash_api_error_code = R_FLASH_Erase((flash_block_address_t)RX_BOOTLOADER_USER_CONST_DATA_LOW_ADDRESS,
                                                                     RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER);
                                if (FLASH_SUCCESS != flash_api_error_code)
                                {
                                    printf("R_FLASH_Erase() returns error. %d.\r\n", flash_error_code);
                                    printf("system error.\r\n");
                                    secure_boot_error_code = BOOT_LOADER_FAIL;
                                    break;
                                }
                                secure_boot_state = BOOT_LOADER_STATE_INSTALL_DATA_FLASH_ERASE_WAIT;
                            }
                            break;

                        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_ERASE_WAIT:
                            /* this state will be updated by flash callback */
                            break;

                        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_ERASE_COMPLETE:
                            if (FLASH_SUCCESS == flash_error_code)
                            {
                                printf("OK\r\n");
                            }
                            else
                            {
                                printf("R_FLASH_Write() callback error. %d.\r\n", flash_error_code);
                                printf("system error.\r\n");
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                                break;
                            }
                            printf("erase install area (code flash): ");
                            flash_api_error_code = R_FLASH_Erase((flash_block_address_t)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_HIGH_ADDRESS,
                                                                 FLASH_NUM_BLOCKS_CF - RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL - RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM);
                            if (FLASH_SUCCESS != flash_api_error_code)
                            {
                                printf("R_FLASH_Erase() returns error. %d.\r\n", flash_error_code);
                                printf("system error.\r\n");
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                                break;
                            }
                            secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_ERASE_WAIT;
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_ERASE_WAIT:
                            /* this state will be updated by flash callback */
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_ERASE_COMPLETE:
                            if (FLASH_SUCCESS == flash_error_code)
                            {
                                printf("OK\r\n");
                            }
                            else
                            {
                                printf("R_FLASH_Write() callback error. %d.\r\n", flash_error_code);
                                printf("system error.\r\n");
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                                break;
                            }
                            sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer_full_flag = BOOT_LOADER_SCI_RECEIVE_BUFFER_EMPTY;
                            sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer_full_flag = BOOT_LOADER_SCI_RECEIVE_BUFFER_EMPTY;
                            sci_receive_control_block.p_sci_buffer_control = &sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A];
                            sci_receive_control_block.current_state        = BOOT_LOADER_SCI_CONTROL_BLOCK_A;
                            printf("send \"%s\" via UART.\r\n", RX_BOOTLOADER_INITIAL_FW_FILENAME);
                            secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_READ_WAIT;
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_READ_WAIT:
                            if (!firm_block_read(load_firmware_control_block.flash_buffer, load_firmware_control_block.offset))
                            {
                                flash_api_error_code = R_FLASH_Write((uint32_t)load_firmware_control_block.flash_buffer,
                                                                     (uint32_t)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS + load_firmware_control_block.offset,
                                                                     sizeof(load_firmware_control_block.flash_buffer));
                                if (FLASH_SUCCESS != flash_api_error_code)
                                {
                                    printf("R_FLASH_Write() returns error. %d.\r\n", flash_error_code);
                                    printf("system error.\r\n");
                                    secure_boot_error_code = BOOT_LOADER_FAIL;
                                    break;
                                }
                                secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_WRITE_WAIT;
                            }
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_WRITE_WAIT:
                            /* this state will be updated by flash callback */
                            break;

                        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_WRITE_COMPLETE:
                            if (FLASH_SUCCESS != flash_error_code)
                            {
                                printf("R_FLASH_Write() callback error. %d.\r\n", flash_error_code);
                                printf("system error.\r\n");
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                                break;
                            }

                            load_firmware_control_block.offset += FLASH_CF_MEDIUM_BLOCK_SIZE;
                            load_firmware_control_block.progress =
                                (uint32_t)(((float)(load_firmware_control_block.offset) /
                                            (float)((FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER)) * 100));
                            printf("installing firmware...%d%%(%d/%dKB).\r",
                                   load_firmware_control_block.progress,
                                   load_firmware_control_block.offset / 1024,
                                   (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER) / 1024);
                            if (load_firmware_control_block.offset < (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER))
                            {
                                secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_READ_WAIT;
                            }
                            else if (load_firmware_control_block.offset == (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER))
                            {
                                printf("\n");
                                printf("completed installing firmware.\r\n");
                                printf("integrity check scheme = %-.32s\r\n", firmware_update_control_block_bank1->signature_type);
                                printf("bank1(temporary area) on code flash integrity check...");

                                if (!strcmp((const char *)firmware_update_control_block_bank1->signature_type,
                                            INTEGRITY_CHECK_SCHEME_HASH_SHA256_STANDALONE))
                                {
                                    uint8_t hash_sha256[TC_SHA256_DIGEST_SIZE];
                                    struct tc_sha256_state_struct xCtx;
                                    tc_sha256_init(&xCtx);
                                    tc_sha256_update(&xCtx,
                                        (uint8_t *)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS + RX_BOOTLOADER_FW_HEADER_LENGTH,
                                        (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER) - RX_BOOTLOADER_FW_HEADER_LENGTH);
                                    tc_sha256_final(hash_sha256, &xCtx);
                                    verification_result = memcmp(firmware_update_control_block_bank1->signature, hash_sha256, sizeof(hash_sha256));
                                }
                                else if (!strcmp((const char *)firmware_update_control_block_bank1->signature_type,
                                                 INTEGRITY_CHECK_SCHEME_SIG_SHA256_ECDSA_STANDALONE))
                                {
                                    verification_result = firmware_verification_sha256_ecdsa(
                                        (const uint8_t *)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS + RX_BOOTLOADER_FW_HEADER_LENGTH,
                                        (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER) - RX_BOOTLOADER_FW_HEADER_LENGTH,
                                        firmware_update_control_block_bank1->signature,
                                        firmware_update_control_block_bank1->signature_size,
                                        local_code_signer_public_key);
                                }
                                else
                                {
                                    verification_result = -1;
                                }

                                if (0 == verification_result)
                                {
                                    printf("OK\r\n");
                                    load_const_data_control_block.offset = 0;
                                    secure_boot_state = BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_WAIT;
                                }
                                else
                                {
                                    printf("NG\r\n");
                                    secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                    secure_boot_error_code = BOOT_LOADER_FAIL;
                                }
                            }
                            else
                            {
                                printf("\n");
                                printf("fatal error occurred.\r\n");
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                            }
                            break;

                        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_WAIT:
                            if (!const_data_block_read(load_const_data_control_block.flash_buffer, load_const_data_control_block.offset))
                            {
                                secure_boot_state = BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_COMPLETE;
                            }
                            break;

                        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_COMPLETE:
                            flash_api_error_code = R_FLASH_Write(
                                (uint32_t)&load_const_data_control_block.flash_buffer[load_const_data_control_block.offset / 4],
                                (uint32_t)RX_BOOTLOADER_USER_CONST_DATA_LOW_ADDRESS + load_const_data_control_block.offset,
                                FLASH_DF_BLOCK_SIZE);
                            if (FLASH_SUCCESS != flash_api_error_code)
                            {
                                printf("R_FLASH_Write() returns error. %d.\r\n", flash_error_code);
                                printf("system error.\r\n");
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                                break;
                            }
                            secure_boot_state = BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_WAIT;
                            break;

                        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_WAIT:
                            /* this state will be updated by flash callback */
                            break;

                        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_COMPLETE:
                            if (FLASH_SUCCESS != flash_error_code)
                            {
                                printf("R_FLASH_Write() callback error. %d.\r\n", flash_error_code);
                                printf("system error.\r\n");
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                                break;
                            }

                            load_const_data_control_block.offset += FLASH_DF_BLOCK_SIZE;
                            load_const_data_control_block.progress =
                                (uint32_t)(((float)(load_const_data_control_block.offset) /
                                            (float)((FLASH_DF_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER)) * 100));
                            {
                                static uint32_t previous_offset = 0;
                                if (previous_offset != (load_const_data_control_block.offset / 1024))
                                {
                                    printf("installing const data...%d%%(%d/%dKB).\r",
                                           load_const_data_control_block.progress,
                                           load_const_data_control_block.offset / 1024,
                                           (FLASH_DF_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER) / 1024);
                                    previous_offset = load_const_data_control_block.offset / 1024;
                                }
                            }
                            if (load_const_data_control_block.offset < (FLASH_DF_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER))
                            {
                                secure_boot_state = BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_COMPLETE;
                            }
                            else if (load_const_data_control_block.offset == (FLASH_DF_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER))
                            {
                                printf("\n");
                                printf("completed installing const data.\r\n");
                                printf("software reset...\r\n");
                                R_BSP_SoftwareDelay(3000, BSP_DELAY_MILLISECS);
                                software_reset();
                            }
                            else
                            {
                                printf("\n");
                                printf("fatal error occurred.\r\n");
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                            }
                            break;
                    }
                    break;

                case LIFECYCLE_STATE_TESTING:
                    printf("illegal status\r\n");
                    printf("swap bank...");
                    R_BSP_SoftwareDelay(3000, BSP_DELAY_MILLISECS);
                    bank_swap_with_software_reset();
                    while (1);
                    break;

                case LIFECYCLE_STATE_VALID:
                    switch (secure_boot_state)
                    {
                        case BOOT_LOADER_STATE_BANK0_UPDATE_CHECK:
                            printf("integrity check scheme = %-.32s\r\n", firmware_update_control_block_bank0->signature_type);
                            printf("bank0(execute area) on code flash integrity check...");
                            if (!strcmp((const char *)firmware_update_control_block_bank0->signature_type,
                                        INTEGRITY_CHECK_SCHEME_HASH_SHA256_STANDALONE))
                            {
                                uint8_t hash_sha256[TC_SHA256_DIGEST_SIZE];
                                struct tc_sha256_state_struct xCtx;
                                tc_sha256_init(&xCtx);
                                tc_sha256_update(&xCtx,
                                    (uint8_t *)RX_BOOTLOADER_UPDATE_EXECUTE_AREA_LOW_ADDRESS + RX_BOOTLOADER_FW_HEADER_LENGTH,
                                    (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER) - RX_BOOTLOADER_FW_HEADER_LENGTH);
                                tc_sha256_final(hash_sha256, &xCtx);
                                verification_result = memcmp(firmware_update_control_block_bank0->signature, hash_sha256, sizeof(hash_sha256));
                            }
                            else if (!strcmp((const char *)firmware_update_control_block_bank0->signature_type,
                                             INTEGRITY_CHECK_SCHEME_SIG_SHA256_ECDSA_STANDALONE))
                            {
                                verification_result = firmware_verification_sha256_ecdsa(
                                    (const uint8_t *)RX_BOOTLOADER_UPDATE_EXECUTE_AREA_LOW_ADDRESS + RX_BOOTLOADER_FW_HEADER_LENGTH,
                                    (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER) - RX_BOOTLOADER_FW_HEADER_LENGTH,
                                    firmware_update_control_block_bank0->signature,
                                    firmware_update_control_block_bank0->signature_size,
                                    local_code_signer_public_key);
                            }
                            else
                            {
                                verification_result = -1;
                            }

                            if (0 == verification_result)
                            {
                                printf("OK\r\n");
                                if (firmware_update_control_block_bank1->image_flag != LIFECYCLE_STATE_BLANK)
                                {
                                    printf("erase install area (code flash): ");
                                    flash_api_error_code = R_FLASH_Erase((flash_block_address_t)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_HIGH_ADDRESS,
                                                                         FLASH_NUM_BLOCKS_CF - RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_SMALL - RX_BOOTLOADER_MIRROR_BLOCK_NUM_FOR_MEDIUM);
                                    if (FLASH_SUCCESS != flash_api_error_code)
                                    {
                                        printf("R_FLASH_Erase() returns error. %d.\r\n", flash_error_code);
                                        printf("system error.\r\n");
                                        secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                        secure_boot_error_code = BOOT_LOADER_FAIL;
                                        break;
                                    }
                                    secure_boot_state = BOOT_LOADER_STATE_BANK1_UPDATE_CODE_FLASH_ERASE_WAIT;
                                }
                                else
                                {
#if RX_BOOTLOADER_USE_PERF_COUNTER
                                    printf("integrity check(parts of SHA256 process) needs %d us.\r\n", sha256_time);
                                    printf("integrity check(parts of ECDSA process) needs %d us.\r\n", ecdsa_time);
#endif
                                    secure_boot_state = BOOT_LOADER_STATE_FINALIZE;
                                }
                            }
                            else
                            {
                                printf("NG.\r\n");
                                printf("Code flash is completely broken.\r\n");
                                printf("Please erase all code flash.\r\n");
                                printf("And, write secure boot using debugger.\r\n");
                                secure_boot_state      = BOOT_LOADER_STATE_FATAL_ERROR;
                                secure_boot_error_code = BOOT_LOADER_FAIL;
                            }
                            break;

                        case BOOT_LOADER_STATE_BANK1_UPDATE_CODE_FLASH_ERASE_WAIT:
                            /* this state will be updated by flash callback */
                            break;

                        case BOOT_LOADER_STATE_BANK1_UPDATE_CODE_FLASH_ERASE_COMPLETE:
                            if (FLASH_SUCCESS == flash_error_code)
                            {
                                printf("OK\r\n");
                                secure_boot_state = BOOT_LOADER_STATE_FINALIZE;
                            }
                            else
                            {
                                printf("R_FLASH_Erase() callback error. %d.\r\n", flash_error_code);
                                printf("system error.\r\n");
                                secure_boot_state = BOOT_LOADER_STATE_FATAL_ERROR;
                            }
                            break;

                        case BOOT_LOADER_STATE_FINALIZE:
                            printf("jump to user program\r\n");
                            R_BSP_SoftwareDelay(1000, BSP_DELAY_MILLISECS);
                            secure_boot_error_code = BOOT_LOADER_SUCCESS;
                            break;
                    }
                    break;

                default:
                    printf("illegal flash rom status code 0x%x.\r\n", firmware_update_control_block_bank0->image_flag);
                    printf("integrity check scheme = %-.32s\r\n", firmware_update_control_block_bank1->signature_type);
                    printf("bank1(temporary area) on code flash integrity check...");

                    if (!strcmp((const char *)firmware_update_control_block_bank1->signature_type,
                                INTEGRITY_CHECK_SCHEME_HASH_SHA256_STANDALONE))
                    {
                        uint8_t hash_sha256[TC_SHA256_DIGEST_SIZE];
                        struct tc_sha256_state_struct xCtx;
                        tc_sha256_init(&xCtx);
                        tc_sha256_update(&xCtx,
                            (uint8_t *)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS + RX_BOOTLOADER_FW_HEADER_LENGTH,
                            (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER) - RX_BOOTLOADER_FW_HEADER_LENGTH);
                        tc_sha256_final(hash_sha256, &xCtx);
                        verification_result = memcmp(firmware_update_control_block_bank1->signature, hash_sha256, sizeof(hash_sha256));
                    }
                    else if (!strcmp((const char *)firmware_update_control_block_bank1->signature_type,
                                     INTEGRITY_CHECK_SCHEME_SIG_SHA256_ECDSA_STANDALONE))
                    {
                        verification_result = firmware_verification_sha256_ecdsa(
                            (const uint8_t *)RX_BOOTLOADER_UPDATE_TEMPORARY_AREA_LOW_ADDRESS + RX_BOOTLOADER_FW_HEADER_LENGTH,
                            (FLASH_CF_MEDIUM_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_TARGET_BLOCK_NUMBER) - RX_BOOTLOADER_FW_HEADER_LENGTH,
                            firmware_update_control_block_bank1->signature,
                            firmware_update_control_block_bank1->signature_size,
                            local_code_signer_public_key);
                    }
                    else
                    {
                        printf("This Firmware Verification Type is not implemented yet.\r\n");
                        verification_result = -1;
                    }

                    if (0 == verification_result)
                    {
                        printf("OK\r\n");
                        R_BSP_SoftwareDelay(1000, BSP_DELAY_MILLISECS);
                        bank_swap_with_software_reset();
                    }
                    else
                    {
                        printf("NG\r\n");
                        R_BSP_SoftwareDelay(1000, BSP_DELAY_MILLISECS);
                        software_reset();
                    }
                    break;
            }
    }
    return secure_boot_error_code;
}

/***********************************************************************************************************************
* Function Name: software_reset
***********************************************************************************************************************/
__STATIC void software_reset(void)
{
    set_psw(0);
    R_BSP_InterruptsDisable();
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_LPC_CGC_SWR);
    SYSTEM.SWRR = 0xa501;
    while (1);
}

/***********************************************************************************************************************
* Function Name: bank_swap_with_software_reset
***********************************************************************************************************************/
__STATIC void bank_swap_with_software_reset(void)
{
    set_psw(0);
    R_BSP_InterruptsDisable();
#if RX_BOOTLOADER_USE_DUAL_BANK
    R_FLASH_Control(FLASH_CMD_BANK_TOGGLE, NULL);
#endif
    R_BSP_RegisterProtectDisable(BSP_REG_PROTECT_LPC_CGC_SWR);
    SYSTEM.SWRR = 0xa501;
    while (1);
}

/***********************************************************************************************************************
* Function Name: firm_block_read
***********************************************************************************************************************/
__STATIC int32_t firm_block_read(uint32_t *firmware, uint32_t offset)
{
    int32_t error_code = -1;
    (void)offset;
    if (BOOT_LOADER_SCI_RECEIVE_BUFFER_FULL == sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer_full_flag)
    {
        memcpy(firmware, sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer, FLASH_CF_MEDIUM_BLOCK_SIZE);
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer_full_flag = BOOT_LOADER_SCI_RECEIVE_BUFFER_EMPTY;
        error_code = 0;
    }
    else if (BOOT_LOADER_SCI_RECEIVE_BUFFER_FULL == sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer_full_flag)
    {
        memcpy(firmware, sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer, FLASH_CF_MEDIUM_BLOCK_SIZE);
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer_full_flag = BOOT_LOADER_SCI_RECEIVE_BUFFER_EMPTY;
        error_code = 0;
    }
    return error_code;
}

/***********************************************************************************************************************
* Function Name: const_data_block_read
***********************************************************************************************************************/
__STATIC int32_t const_data_block_read(uint32_t *const_data, uint32_t offset)
{
    int32_t error_code = -1;
    (void)offset;
    if (BOOT_LOADER_SCI_RECEIVE_BUFFER_FULL == sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer_full_flag)
    {
        memcpy(const_data, sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer, RX_BOOTLOADER_CONST_DATA_TOTAL_SIZE);
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer_occupied_byte_size = 0;
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer_full_flag = BOOT_LOADER_SCI_RECEIVE_BUFFER_EMPTY;
        error_code = 0;
    }
    else if (sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer_occupied_byte_size >= RX_BOOTLOADER_CONST_DATA_TOTAL_SIZE)
    {
        memcpy(const_data, sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer, RX_BOOTLOADER_CONST_DATA_TOTAL_SIZE);
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer_occupied_byte_size = 0;
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A].buffer_full_flag = BOOT_LOADER_SCI_RECEIVE_BUFFER_EMPTY;
        error_code = 0;
    }
    else if (BOOT_LOADER_SCI_RECEIVE_BUFFER_FULL == sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer_full_flag)
    {
        memcpy(const_data, sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer, RX_BOOTLOADER_CONST_DATA_TOTAL_SIZE);
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer_occupied_byte_size = 0;
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer_full_flag = BOOT_LOADER_SCI_RECEIVE_BUFFER_EMPTY;
        error_code = 0;
    }
    else if (sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer_occupied_byte_size >= RX_BOOTLOADER_CONST_DATA_TOTAL_SIZE)
    {
        memcpy(const_data, sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer, RX_BOOTLOADER_CONST_DATA_TOTAL_SIZE);
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer_occupied_byte_size = 0;
        sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B].buffer_full_flag = BOOT_LOADER_SCI_RECEIVE_BUFFER_EMPTY;
        error_code = 0;
    }
    return error_code;
}

/***********************************************************************************************************************
* Function Name: sci_expected_receive_size
***********************************************************************************************************************/
__STATIC uint32_t sci_expected_receive_size(void)
{
    if ((BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_WAIT == secure_boot_state) ||
        (BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_COMPLETE == secure_boot_state) ||
        (BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_WAIT == secure_boot_state) ||
        (BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_COMPLETE == secure_boot_state))
    {
        return RX_BOOTLOADER_CONST_DATA_TOTAL_SIZE;
    }

    return FLASH_CF_MEDIUM_BLOCK_SIZE;
}

/***********************************************************************************************************************
* Function Name: my_sci_callback
* Description  : SCI async mode RX callback. Fills double-buffered receive queue.
***********************************************************************************************************************/
uint32_t error_count1 = 0;
uint32_t error_count2 = 0;
uint32_t rcv_count1   = 0;
uint32_t rcv_count2   = 0;

__STATIC void my_sci_callback(void *pArgs)
{
    sci_cb_args_t *p_args = (sci_cb_args_t *)pArgs;
    uint32_t expected_receive_size = sci_expected_receive_size();

    if (SCI_EVT_RX_CHAR == p_args->event)
    {
        if (sci_receive_control_block.p_sci_buffer_control->buffer_occupied_byte_size <
            expected_receive_size)
        {
            R_SCI_Receive(p_args->hdl,
                &sci_receive_control_block.p_sci_buffer_control->buffer[sci_receive_control_block.p_sci_buffer_control->buffer_occupied_byte_size++],
                1);
            if (sci_receive_control_block.p_sci_buffer_control->buffer_occupied_byte_size ==
                expected_receive_size)
            {
                sci_receive_control_block.p_sci_buffer_control->buffer_occupied_byte_size = 0;
                sci_receive_control_block.p_sci_buffer_control->buffer_full_flag          = BOOT_LOADER_SCI_RECEIVE_BUFFER_FULL;
                sci_receive_control_block.total_byte_size += expected_receive_size;
                if (BOOT_LOADER_SCI_CONTROL_BLOCK_A == sci_receive_control_block.current_state)
                {
                    sci_receive_control_block.current_state        = BOOT_LOADER_SCI_CONTROL_BLOCK_B;
                    sci_receive_control_block.p_sci_buffer_control = &sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_B];
                }
                else
                {
                    sci_receive_control_block.current_state        = BOOT_LOADER_SCI_CONTROL_BLOCK_A;
                    sci_receive_control_block.p_sci_buffer_control = &sci_buffer_control[BOOT_LOADER_SCI_CONTROL_BLOCK_A];
                }
            }
            rcv_count1++;
        }
        rcv_count2++;
    }
    else if (SCI_EVT_RXBUF_OVFL == p_args->event)
    {
        nop();
        error_count1++;
    }
    else if (SCI_EVT_OVFL_ERR == p_args->event)
    {
        nop();
        error_count2++;
    }
    else if (SCI_EVT_FRAMING_ERR == p_args->event)
    {
        nop();
    }
    else if (SCI_EVT_PARITY_ERR == p_args->event)
    {
        nop();
    }
}

/***********************************************************************************************************************
* Function Name: my_flash_callback
***********************************************************************************************************************/
__STATIC void my_flash_callback(void *event)
{
    uint32_t event_code = FLASH_ERR_FAILURE;
    event_code          = *((uint32_t *)event);

    flash_error_code = FLASH_ERR_FAILURE;
    if ((event_code == FLASH_INT_EVENT_WRITE_COMPLETE) || (event_code == FLASH_INT_EVENT_ERASE_COMPLETE))
    {
        flash_error_code = FLASH_SUCCESS;
    }

    switch (secure_boot_state)
    {
        case BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_ERASE_WAIT:
            secure_boot_state = BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_ERASE_COMPLETE; break;
        case BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_WRITE_WAIT:
            secure_boot_state = BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_WRITE_COMPLETE; break;
        case BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_ERASE_WAIT:
            secure_boot_state = BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_ERASE_COMPLETE; break;
        case BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_WAIT1:
            secure_boot_state = BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_COMPLETE1; break;
        case BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_WAIT2:
            secure_boot_state = BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_COMPLETE2; break;
        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_WAIT:
            secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_COMPLETE; break;
        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT1:
            secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_COMPLETE1; break;
        case BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT2:
            secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_COMPLETE2; break;
        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_ERASE_WAIT:
            secure_boot_state = BOOT_LOADER_STATE_INSTALL_DATA_FLASH_ERASE_COMPLETE; break;
        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_ERASE_WAIT:
            secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_ERASE_COMPLETE; break;
        case BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_WRITE_WAIT:
            secure_boot_state = BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_WRITE_COMPLETE; break;
        case BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_WAIT:
            secure_boot_state = BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_COMPLETE; break;
        case BOOT_LOADER_STATE_BANK1_UPDATE_CODE_FLASH_ERASE_WAIT:
            secure_boot_state = BOOT_LOADER_STATE_BANK1_UPDATE_CODE_FLASH_ERASE_COMPLETE; break;
        default:
            break;
    }
}

/***********************************************************************************************************************
* Function Name: my_sw_charput_function
* Description  : Default char output: sends one byte over the configured SCI channel (+ LCD if enabled).
*                NOTE: this waits for the SCI TX queue to drain using the configured SCI channel TX buffer size.
***********************************************************************************************************************/
void my_sw_charput_function(uint8_t data)
{
    uint32_t arg = 0;
    do
    {
        R_SCI_Control(my_sci_handle, SCI_CMD_TX_Q_BYTES_FREE, (void *)&arg);
    } while (SCI_CFG_serial_term_TX_BUFSIZ != arg);
    R_SCI_Send(my_sci_handle, (uint8_t *)&data, 1);
#if RX_BOOTLOADER_USE_LCD
    R_SIMPLE_GRAPHIC_PutCharacter(data);
#endif
}

/***********************************************************************************************************************
* Function Name: my_sw_charget_function
***********************************************************************************************************************/
void my_sw_charget_function(void)
{
}

/***********************************************************************************************************************
* Function Name: get_status_string
***********************************************************************************************************************/
__STATIC const uint8_t *get_status_string(uint8_t status)
{
    static const uint8_t status_string[][32] = {
        {"LIFECYCLE_STATE_BLANK"},
        {"LIFECYCLE_STATE_TESTING"},
        {"LIFECYCLE_STATE_INSTALLING"},
        {"LIFECYCLE_STATE_VALID"},
        {"LIFECYCLE_STATE_INVALID"},
        {"LIFECYCLE_STATE_UNKNOWN"},
    };
    const uint8_t *tmp;

    if (status == LIFECYCLE_STATE_BLANK)            tmp = status_string[0];
    else if (status == LIFECYCLE_STATE_TESTING)     tmp = status_string[1];
    else if (status == LIFECYCLE_STATE_INSTALLING)  tmp = status_string[2];
    else if (status == LIFECYCLE_STATE_VALID)       tmp = status_string[3];
    else if (status == LIFECYCLE_STATE_INVALID)     tmp = status_string[4];
    else                                            tmp = status_string[5];
    return tmp;
}

/***********************************************************************************************************************
* Function Name: firmware_verification_sha256_ecdsa
* Description  : Verifies ECDSA (P-256) signature over SHA-256 hash of the firmware body, using the PEM-encoded
*                public key supplied via the local_code_signer_public_key pointer.
***********************************************************************************************************************/
__STATIC int32_t firmware_verification_sha256_ecdsa(const uint8_t *pucData,
                                                    uint32_t       ulSize,
                                                    const uint8_t *pucSignature,
                                                    uint32_t       ulSignatureSize,
                                                    const uint8_t *local_code_signer_public_key)
{
    int32_t  xResult = -1;
    uint8_t  pucHash[TC_SHA256_DIGEST_SIZE];
    uint8_t  data_length;
    uint8_t  public_key[64];
    uint8_t  binary[256];
    uint8_t *head_pointer, *current_pointer, *tail_pointer;
    (void)ulSignatureSize;

    /* SHA256 hash of firmware body */
#if RX_BOOTLOADER_USE_PERF_COUNTER
    reset_10us_counter();
    start_10us_counter();
#endif
    {
        struct tc_sha256_state_struct xCtx;
        tc_sha256_init(&xCtx);
        tc_sha256_update(&xCtx, pucData, ulSize);
        tc_sha256_final(pucHash, &xCtx);
    }
#if RX_BOOTLOADER_USE_PERF_COUNTER
    stop_10us_counter();
    sha256_time = read_10us_counter() * 10;
#endif

    /* Extract public key from PEM-encoded blob */
    head_pointer = (uint8_t *)strstr((const char *)local_code_signer_public_key, "-----BEGIN PUBLIC KEY-----");
    if (head_pointer)
    {
        head_pointer += strlen("-----BEGIN PUBLIC KEY-----");
        tail_pointer = (uint8_t *)strstr((const char *)local_code_signer_public_key, "-----END PUBLIC KEY-----");
        base64_decode(head_pointer, binary, tail_pointer - head_pointer);
        current_pointer = binary;
        data_length     = *(current_pointer + 1);
        while (1)
        {
            switch (*current_pointer)
            {
                case 0x30: /* SEQUENCE */
                    current_pointer += 2;
                    break;
                case 0x03: /* BIT STRING (public key) */
                    if (*(current_pointer + 1) == 0x42)
                    {
                        memcpy(public_key, current_pointer + 4, 64);
#if RX_BOOTLOADER_USE_PERF_COUNTER
                        reset_10us_counter();
                        start_10us_counter();
#endif
                        if (uECC_verify(public_key, pucHash, TC_SHA256_DIGEST_SIZE, pucSignature, uECC_secp256r1()))
                        {
                            xResult = 0;
                        }
#if RX_BOOTLOADER_USE_PERF_COUNTER
                        stop_10us_counter();
                        ecdsa_time = read_10us_counter() * 10;
#endif
                    }
                    current_pointer += *(current_pointer + 1) + 2;
                    break;
                default:
                    current_pointer += *(current_pointer + 1) + 2;
                    break;
            }
            if ((current_pointer - binary) > data_length)
            {
                break;
            }
        }
    }
    return xResult;
}

#if RX_BOOTLOADER_USE_PERF_COUNTER
/***********************************************************************************************************************
* 10us performance counter (driven by r_cmt_rx periodic callback).
***********************************************************************************************************************/
void bootloader_software_timer_handler(void *arg)
{
    (void)arg;
    if (s_10us_counter_start_flag)
    {
        s_10us_counter++;
    }
}

__STATIC void     reset_10us_counter(void) { s_10us_counter = 0; }
__STATIC uint32_t read_10us_counter(void)  { return s_10us_counter; }
__STATIC void     start_10us_counter(void) { s_10us_counter_start_flag = 1; }
__STATIC void     stop_10us_counter(void)  { s_10us_counter_start_flag = 0; }
#endif /* RX_BOOTLOADER_USE_PERF_COUNTER */
