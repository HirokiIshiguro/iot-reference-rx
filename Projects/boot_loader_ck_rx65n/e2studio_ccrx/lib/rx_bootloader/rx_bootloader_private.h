/***********************************************************************************************************************
* File Name    : rx_bootloader_private.h
* Description  : Internal type definitions and constants for rx_bootloader.
*                Not intended for inclusion by application code.
*
*                Based on the RX65N-RSK boot_loader reference implementation
*                (amazon-freertos/projects/renesas/rx65n-rsk/e2studio/boot_loader/src/boot_loader.h).
***********************************************************************************************************************/

#ifndef RX_BOOTLOADER_PRIVATE_H
#define RX_BOOTLOADER_PRIVATE_H

#include <stdint.h>
#include "r_flash_rx_if.h"
#include "r_bsp_config.h"

/*---------------------------------------------------------------------------------------------------------------------*
 * Unit-test hook (controlled by defining UNITY_TEST in the test build)
 *---------------------------------------------------------------------------------------------------------------------*/
#if defined(UNITY_TEST)
#define __STATIC
#define __CONST
#else
#define __STATIC static
#define __CONST  const
#endif

/*---------------------------------------------------------------------------------------------------------------------*
 * Return codes
 *---------------------------------------------------------------------------------------------------------------------*/
#define BOOT_LOADER_SUCCESS         (0)
#define BOOT_LOADER_FAIL            (-1)
#define BOOT_LOADER_GOTO_INSTALL    (-2)
#define BOOT_LOADER_IN_PROGRESS     (-3)

/*---------------------------------------------------------------------------------------------------------------------*
 * State machine states
 *---------------------------------------------------------------------------------------------------------------------*/
#define BOOT_LOADER_STATE_INITIALIZING                              1
#define BOOT_LOADER_STATE_BANK1_CHECK                               2
#define BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_ERASE_WAIT         3
#define BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_ERASE_COMPLETE     4
#define BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_WRITE_WAIT         5
#define BOOT_LOADER_STATE_BANK1_UPDATE_LIFECYCLE_WRITE_COMPLETE     6
#define BOOT_LOADER_STATE_BANK0_CHECK                               7
#define BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_WAIT      8
#define BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_ERASE_COMPLETE  9
#define BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT1     10
#define BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_COMPLETE1 11
#define BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_WAIT2     12
#define BOOT_LOADER_STATE_BANK0_INSTALL_SECURE_BOOT_WRITE_COMPLETE2 13
#define BOOT_LOADER_STATE_INSTALL_DATA_FLASH_ERASE_WAIT             14
#define BOOT_LOADER_STATE_INSTALL_DATA_FLASH_ERASE_COMPLETE         15
#define BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_ERASE_WAIT       16
#define BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_ERASE_COMPLETE   17
#define BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_READ_WAIT        18
#define BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_READ_COMPLETE    19
#define BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_WRITE_WAIT       20
#define BOOT_LOADER_STATE_BANK0_INSTALL_CODE_FLASH_WRITE_COMPLETE   21
#define BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_WAIT              22
#define BOOT_LOADER_STATE_INSTALL_DATA_FLASH_READ_COMPLETE          23
#define BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_WAIT             24
#define BOOT_LOADER_STATE_INSTALL_DATA_FLASH_WRITE_COMPLETE         25
#define BOOT_LOADER_STATE_BANK0_UPDATE_CHECK                        26
#define BOOT_LOADER_STATE_BANK1_UPDATE_CODE_FLASH_ERASE_WAIT        27
#define BOOT_LOADER_STATE_BANK1_UPDATE_CODE_FLASH_ERASE_COMPLETE    28
#define BOOT_LOADER_STATE_FINALIZE                                  29
#define BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_ERASE_WAIT      30
#define BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_ERASE_COMPLETE  31
#define BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_WAIT1     32
#define BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_COMPLETE1 33
#define BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_WAIT2     34
#define BOOT_LOADER_STATE_BANK1_REFRESH_SECURE_BOOT_WRITE_COMPLETE2 35
#define BOOT_LOADER_STATE_FATAL_ERROR                               200

/*---------------------------------------------------------------------------------------------------------------------*
 * SCI receive control
 *---------------------------------------------------------------------------------------------------------------------*/
#define BOOT_LOADER_SCI_CONTROL_BLOCK_A         (0)
#define BOOT_LOADER_SCI_CONTROL_BLOCK_B         (1)
#define BOOT_LOADER_SCI_CONTROL_BLOCK_TOTAL_NUM (2)

#define BOOT_LOADER_SCI_RECEIVE_BUFFER_EMPTY    (0)
#define BOOT_LOADER_SCI_RECEIVE_BUFFER_FULL     (1)

/*---------------------------------------------------------------------------------------------------------------------*
 * Lifecycle states (written to the image_flag field of FIRMWARE_UPDATE_CONTROL_BLOCK)
 *---------------------------------------------------------------------------------------------------------------------*/
#define LIFECYCLE_STATE_BLANK       (0xff)
#define LIFECYCLE_STATE_TESTING     (0xfe)
#define LIFECYCLE_STATE_INSTALLING  (0xfc)
#define LIFECYCLE_STATE_VALID       (0xf8)
#define LIFECYCLE_STATE_INVALID     (0xf0)

/*---------------------------------------------------------------------------------------------------------------------*
 * Misc constants
 *---------------------------------------------------------------------------------------------------------------------*/
#define MAX_CHECK_DATAFLASH_AREA_RETRY_COUNT    (3)
#define SHA1_HASH_LENGTH_BYTE_SIZE              (20)

#define FLASH_DF_TOTAL_BLOCK_SIZE               (FLASH_DF_BLOCK_INVALID - FLASH_DF_BLOCK_0)
#define RX_BOOTLOADER_CONST_DATA_TOTAL_SIZE     (FLASH_DF_BLOCK_SIZE * RX_BOOTLOADER_UPDATE_CONST_DATA_TARGET_BLOCK_NUMBER)

/* The current const-data install state machine assembles the whole const-data image
 * into RAM before programming Data Flash. Keep the accepted UART payload within one
 * SCI receive buffer until the state machine is chunked. */
#if (RX_BOOTLOADER_CONST_DATA_TOTAL_SIZE > FLASH_CF_MEDIUM_BLOCK_SIZE)
    #error "RX bootloader const-data receive path currently requires const data <= FLASH_CF_MEDIUM_BLOCK_SIZE."
#endif

#define INTEGRITY_CHECK_SCHEME_HASH_SHA256_STANDALONE       "hash-sha256"
#define INTEGRITY_CHECK_SCHEME_SIG_SHA256_ECDSA_STANDALONE  "sig-sha256-ecdsa"

/*---------------------------------------------------------------------------------------------------------------------*
 * Internal structures
 *---------------------------------------------------------------------------------------------------------------------*/
typedef struct _load_firmware_control_block {
    uint32_t flash_buffer[FLASH_CF_MEDIUM_BLOCK_SIZE / 4];
    uint32_t offset;
    uint32_t progress;
} LOAD_FIRMWARE_CONTROL_BLOCK;

typedef struct _load_const_data_control_block {
    uint32_t flash_buffer[FLASH_DF_TOTAL_BLOCK_SIZE / 4];
    uint32_t offset;
    uint32_t progress;
} LOAD_CONST_DATA_CONTROL_BLOCK;

typedef struct _sci_buffer_control {
    uint8_t  buffer[FLASH_CF_MEDIUM_BLOCK_SIZE];
    uint32_t buffer_occupied_byte_size;
    uint32_t buffer_full_flag;
} SCI_BUFFER_CONTROL;

typedef struct _sci_receive_control_block {
    SCI_BUFFER_CONTROL * p_sci_buffer_control;
    uint32_t total_byte_size;
    uint32_t current_state;
} SCI_RECEIVE_CONTROL_BLOCK;

/* Firmware image header (placed at the top of each firmware image; 512 bytes total) */
typedef struct _firmware_update_control_block {
    uint8_t  magic_code[7];
    uint8_t  image_flag;
    uint8_t  signature_type[32];
    uint32_t signature_size;
    uint8_t  signature[256];
    uint32_t dataflash_flag;
    uint32_t dataflash_start_address;
    uint32_t dataflash_end_address;
    uint8_t  reserved1[200];
    uint32_t sequence_number;
    uint32_t start_address;
    uint32_t end_address;
    uint32_t execution_address;
    uint32_t hardware_id;
    uint8_t  reserved2[236];
} FIRMWARE_UPDATE_CONTROL_BLOCK;

/*---------------------------------------------------------------------------------------------------------------------*
 * SCI channel selection macros (driven by BSP_CFG_SCI_UART_TERMINAL_CHANNEL in r_bsp_config.h)
 *---------------------------------------------------------------------------------------------------------------------*/
#if !defined(BSP_CFG_SCI_UART_TERMINAL_CHANNEL)
#error "Error! Need to define BSP_CFG_SCI_UART_TERMINAL_CHANNEL in r_bsp_config.h"
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (0)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI0()
#define SCI_CH_serial_term          SCI_CH0
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH0_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (1)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI1()
#define SCI_CH_serial_term          SCI_CH1
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH1_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (2)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI2()
#define SCI_CH_serial_term          SCI_CH2
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH2_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (3)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI3()
#define SCI_CH_serial_term          SCI_CH3
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH3_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (4)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI4()
#define SCI_CH_serial_term          SCI_CH4
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH4_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (5)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI5()
#define SCI_CH_serial_term          SCI_CH5
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH5_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (6)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI6()
#define SCI_CH_serial_term          SCI_CH6
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH6_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (7)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI7()
#define SCI_CH_serial_term          SCI_CH7
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH7_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (8)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI8()
#define SCI_CH_serial_term          SCI_CH8
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH8_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (9)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI9()
#define SCI_CH_serial_term          SCI_CH9
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH9_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (10)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI10()
#define SCI_CH_serial_term          SCI_CH10
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH10_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (11)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI11()
#define SCI_CH_serial_term          SCI_CH11
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH11_TX_BUFSIZ
#elif BSP_CFG_SCI_UART_TERMINAL_CHANNEL == (12)
#define R_SCI_PinSet_serial_term()  R_SCI_PinSet_SCI12()
#define SCI_CH_serial_term          SCI_CH12
#define SCI_CFG_serial_term_TX_BUFSIZ  SCI_CFG_CH12_TX_BUFSIZ
#else
#error "Error! Invalid setting for BSP_CFG_SCI_UART_TERMINAL_CHANNEL in r_bsp_config.h"
#endif

#endif /* RX_BOOTLOADER_PRIVATE_H */
