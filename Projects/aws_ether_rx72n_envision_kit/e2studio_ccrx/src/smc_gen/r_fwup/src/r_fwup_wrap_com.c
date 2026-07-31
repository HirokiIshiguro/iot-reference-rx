/*
* Copyright (c) 2023-2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/
/**********************************************************************************************************************
 * File Name    : r_fwup_wrap_com.c
 * Description  : Functions for the Firmware update module.
 **********************************************************************************************************************
 * History : DD.MM.YYYY Version Description
 *         : 20.07.2023 2.00    First Release
 *         : 29.09.2023 2.01    Fixed log messages.
 *                              Add parameter checking.
 *                              Added arguments to R_FWUP_WriteImageProgram API.
 *         : 28.03.2024 2.02    Update wrapper functions.
 *         : 09.04.2024 2.03    Fixed wrapper function.
 *         : 15.10.2024 2.04    Fixed wrapper function.
 *         : 24.10.2025 2.05    V205 Release.
 *         : 23.01.2025 2.06    V206 Release.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "r_fwup_wrap_com.h"

/**********************************************************************************************************************
 Exported global variables
 *********************************************************************************************************************/
#if (FWUP_CFG_USER_DISABLE_INTERRUPT_ENABLED != 0)
void FWUP_CFG_USER_DISABLE_INTERRUPT_FUNCTION(void);
#endif /* (FWUP_CFG_USER_DISABLE_INTERRUPT_ENABLED != 0) */

#if (FWUP_CFG_USER_ENABLE_INTERRUPT_ENABLED != 0)
void FWUP_CFG_USER_ENABLE_INTERRUPT_FUNCTION(void);
#endif /* (FWUP_CFG_USER_ENABLE_INTERRUPT_ENABLED != 0) */

#if (FWUP_CFG_USER_SOFTWARE_RESET_ENABLED != 0)
void FWUP_CFG_USER_SOFTWARE_RESET_FUNCTION(void);
#endif /* (FWUP_CFG_USER_SOFTWARE_RESET_ENABLED != 0) */

#if (FWUP_CFG_USER_SOFTWARE_DELAY_ENABLED != 0)
uint32_t FWUP_CFG_USER_SOFTWARE_DELAY_FUNCTION(uint32_t delay, e_fwup_delay_units_t units);
#endif /* (FWUP_CFG_USER_SOFTWARE_DELAY_ENABLED != 0) */

/*
 * Common functions
 */
/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_disable_interrupt
 * Description  : wrapper function for disable interrupts
 * Arguments    : none
 * Return Value : none
 *********************************************************************************************************************/
void r_fwup_wrap_disable_interrupt(void)
{
#if (FWUP_CFG_USER_DISABLE_INTERRUPT_ENABLED == 1)
    FWUP_CFG_USER_DISABLE_INTERRUPT_FUNCTION();
#else
    R_BSP_InterruptsDisable();
#endif /* (FWUP_CFG_USER_DISABLE_INTERRUPT_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_disable_interrupt
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_enable_interrupt
 * Description  : wrapper function for enable interrupts
 * Arguments    : none
 * Return Value : none
 *********************************************************************************************************************/
void r_fwup_wrap_enable_interrupt(void)
{
#if (FWUP_CFG_USER_ENABLE_INTERRUPT_ENABLED == 1)
    FWUP_CFG_USER_ENABLE_INTERRUPT_FUNCTION();
#else /* (FWUP_CFG_USER_ENABLE_INTERRUPT_ENABLED == 1) */
    R_BSP_InterruptsEnable();
#endif /* (FWUP_CFG_USER_ENABLE_INTERRUPT_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_enable_interrupt
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_software_reset
 * Description  : wrapper function for execute software reset.
 * Arguments    : none
 * Return Value : none
 *********************************************************************************************************************/
void r_fwup_wrap_software_reset(void)
{
#if (FWUP_CFG_USER_SOFTWARE_RESET_ENABLED == 1)
    FWUP_CFG_USER_SOFTWARE_RESET_FUNCTION();
#else
    r_fwup_wrap_disable_interrupt();
    r_fwup_wrap_software_delay(1000, FWUP_DELAY_MILLISECS);

    /* SW Reset */
    R_BSP_SoftwareReset();
#endif /* (FWUP_CFG_USER_SOFTWARE_RESET_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_software_reset
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Function Name: r_fwup_wrap_software_delay
 * Description  : wrapper function for execute software delay.
 * Arguments    : delay : delay count
 *                units : FWUP_DELAY_MICROSECS/FWUP_DELAY_MILLISECS/FWUP_DELAY_SECS
 * Return Value : 1     : success
 *                other : error
 *********************************************************************************************************************/
uint32_t r_fwup_wrap_software_delay(uint32_t delay, e_fwup_delay_units_t units)
{
#if (FWUP_CFG_USER_SOFTWARE_DELAY_ENABLED == 1)
    return FWUP_CFG_USER_SOFTWARE_DELAY_FUNCTION(delay, units);
#else
    uint32_t  time_units;

    if (FWUP_DELAY_MICROSECS == units)
    {
        time_units = BSP_DELAY_MICROSECS;
    }
    else if (FWUP_DELAY_MILLISECS == units)
    {
        time_units = BSP_DELAY_MILLISECS;
    }
    else
    {
        time_units = BSP_DELAY_SECS;
    }
    return ((uint32_t)R_BSP_SoftwareDelay(delay, (bsp_delay_units_t)time_units));
#endif /* (FWUP_CFG_USER_SOFTWARE_DELAY_ENABLED == 1) */
}
/**********************************************************************************************************************
 End of function r_fwup_wrap_software_delay
 *********************************************************************************************************************/
