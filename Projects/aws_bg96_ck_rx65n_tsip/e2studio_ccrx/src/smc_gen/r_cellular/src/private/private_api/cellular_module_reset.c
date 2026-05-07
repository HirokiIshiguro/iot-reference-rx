/**********************************************************************************************************************
 * DISCLAIMER
 * This software is supplied by Renesas Electronics Corporation and is only intended for use with Renesas products. No
 * other uses are authorized. This software is owned by Renesas Electronics Corporation and is protected under all
 * applicable laws, including copyright laws.
 * THIS SOFTWARE IS PROVIDED "AS IS" AND RENESAS MAKES NO WARRANTIES REGARDING
 * THIS SOFTWARE, WHETHER EXPRESS, IMPLIED OR STATUTORY, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. ALL SUCH WARRANTIES ARE EXPRESSLY DISCLAIMED. TO THE MAXIMUM
 * EXTENT PERMITTED NOT PROHIBITED BY LAW, NEITHER RENESAS ELECTRONICS CORPORATION NOR ANY OF ITS AFFILIATED COMPANIES
 * SHALL BE LIABLE FOR ANY DIRECT, INDIRECT, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES FOR ANY REASON RELATED TO
 * THIS SOFTWARE, EVEN IF RENESAS OR ITS AFFILIATES HAVE BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
 * Renesas reserves the right, without notice, to make changes to this software and to discontinue the availability of
 * this software. By using this software, you agree to the additional terms and conditions found by accessing the
 * following link:
 * http://www.renesas.com/disclaimer
 *
 * Copyright (C) 2024 Renesas Electronics Corporation. All rights reserved.
 *********************************************************************************************************************/
/**********************************************************************************************************************
 * File Name    : cellular_module_reset.c
 * Description  : Function to reset the module.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include <stdio.h>

#include "cellular_private_api.h"
#include "at_command.h"
#include "cellular_freertos.h"
#include "bg96_private.h"

/**********************************************************************************************************************
 * Macro definitions
 *********************************************************************************************************************/
#define CELLULAR_TASK_LIMIT         (1000)
#define CELLULAR_RESTART_LIMIT      (100)
#define BG96_READY_POLL_INTERVAL_MS (250U)
#define BG96_READY_WAIT_MS          (8000U)
#define BG96_STATUS_READY_WAIT_MS   (15000U)
#define BG96_BOOT_URC_QUIET_MS      (3000U)
#define BG96_PWRKEY_PULSE_MS        (700U)
#define BG96_RESET_PULSE_MS         (300U)

/**********************************************************************************************************************
 * Typedef definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Exported global variables
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Private (static) variables and functions
 *********************************************************************************************************************/
#if defined(CELLULAR_TARGET_BG96)
static void             cellular_bg96_prepare_pins (void);
static void             cellular_bg96_pulse_pwrkey (void);
static void             cellular_bg96_pulse_reset (void);
static e_cellular_err_t cellular_bg96_ensure_running (st_cellular_ctrl_t * const p_ctrl);
static e_cellular_err_t cellular_bg96_pwrkey_recovery (st_cellular_ctrl_t * const p_ctrl);
static e_cellular_err_t cellular_bg96_quick_ate0 (st_cellular_ctrl_t * const p_ctrl, uint32_t timeout_ms);
static e_cellular_err_t cellular_bg96_wait_ready_ate0 (st_cellular_ctrl_t * const p_ctrl, uint32_t wait_ms);
static uint8_t          cellular_bg96_status_is_running (void);
static uint8_t          cellular_bg96_wait_status_running (uint32_t wait_ms);
static e_cellular_err_t cellular_bg96_reset_n_recovery (st_cellular_ctrl_t * const p_ctrl);
static e_cellular_err_t cellular_baud_upgrade (st_cellular_ctrl_t * const p_ctrl, uint32_t new_baud);
#else
static e_cellular_err_t cellular_pin_reset (st_cellular_ctrl_t * const p_ctrl);
#endif

/************************************************************************
 * Function Name  @fn            cellular_module_reset
 ***********************************************************************/
e_cellular_err_t cellular_module_reset(st_cellular_ctrl_t * const p_ctrl)
{
    uint16_t                           cnt           = 0;
    e_cellular_err_t                   ret           = CELLULAR_ERR_MODULE_TIMEOUT;
    e_cellular_err_semaphore_t         semaphore_ret = CELLULAR_SEMAPHORE_ERR_TAKE;
    volatile e_cellular_auto_connect_t type          = CELLULAR_DISABLE_AUTO_CONNECT;

    /* WAIT_LOOP */
    for (cnt = CELLULAR_START_SOCKET_NUMBER; cnt <= p_ctrl->creatable_socket; cnt++)
    {
        ret = cellular_shutdownsocket(p_ctrl, (uint8_t)cnt);    //cast
        if (CELLULAR_SUCCESS != ret)
        {
            cnt = p_ctrl->creatable_socket;
        }
    }

    /* WAIT_LOOP */
    for (cnt = CELLULAR_START_SOCKET_NUMBER; cnt <= p_ctrl->creatable_socket; cnt++)
    {
        ret = cellular_closesocket(p_ctrl, (uint8_t)cnt);       //cast
    }

    if (CELLULAR_PSM_ACTIVE == p_ctrl->ring_ctrl.psm)
    {
        /* WAIT_LOOP */
        while (1)
        {
            semaphore_ret = cellular_take_semaphore(p_ctrl->ring_ctrl.rts_semaphore);
            if (CELLULAR_SEMAPHORE_SUCCESS == semaphore_ret)
            {
                break;
            }
            else
            {
                cellular_delay_task(1);
            }
        }
#if CELLULAR_CFG_CTS_SW_CTRL == 1
        cellular_rts_hw_flow_enable();
#else
        cellular_rts_ctrl(0);
#endif
#ifdef CELLULAR_RTS_DELAY
        cellular_delay_task(CELLULAR_RTS_DELAYTIME);
#endif
    }

    if (CELLULAR_PSM_ACTIVE == p_ctrl->ring_ctrl.psm)
    {
#if CELLULAR_CFG_CTS_SW_CTRL == 1
        cellular_rts_hw_flow_disable();
#endif
        cellular_rts_ctrl(1);
        cellular_give_semaphore(p_ctrl->ring_ctrl.rts_semaphore);
    }

#if defined(CELLULAR_TARGET_BG96)
    (void) type;
    p_ctrl->recv_data = NULL;
    cellular_bg96_prepare_pins();
    p_ctrl->module_status    = CELLULAR_MODULE_OPERATING_RESET;
    p_ctrl->sci_ctrl.atc_flg = CELLULAR_ATC_RESPONSE_CONFIRMED;

    if (0U == cellular_bg96_status_is_running())
    {
        ret = cellular_bg96_ensure_running(p_ctrl);
        if (CELLULAR_SUCCESS != ret)
        {
            p_ctrl->recv_data = NULL;
            return ret;
        }
    }

    semaphore_ret = cellular_take_semaphore(p_ctrl->at_semaphore);
    if (CELLULAR_SEMAPHORE_SUCCESS != semaphore_ret)
    {
        p_ctrl->recv_data = NULL;
        return CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING;
    }

    ret = cellular_bg96_quick_ate0(p_ctrl, 3000u);

    if (CELLULAR_SUCCESS != ret)
    {
#if CELLULAR_BAUDRATE_TARGET != CELLULAR_BAUDRATE
        CELLULAR_LOG_INFO(("ATE0 at %lu bps timed out - probing %lu bps.",
                           (unsigned long)p_ctrl->sci_ctrl.baud_rate,
                           (unsigned long)CELLULAR_BAUDRATE_TARGET));
        ret = cellular_serial_reopen(p_ctrl, CELLULAR_BAUDRATE_TARGET);
        if (CELLULAR_SUCCESS == ret)
        {
            cellular_delay_task(500);
            ret = cellular_bg96_quick_ate0(p_ctrl, 3000U);
        }
#endif
    }

    if (CELLULAR_SUCCESS != ret)
    {
        CELLULAR_LOG_INFO(("ATE0 probes failed - issuing BG96 control pulse."));
        ret = cellular_bg96_ensure_running(p_ctrl);
        if (CELLULAR_SUCCESS == ret)
        {
            ret = cellular_bg96_wait_ready_ate0(p_ctrl, BG96_READY_WAIT_MS);
        }

#if CELLULAR_BAUDRATE_TARGET != CELLULAR_BAUDRATE
        if (CELLULAR_SUCCESS != ret)
        {
            CELLULAR_LOG_INFO(("ATE0 after control pulse at %lu bps timed out - probing %lu bps.",
                               (unsigned long)p_ctrl->sci_ctrl.baud_rate,
                               (unsigned long)CELLULAR_BAUDRATE_TARGET));
            ret = cellular_serial_reopen(p_ctrl, CELLULAR_BAUDRATE_TARGET);
            if (CELLULAR_SUCCESS == ret)
            {
                cellular_delay_task(500);
                ret = cellular_bg96_wait_ready_ate0(p_ctrl, BG96_READY_WAIT_MS);
            }
        }
#endif
    }

    if (CELLULAR_SUCCESS != ret)
    {
        CELLULAR_LOG_INFO(("BG96 still silent after status-based recovery - issuing PWRKEY fallback pulse."));
        ret = cellular_bg96_pwrkey_recovery(p_ctrl);
        if (CELLULAR_SUCCESS == ret)
        {
            ret = cellular_bg96_wait_ready_ate0(p_ctrl, BG96_READY_WAIT_MS);
        }

#if CELLULAR_BAUDRATE_TARGET != CELLULAR_BAUDRATE
        if (CELLULAR_SUCCESS != ret)
        {
            CELLULAR_LOG_INFO(("ATE0 after PWRKEY fallback at %lu bps timed out - probing %lu bps.",
                               (unsigned long)p_ctrl->sci_ctrl.baud_rate,
                               (unsigned long)CELLULAR_BAUDRATE_TARGET));
            ret = cellular_serial_reopen(p_ctrl, CELLULAR_BAUDRATE_TARGET);
            if (CELLULAR_SUCCESS == ret)
            {
                cellular_delay_task(500);
                ret = cellular_bg96_wait_ready_ate0(p_ctrl, BG96_READY_WAIT_MS);
            }
        }
#endif
    }

#if CELLULAR_BAUDRATE_TARGET != CELLULAR_BAUDRATE
    if ((CELLULAR_SUCCESS == ret) && (p_ctrl->sci_ctrl.baud_rate == CELLULAR_BAUDRATE))
    {
        ret = cellular_baud_upgrade(p_ctrl, CELLULAR_BAUDRATE_TARGET);
    }
#endif

    if (CELLULAR_SUCCESS == ret)
    {
        ret = atc_cfun(p_ctrl, CELLULAR_MODULE_OPERATING_LEVEL4);
    }

    cellular_give_semaphore(p_ctrl->at_semaphore);

    if ((CELLULAR_SUCCESS == ret) &&
        (CELLULAR_SYSTEM_CLOSE != p_ctrl->system_state) &&
        (CELLULAR_SYSTEM_OPEN != p_ctrl->system_state))
    {
        p_ctrl->system_state = CELLULAR_SYSTEM_OPEN;
    }

    p_ctrl->recv_data = NULL;
    return ret;
#else
    ret = cellular_pin_reset(p_ctrl);

    if (CELLULAR_SUCCESS == ret)
    {
        semaphore_ret = cellular_take_semaphore(p_ctrl->at_semaphore);
        if (CELLULAR_SEMAPHORE_SUCCESS == semaphore_ret)
        {
            p_ctrl->recv_data = (void *) &type; //cast
            ret               = atc_sqnautoconnect_check(p_ctrl);
            if ((CELLULAR_SUCCESS == ret) && (CELLULAR_DISABLE_AUTO_CONNECT == type))
            {
                ret = atc_cfun(p_ctrl, CELLULAR_MODULE_OPERATING_LEVEL4);
            }

            cellular_give_semaphore(p_ctrl->at_semaphore);
        }
        else
        {
            ret = CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING;
        }
    }

    p_ctrl->recv_data = NULL;

    return ret;
#endif
}
/**********************************************************************************************************************
 * End of function cellular_module_reset
 *********************************************************************************************************************/

#if defined(CELLULAR_TARGET_BG96)
/************************************************************************
 * Function Name  @fn            cellular_bg96_prepare_pins
 ***********************************************************************/
static void cellular_bg96_prepare_pins(void)
{
#if CELLULAR_CFG_BG96_POWER_ENABLE == 1
    CELLULAR_SET_PMR(CELLULAR_CFG_BG96_POWER_ENABLE_PORT, CELLULAR_CFG_BG96_POWER_ENABLE_PIN) = 0U;
    CELLULAR_SET_PDR(CELLULAR_CFG_BG96_POWER_ENABLE_PORT, CELLULAR_CFG_BG96_POWER_ENABLE_PIN) =
            CELLULAR_PIN_DIRECTION_MODE_OUTPUT;
    CELLULAR_SET_PODR(CELLULAR_CFG_BG96_POWER_ENABLE_PORT, CELLULAR_CFG_BG96_POWER_ENABLE_PIN) =
            CELLULAR_CFG_BG96_POWER_ENABLE_ACTIVE_LEVEL;
    cellular_delay_task(30);
#endif

    CELLULAR_SET_PMR(CELLULAR_CFG_RESET_PORT, CELLULAR_CFG_RESET_PIN) = 0U;
    CELLULAR_SET_PDR(CELLULAR_CFG_RESET_PORT, CELLULAR_CFG_RESET_PIN) = CELLULAR_PIN_DIRECTION_MODE_OUTPUT;
    CELLULAR_SET_PODR(CELLULAR_CFG_RESET_PORT, CELLULAR_CFG_RESET_PIN) = CELLULAR_CFG_RESET_SIGNAL_OFF;

    CELLULAR_SET_PMR(CELLULAR_CFG_BG96_PWRKEY_PORT, CELLULAR_CFG_BG96_PWRKEY_PIN) = 0U;
    CELLULAR_SET_PDR(CELLULAR_CFG_BG96_PWRKEY_PORT, CELLULAR_CFG_BG96_PWRKEY_PIN) = CELLULAR_PIN_DIRECTION_MODE_OUTPUT;
    CELLULAR_SET_PODR(CELLULAR_CFG_BG96_PWRKEY_PORT, CELLULAR_CFG_BG96_PWRKEY_PIN) =
            (uint8_t)!CELLULAR_CFG_BG96_PWRKEY_ACTIVE_LEVEL;

    CELLULAR_SET_PMR(CELLULAR_CFG_RTS_PORT, CELLULAR_CFG_RTS_PIN) = 0U;
    CELLULAR_SET_PDR(CELLULAR_CFG_RTS_PORT, CELLULAR_CFG_RTS_PIN) = CELLULAR_PIN_DIRECTION_MODE_OUTPUT;
    CELLULAR_SET_PODR(CELLULAR_CFG_RTS_PORT, CELLULAR_CFG_RTS_PIN) = CELLULAR_CFG_BG96_RTS_IDLE_LEVEL;

#if CELLULAR_CFG_BG96_DTR_ENABLE == 1
    CELLULAR_SET_PMR(CELLULAR_CFG_BG96_DTR_PORT, CELLULAR_CFG_BG96_DTR_PIN) = 0U;
    CELLULAR_SET_PDR(CELLULAR_CFG_BG96_DTR_PORT, CELLULAR_CFG_BG96_DTR_PIN) = CELLULAR_PIN_DIRECTION_MODE_OUTPUT;
    CELLULAR_SET_PODR(CELLULAR_CFG_BG96_DTR_PORT, CELLULAR_CFG_BG96_DTR_PIN) = CELLULAR_CFG_BG96_DTR_IDLE_LEVEL;
#endif

    CELLULAR_SET_PMR(CELLULAR_CFG_BG96_STATUS_PORT, CELLULAR_CFG_BG96_STATUS_PIN) = 0U;
    CELLULAR_SET_PDR(CELLULAR_CFG_BG96_STATUS_PORT, CELLULAR_CFG_BG96_STATUS_PIN) = CELLULAR_PIN_DIRECTION_MODE_INPUT;
}

/************************************************************************
 * Function Name  @fn            cellular_bg96_pulse_pwrkey
 ***********************************************************************/
static void cellular_bg96_pulse_pwrkey(void)
{
    CELLULAR_SET_PODR(CELLULAR_CFG_BG96_PWRKEY_PORT, CELLULAR_CFG_BG96_PWRKEY_PIN) =
            CELLULAR_CFG_BG96_PWRKEY_ACTIVE_LEVEL;
    cellular_delay_task(BG96_PWRKEY_PULSE_MS);
    CELLULAR_SET_PODR(CELLULAR_CFG_BG96_PWRKEY_PORT, CELLULAR_CFG_BG96_PWRKEY_PIN) =
            (uint8_t)!CELLULAR_CFG_BG96_PWRKEY_ACTIVE_LEVEL;
}

/************************************************************************
 * Function Name  @fn            cellular_bg96_pulse_reset
 ***********************************************************************/
static void cellular_bg96_pulse_reset(void)
{
    CELLULAR_SET_PODR(CELLULAR_CFG_RESET_PORT, CELLULAR_CFG_RESET_PIN) = CELLULAR_CFG_RESET_SIGNAL_ON;
    cellular_delay_task(BG96_RESET_PULSE_MS);
    CELLULAR_SET_PODR(CELLULAR_CFG_RESET_PORT, CELLULAR_CFG_RESET_PIN) = CELLULAR_CFG_RESET_SIGNAL_OFF;
}

/************************************************************************
 * Function Name  @fn            cellular_bg96_quick_ate0
 ***********************************************************************/
static e_cellular_err_t cellular_bg96_quick_ate0(st_cellular_ctrl_t * const p_ctrl, uint32_t timeout_ms)
{
    e_cellular_err_t ret = CELLULAR_SUCCESS;
    uint32_t saved_atc_timeout = p_ctrl->sci_ctrl.atc_timeout;

    p_ctrl->recv_data = NULL;
    p_ctrl->sci_ctrl.atc_timeout = timeout_ms;
    ret = atc_ate0(p_ctrl);
    p_ctrl->sci_ctrl.atc_timeout = saved_atc_timeout;

    return ret;
}

/************************************************************************
 * Function Name  @fn            cellular_bg96_wait_ready_ate0
 ***********************************************************************/
static e_cellular_err_t cellular_bg96_wait_ready_ate0(st_cellular_ctrl_t * const p_ctrl, uint32_t wait_ms)
{
    e_cellular_err_t ret = CELLULAR_ERR_MODULE_TIMEOUT;
    uint32_t elapsed_ms = 0U;

    while (elapsed_ms < wait_ms)
    {
        ret = cellular_bg96_quick_ate0(p_ctrl, 300U);
        if (CELLULAR_SUCCESS == ret)
        {
            return ret;
        }

        cellular_delay_task(BG96_READY_POLL_INTERVAL_MS);
        elapsed_ms += BG96_READY_POLL_INTERVAL_MS;
    }

    return ret;
}

/************************************************************************
 * Function Name  @fn            cellular_bg96_status_is_running
 ***********************************************************************/
static uint8_t cellular_bg96_status_is_running(void)
{
    return (uint8_t)(CELLULAR_GET_PIDR(CELLULAR_CFG_BG96_STATUS_PORT, CELLULAR_CFG_BG96_STATUS_PIN) ==
                     CELLULAR_CFG_BG96_STATUS_RUNNING_LEVEL);
}

/************************************************************************
 * Function Name  @fn            cellular_bg96_ensure_running
 ***********************************************************************/
static e_cellular_err_t cellular_bg96_ensure_running(st_cellular_ctrl_t * const p_ctrl)
{
    uint32_t cnt = 0U;
    e_cellular_err_t ret = CELLULAR_SUCCESS;

    p_ctrl->recv_data = NULL;
    cellular_serial_close(p_ctrl);

    CELLULAR_LOG_INFO(("BG96 STATUS sampled as %u before control pulse",
                       (unsigned int) cellular_bg96_status_is_running()));

    if (0U != cellular_bg96_status_is_running())
    {
        CELLULAR_LOG_INFO(("BG96 STATUS indicates running - issuing RESET_N pulse"));
        cellular_bg96_pulse_reset();
    }
    else
    {
        CELLULAR_LOG_INFO(("BG96 STATUS indicates stopped - issuing PWRKEY start pulse"));
        cellular_bg96_pulse_pwrkey();
    }

    CELLULAR_LOG_INFO(("BG96 control pulse complete - waiting for STATUS running"));

    while (cnt < BG96_STATUS_READY_WAIT_MS)
    {
        if (0U != cellular_bg96_status_is_running())
        {
            CELLULAR_LOG_INFO(("BG96 STATUS running observed after %lu ms.", (unsigned long) cnt));
            cellular_delay_task(BG96_BOOT_URC_QUIET_MS);
            p_ctrl->module_status    = CELLULAR_MODULE_OPERATING_RESET;
            p_ctrl->sci_ctrl.atc_flg = CELLULAR_ATC_RESPONSE_CONFIRMED;
            p_ctrl->sci_ctrl.baud_rate = CELLULAR_BAUDRATE;
            ret = cellular_serial_open(p_ctrl);
            if (CELLULAR_SUCCESS != ret)
            {
                CELLULAR_LOG_ERROR(("BG96 SCI reopen failed after boot quiet."));
            }
            return ret;
        }

        cellular_delay_task(1);
        cnt++;
    }

    CELLULAR_LOG_ERROR(("BG96 control pulse failed: STATUS did not become running."));
    p_ctrl->sci_ctrl.baud_rate = CELLULAR_BAUDRATE;
    (void) cellular_serial_open(p_ctrl);
    return CELLULAR_ERR_RECV_TASK;
}

/************************************************************************
 * Function Name  @fn            cellular_bg96_pwrkey_recovery
 ***********************************************************************/
static e_cellular_err_t cellular_bg96_pwrkey_recovery(st_cellular_ctrl_t * const p_ctrl)
{
    e_cellular_err_t ret = CELLULAR_SUCCESS;

    p_ctrl->recv_data = NULL;
    cellular_serial_close(p_ctrl);

    cellular_bg96_pulse_pwrkey();
    cellular_delay_task(BG96_BOOT_URC_QUIET_MS);

    p_ctrl->module_status    = CELLULAR_MODULE_OPERATING_RESET;
    p_ctrl->sci_ctrl.atc_flg = CELLULAR_ATC_RESPONSE_CONFIRMED;
    p_ctrl->sci_ctrl.baud_rate = CELLULAR_BAUDRATE;
    ret = cellular_serial_open(p_ctrl);
    if (CELLULAR_SUCCESS != ret)
    {
        CELLULAR_LOG_ERROR(("BG96 SCI reopen failed after PWRKEY fallback."));
    }

    return ret;
}

/************************************************************************
 * Function Name  @fn            cellular_bg96_wait_status_running
 ***********************************************************************/
static uint8_t cellular_bg96_wait_status_running(uint32_t wait_ms)
{
    uint32_t elapsed_ms = 0U;

    while (elapsed_ms < wait_ms)
    {
        if (0U != cellular_bg96_status_is_running())
        {
            return 1U;
        }

        cellular_delay_task(BG96_READY_POLL_INTERVAL_MS);
        elapsed_ms += BG96_READY_POLL_INTERVAL_MS;
    }

    return 0U;
}

/************************************************************************
 * Function Name  @fn            cellular_bg96_reset_n_recovery
 ***********************************************************************/
static e_cellular_err_t cellular_bg96_reset_n_recovery(st_cellular_ctrl_t * const p_ctrl)
{
    e_cellular_err_t ret = CELLULAR_SUCCESS;

    cellular_serial_close(p_ctrl);
    cellular_bg96_pulse_reset();

    if (0U == cellular_bg96_wait_status_running(BG96_STATUS_READY_WAIT_MS))
    {
        ret = CELLULAR_ERR_RECV_TASK;
    }
    else
    {
        CELLULAR_LOG_INFO(("BG96 RESET_N recovery observed STATUS running."));
        cellular_delay_task(BG96_BOOT_URC_QUIET_MS);
        p_ctrl->module_status    = CELLULAR_MODULE_OPERATING_RESET;
        p_ctrl->sci_ctrl.atc_flg = CELLULAR_ATC_RESPONSE_CONFIRMED;
        p_ctrl->sci_ctrl.baud_rate = CELLULAR_BAUDRATE;
        ret = cellular_serial_open(p_ctrl);
    }

    return ret;
}

/************************************************************************
 * Function Name  @fn            cellular_baud_upgrade
 ***********************************************************************/
static e_cellular_err_t cellular_baud_upgrade(st_cellular_ctrl_t * const p_ctrl, uint32_t new_baud)
{
    e_cellular_err_t ret = CELLULAR_SUCCESS;
    uint32_t         saved_atc_timeout = 0;

    if (p_ctrl->sci_ctrl.baud_rate == new_baud)
    {
        return CELLULAR_SUCCESS;
    }

    memset(p_ctrl->sci_ctrl.atc_buff, 0x00, CELLULAR_ATC_BUFF_SIZE);
    (void) snprintf((char *)p_ctrl->sci_ctrl.atc_buff,
                    CELLULAR_ATC_BUFF_SIZE,
                    "AT+IPR=%lu\r",
                    (unsigned long)new_baud);

    ret = cellular_execute_at_command(p_ctrl,
                                      p_ctrl->sci_ctrl.atc_timeout,
                                      ATC_RETURN_OK,
                                      ATC_ECHO_OFF);
    if (CELLULAR_SUCCESS != ret)
    {
        return ret;
    }

    cellular_delay_task(100);

    ret = cellular_serial_reopen(p_ctrl, new_baud);
    if (CELLULAR_SUCCESS != ret)
    {
        return ret;
    }

    cellular_delay_task(500);

    saved_atc_timeout = p_ctrl->sci_ctrl.atc_timeout;
    p_ctrl->sci_ctrl.atc_timeout = 3000u;
    ret = atc_ate0(p_ctrl);
    p_ctrl->sci_ctrl.atc_timeout = saved_atc_timeout;

    return ret;
}
#else
/************************************************************************
 * Function Name  @fn            cellular_pin_reset
 ***********************************************************************/
static e_cellular_err_t cellular_pin_reset(st_cellular_ctrl_t * const p_ctrl)
{
    volatile uint8_t flg = CELLULAR_FLG_OFF;
    uint16_t         cnt = 0;
    e_cellular_err_t ret = CELLULAR_SUCCESS;

    p_ctrl->recv_data = (void *) &flg; //(&uint8_t)->(void *)

    CELLULAR_SET_PODR(CELLULAR_CFG_RESET_PORT, CELLULAR_CFG_RESET_PIN) = CELLULAR_CFG_RESET_SIGNAL_ON;
    CELLULAR_SET_PDR(CELLULAR_CFG_RESET_PORT, CELLULAR_CFG_RESET_PIN)  = CELLULAR_PIN_DIRECTION_MODE_OUTPUT;

    p_ctrl->module_status    = CELLULAR_MODULE_OPERATING_RESET;
    p_ctrl->sci_ctrl.atc_flg = CELLULAR_ATC_RESPONSE_CONFIRMED;

    cnt = 0;

    /* WAIT_LOOP */
    do
    {
        cellular_delay_task(1); /* hold reset signal time for cellular module */
        cnt++;
    } while ((cnt < CELLULAR_TASK_LIMIT) && (CELLULAR_MODULE_OPERATING_LEVEL0 != p_ctrl->module_status));

    CELLULAR_SET_PODR(CELLULAR_CFG_RESET_PORT, CELLULAR_CFG_RESET_PIN) = CELLULAR_CFG_RESET_SIGNAL_OFF;

    if (CELLULAR_TASK_LIMIT > cnt)
    {
        cnt = 0;

        /* WAIT_LOOP */
        do
        {
            if (CELLULAR_FLG_START == flg)
            {
                cnt = CELLULAR_RESTART_LIMIT;
                ret = CELLULAR_SUCCESS;
            }
            else
            {
                cellular_delay_task(1000);
            }
            cnt++;
        } while (cnt < CELLULAR_RESTART_LIMIT);

        if (CELLULAR_FLG_START != flg)
        {
            ret = CELLULAR_ERR_RECV_TASK;
        }
    }
    else
    {
        ret = CELLULAR_ERR_RECV_TASK;
    }

    if ((CELLULAR_SYSTEM_CLOSE != p_ctrl->system_state) && (CELLULAR_SYSTEM_OPEN != p_ctrl->system_state))
    {
        p_ctrl->system_state = CELLULAR_SYSTEM_OPEN;
    }

    p_ctrl->recv_data = NULL;

    return ret;
}
#endif
/**********************************************************************************************************************
 * End of function cellular_pin_reset
 *********************************************************************************************************************/
