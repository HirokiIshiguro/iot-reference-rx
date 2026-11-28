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
 * File Name    : r_cellular_sendsocket.c
 * Description  : Function to send data to a socket.
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "cellular_private_api.h"
#include "cellular_freertos.h"
#include "at_command.h"

/**********************************************************************************************************************
 * Macro definitions
 *********************************************************************************************************************/
#if defined(CELLULAR_TARGET_BG96)
/* Resend of a chunk that BG96 answered with "SEND FAIL" (send buffer full). The values are not tuned
 * against the Quectel manual; they bound the extra time per chunk to about
 * BG96_SEND_FAIL_RETRY_MAX x (BG96_SEND_FAIL_RETRY_WAIT_MS + one AT+QISEND round trip). */
#define BG96_SEND_FAIL_RETRY_MAX        (20U)       /* Resends of one chunk after "SEND FAIL" */
#define BG96_SEND_FAIL_RETRY_WAIT_MS    (100U)      /* Wait without the AT semaphore before a resend (ms) */
#define BG96_SEND_FAIL_POLL_MS          (10U)       /* Step of that wait and of taking the semaphore back:
                                                     * the timeout_ms deadline is checked between the steps */
#endif /* CELLULAR_TARGET_BG96 */

/**********************************************************************************************************************
 * Typedef definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Exported global variables
 *********************************************************************************************************************/

/**********************************************************************************************************************
 * Private (static) variables and functions
 *********************************************************************************************************************/
static int32_t cellular_send_data (st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                                        const uint8_t * const p_data, const int32_t length, const uint32_t timeout_ms);
static uint16_t cellular_send_size_check (st_cellular_ctrl_t * const p_ctrl, const int32_t length,
                                            const int32_t complete_length);
static e_cellular_timeout_check_t cellular_tx_flag_check (st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no);
static e_cellular_timeout_check_t cellular_atc_response_check (st_cellular_ctrl_t * const p_ctrl,
                                                                    const uint8_t socket_no);
#if defined(CELLULAR_TARGET_BG96)
static bool cellular_send_fail_resend (st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                                        uint8_t * const p_retry_count, e_cellular_err_t * const p_ret);
static void cellular_send_flag_set (volatile uint8_t * const p_flags, const uint8_t socket_no, const bool on);
static bool cellular_send_flag_get (const volatile uint8_t * const p_flags, const uint8_t socket_no);

/* One bit per socket (socket_no - CELLULAR_START_SOCKET_NUMBER). */
/* A SendSocket is sending on the socket. Another SendSocket on the same socket is refused while it is set:
 * the sender may release the AT semaphore to wait after "SEND FAIL", and a second sender would then put its
 * data between the chunks and restart the deadline of the socket (cellular_tx_timeout_ctrl). */
static volatile uint8_t s_send_busy     = 0U;
/* The sender released the AT semaphore after "SEND FAIL" and does not hold it again (the deadline passed or
 * the semaphore could not be taken back): R_CELLULAR_SendSocket() must not give it. */
static volatile uint8_t s_send_released = 0U;
#endif /* CELLULAR_TARGET_BG96 */

/*************************************************************************************************
 * Function Name  @fn            R_CELLULAR_SendSocket
 ************************************************************************************************/
int32_t R_CELLULAR_SendSocket(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                    const uint8_t * const p_data, const int32_t length, const uint32_t timeout_ms)
{
    int32_t                    complete_length = 0;
    uint32_t                   preemption      = 0;
    e_cellular_err_t           ret             = CELLULAR_SUCCESS;
    e_cellular_err_semaphore_t semaphore_ret   = CELLULAR_SEMAPHORE_SUCCESS;

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
        else if (CELLULAR_SYSTEM_OPEN == p_ctrl->system_state)
        {
            ret = CELLULAR_ERR_NOT_CONNECT;
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
            else if ((CELLULAR_SOCKET_STATUS_CONNECTED !=
                    p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].socket_status)
#if defined(CELLULAR_TARGET_BG96)
                    || (0 != p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].bg96_peer_closed)
#endif
                    )
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
        semaphore_ret = cellular_take_semaphore(p_ctrl->at_semaphore);
        if (CELLULAR_SEMAPHORE_SUCCESS == semaphore_ret)
        {
#if defined(CELLULAR_TARGET_BG96)
            if (true == cellular_send_flag_get(&s_send_busy, socket_no))
            {
                /* Another SendSocket on this socket is waiting after "SEND FAIL" without the semaphore. */
                cellular_give_semaphore(p_ctrl->at_semaphore);
                ret = CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING;
            }
            else
            {
                cellular_send_flag_set(&s_send_busy, socket_no, true);
                complete_length = cellular_send_data(p_ctrl, socket_no, p_data, length, timeout_ms);
                if (true == cellular_send_flag_get(&s_send_released, socket_no))
                {
                    /* released after "SEND FAIL" and not taken back: not held, do not give it */
                    cellular_send_flag_set(&s_send_released, socket_no, false);
                }
                else
                {
                    cellular_give_semaphore(p_ctrl->at_semaphore);
                }
                cellular_send_flag_set(&s_send_busy, socket_no, false);
            }
#else
            complete_length = cellular_send_data(p_ctrl, socket_no, p_data, length, timeout_ms);
            cellular_give_semaphore(p_ctrl->at_semaphore);
#endif /* CELLULAR_TARGET_BG96 */
            cellular_delay_task(1);
        }
        else
        {
            ret = CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING;
        }
        p_ctrl->running_api_count -= 2;
    }

    if (CELLULAR_SUCCESS != ret)
    {
        complete_length = (int32_t)ret; //cast
    }

    return complete_length;
}
/**********************************************************************************************************************
 * End of function R_CELLULAR_SendSocket
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_send_data
 * Description    @details       Send data to the module.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     socket_no -
 *                                  Socket number for sending data.
 *                @param[in]     p_data -
 *                                  Pointer to send data.
 *                @param[in]     length -
 *                                  Send data size.
 *                @param[in]     timeout_ms -
 *                                  timeout millisecond.
 * Return Value   @retval        More than 1 -
 *                                  Successfully sent data.
 *                @retval        CELLULAR_ERR_PARAMETER -
 *                                  Argument is abnormal.
 *                @retval        CELLULAR_ERR_SOCKET_NUM -
 *                                  No available socket.
 *                @retval        CELLULAR_ERR_MODULE_COM -
 *                                  Communication with module failed.
 *                @retval        CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING -
 *                                  Other AT commands are running.
 ************************************************************************************************/
static int32_t cellular_send_data(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                                    const uint8_t * const p_data, const int32_t length, const uint32_t timeout_ms)
{
#if CELLULAR_CFG_CTS_SW_CTRL == 1
    uint16_t sci_send_size = 0;
#endif
    int32_t                    complete_length = 0;
    uint16_t                   send_size       = 0;
    sci_err_t                  sci_ret         = SCI_SUCCESS;
    e_cellular_err_t           ret             = CELLULAR_SUCCESS;
    e_cellular_timeout_check_t timeout         = CELLULAR_NOT_TIMEOUT;
    e_cellular_err_semaphore_t semaphore_ret   = CELLULAR_SEMAPHORE_ERR_TAKE;
#if defined(CELLULAR_TARGET_BG96)
    uint8_t                    send_fail_count = 0;
#endif

    st_cellular_time_ctrl_t * const p_cellular_timeout_ctrl =
            &p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].cellular_tx_timeout_ctrl;

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
    while (complete_length < length)
    {
#if defined(CELLULAR_TARGET_BG96)
        if (0 != p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].bg96_peer_closed)
        {
            /* Preserve an already completed partial send; an unsent call must
             * report the known peer close instead of apparent zero progress. */
            if (0 == complete_length)
            {
                complete_length = CELLULAR_ERR_SOCKET_NOT_READY;
            }
            break;
        }
#endif /* CELLULAR_TARGET_BG96 */
        if (CELLULAR_SOCKET_STATUS_CONNECTED !=
                p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].socket_status)
        {
            break;
        }

        send_size = cellular_send_size_check(p_ctrl, length, complete_length);

        ret = atc_sqnssendext(p_ctrl, socket_no, send_size);
        if (CELLULAR_SUCCESS != ret)
        {
#if defined(CELLULAR_TARGET_BG96)
            break;
#else
            if ((ATC_RETURN_ERROR == p_ctrl->sci_ctrl.atc_res) && (CELLULAR_ERR_MODULE_COM == ret))
            {
                ret = CELLULAR_SUCCESS;
            }
            break;
#endif /* CELLULAR_TARGET_BG96 */
        }

#if CELLULAR_CFG_CTS_SW_CTRL == 0
        p_ctrl->sci_ctrl.tx_end_flg = CELLULAR_TX_END_FLAG_OFF;

        sci_ret = R_SCI_Send(p_ctrl->sci_ctrl.sci_hdl, (uint8_t *)p_data + complete_length, send_size); //cast
        if (SCI_SUCCESS != sci_ret)
        {
            ret = CELLULAR_ERR_MODULE_COM;
            break;
        }

        cellular_set_atc_number(p_ctrl, ATC_SQNSSENDEXT_END);

        timeout = cellular_tx_flag_check(p_ctrl, socket_no);
        if (CELLULAR_TIMEOUT != timeout)
        {
            timeout = cellular_atc_response_check(p_ctrl, socket_no);
        }

        if (CELLULAR_TIMEOUT == timeout)
        {
            ret = CELLULAR_ERR_MODULE_TIMEOUT;
            break;
        }

        if (ATC_RETURN_ERROR == p_ctrl->sci_ctrl.atc_res)
        {
#if defined(CELLULAR_TARGET_BG96)
            /* Keep completed chunks; an unconfirmed first chunk is a send
             * rejection, not retryable zero progress or a confirmed peer FIN. */
            if (0 == complete_length)
            {
                complete_length = (int32_t)CELLULAR_ERR_SEND_REJECTED; //cast
            }
#endif /* CELLULAR_TARGET_BG96 */
            break;
        }

#if defined(CELLULAR_TARGET_BG96)
        if (ATC_RETURN_SEND_FAIL == p_ctrl->sci_ctrl.atc_res)
        {
            /* The chunk was not taken: resend it (complete_length is not advanced) or stop. */
            if (true == cellular_send_fail_resend(p_ctrl, socket_no, &send_fail_count, &ret))
            {
                continue;
            }
            break;
        }
        send_fail_count = 0;
#endif /* CELLULAR_TARGET_BG96 */

        complete_length += send_size;
#else
        sci_send_size = 0;

        /* WAIT_LOOP */
        do
        {
            if (1 != CELLULAR_GET_PIDR(CELLULAR_CFG_CTS_PORT, CELLULAR_CFG_CTS_PIN))
            {
                p_ctrl->sci_ctrl.tx_end_flg = CELLULAR_TX_END_FLAG_OFF;

                sci_ret = R_SCI_Send(p_ctrl->sci_ctrl.sci_hdl,
                                        (uint8_t *)p_data + complete_length + sci_send_size, 1);    //cast
                if (SCI_SUCCESS != sci_ret)
                {
                    ret           = CELLULAR_ERR_MODULE_COM;
                    sci_send_size = send_size;
                }
                else
                {
                    timeout = cellular_tx_flag_check(p_ctrl, socket_no);
                    if (CELLULAR_TIMEOUT == timeout)
                    {
                        ret           = CELLULAR_ERR_MODULE_TIMEOUT;
                        sci_send_size = send_size;
                    }
                    else
                    {
                        sci_send_size++;
                    }
                }
            }
        } while (sci_send_size < send_size);

        if (CELLULAR_SUCCESS != ret)
        {
            break;
        }

        cellular_set_atc_number(p_ctrl, ATC_SQNSSENDEXT_END);

        timeout = cellular_atc_response_check(p_ctrl, socket_no);
        if (CELLULAR_TIMEOUT == timeout)
        {
            ret = CELLULAR_ERR_MODULE_TIMEOUT;
            break;
        }

        if (ATC_RETURN_ERROR == p_ctrl->sci_ctrl.atc_res)
        {
#if defined(CELLULAR_TARGET_BG96)
            /* Keep completed chunks; an unconfirmed first chunk is a send
             * rejection, not retryable zero progress or a confirmed peer FIN. */
            if (0 == complete_length)
            {
                complete_length = (int32_t)CELLULAR_ERR_SEND_REJECTED; //cast
            }
#endif /* CELLULAR_TARGET_BG96 */
            break;
        }

#if defined(CELLULAR_TARGET_BG96)
        if (ATC_RETURN_SEND_FAIL == p_ctrl->sci_ctrl.atc_res)
        {
            /* The chunk was not taken: resend it (complete_length is not advanced) or stop. */
            if (true == cellular_send_fail_resend(p_ctrl, socket_no, &send_fail_count, &ret))
            {
                continue;
            }
            break;
        }
        send_fail_count = 0;
#endif /* CELLULAR_TARGET_BG96 */

        complete_length += sci_send_size;
#endif  /* CELLULAR_CFG_CTS_SW_CTRL == 0 */
    }

    if (CELLULAR_PSM_ACTIVE == p_ctrl->ring_ctrl.psm)
    {
#if CELLULAR_CFG_CTS_SW_CTRL == 1
        cellular_rts_hw_flow_disable();
#endif
        cellular_rts_ctrl(1);
        cellular_give_semaphore(p_ctrl->ring_ctrl.rts_semaphore);
    }

    if ((CELLULAR_ERR_MODULE_TIMEOUT == ret) || (CELLULAR_ERR_MODULE_COM == ret))
    {
        complete_length = (int32_t)ret; //cast
    }
#if defined(CELLULAR_TARGET_BG96)
    /* The AT semaphore was released after "SEND FAIL" and could not be taken back within
     * CELLULAR_CFG_SEMAPHORE_BLOCK_TIME (s_send_released tells R_CELLULAR_SendSocket() not to give it). */
    if (CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING == ret)
    {
        complete_length = (int32_t)ret; //cast
    }
#endif /* CELLULAR_TARGET_BG96 */

    return complete_length;
}
/**********************************************************************************************************************
 * End of function cellular_send_data
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_send_size_check
 * Description    @details       Check the size of the data to be sent.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     length -
 *                                  Send data size.
 *                @param[in]     complete_length -
 *                                  Size of the completed transmission to the module.
 * Return Value   @retval        More than 1 -
 *                                  Successfully size check.
 ************************************************************************************************/
static uint16_t cellular_send_size_check(st_cellular_ctrl_t * const p_ctrl, const int32_t length,
                                            const int32_t complete_length)
{
    int32_t  send_size = 0;
    uint16_t ret       = 0;

    if ((length - complete_length) > p_ctrl->sci_ctrl.tx_buff_size)
    {
        send_size = (int32_t)p_ctrl->sci_ctrl.tx_buff_size; //cast
    }
    else
    {
        send_size = (length - complete_length);
    }

    if (send_size > p_ctrl->sci_ctrl.tx_process_size) //tx_process_size is max 1500
    {
        ret = p_ctrl->sci_ctrl.tx_process_size;
    }
    else
    {
        ret = (uint16_t)send_size; // send_size is less than 1500
    }

    return ret;
}
/**********************************************************************************************************************
 * End of function cellular_send_size_check
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_tx_flag_check
 * Description    @details       Wait for transmission completion flag.
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     socket_no -
 *                                  Socket number for sending data.
 * Return Value   @retval        CELLULAR_NOT_TIMEOUT -
 *                                  Successfully flag check.
 *                @retval        CELLULAR_TIMEOUT -
 *                                  Time out.
 ************************************************************************************************/
static e_cellular_timeout_check_t cellular_tx_flag_check(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no)
{
    e_cellular_timeout_check_t timeout = CELLULAR_NOT_TIMEOUT;

    st_cellular_time_ctrl_t * const p_cellular_timeout_ctrl =
            &p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].cellular_tx_timeout_ctrl;

    /* WAIT_LOOP */
    while (1)
    {
        if (CELLULAR_TX_END_FLAG_ON == p_ctrl->sci_ctrl.tx_end_flg)
        {
            break;
        }
#if CELLULAR_CFG_CTS_SW_CTRL == 0
        timeout = cellular_check_timeout(p_cellular_timeout_ctrl);

        if (CELLULAR_TIMEOUT == timeout)
        {
            break;
        }

        cellular_delay_task(1);
#else
        p_cellular_timeout_ctrl->this_time = cellular_get_tickcount();

        if (CELLULAR_TIMEOUT_NOT_OVERFLOW == p_cellular_timeout_ctrl->timeout_overflow_flag)
        {
            if ((p_cellular_timeout_ctrl->this_time >= p_cellular_timeout_ctrl->end_time) ||
                    (p_cellular_timeout_ctrl->this_time < p_cellular_timeout_ctrl->start_time))
            {
                timeout = CELLULAR_TIMEOUT;
                break;
            }
        }
        else
        {
            if ((p_cellular_timeout_ctrl->this_time < p_cellular_timeout_ctrl->start_time) &&
                    (p_cellular_timeout_ctrl->this_time >= p_cellular_timeout_ctrl->end_time))
            {
                timeout = CELLULAR_TIMEOUT;
                break;
            }
        }

        R_BSP_NOP();
#endif  /* CELLULAR_CFG_CTS_SW_CTRL == 0 */
    }

    return timeout;
}
/**********************************************************************************************************************
 * End of function cellular_tx_flag_check
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_atc_response_check
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
static e_cellular_timeout_check_t cellular_atc_response_check(st_cellular_ctrl_t * const p_ctrl,
                                                                    const uint8_t socket_no)
{
    e_cellular_atc_return_t    at_ret  = ATC_RETURN_NONE;
    e_cellular_timeout_check_t timeout = CELLULAR_NOT_TIMEOUT;

    st_cellular_time_ctrl_t * const p_cellular_timeout_ctrl =
            &p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].cellular_tx_timeout_ctrl;

    /* WAIT_LOOP */
    while (1)
    {
        at_ret = cellular_get_atc_response(p_ctrl);
        if ((ATC_RETURN_OK == at_ret) || (ATC_RETURN_ERROR == at_ret))
        {
            break;
        }
#if defined(CELLULAR_TARGET_BG96)
        if (ATC_RETURN_SEND_FAIL == at_ret)
        {
            break;
        }
#endif /* CELLULAR_TARGET_BG96 */

        timeout = cellular_check_timeout(p_cellular_timeout_ctrl);
        if (CELLULAR_TIMEOUT == timeout)
        {
            break;
        }

        cellular_delay_task(1);
    }

    return timeout;
}
/**********************************************************************************************************************
 * End of function cellular_atc_response_check
 *********************************************************************************************************************/

#if defined(CELLULAR_TARGET_BG96)
/*************************************************************************************************
 * Function Name  @fn            cellular_send_fail_resend
 * Description    @details       Decide whether to resend a chunk that BG96 answered with "SEND FAIL"
 *                               (its send buffer is full) and wait before the resend.
 *                               The wait is done without the AT semaphore so that other tasks can run
 *                               AT commands meanwhile, above all AT+QIRD: unread received data can keep
 *                               the peer from reading, and with it the send buffer from emptying.
 *                               While the semaphore is released, another task's AT command may run
 *                               between the chunks of this call.
 *                               Whether BG96 discards the whole chunk on "SEND FAIL" is not confirmed
 *                               against the Quectel manual (a resend assumes it does).
 * Arguments      @param[in/out] p_ctrl -
 *                                  Pointer to managed structure.
 *                @param[in]     socket_no -
 *                                  Socket number for sending data.
 *                @param[in/out] p_retry_count -
 *                                  Resends of the current chunk so far.
 *                @param[out]    p_ret -
 *                                  Set to CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING when the AT semaphore
 *                                  could not be taken back within CELLULAR_CFG_SEMAPHORE_BLOCK_TIME.
 * Return Value   @retval        true -
 *                                  Resend the chunk. The AT semaphore is held again.
 *                @retval        false -
 *                                  Stop sending: the resend limit or the timeout_ms deadline was reached
 *                                  (also when the AT semaphore was taken back past the deadline; it is
 *                                  then held), or the AT semaphore could not be taken back (see p_ret).
 *                                  When the semaphore was released and is not held again, s_send_released
 *                                  is set for the socket.
 ************************************************************************************************/
static bool cellular_send_fail_resend(st_cellular_ctrl_t * const p_ctrl, const uint8_t socket_no,
                                        uint8_t * const p_retry_count, e_cellular_err_t * const p_ret)
{
    bool     resend    = false;
    uint32_t waited_ms = 0;

    st_cellular_time_ctrl_t * const p_cellular_timeout_ctrl =
            &p_ctrl->p_socket_ctrl[socket_no - CELLULAR_START_SOCKET_NUMBER].cellular_tx_timeout_ctrl;

    if ((BG96_SEND_FAIL_RETRY_MAX > (*p_retry_count)) &&
        (CELLULAR_NOT_TIMEOUT == cellular_check_timeout(p_cellular_timeout_ctrl)))
    {
        (*p_retry_count)++;
        CELLULAR_LOG_DEBUG(("SEND FAIL: resend %d of %d\n", (int)(*p_retry_count), (int)BG96_SEND_FAIL_RETRY_MAX));

        cellular_send_flag_set(&s_send_released, socket_no, true);
        cellular_give_semaphore(p_ctrl->at_semaphore);

        /* The wait and the taking back are done in short steps so that neither goes past the timeout_ms
         * deadline. Taking back gives up after CELLULAR_CFG_SEMAPHORE_BLOCK_TIME, as the first take does. */
        /* WAIT_LOOP */
        while ((BG96_SEND_FAIL_RETRY_WAIT_MS > waited_ms) &&
               (CELLULAR_NOT_TIMEOUT == cellular_check_timeout(p_cellular_timeout_ctrl)))
        {
            cellular_delay_task(BG96_SEND_FAIL_POLL_MS);
            waited_ms += BG96_SEND_FAIL_POLL_MS;
        }

        waited_ms = 0;
        /* WAIT_LOOP */
        while (CELLULAR_NOT_TIMEOUT == cellular_check_timeout(p_cellular_timeout_ctrl))
        {
            if (CELLULAR_SEMAPHORE_SUCCESS == cellular_take_semaphore_wait(p_ctrl->at_semaphore,
                                                                            BG96_SEND_FAIL_POLL_MS))
            {
                cellular_send_flag_set(&s_send_released, socket_no, false);

                /* The take may end past the deadline: then no new AT+QISEND is started, and sending stops
                 * with the bytes sent so far and the semaphore held. */
                if (CELLULAR_NOT_TIMEOUT == cellular_check_timeout(p_cellular_timeout_ctrl))
                {
                    resend = true;
                }
                break;
            }
            waited_ms += BG96_SEND_FAIL_POLL_MS;
            if (CELLULAR_CFG_SEMAPHORE_BLOCK_TIME <= waited_ms)
            {
                *p_ret = CELLULAR_ERR_OTHER_ATCOMMAND_RUNNING;
                break;
            }
        }
        /* Not resent with s_send_released still set: the deadline passed before the semaphore was taken back
         * (stop with the bytes sent so far) or the semaphore could not be taken back. Either way the
         * semaphore is not held. */
    }

    return resend;
}
/**********************************************************************************************************************
 * End of function cellular_send_fail_resend
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_send_flag_set
 * Description    @details       Set or clear the bit of a socket in s_send_busy or s_send_released.
 ************************************************************************************************/
static void cellular_send_flag_set(volatile uint8_t * const p_flags, const uint8_t socket_no, const bool on)
{
    const uint8_t bit        = (uint8_t)(1U << (socket_no - CELLULAR_START_SOCKET_NUMBER)); //cast
    uint32_t      preemption = cellular_interrupt_disable();

    if (true == on)
    {
        *p_flags = (uint8_t)(*p_flags | bit);       //cast
    }
    else
    {
        *p_flags = (uint8_t)(*p_flags & (~bit));    //cast
    }
    cellular_interrupt_enable(preemption);
}
/**********************************************************************************************************************
 * End of function cellular_send_flag_set
 *********************************************************************************************************************/

/*************************************************************************************************
 * Function Name  @fn            cellular_send_flag_get
 * Description    @details       Whether the bit of a socket is set in s_send_busy or s_send_released.
 ************************************************************************************************/
static bool cellular_send_flag_get(const volatile uint8_t * const p_flags, const uint8_t socket_no)
{
    const uint8_t bit = (uint8_t)(1U << (socket_no - CELLULAR_START_SOCKET_NUMBER)); //cast

    return (0U != ((*p_flags) & bit));
}
/**********************************************************************************************************************
 * End of function cellular_send_flag_get
 *********************************************************************************************************************/
#endif /* CELLULAR_TARGET_BG96 */
