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
 * File Name    : r_cellular_receivesocket.c
 * Description  : Functions to read data from a socket.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "cellular_private_api.h"
#include "cellular_freertos.h"
#include "at_command.h"
#if BSP_CFG_RTOS_USED == (1)
#include "FreeRTOS.h"
#include "task.h"
#endif

/**********************************************************************************************************************
 * Macro definitions
 *********************************************************************************************************************/
#define CELLULAR_RECONNECT_TIMEOUT    (120000)
#if defined(CELLULAR_TARGET_BG96)
#define CELLULAR_BG96_QIRD_FRAME_MARGIN    (128U)
#endif /* CELLULAR_TARGET_BG96 */

/**********************************************************************************************************************
 * Typedef definitions
 *********************************************************************************************************************/
typedef enum
{
    CELLULAR_AP_RECONNECTED = 0,
    CELLULAR_SOCKET_DISCONNECTED,
    CELLULAR_AP_RECONNECT_TIMEOUT,
} e_cellular_reconnect_status_t;

/**********************************************************************************************************************
 * Exported global variables
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Private (static) variables and functions
 *********************************************************************************************************************/
static int32_t cellular_receive_data (st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                                        uint8_t * const p_data, const int32_t length, const uint32_t timeout_ms);
#if defined(CELLULAR_TARGET_BG96)
static int32_t cellular_receive_data_bg96 (st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                                        uint8_t * const p_data, const int32_t length, const uint32_t timeout_ms);
static uint16_t cellular_bg96_copy_from_cache (st_cellular_socket_ctrl_t * const p_socket_ctrl,
                                        uint8_t * const p_data, const int32_t length);
#endif /* CELLULAR_TARGET_BG96 */
static int32_t cellular_recv_size_check (st_cellular_ctrl_t * const p_ctrl,
                                            const uint8_t socket_no, const int32_t length);
static e_cellular_timeout_check_t cellular_receive_flag_check (st_cellular_ctrl_t * const p_ctrl,
                                        st_cellular_time_ctrl_t * const p_cellular_timeout_ctrl,
                                        const uint8_t socket_no, const uint32_t timeout_ms);
static e_cellular_reconnect_status_t cellular_connect_check (st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no);
#if BSP_CFG_RTOS_USED == (1)
static void cellular_prepare_socket_rx_wait (st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no);
static void cellular_clear_socket_rx_wait (st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no);
static void cellular_wait_socket_rx_event (void);
#endif

/*************************************************************************************************
 * Function Name  @fn            R_CELLULAR_ReceiveSocket
 * Description    @details       Reading data from a socket.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     socket_no -
 *                                  Socket number for reading data.
 *                @param[in]     p_data -
 *                                  Pointer to store the read data.
 *                @param[in]     length -
 *                                  Read data size.
 *                @param[in]     timeout_ms -
 *                                  timeout millisecond.
 * Return Value   @retval        More than 1 -
 *                                  Successfully loaded data.
 *                @retval        CELLULAR_ERR_PARAMETER -
 *                                  Argument is abnormal.
 *                @retval        CELLULAR_ERR_SOCKET_NUM -
 *                                  No available socket.
 *                @retval        CELLULAR_ERR_MODULE_COM -
 *                                  Communication with module failed.
 *                @retval        CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING -
 *                                  Other AT commands are running.
 ************************************************************************************************/
int32_t R_CELLULAR_ReceiveSocket(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                        uint8_t * const p_data, const int32_t length, const uint32_t timeout_ms)
{
    int32_t                    total_receive_length = 0;
    uint32_t                   preemption           = 0;
    e_cellular_err_t           ret                  = CELLULAR_SUCCESS;
    e_cellular_err_semaphore_t semaphore_ret        = CELLULAR_SEMAPHORE_SUCCESS;

    preemption = cellular_interrupt_disable();
    if ((NULL == p_data) || (0 >= length) || (NULL == p_ctrl))
    {
        ret = CELLULAR_ERR_PARAMETER;
    }
    else
    {
        if (0 != (p_ctrl->running_api_count % 2))
        {
            ret = CELLULAR_ERR_OTHER_API_RUNNING;
        }
        else if (CELLULAR_SYSTEM_CLOSE == p_ctrl->system_state)
        {
            ret = CELLULAR_ERR_NOT_OPEN;
        }
        else
        {
            R_BSP_NOP();
        }

        if (CELLULAR_SUCCESS == ret)
        {
            if ((CELLULAR_START_SOCKET_NUMBER > socket_no) || (p_ctrl->creatable_socket < socket_no))
            {
                ret = CELLULAR_ERR_PARAMETER;
            }
            else if (CELLULAR_SOCKET_STATUS_CONNECTED !=
                        p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].socket_status)
            {
                ret = CELLULAR_ERR_SOCKET_NOT_READY;
            }
            else
            {
                p_ctrl->running_api_count += 2;
            }
        }
    }
    cellular_interrupt_enable(preemption);

    if (CELLULAR_SUCCESS == ret)
    {
        semaphore_ret = cellular_take_semaphore(p_ctrl->p_socket_ctrl[socket_no
                                                    - CELLULAR_START_SOCKET_NUMBER].rx_semaphore);
        if (CELLULAR_SEMAPHORE_SUCCESS == semaphore_ret)
        {
#if defined(CELLULAR_TARGET_BG96)
            total_receive_length = cellular_receive_data_bg96(p_ctrl, socket_no, p_data, length, timeout_ms);
#else
            total_receive_length = cellular_receive_data(p_ctrl, socket_no, p_data, length, timeout_ms);
#endif /* CELLULAR_TARGET_BG96 */
            cellular_give_semaphore(p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].rx_semaphore);
        }
        else
        {
            ret = CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING;
        }
        p_ctrl->running_api_count -= 2;
    }

    if (CELLULAR_SUCCESS != ret)
    {
        total_receive_length = (int32_t)ret;    //cast
    }

    return total_receive_length;
}
/**********************************************************************************************************************
 * End of function R_CELLULAR_ReceiveSocket
 *********************************************************************************************************************/

#if defined(CELLULAR_TARGET_BG96)
/*************************************************************************************************
 * Function Name  @fn            cellular_receive_data_bg96
 * Description    @details       Reading data from a socket (BG96).
 *                               BG96 may answer AT+QIRD=<cid>,<n> with more than <n> bytes (up to
 *                               CELLULAR_BG96_QIRD_MAX_READ_SIZE). Each AT+QIRD is therefore read into a
 *                               buffer with room for that maximum: into the socket's receive cache when
 *                               less than that remains to be stored, else directly into p_data. Bytes
 *                               beyond the request stay in the cache and are returned first by the next
 *                               call. As in cellular_receive_data, it returns when length bytes are
 *                               stored or the timeout expires.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     socket_no -
 *                                  Socket number for reading data.
 *                @param[in]     p_data -
 *                                  Pointer to store the read data.
 *                @param[in]     length -
 *                                  Read data size.
 *                @param[in]     timeout_ms -
 *                                  timeout millisecond.
 * Return Value   @retval        0 or more -
 *                                  Size of the stored data.
 ************************************************************************************************/
static int32_t cellular_receive_data_bg96(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                                        uint8_t * const p_data, const int32_t length, const uint32_t timeout_ms)
{
    int32_t                    total_receive_length = 0;
    int32_t                    receive_size         = 0;
    int32_t                    requested_size       = 0;
    uint8_t *                  p_dst                = NULL;
    e_cellular_err_t           ret                  = CELLULAR_SUCCESS;
    e_cellular_err_semaphore_t semaphore_ret        = CELLULAR_SEMAPHORE_ERR_TAKE;
    e_cellular_timeout_check_t timeout              = CELLULAR_NOT_TIMEOUT;
    bool                      peer_closed_read     = false;

    st_cellular_socket_ctrl_t * const p_socket_ctrl
        = &p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER];
    st_cellular_time_ctrl_t * const p_cellular_timeout_ctrl = &p_socket_ctrl->cellular_rx_timeout_ctrl;

    /* Bytes that an earlier AT+QIRD returned beyond its request come first. */
    total_receive_length = (int32_t)cellular_bg96_copy_from_cache(p_socket_ctrl, p_data, length);
    if (length <= total_receive_length)
    {
        return total_receive_length;
    }
    cellular_timeout_init(p_cellular_timeout_ctrl, timeout_ms);
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
            cellular_delay_task(1);
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

    /* WAIT_LOOP */
    /* Data receive loop. The cache is empty here and after every pass that does not fill the request. */
    while (length > total_receive_length)
    {
        timeout = cellular_receive_flag_check(p_ctrl, p_cellular_timeout_ctrl, socket_no, timeout_ms);
        if (CELLULAR_TIMEOUT == timeout)
        {
            break; /* Break of the data receive loop */
        }

        semaphore_ret = cellular_take_semaphore(p_ctrl->at_semaphore);
        if (CELLULAR_SEMAPHORE_SUCCESS != semaphore_ret)
        {
            break; /* Break of the data receive loop */
        }

        peer_closed_read = (0 != p_socket_ctrl->bg96_peer_closed);
        if (true == peer_closed_read)
        {
            /* URC counters are hints, not proof of EOF. QIRD status reports
             * modem bytes even when a recv URC was missing or understated. */
            ret = atc_sqnsrecv(p_ctrl, socket_no, 0);
            if (CELLULAR_SUCCESS != ret)
            {
                cellular_give_semaphore(p_ctrl->at_semaphore);
                break;
            }
            if (0 == p_socket_ctrl->receive_unprocessed_size)
            {
                ret = CELLULAR_ERR_SOCKET_NOT_READY;
                cellular_give_semaphore(p_ctrl->at_semaphore);
                break;
            }
        }

        if ((length - total_receive_length) < (int32_t)CELLULAR_BG96_RX_CACHE_SIZE)
        {
            p_dst = p_socket_ctrl->bg96_rx_cache;
        }
        else
        {
            p_dst = &p_data[total_receive_length];
        }

        /* Either buffer has room for one AT+QIRD at its largest, so ask for as much as the modem holds. */
        receive_size = cellular_recv_size_check(p_ctrl, socket_no, (int32_t)CELLULAR_BG96_RX_CACHE_SIZE);
        if ((true == peer_closed_read) && (0 >= receive_size))
        {
            /* The modem reported data but this call cannot make progress. */
            ret = CELLULAR_ERR_MODULE_COM;
            cellular_give_semaphore(p_ctrl->at_semaphore);
            break;
        }
        p_socket_ctrl->total_recv_count       = 0;
        p_socket_ctrl->p_recv                 = p_dst;
        p_ctrl->sci_ctrl.active_recv_capacity = (uint16_t)CELLULAR_BG96_RX_CACHE_SIZE;

        requested_size = receive_size;
        ret = atc_sqnsrecv(p_ctrl, socket_no, requested_size);

        p_ctrl->sci_ctrl.active_recv_capacity = 0;
        receive_size                          = p_socket_ctrl->total_recv_count;
        p_socket_ctrl->total_recv_count       = 0;
        p_socket_ctrl->p_recv                 = NULL;
        if ((CELLULAR_SUCCESS == ret) && (0 < requested_size) &&
                (0 != p_socket_ctrl->bg96_peer_closed) && (0 >= receive_size))
        {
            /* A successful zero-byte read after FIN is not a confirmed empty
             * status reply. Stop, including timeout=0, rather than retry forever. */
            peer_closed_read = true;
            ret = CELLULAR_ERR_MODULE_COM;
        }
        if ((CELLULAR_SUCCESS == ret) && (p_dst == p_socket_ctrl->bg96_rx_cache))
        {
            /* Recorded while at_semaphore is held: ShutdownSocket and ConnectSocket empty the cache under the
             * same semaphore, so the data of a connection that ended is not kept for the next one. */
            uint32_t preemption = cellular_interrupt_disable();

            p_socket_ctrl->bg96_rx_cache_pos = 0;
            p_socket_ctrl->bg96_rx_cache_len = (uint16_t)receive_size;
            cellular_interrupt_enable(preemption);
        }
        cellular_give_semaphore(p_ctrl->at_semaphore);

        if (CELLULAR_SUCCESS != ret)
        {
            break; /* Break of the data receive loop */
        }

        if (p_dst == p_socket_ctrl->bg96_rx_cache)
        {
            total_receive_length += (int32_t)cellular_bg96_copy_from_cache(p_socket_ctrl,
                                                &p_data[total_receive_length], length - total_receive_length);
        }
        else
        {
            total_receive_length += receive_size;
        }

        timeout = cellular_check_timeout(p_cellular_timeout_ctrl);
        if (CELLULAR_TIMEOUT == timeout)
        {
            break; /* Break of the data receive loop */
        }
    } /* End of data receive loop */

    if (CELLULAR_PSM_ACTIVE == p_ctrl->ring_ctrl.psm)
    {
#if CELLULAR_CFG_CTS_SW_CTRL == 1
        cellular_rts_hw_flow_disable();
#endif
        cellular_rts_ctrl(1);
        cellular_give_semaphore(p_ctrl->ring_ctrl.rts_semaphore);
    }

    if ((0 == total_receive_length) && (true == peer_closed_read) && (CELLULAR_SUCCESS != ret))
    {
        total_receive_length = (int32_t)ret;
    }
    return total_receive_length;
}
/**********************************************************************************************************************
 * End of function cellular_receive_data_bg96
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_bg96_copy_from_cache
 * Description    @details       Move up to length bytes from the socket's receive cache to p_data.
 * Arguments      @param[in/out] p_socket_ctrl -
 *                                  Pointer to the socket management structure.
 *                @param[in]     p_data -
 *                                  Pointer to store the data.
 *                @param[in]     length -
 *                                  Room in p_data.
 * Return Value   @retval        0 or more -
 *                                  Number of bytes moved.
 ************************************************************************************************/
static uint16_t cellular_bg96_copy_from_cache(st_cellular_socket_ctrl_t * const p_socket_ctrl,
                                        uint8_t * const p_data, const int32_t length)
{
    uint32_t preemption = 0;
    uint16_t available  = 0;
    uint16_t copy_size  = 0;
    uint16_t start      = 0;

    if (0 >= length)
    {
        return 0;
    }

    /* Take the bytes (move the position past them) in the critical section that cellular_bg96_rx_cache_clear()
     * also takes: ShutdownSocket, ConnectSocket and CloseSocket of another task may empty the cache meanwhile.
     * The bytes are copied after it. Only the reader of this socket (it holds rx_semaphore) writes the cache, and
     * it does not write it while it is in this function, so the bytes taken do not change. */
    preemption = cellular_interrupt_disable();
    if (p_socket_ctrl->bg96_rx_cache_len > p_socket_ctrl->bg96_rx_cache_pos)
    {
        available = (uint16_t)(p_socket_ctrl->bg96_rx_cache_len - p_socket_ctrl->bg96_rx_cache_pos);
        copy_size = ((int32_t)available < length) ? available : (uint16_t)length;    //cast
        start     = p_socket_ctrl->bg96_rx_cache_pos;
        p_socket_ctrl->bg96_rx_cache_pos = (uint16_t)(start + copy_size);
    }
    if (p_socket_ctrl->bg96_rx_cache_pos >= p_socket_ctrl->bg96_rx_cache_len)
    {
        p_socket_ctrl->bg96_rx_cache_pos = 0;
        p_socket_ctrl->bg96_rx_cache_len = 0;
    }
    cellular_interrupt_enable(preemption);

    if (0U < copy_size)
    {
        memcpy(p_data, &p_socket_ctrl->bg96_rx_cache[start], copy_size);
    }

    return copy_size;
}
/**********************************************************************************************************************
 * End of function cellular_bg96_copy_from_cache
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_bg96_rx_cache_clear
 ************************************************************************************************/
void cellular_bg96_rx_cache_clear(st_cellular_socket_ctrl_t * const p_socket_ctrl)
{
    uint32_t preemption = 0;

    preemption = cellular_interrupt_disable();
    p_socket_ctrl->bg96_rx_cache_pos = 0;
    p_socket_ctrl->bg96_rx_cache_len = 0;
    cellular_interrupt_enable(preemption);
}
/**********************************************************************************************************************
 * End of function cellular_bg96_rx_cache_clear
 *********************************************************************************************************************/
#endif /* CELLULAR_TARGET_BG96 */

/*************************************************************************************************
 * Function Name  @fn            cellular_receive_data
 * Description    @details       Reading data from a socket.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     socket_no -
 *                                  Socket number for reading data.
 *                @param[in]     p_data -
 *                                  Pointer to store the read data.
 *                @param[in]     length -
 *                                  Read data size.
 *                @param[in]     timeout_ms -
 *                                  timeout millisecond.
 * Return Value   @retval        More than 1 -
 *                                  Successfully loaded data.
 *                @retval        CELLULAR_ERR_PARAMETER -
 *                                  Argument is abnormal.
 *                @retval        CELLULAR_ERR_SOCKET_NUM -
 *                                  No available socket.
 *                @retval        CELLULAR_ERR_MODULE_COM -
 *                                  Communication with module failed.
 *                @retval        CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING -
 *                                  Other AT commands are running.
 ************************************************************************************************/
static int32_t cellular_receive_data(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                                        uint8_t * const p_data, const int32_t length, const uint32_t timeout_ms)
{
    int32_t                    total_receive_length = 0;
    int32_t                    receive_size;
    e_cellular_err_t           ret                  = CELLULAR_SUCCESS;
    e_cellular_err_semaphore_t semaphore_ret        = CELLULAR_SEMAPHORE_ERR_TAKE;
    e_cellular_timeout_check_t timeout              = CELLULAR_NOT_TIMEOUT;

    st_cellular_time_ctrl_t * const p_cellular_timeout_ctrl
        = &p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].cellular_rx_timeout_ctrl;

    cellular_timeout_init(p_cellular_timeout_ctrl, timeout_ms);
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
            cellular_delay_task(1);
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

    /* WAIT_LOOP */
    /* Data receive loop */
    while (length > total_receive_length)
    {
        timeout = cellular_receive_flag_check(p_ctrl, p_cellular_timeout_ctrl, socket_no, timeout_ms);
        if (CELLULAR_TIMEOUT == timeout)
        {
            break; /* Break of the data receive loop */
        }

        semaphore_ret = cellular_take_semaphore(p_ctrl->at_semaphore);
        if (CELLULAR_SEMAPHORE_SUCCESS == semaphore_ret)
        {
            receive_size = cellular_recv_size_check(p_ctrl, socket_no,
                        length - p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].total_recv_count);

            p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].p_recv = p_data;

            ret = atc_sqnsrecv(p_ctrl, socket_no, receive_size);
            cellular_give_semaphore(p_ctrl->at_semaphore);

            if (CELLULAR_SUCCESS == ret)
            {
                total_receive_length = p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].total_recv_count;
                timeout              = cellular_check_timeout(p_cellular_timeout_ctrl);
                if (CELLULAR_TIMEOUT == timeout)
                {
                    break; /* Break of the data receive loop */
                }

            }
            else
            {
                break; /* Break of the data receive loop */
            }
        }
        else
        {
            break; /* Break of the data receive loop */
        }
    } /* End of data receive loop */

    if (CELLULAR_PSM_ACTIVE == p_ctrl->ring_ctrl.psm)
    {
#if CELLULAR_CFG_CTS_SW_CTRL == 1
        cellular_rts_hw_flow_disable();
#endif
        cellular_rts_ctrl(1);
        cellular_give_semaphore(p_ctrl->ring_ctrl.rts_semaphore);
    }
    p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].total_recv_count = 0;
    p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].p_recv           = NULL;

    return total_receive_length;
}
/**********************************************************************************************************************
 * End of function  cellular_receive_data
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_receive_flag_check
 * Description    @details       Wait for the AT command response.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     socket_no -
 *                                  Socket number for sending data.
 * Return Value   @retval        CELLULAR_NOT_TIMEOUT -
 *                                  Successfully flag check.
 *                @retval        CELLULAR_TIMEOUT -
 *                                  Time out.
 ************************************************************************************************/
static e_cellular_timeout_check_t cellular_receive_flag_check(st_cellular_ctrl_t * const p_ctrl,
                                        st_cellular_time_ctrl_t * const p_cellular_timeout_ctrl,
                                        const uint8_t socket_no, const uint32_t timeout_ms)
{
    e_cellular_timeout_check_t    timeout = CELLULAR_NOT_TIMEOUT;
    e_cellular_reconnect_status_t status  = CELLULAR_AP_RECONNECTED;

#if BSP_CFG_RTOS_USED == (1)
    cellular_prepare_socket_rx_wait(p_ctrl, socket_no);
#endif

    /* WAIT_LOOP */
    while (1)
    {
        if (CELLULAR_RECEIVE_FLAG_ON == p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].receive_flg)
        {
            break;
        }
#if defined(CELLULAR_TARGET_BG96)
        if (0 != p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].bg96_peer_closed)
        {
            /* FIN makes the caller query modem status under the AT semaphore;
             * missing recv URCs and zero hint counters must not imply EOF. */
            break;
        }
#endif /* CELLULAR_TARGET_BG96 */

        timeout = cellular_check_timeout(p_cellular_timeout_ctrl);
        if (CELLULAR_TIMEOUT == timeout)
        {
            break;
        }

        if ((0 == timeout_ms) && (CELLULAR_SOCKET_STATUS_CONNECTED
                != p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].socket_status))
        {
            timeout = CELLULAR_TIMEOUT;
            break;
        }

        if ((0 == timeout_ms) && (CELLULAR_SYSTEM_CONNECT != p_ctrl->system_state))
        {
            status = cellular_connect_check(p_ctrl, socket_no);
            if (CELLULAR_AP_RECONNECTED != status)
            {
                /* Treat DISCONNECT as timeout */
                timeout = CELLULAR_TIMEOUT;
                break;
            }
        }

#if BSP_CFG_RTOS_USED == (1)
        cellular_wait_socket_rx_event();
#endif
    }

#if BSP_CFG_RTOS_USED == (1)
    cellular_clear_socket_rx_wait(p_ctrl, socket_no);
#endif

    return timeout;
}
/**********************************************************************************************************************
 * End of function cellular_receive_flag_check
 *********************************************************************************************************************/

#if BSP_CFG_RTOS_USED == (1)
/*************************************************************************************************
 * Function Name  @fn            cellular_prepare_socket_rx_wait
 ************************************************************************************************/
static void cellular_prepare_socket_rx_wait(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no)
{
#if configTASK_NOTIFICATION_ARRAY_ENTRIES <= CELLULAR_TASK_NOTIFY_INDEX
#error "configTASK_NOTIFICATION_ARRAY_ENTRIES must reserve CELLULAR_TASK_NOTIFY_INDEX."
#endif
    p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].rx_wait_taskhandle =
        (void *)xTaskGetCurrentTaskHandle();
    while (0U != ulTaskNotifyTakeIndexed(CELLULAR_TASK_NOTIFY_INDEX, pdTRUE, 0))
    {
        R_BSP_NOP();
    }
}
/**********************************************************************************************************************
 * End of function cellular_prepare_socket_rx_wait
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_clear_socket_rx_wait
 ************************************************************************************************/
static void cellular_clear_socket_rx_wait(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no)
{
    p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].rx_wait_taskhandle = NULL;
}
/**********************************************************************************************************************
 * End of function cellular_clear_socket_rx_wait
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_wait_socket_rx_event
 ************************************************************************************************/
static void cellular_wait_socket_rx_event(void)
{
    (void)ulTaskNotifyTakeIndexed(CELLULAR_TASK_NOTIFY_INDEX, pdTRUE, pdMS_TO_TICKS(1));
}
/**********************************************************************************************************************
 * End of function cellular_wait_socket_rx_event
 *********************************************************************************************************************/
#endif /* BSP_CFG_RTOS_USED == (1) */

/*************************************************************************************************
 * Function Name  @fn            cellular_connect_check
 ************************************************************************************************/
static e_cellular_reconnect_status_t cellular_connect_check(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no)
{
    volatile uint8_t           over_flg   = 0;
    uint32_t                   start_time = 0;
    uint32_t                   now_time   = 0;
    uint32_t                   end_time   = 0;

    e_cellular_reconnect_status_t status  = CELLULAR_AP_RECONNECTED;


    start_time = cellular_get_tickcount();
    if ((uint32_t)(start_time + CELLULAR_RECONNECT_TIMEOUT) < start_time) //cast
    {
        over_flg = 1;
    }
    end_time = start_time + CELLULAR_RECONNECT_TIMEOUT;

    /* WAIT_LOOP */
    while (1)
    {
        if (CELLULAR_SYSTEM_CONNECT == p_ctrl->system_state)
        {
            status = CELLULAR_AP_RECONNECTED;
            break;  //Reconnect to AP
        }

        if (CELLULAR_SOCKET_STATUS_CONNECTED !=
                p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].socket_status)
        {
            status = CELLULAR_SOCKET_DISCONNECTED;
            break;  //Socket connection disconnected
        }

        now_time = cellular_get_tickcount();
        if (1 == over_flg)
        {
            if ((now_time >= end_time) && (now_time < start_time))
            {
                status = CELLULAR_AP_RECONNECT_TIMEOUT;
                break;    //Timeout
            }
        }
        else
        {
            if ((now_time >= end_time) || (now_time < start_time))
            {
                status = CELLULAR_AP_RECONNECT_TIMEOUT;
                break;    //Timeout
            }
        }

        cellular_delay_task(1);
    }

    return status;
}
/**********************************************************************************************************************
 * End of function cellular_connect_check
 *********************************************************************************************************************/


/*************************************************************************************************
 * Function Name  @fn            cellular_recv_size_check
 * Description    @details       Check the size of the data to be receive.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     socket_no -
 *                                  Socket number for sending data.
 * Return Value   @retval        Number of bytes received from the module.
 ************************************************************************************************/
static int32_t cellular_recv_size_check(st_cellular_ctrl_t * const p_ctrl,
                                            const uint8_t socket_no, const int32_t length)
{
    int32_t receive_size = 0;
#if defined(CELLULAR_TARGET_BG96)
    uint16_t rx_queue_used = 0;
    uint32_t rx_queue_free = 0;
#endif /* CELLULAR_TARGET_BG96 */

    if (p_ctrl->sci_ctrl.rx_buff_size > p_ctrl->sci_ctrl.rx_process_size)
    {
        receive_size = (int32_t)p_ctrl->sci_ctrl.rx_process_size;   //cast
    }
    else
    {
        receive_size = (int32_t)p_ctrl->sci_ctrl.rx_buff_size;      //cast
    }

    if (receive_size > p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].receive_unprocessed_size)
    {
        receive_size =
            (int32_t)p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].receive_unprocessed_size;  //cast
    }

    if (receive_size > length)
    {
        receive_size = length;
    }

#if defined(CELLULAR_TARGET_BG96)
    if (receive_size > CELLULAR_BG96_QIRD_MAX_READ_SIZE)
    {
        receive_size = CELLULAR_BG96_QIRD_MAX_READ_SIZE;
    }

    if (0 < receive_size)
    {
        if (SCI_SUCCESS == R_SCI_Control(p_ctrl->sci_ctrl.sci_hdl,
                                         SCI_CMD_RX_Q_BYTES_AVAIL_TO_READ,
                                         &rx_queue_used))
        {
            if (p_ctrl->sci_ctrl.rx_buff_size > (uint32_t)rx_queue_used)
            {
                rx_queue_free = p_ctrl->sci_ctrl.rx_buff_size - (uint32_t)rx_queue_used;
            }

            if (rx_queue_free > CELLULAR_BG96_QIRD_FRAME_MARGIN)
            {
                rx_queue_free -= CELLULAR_BG96_QIRD_FRAME_MARGIN;
            }
            else
            {
                rx_queue_free = 0;
            }

            if ((uint32_t)receive_size > rx_queue_free)
            {
                receive_size = (int32_t)rx_queue_free;
            }
        }
    }
#endif /* CELLULAR_TARGET_BG96 */

    return receive_size;
}
/**********************************************************************************************************************
 * End of function cellular_recv_size_check
 *********************************************************************************************************************/
