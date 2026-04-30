/***********************************************************************************************************************
* File Name    : rx_bootloader.h
* Description  : Public API for the RX family secure boot loader submodule.
***********************************************************************************************************************/

#ifndef RX_BOOTLOADER_H
#define RX_BOOTLOADER_H

#include <stdint.h>
#include "rx_bootloader_config.h"

#ifdef __cplusplus
extern "C" {
#endif

/***********************************************************************************************************************
* Function Name: rx_bootloader_main
* Description  : Bootloader entry point. Call this from the application's main().
*                This function does not return under normal operation; on successful verification it jumps to the
*                user program's reset vector.
* Arguments    : none
* Return Value : none
***********************************************************************************************************************/
void rx_bootloader_main(void);

/***********************************************************************************************************************
* Weak hooks that the application may override.
* Default implementations write to / read from the configured SCI channel.
***********************************************************************************************************************/
extern void my_sw_charput_function(uint8_t data);
extern void my_sw_charget_function(void);

#ifdef __cplusplus
}
#endif

#endif /* RX_BOOTLOADER_H */
