/*
 * Copyright (c) 2026
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */

/**********************************************************************************************************************
 * File Name    : spi_logic_probe.c
 * Description  : SCI2 simple-SPI waveform generator for RX72N Envision Kit PMOD1(CN1).
 *********************************************************************************************************************/

/******************************************************************************
 Includes   <System Includes> , "Project Includes"
 ******************************************************************************/
#include <stdbool.h>
#include <stdint.h>

#include "platform.h"
#include "r_sci_rx_if.h"
#include "r_pinset.h"
#include "FreeRTOS.h"
#include "task.h"

#include "spi_logic_probe.h"

/******************************************************************************
 External function prototypes
 ******************************************************************************/
void R_SCI_PinSet_SCI2(void);

/**********************************************************************************************************************
 Macro definitions
 *********************************************************************************************************************/
#define SPI_PROBE_CHANNEL       (SCI_CH2)
#ifndef SPI_PROBE_BIT_RATE
#define SPI_PROBE_BIT_RATE      (1000000UL)
#endif
#define SPI_PROBE_INT_PRIORITY  (5U)
#define SPI_PROBE_PERIOD_MS     (10U)
#define SPI_PROBE_SEND_TIMEOUT  (1000000UL)

/**********************************************************************************************************************
 Private global variables
 *********************************************************************************************************************/
static sci_hdl_t s_sci_hdl = FIT_NO_PTR;
static volatile bool s_transfer_done = false;

/**********************************************************************************************************************
 Private function prototypes
 *********************************************************************************************************************/
static void spi_logic_probe_callback(void *p_args);
static void spi_logic_probe_configure_cs_pin(void);
static void spi_logic_probe_cs_low(void);
static void spi_logic_probe_cs_high(void);

/**********************************************************************************************************************
* Function Name: SPI_LogicProbeRun
* Description  : Outputs repeated SPI frames on PMOD1(CN1): P54=CS, P50=MOSI, P52=MISO, P51=SCK.
* Arguments    : none
* Return Value : none
**********************************************************************************************************************/
void SPI_LogicProbeRun(void)
{
    static uint8_t tx_pattern[] =
    {
        0xA5U, 0x5AU, 0x3CU, 0xC3U,
        0x00U, 0xFFU, 0x81U, 0x7EU
    };
    sci_cfg_t cfg;
    sci_err_t sci_err;

    cfg.sspi.spi_mode = SCI_SPI_MODE_0;
    cfg.sspi.bit_rate = SPI_PROBE_BIT_RATE;
    cfg.sspi.msb_first = true;
    cfg.sspi.invert_data = false;
    cfg.sspi.int_priority = SPI_PROBE_INT_PRIORITY;

    sci_err = R_SCI_Open(SPI_PROBE_CHANNEL, SCI_MODE_SSPI, &cfg, spi_logic_probe_callback, &s_sci_hdl);
    if (SCI_SUCCESS == sci_err)
    {
        R_SCI_PinSet_SCI2();
    }

    spi_logic_probe_configure_cs_pin();
    spi_logic_probe_cs_high();

    while (1)
    {
        if ((SCI_SUCCESS == sci_err) && (FIT_NO_PTR != s_sci_hdl))
        {
            uint32_t timeout = SPI_PROBE_SEND_TIMEOUT;

            s_transfer_done = false;
            spi_logic_probe_cs_low();
            if (SCI_SUCCESS == R_SCI_Send(s_sci_hdl, tx_pattern, (uint16_t)sizeof(tx_pattern)))
            {
                while ((false == s_transfer_done) && (timeout > 0UL))
                {
                    timeout--;
                    taskYIELD();
                }
            }
            spi_logic_probe_cs_high();
        }
        else
        {
            spi_logic_probe_cs_low();
            vTaskDelay(pdMS_TO_TICKS(1U));
            spi_logic_probe_cs_high();
        }

        vTaskDelay(pdMS_TO_TICKS(SPI_PROBE_PERIOD_MS));
    }
}

/**********************************************************************************************************************
* Function Name: spi_logic_probe_callback
* Description  : SCI transfer completion callback.
* Arguments    : p_args -
*                    SCI callback arguments.
* Return Value : none
**********************************************************************************************************************/
static void spi_logic_probe_callback(void *p_args)
{
    sci_cb_args_t *p_sci_args = (sci_cb_args_t *)p_args;

    if ((FIT_NO_PTR != p_sci_args) && (SCI_EVT_XFER_DONE == p_sci_args->event))
    {
        s_transfer_done = true;
    }
}

/**********************************************************************************************************************
* Function Name: spi_logic_probe_configure_cs_pin
* Description  : Configures PMOD1 Pin1 / SS2# (P54) as a GPIO chip-select signal.
* Arguments    : none
* Return Value : none
**********************************************************************************************************************/
static void spi_logic_probe_configure_cs_pin(void)
{
    PORT5.PMR.BIT.B4 = 0U;
    PORT5.PODR.BIT.B4 = 1U;
    PORT5.PDR.BIT.B4 = 1U;
}

/**********************************************************************************************************************
* Function Name: spi_logic_probe_cs_low
* Description  : Assert PMOD1 Pin1 / SS2# (P54).
* Arguments    : none
* Return Value : none
**********************************************************************************************************************/
static void spi_logic_probe_cs_low(void)
{
    PORT5.PODR.BIT.B4 = 0U;
}

/**********************************************************************************************************************
* Function Name: spi_logic_probe_cs_high
* Description  : Deassert PMOD1 Pin1 / SS2# (P54).
* Arguments    : none
* Return Value : none
**********************************************************************************************************************/
static void spi_logic_probe_cs_high(void)
{
    PORT5.PODR.BIT.B4 = 1U;
}
