/* Generated configuration header file - do not edit */
/***********************************************************************************************************************
* Copyright (c) 2026 SAFFTI (Smart Agriculture, Forestry & Fisheries Technology Institute) and contributors
*
* SPDX-License-Identifier: BSD-3-Clause
***********************************************************************************************************************/
/***********************************************************************************************************************
* File Name    : r_sdio_rx_config.h
* Description  : Configuration for r_sdio_rx FIT module.
***********************************************************************************************************************/
#ifndef R_SDIO_RX_CONFIG_H
#define R_SDIO_RX_CONFIG_H

/* SPECIFY WHETHER TO INCLUDE CODE FOR API PARAMETER CHECKING */
/* Setting to BSP_CFG_PARAM_CHECKING_ENABLE utilizes the system default setting */
/* Setting to 1 includes parameter checking; 0 compiles out parameter checking */
#define SDIO_CFG_PARAM_CHECKING_ENABLE          (BSP_CFG_PARAM_CHECKING_ENABLE)

/* Maximum byte-mode CMD53 transfer count accepted by the wrapper APIs. */
#define SDIO_CFG_CMD53_MAX_BYTE_COUNT           (512)

/* Default number of IO_READY polling attempts used by R_SDIO_EnableFunction. */
#define SDIO_CFG_IO_READY_POLL_COUNT            (1000)

/* Cache Broadcom/Infineon backplane window register state in the control block. */
#define SDIO_CFG_BACKPLANE_WINDOW_CACHE_ENABLE  (1)

#endif /* R_SDIO_RX_CONFIG_H */
