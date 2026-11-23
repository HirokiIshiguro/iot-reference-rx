/***********************************************************************************************************************
* DISCLAIMER
* This software is supplied by Renesas Electronics Corporation and is only intended for use with Renesas products. No 
* other uses are authorized. This software is owned by Renesas Electronics Corporation and is protected under all 
* applicable laws, including copyright laws. 
* THIS SOFTWARE IS PROVIDED "AS IS" AND RENESAS MAKES NO WARRANTIES REGARDING
* THIS SOFTWARE, WHETHER EXPRESS, IMPLIED OR STATUTORY, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, 
* FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. ALL SUCH WARRANTIES ARE EXPRESSLY DISCLAIMED. TO THE MAXIMUM 
* EXTENT PERMITTED NOT PROHIBITED BY LAW, NEITHER RENESAS ELECTRONICS CORPORATION NOR ANY OF ITS AFFILIATED COMPANIES 
* SHALL BE LIABLE FOR ANY DIRECT, INDIRECT, SPECIAL, INCIDENTAL OR CONSEQUENTIAL DAMAGES FOR ANY REASON RELATED TO THIS 
* SOFTWARE, EVEN IF RENESAS OR ITS AFFILIATES HAVE BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.
* Renesas reserves the right, without notice, to make changes to this software and to discontinue the availability of 
* this software. By using this software, you agree to the additional terms and conditions found by accessing the 
* following link:
* http://www.renesas.com/disclaimer 
*
* Copyright (C) 2013-2019 Renesas Electronics Corporation. All rights reserved.
***********************************************************************************************************************/
/***********************************************************************************************************************
* File Name     : r_simple_glcdc_config_rx_config.h
* Description   : Configures the GLCDC driver
************************************************************************************************************************
* History : DD.MM.YYYY Version Description
*           04.01.2019 0.80    Initial Release
***********************************************************************************************************************/
#ifndef GLCDC_CONFIG_CONFIG_H
#define GLCDC_CONFIG_CONFIG_H

#include "platform.h"

/***********************************************************************************************************************
Configuration Options
***********************************************************************************************************************/

#define XSIZE_PHYS 480
#define YSIZE_PHYS 272
#define XSIZE_OUTOF_DISPLAY 32

#define _BRIGHTNESS 0x200
#define _CONTRAST   0x80
#define DISP_SIGNAL_PORT_DIRECTION 			PORTB.PDR.BIT.B3
#define DISP_SIGNAL_PORT_OUTPUT_DATA 		PORTB.PODR.BIT.B3
#define BACKLIGHT_SIGNAL_PORT_DIRECTION 	PORT6.PDR.BIT.B7
#define BACKLIGHT_SIGNAL_PORT_OUTPUT_DATA 	PORT6.PODR.BIT.B7


/* Public interface of r_simple_glcdc_config_rx 1.01. */
#define R_SIMPLE_GLCDC_CFG_BITS_PER_PIXEL       (8)
#define R_SIMPLE_GLCDC_CFG_BYTES_PER_LINE       ((R_SIMPLE_GLCDC_CFG_BITS_PER_PIXEL * XSIZE_PHYS) / 8)
#define R_SIMPLE_GLCDC_CFG_LINE_OFFSET          (((R_SIMPLE_GLCDC_CFG_BYTES_PER_LINE + 63) / 64) * 64)
#define R_SIMPLE_GLCDC_CFG_VXSIZE_PHYS          ((R_SIMPLE_GLCDC_CFG_LINE_OFFSET * 8) / R_SIMPLE_GLCDC_CFG_BITS_PER_PIXEL)
#define R_SIMPLE_GLCDC_CFG_FRAME_BUFFER_BYTES   (R_SIMPLE_GLCDC_CFG_LINE_OFFSET * YSIZE_PHYS)

#endif /* GLCDC_CONFIG_CONFIG_H */
