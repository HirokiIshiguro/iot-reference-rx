/*
 * Copyright (c) 2015 Renesas Electronics Corporation and/or its affiliates
 *
 * SPDX-License-Identifier: BSD-3-Clause
 */
/**********************************************************************************************************************
 * History : DD.MM.YYYY Version  Description
 *         : 27.06.2015 1.00     First Release
 *         : 15.05.2017 1.01     Add AES-CMAC
 *         : 30.09.2017 1.03     Add Init/Update/Final API and SHA, RSA
 *         : 28.02.2018 1.04     Change Init/Update/Final API for RX231, add TLS function and 
 *         :                     return values change FIT rules.
 *         : 30.04.2018 1.05     Add TDES, MD5 and RSAES-PKCS1-v1_5 API
 *         : 28.09.2018 1.06     Add RSA Key Generation, AES, TDES, RSA Key update features, RX66T support
 *         : 28.12.2018 1.07     Add RX72T support
 *         : 30.09.2019 1.08     Added support for GCC and IAR compiler, ECC API, RX23W and RX72M
 *         : 31.03.2020 1.09     Added support for AES-CCM, HMAC key generation, ECDH, Key Wrap API, RX66N and RX72N
 *         : 30.06.2020 1.10     Added support for ARC4, ECC(P-384) API
 *         : 30.09.2020 1.11     Added support for DH, ECDHE P-512r1 API, and generalization of KDF.
 *         :                     Added support for Key wrap API with TSIP-Lite.
 *         : 30.06.2021 1.12     Added support for RX23W chip version D
 *         : 31.08.2021 1.13     Added support for RX671
 *         : 22.10.2021 1.14     Added support for TLS1.3
 *         : 31.03.2022 1.15     Added support for TLS1.3(RX72M_RX72N_RX66N)
 *         : 15.09.2022 1.16     Added support for RSA 3k/4k and updated support for TLS1.3
 *         : 20.01.2023 1.17     Added support for TLS1.3 server
 *         : 24.05.2023 1.18     Added support for RX26T
 *         : 30.11.2023 1.19     Update example of Secure Bootloader / Firmware Update
 *         : 28.02.2024 1.20     Applied software workaround of AES-CCM decryption
 *         : 28.06.2024 1.21     Added support for TLS1.2 server
 *         : 10.04.2025 1.22     Added support for RSAES-OAEP, SSH
 *         :                     Updated Firmware Update API
 *         : 15.10.2025 1.23     Updated Open/Close API to store the driver status
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include "../r_tsip_rx_private.h"

/**********************************************************************************************************************
 Macro definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Typedef definitions
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Imported global variables and functions (from other files)
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Exported global variables (to be accessed by other files)
 *********************************************************************************************************************/

/**********************************************************************************************************************
 Private global variables and functions
 *********************************************************************************************************************/

/***********************************************************************************************************************
* Function Name: RX72M_RX72N_RX66N_func405
*******************************************************************************************************************/ /**
* @details       RX72M func405
* @param[in]     ARG1
* @param[in]     ARG2
* @param[in]     ARG3
* @param[in]     ARG4
* @param[in]     ARG5
* @param[in]     ARG6
* @param[in]     ARG7
* @param[in]     ARG8
* @param[in]     ARG9
* @note          None
*/
void RX72M_RX72N_RX66N_func405(uint32_t ARG1, uint32_t ARG2, uint32_t *ARG3, uint32_t *ARG4, uint32_t *ARG5, uint32_t *ARG6, uint32_t *ARG7, const uint32_t *ARG8, uint32_t *ARG9)
{
    int32_t iLoop = 0u, jLoop = 0u, kLoop = 0u, oLoop1 = 0u, oLoop2 = 0u, iLoop2 = 0u;
    uint32_t KEY_ADR = 0u, OFS_ADR = 0u;
    (void)iLoop;
    (void)jLoop;
    (void)kLoop;
    (void)iLoop2;
    (void)oLoop1;
    (void)oLoop2;
    (void)KEY_ADR;
    (void)OFS_ADR;
    TSIP.REG_104H.WORD = 0x00000068u;
    TSIP.REG_E0H.WORD = 0x800101e0u;
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = ARG3[0];
    TSIP.REG_ECH.WORD = 0x00000bffu;
    TSIP.REG_ECH.WORD = 0x38000defu;
    TSIP.REG_ECH.WORD = 0x1000d3e0u;
    TSIP.REG_ECH.WORD = 0x380089e0u;
    TSIP.REG_ECH.WORD = 0x00000002u;
    TSIP.REG_ECH.WORD = 0x1000d3e1u;
    TSIP.REG_ECH.WORD = 0x38000fffu;
    TSIP.REG_E0H.WORD = 0x00000080u;
    TSIP.REG_1CH.WORD = 0x00260000u;
    RX72M_RX72N_RX66N_func100(change_endian_long(0x5d3dff92u), change_endian_long(0xf114c5feu), change_endian_long(0xca11c28du), change_endian_long(0xc96a52c8u));
    TSIP.REG_1CH.WORD = 0x00400000u;
    TSIP.REG_1D0H.WORD = 0x00000000u;
    if (1u == (TSIP.REG_1CH.BIT.B22))
    {
        TSIP.REG_ECH.WORD = 0x0000b400u;
        TSIP.REG_ECH.WORD = 0xffffffffu;
        RX72M_RX72N_RX66N_func101(change_endian_long(0x44d290bau), change_endian_long(0x4b0c2f57u), change_endian_long(0xcf64d4a8u), change_endian_long(0xbc17108fu));
    }
    else
    {
        RX72M_RX72N_RX66N_func100(change_endian_long(0x92940406u), change_endian_long(0x4b16ed19u), change_endian_long(0x052ef66eu), change_endian_long(0x5c83a98au));
        TSIP.REG_104H.WORD = 0x00000468u;
        TSIP.REG_E0H.WORD = 0x800502c0u;
        /* WAIT_LOOP */
        while (1u != TSIP.REG_104H.BIT.B31)
        {
            /* waiting */
        }
        TSIP.REG_100H.WORD = ARG5[0];
        for (iLoop = 0; iLoop < 4; iLoop = iLoop + 1)
        {
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = ARG7[iLoop];
        }
        TSIP.REG_ECH.WORD = 0x00007c0fu;
        TSIP.REG_1CH.WORD = 0x00600000u;
        TSIP.REG_1D0H.WORD = 0x00000000u;
        if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
        {
            TSIP.REG_ECH.WORD = 0x3c002af8u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_ECH.WORD = 0x3c002b19u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_ECH.WORD = 0x3c002b59u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00A60000u;
            TSIP.REG_ECH.WORD = 0x3c002b56u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_ECH.WORD = 0x00003417u;
            TSIP.REG_ECH.WORD = 0x0000a400u;
            TSIP.REG_ECH.WORD = 0x000000ffu;
            TSIP.REG_ECH.WORD = 0x08002818u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00A60000u;
            TSIP.REG_ECH.WORD = 0x00003419u;
            TSIP.REG_ECH.WORD = 0x0000a400u;
            TSIP.REG_ECH.WORD = 0x00000003u;
            TSIP.REG_ECH.WORD = 0x0c00281au;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00A60000u;
            RX72M_RX72N_RX66N_func101(change_endian_long(0xebbb8745u), change_endian_long(0x91f23908u), change_endian_long(0x23864b62u), change_endian_long(0x4fea2465u));
        }
        else
        {
            TSIP.REG_ECH.WORD = 0x3c002af8u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_ECH.WORD = 0x3c002b19u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_ECH.WORD = 0x3c002b3au;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_ECH.WORD = 0x3c002b56u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_ECH.WORD = 0x00003417u;
            TSIP.REG_ECH.WORD = 0x0000a400u;
            TSIP.REG_ECH.WORD = 0x0000001fu;
            TSIP.REG_ECH.WORD = 0x08002818u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00A60000u;
            TSIP.REG_ECH.WORD = 0x00003419u;
            TSIP.REG_ECH.WORD = 0x0000a400u;
            TSIP.REG_ECH.WORD = 0x0000001fu;
            TSIP.REG_ECH.WORD = 0x0800281au;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00A60000u;
            RX72M_RX72N_RX66N_func101(change_endian_long(0x43fbc496u), change_endian_long(0xa7693ad2u), change_endian_long(0xfd0b13dfu), change_endian_long(0xd9893c56u));
        }
        RX72M_RX72N_RX66N_func100(change_endian_long(0x737694a2u), change_endian_long(0x972dc394u), change_endian_long(0x1d689ef6u), change_endian_long(0xcf42cdf4u));
        TSIP.REG_1CH.WORD = 0x00400000u;
        TSIP.REG_1D0H.WORD = 0x00000000u;
        if (1u == (TSIP.REG_1CH.BIT.B22))
        {
            TSIP.REG_ECH.WORD = 0x0000b400u;
            TSIP.REG_ECH.WORD = 0xffffffffu;
            RX72M_RX72N_RX66N_func101(change_endian_long(0xc3f8c2f4u), change_endian_long(0x95a6461eu), change_endian_long(0x62cb0442u), change_endian_long(0xbb3e2a95u));
        }
        else
        {
            RX72M_RX72N_RX66N_func100(change_endian_long(0x5c5bc3f5u), change_endian_long(0x4df453f1u), change_endian_long(0xd2e61deau), change_endian_long(0x41d245f1u));
            TSIP.REG_C4H.WORD = 0x200c3b0du;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = S_INST[ARG1 + 0];
            TSIP.REG_100H.WORD = S_INST[ARG1 + 1];
            TSIP.REG_100H.WORD = S_INST[ARG1 + 2];
            TSIP.REG_100H.WORD = S_INST[ARG1 + 3];
            TSIP.REG_C4H.WORD = 0x00080b8cu;
            TSIP.REG_E0H.WORD = 0x81010240u;
            TSIP.REG_00H.WORD = 0x00002807u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_C4H.WORD = 0x400c0b0cu;
            TSIP.REG_E0H.WORD = 0x81010260u;
            TSIP.REG_00H.WORD = 0x00002807u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_28H.WORD = 0x00bf0001u;
            TSIP.REG_00H.WORD = 0x00013203u;
            TSIP.REG_2CH.WORD = 0x00000014u;
            TSIP.REG_104H.WORD = 0x00007f62u;
            TSIP.REG_D0H.WORD = 0x00001f00u;
            TSIP.REG_C4H.WORD = 0x02f087bfu;
            for (iLoop = 0; iLoop < 64; iLoop = iLoop + 4)
            {
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 0];
                TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 1];
                TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 2];
                TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 3];
            }
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_00H.WORD = 0x00013203u;
            TSIP.REG_2CH.WORD = 0x00000012u;
            for ( ; iLoop < 128; iLoop = iLoop + 4)
            {
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 0];
                TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 1];
                TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 2];
                TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 3];
            }
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_C4H.WORD = 0x00f007bdu;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 0];
            TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 1];
            TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 2];
            TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 3];
            iLoop = iLoop+4;
            TSIP.REG_E0H.WORD = 0x80040140u;
            TSIP.REG_00H.WORD = 0x00008213u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_C4H.WORD = 0x000007bdu;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 0];
            TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 1];
            TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 2];
            TSIP.REG_100H.WORD = S_INST[ARG2+iLoop + 3];
            TSIP.REG_C4H.WORD = 0x00800c45u;
            TSIP.REG_00H.WORD = 0x00002213u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_7CH.WORD = 0x00000011u;
            TSIP.REG_104H.WORD = 0x00000754u;
            TSIP.REG_74H.WORD = 0x00000004u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = change_endian_long(0x6a09e667u);
            TSIP.REG_100H.WORD = change_endian_long(0xbb67ae85u);
            TSIP.REG_100H.WORD = change_endian_long(0x3c6ef372u);
            TSIP.REG_100H.WORD = change_endian_long(0xa54ff53au);
            TSIP.REG_100H.WORD = change_endian_long(0x510e527fu);
            TSIP.REG_100H.WORD = change_endian_long(0x9b05688cu);
            TSIP.REG_100H.WORD = change_endian_long(0x1f83d9abu);
            TSIP.REG_100H.WORD = change_endian_long(0x5be0cd19u);
            TSIP.REG_74H.WORD = 0x00000002u;
            TSIP.REG_ECH.WORD = 0x00003417u;
            TSIP.REG_ECH.WORD = 0x00046800u;
            TSIP.REG_ECH.WORD = 0x00026c00u;
            TSIP.REG_E0H.WORD = 0x81010000u;
            TSIP.REG_04H.WORD = 0x00000606u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
            TSIP.REG_ECH.WORD = 0x000008a5u;
            for (iLoop = 0; iLoop < S_RAM[0]; iLoop = iLoop + 4)
            {
                TSIP.REG_104H.WORD = 0x00000364u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = ARG4[iLoop+0];
                TSIP.REG_100H.WORD = ARG4[iLoop+1];
                TSIP.REG_100H.WORD = ARG4[iLoop+2];
                TSIP.REG_100H.WORD = ARG4[iLoop+3];
                TSIP.REG_ECH.WORD = 0x0000a4a0u;
                TSIP.REG_ECH.WORD = 0x00000004u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0x23fa872fu), change_endian_long(0x79ede766u), change_endian_long(0x644ccfd4u), change_endian_long(0x75fa45edu));
            }
            RX72M_RX72N_RX66N_func100(change_endian_long(0x923bc444u), change_endian_long(0x2e47d56au), change_endian_long(0xca82f6c3u), change_endian_long(0xb3880c88u));
            TSIP.REG_ECH.WORD = 0x38000805u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_1CH.WORD = 0x00402000u;
            TSIP.REG_ECH.WORD = 0x00007c0fu;
            TSIP.REG_1CH.WORD = 0x00600000u;
            TSIP.REG_1D0H.WORD = 0x00000000u;
            if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
            {
                RX72M_RX72N_RX66N_func100(change_endian_long(0x667d0b75u), change_endian_long(0x182f61efu), change_endian_long(0xafcd55f2u), change_endian_long(0x79dc10ecu));
                TSIP.REG_28H.WORD = 0x00bf0001u;
                TSIP.REG_2CH.WORD = 0x00000010u;
                TSIP.REG_ECH.WORD = 0x00003416u;
                TSIP.REG_ECH.WORD = 0x00026800u;
                TSIP.REG_ECH.WORD = 0x38008ec0u;
                TSIP.REG_ECH.WORD = 0x00000003u;
                TSIP.REG_ECH.WORD = 0x20002c00u;
                TSIP.REG_E0H.WORD = 0x81010000u;
                TSIP.REG_04H.WORD = 0x00000606u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
                TSIP.REG_ECH.WORD = 0x00003445u;
                TSIP.REG_ECH.WORD = 0x00026c42u;
                TSIP.REG_ECH.WORD = 0x000034d6u;
                TSIP.REG_ECH.WORD = 0x000030c0u;
                TSIP.REG_ECH.WORD = 0x00000a10u;
                for ( ; iLoop < S_RAM[0]; iLoop = iLoop + 1)
                {
                    TSIP.REG_104H.WORD = 0x00000068u;
                    TSIP.REG_E0H.WORD = 0x80010100u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = ARG4[iLoop];
                    TSIP.REG_ECH.WORD = 0x0000b420u;
                    TSIP.REG_ECH.WORD = 0x00000004u;
                    for (jLoop = 0; jLoop < 4; jLoop = jLoop + 1)
                    {
                        TSIP.REG_ECH.WORD = 0x00003020u;
                        TSIP.REG_ECH.WORD = 0x01886ce8u;
                        TSIP.REG_ECH.WORD = 0x00086d08u;
                        TSIP.REG_ECH.WORD = 0x00000863u;
                        TSIP.REG_ECH.WORD = 0x3c002859u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x3c002b42u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x30000c63u;
                        TSIP.REG_ECH.WORD = 0x00030020u;
                        TSIP.REG_ECH.WORD = 0x00186ce7u;
                        TSIP.REG_ECH.WORD = 0x01886e07u;
                        TSIP.REG_ECH.WORD = 0x001868e7u;
                        TSIP.REG_ECH.WORD = 0x00000080u;
                        TSIP.REG_ECH.WORD = 0x00000863u;
                        TSIP.REG_ECH.WORD = 0x3c002857u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x3c002b02u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x38000c63u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x174a3b6fu), change_endian_long(0x8efef222u), change_endian_long(0xf4a7fc3du), change_endian_long(0xc11c471au));
                        TSIP.REG_1CH.WORD = 0x00400000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (1u == (TSIP.REG_1CH.BIT.B22))
                        {
                            TSIP.REG_E0H.WORD = 0x810100e0u;
                            TSIP.REG_00H.WORD = 0x0800080fu;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            TSIP.REG_00H.WORD = 0x08003807u;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            RX72M_RX72N_RX66N_func101(change_endian_long(0xd2eef8cau), change_endian_long(0xbd24127bu), change_endian_long(0x9e3cfa17u), change_endian_long(0x95aa400au));
                        }
                        TSIP.REG_ECH.WORD = 0x00000863u;
                        TSIP.REG_ECH.WORD = 0x3c0028c2u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x38000c63u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0xfc6f47b3u), change_endian_long(0xefd2bba2u), change_endian_long(0xaf997155u), change_endian_long(0x115cbe5eu));
                        TSIP.REG_1CH.WORD = 0x00400000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (1u == (TSIP.REG_1CH.BIT.B22))
                        {
                            TSIP.REG_E0H.WORD = 0x810100e0u;
                            TSIP.REG_00H.WORD = 0x0800080fu;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            TSIP.REG_00H.WORD = 0x08005807u;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x8f284fc6u), change_endian_long(0x351a6aebu), change_endian_long(0x33651ac6u), change_endian_long(0xa341ed56u));
                        }
                        TSIP.REG_ECH.WORD = 0x00002c40u;
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x3863ff39u), change_endian_long(0xade8b335u), change_endian_long(0x9fe977a2u), change_endian_long(0x48c70bbfu));
                    }
                    TSIP.REG_ECH.WORD = 0x08000c21u;
                    TSIP.REG_E0H.WORD = 0x00000080u;
                    TSIP.REG_1CH.WORD = 0x00260000u;
                    TSIP.REG_1CH.WORD = 0x00402000u;
                    TSIP.REG_ECH.WORD = 0x00002ca0u;
                    RX72M_RX72N_RX66N_func101(change_endian_long(0xa79db8b2u), change_endian_long(0x1071b78bu), change_endian_long(0xb0a706f5u), change_endian_long(0xba70666eu));
                }
                TSIP.REG_ECH.WORD = 0x38000805u;
                TSIP.REG_E0H.WORD = 0x00000080u;
                TSIP.REG_1CH.WORD = 0x00260000u;
                TSIP.REG_1CH.WORD = 0x00402000u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0xe80a8d73u), change_endian_long(0x2aa7cc9bu), change_endian_long(0x734284dau), change_endian_long(0x310f5a89u));
            }
            else
            {
                RX72M_RX72N_RX66N_func100(change_endian_long(0x90c8adc6u), change_endian_long(0x3135d82au), change_endian_long(0x187231c2u), change_endian_long(0xd66d0aa5u));
                TSIP.REG_28H.WORD = 0x008f0001u;
                TSIP.REG_2CH.WORD = 0x00000010u;
                TSIP.REG_ECH.WORD = 0x00003416u;
                TSIP.REG_ECH.WORD = 0x00026800u;
                TSIP.REG_ECH.WORD = 0x38008ec0u;
                TSIP.REG_ECH.WORD = 0x00000003u;
                TSIP.REG_ECH.WORD = 0x20002c00u;
                TSIP.REG_E0H.WORD = 0x81010000u;
                TSIP.REG_04H.WORD = 0x00000606u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
                TSIP.REG_ECH.WORD = 0x00003445u;
                TSIP.REG_ECH.WORD = 0x00026c42u;
                TSIP.REG_ECH.WORD = 0x000034d6u;
                TSIP.REG_ECH.WORD = 0x000030c0u;
                TSIP.REG_ECH.WORD = 0x00000a10u;
                for ( ; iLoop < S_RAM[0]; iLoop = iLoop + 1)
                {
                    TSIP.REG_104H.WORD = 0x00000068u;
                    TSIP.REG_E0H.WORD = 0x80010100u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = ARG4[iLoop];
                    TSIP.REG_ECH.WORD = 0x0000b420u;
                    TSIP.REG_ECH.WORD = 0x00000004u;
                    for (jLoop = 0; jLoop < 4; jLoop = jLoop + 1)
                    {
                        TSIP.REG_ECH.WORD = 0x00003020u;
                        TSIP.REG_ECH.WORD = 0x01886ce8u;
                        TSIP.REG_ECH.WORD = 0x00086d08u;
                        TSIP.REG_ECH.WORD = 0x00000863u;
                        TSIP.REG_ECH.WORD = 0x3c002859u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x3c002b42u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x38000c63u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x747d52e0u), change_endian_long(0x5588ecebu), change_endian_long(0xe163cf96u), change_endian_long(0xa6855a16u));
                        TSIP.REG_1CH.WORD = 0x00400000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (1u == (TSIP.REG_1CH.BIT.B22))
                        {
                            TSIP.REG_E0H.WORD = 0x810100e0u;
                            TSIP.REG_00H.WORD = 0x0800080fu;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            TSIP.REG_00H.WORD = 0x08003807u;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x5d1c5d3bu), change_endian_long(0xafdf2830u), change_endian_long(0x77eac8bfu), change_endian_long(0xd870f11au));
                        }
                        TSIP.REG_ECH.WORD = 0x00000863u;
                        TSIP.REG_ECH.WORD = 0x3c002857u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x3c002b02u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x38000c63u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x36ca7eb6u), change_endian_long(0x4b9df837u), change_endian_long(0xe9dbe00eu), change_endian_long(0xdd82c0a2u));
                        TSIP.REG_1CH.WORD = 0x00400000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (1u == (TSIP.REG_1CH.BIT.B22))
                        {
                            TSIP.REG_E0H.WORD = 0x810100e0u;
                            TSIP.REG_00H.WORD = 0x0800080fu;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            TSIP.REG_00H.WORD = 0x08003807u;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x14d29dd8u), change_endian_long(0xf0724457u), change_endian_long(0xe4a92a10u), change_endian_long(0x2c1f2c56u));
                        }
                        TSIP.REG_ECH.WORD = 0x00000863u;
                        TSIP.REG_ECH.WORD = 0x3c0028c2u;
                        TSIP.REG_ECH.WORD = 0x20002c60u;
                        TSIP.REG_ECH.WORD = 0x38000c63u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x5e9debcau), change_endian_long(0x01edcc27u), change_endian_long(0xfdbb0443u), change_endian_long(0xa97fef07u));
                        TSIP.REG_1CH.WORD = 0x00400000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (1u == (TSIP.REG_1CH.BIT.B22))
                        {
                            TSIP.REG_E0H.WORD = 0x810100e0u;
                            TSIP.REG_00H.WORD = 0x0800080fu;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            TSIP.REG_00H.WORD = 0x08005807u;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x89b14342u), change_endian_long(0x68b12e81u), change_endian_long(0xf35d1cb4u), change_endian_long(0x8b3ff3e6u));
                        }
                        TSIP.REG_ECH.WORD = 0x00002c40u;
                        RX72M_RX72N_RX66N_func101(change_endian_long(0xcabdc1e1u), change_endian_long(0xe931874fu), change_endian_long(0x2d375ec5u), change_endian_long(0x2dc4a2c9u));
                    }
                    TSIP.REG_ECH.WORD = 0x08000c21u;
                    TSIP.REG_E0H.WORD = 0x00000080u;
                    TSIP.REG_1CH.WORD = 0x00260000u;
                    TSIP.REG_1CH.WORD = 0x00402000u;
                    TSIP.REG_ECH.WORD = 0x00002ca0u;
                    RX72M_RX72N_RX66N_func101(change_endian_long(0xd3c4ea0bu), change_endian_long(0x81544061u), change_endian_long(0xfc363798u), change_endian_long(0x2abfe402u));
                }
                TSIP.REG_ECH.WORD = 0x38000805u;
                TSIP.REG_E0H.WORD = 0x00000080u;
                TSIP.REG_1CH.WORD = 0x00260000u;
                TSIP.REG_1CH.WORD = 0x00402000u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0x834c63a6u), change_endian_long(0x8af1c1d7u), change_endian_long(0x38a39de2u), change_endian_long(0xff95bd7du));
            }
            RX72M_RX72N_RX66N_func100(change_endian_long(0x7a774e51u), change_endian_long(0x35f4218eu), change_endian_long(0x1428b08au), change_endian_long(0x98e8b36bu));
            TSIP.REG_ECH.WORD = 0x00003416u;
            TSIP.REG_ECH.WORD = 0x00008c00u;
            TSIP.REG_ECH.WORD = 0x00000003u;
            TSIP.REG_ECH.WORD = 0x0000b440u;
            TSIP.REG_ECH.WORD = 0x00000004u;
            TSIP.REG_ECH.WORD = 0x00002840u;
            TSIP.REG_E0H.WORD = 0x81010040u;
            TSIP.REG_04H.WORD = 0x00000606u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
            TSIP.REG_ECH.WORD = 0x000008a5u;
            TSIP.REG_ECH.WORD = 0x0000b460u;
            TSIP.REG_ECH.WORD = 0x80000000u;
            for (iLoop = 0; iLoop < S_RAM[0]; iLoop = iLoop + 1)
            {
                TSIP.REG_E0H.WORD = 0x81010060u;
                TSIP.REG_00H.WORD = 0x08005807u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x0800080fu;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_ECH.WORD = 0x00086c63u;
                TSIP.REG_ECH.WORD = 0x00002ca0u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0xd2fcefa2u), change_endian_long(0x3427dc32u), change_endian_long(0xe6bec994u), change_endian_long(0xe03176a4u));
            }
            RX72M_RX72N_RX66N_func100(change_endian_long(0x923ed67bu), change_endian_long(0x92cd741du), change_endian_long(0xd3406bd3u), change_endian_long(0x769c989au));
            TSIP.REG_ECH.WORD = 0x38000845u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_1CH.WORD = 0x00402000u;
            TSIP.REG_F8H.WORD = 0x00000040u;
            TSIP.REG_ECH.WORD = 0x00000800u;
            TSIP.REG_ECH.WORD = 0x00003436u;
            TSIP.REG_ECH.WORD = 0x01836c01u;
            TSIP.REG_ECH.WORD = 0x00036c21u;
            TSIP.REG_E0H.WORD = 0x81020000u;
            TSIP.REG_00H.WORD = 0x0000580bu;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_74H.BIT.B18)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001600u;
            TSIP.REG_74H.WORD = 0x00000000u;
            TSIP.REG_ECH.WORD = 0x00007c0fu;
            TSIP.REG_1CH.WORD = 0x00600000u;
            TSIP.REG_1D0H.WORD = 0x00000000u;
            if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
            {
                TSIP.REG_D0H.WORD = 0x00000f14u;
                TSIP.REG_C4H.WORD = 0x00008a07u;
                TSIP.REG_00H.WORD = 0x00012303u;
                TSIP.REG_2CH.WORD = 0x00000020u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0x6e6cb1d0u), change_endian_long(0x7665e457u), change_endian_long(0x1da83348u), change_endian_long(0xb37b27bau));
            }
            else
            {
                TSIP.REG_D0H.WORD = 0x00000314u;
                TSIP.REG_C4H.WORD = 0x00008a07u;
                TSIP.REG_00H.WORD = 0x00002343u;
                TSIP.REG_2CH.WORD = 0x00000020u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_28H.WORD = 0x00bf0001u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0xfeee7c65u), change_endian_long(0x3c104369u), change_endian_long(0x106b047eu), change_endian_long(0x753d4753u));
            }
            TSIP.REG_2CH.WORD = 0x00000010u;
            TSIP.REG_104H.WORD = 0x00003f67u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = ARG6[0];
            TSIP.REG_100H.WORD = ARG6[1];
            TSIP.REG_100H.WORD = ARG6[2];
            TSIP.REG_100H.WORD = ARG6[3];
            TSIP.REG_100H.WORD = ARG6[4];
            TSIP.REG_100H.WORD = ARG6[5];
            TSIP.REG_100H.WORD = ARG6[6];
            TSIP.REG_100H.WORD = ARG6[7];
            TSIP.REG_100H.WORD = ARG6[8];
            TSIP.REG_100H.WORD = ARG6[9];
            TSIP.REG_100H.WORD = ARG6[10];
            TSIP.REG_100H.WORD = ARG6[11];
            TSIP.REG_100H.WORD = ARG6[12];
            TSIP.REG_100H.WORD = ARG6[13];
            TSIP.REG_100H.WORD = ARG6[14];
            TSIP.REG_100H.WORD = ARG6[15];
            TSIP.REG_100H.WORD = ARG6[16];
            TSIP.REG_100H.WORD = ARG6[17];
            TSIP.REG_100H.WORD = ARG6[18];
            TSIP.REG_100H.WORD = ARG6[19];
            TSIP.REG_100H.WORD = ARG6[20];
            TSIP.REG_100H.WORD = ARG6[21];
            TSIP.REG_100H.WORD = ARG6[22];
            TSIP.REG_100H.WORD = ARG6[23];
            TSIP.REG_100H.WORD = ARG6[24];
            TSIP.REG_100H.WORD = ARG6[25];
            TSIP.REG_100H.WORD = ARG6[26];
            TSIP.REG_100H.WORD = ARG6[27];
            TSIP.REG_100H.WORD = ARG6[28];
            TSIP.REG_100H.WORD = ARG6[29];
            TSIP.REG_100H.WORD = ARG6[30];
            TSIP.REG_100H.WORD = ARG6[31];
            TSIP.REG_100H.WORD = ARG6[32];
            TSIP.REG_100H.WORD = ARG6[33];
            TSIP.REG_100H.WORD = ARG6[34];
            TSIP.REG_100H.WORD = ARG6[35];
            TSIP.REG_100H.WORD = ARG6[36];
            TSIP.REG_100H.WORD = ARG6[37];
            TSIP.REG_100H.WORD = ARG6[38];
            TSIP.REG_100H.WORD = ARG6[39];
            TSIP.REG_100H.WORD = ARG6[40];
            TSIP.REG_100H.WORD = ARG6[41];
            TSIP.REG_100H.WORD = ARG6[42];
            TSIP.REG_100H.WORD = ARG6[43];
            TSIP.REG_100H.WORD = ARG6[44];
            TSIP.REG_100H.WORD = ARG6[45];
            TSIP.REG_100H.WORD = ARG6[46];
            TSIP.REG_100H.WORD = ARG6[47];
            TSIP.REG_100H.WORD = ARG6[48];
            TSIP.REG_100H.WORD = ARG6[49];
            TSIP.REG_100H.WORD = ARG6[50];
            TSIP.REG_100H.WORD = ARG6[51];
            TSIP.REG_100H.WORD = ARG6[52];
            TSIP.REG_100H.WORD = ARG6[53];
            TSIP.REG_100H.WORD = ARG6[54];
            TSIP.REG_100H.WORD = ARG6[55];
            TSIP.REG_100H.WORD = ARG6[56];
            TSIP.REG_100H.WORD = ARG6[57];
            TSIP.REG_100H.WORD = ARG6[58];
            TSIP.REG_100H.WORD = ARG6[59];
            TSIP.REG_100H.WORD = ARG6[60];
            TSIP.REG_100H.WORD = ARG6[61];
            TSIP.REG_100H.WORD = ARG6[62];
            TSIP.REG_100H.WORD = ARG6[63];
            TSIP.REG_ECH.WORD = 0x0000342au;
            TSIP.REG_ECH.WORD = 0x0000b400u;
            TSIP.REG_ECH.WORD = 0x000000e0u;
            TSIP.REG_ECH.WORD = 0x0000b440u;
            TSIP.REG_ECH.WORD = 0x00000020u;
            TSIP.REG_ECH.WORD = 0x0000b4e0u;
            TSIP.REG_ECH.WORD = 0x000000f0u;
            TSIP.REG_E0H.WORD = 0x81840007u;
            TSIP.REG_C4H.WORD = 0x00000885u;
            TSIP.REG_00H.WORD = 0x00002813u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_E0H.WORD = 0x80040100u;
            TSIP.REG_00H.WORD = 0x00008213u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            RX72M_RX72N_RX66N_func101(change_endian_long(0xf6c31eceu), change_endian_long(0x5d93ef9fu), change_endian_long(0xc0082667u), change_endian_long(0x76e11262u));
            R_TSIP_TlsRootCertificateVerificationSubSub();

            TSIP.REG_ECH.WORD = 0x0000b4e0u;
            TSIP.REG_ECH.WORD = 0x000000f0u;
            TSIP.REG_E0H.WORD = 0x81040100u;
            TSIP.REG_C4H.WORD = 0x00000885u;
            TSIP.REG_00H.WORD = 0x00002813u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_E0H.WORD = 0x80840007u;
            TSIP.REG_00H.WORD = 0x00008213u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            RX72M_RX72N_RX66N_func100(change_endian_long(0x75a83466u), change_endian_long(0x80d3fb76u), change_endian_long(0xa8fb1ce4u), change_endian_long(0x6e683cf8u));
            TSIP.REG_1CH.WORD = 0x00400000u;
            TSIP.REG_1D0H.WORD = 0x00000000u;
            if (1u == (TSIP.REG_1CH.BIT.B22))
            {
                TSIP.REG_ECH.WORD = 0x0000b400u;
                TSIP.REG_ECH.WORD = 0xffffffffu;
                RX72M_RX72N_RX66N_func101(change_endian_long(0xcaf59ab9u), change_endian_long(0x66a07bb7u), change_endian_long(0xf8a46c97u), change_endian_long(0x37c385aeu));
            }
            else
            {
                RX72M_RX72N_RX66N_func100(change_endian_long(0xc72017cbu), change_endian_long(0xf544172cu), change_endian_long(0xaacbc6a1u), change_endian_long(0xe15fa06au));
                TSIP.REG_ECH.WORD = 0x00007c0fu;
                TSIP.REG_1CH.WORD = 0x00600000u;
                TSIP.REG_1D0H.WORD = 0x00000000u;
                if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                {
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xf2de4c0du), change_endian_long(0xa0306a8du), change_endian_long(0xa3c3cbd2u), change_endian_long(0xb8caa7eeu));
                    TSIP.REG_28H.WORD = 0x00bf0001u;
                    TSIP.REG_D0H.WORD = 0x00000f1cu;
                    TSIP.REG_C4H.WORD = 0x00008a83u;
                    TSIP.REG_00H.WORD = 0x00013203u;
                    TSIP.REG_2CH.WORD = 0x00000014u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_24H.WORD = 0x000005c0u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_24H.BIT.B21)
                    {
                        /* waiting */
                    }
                    TSIP.REG_24H.WORD = 0x000080c1u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_24H.BIT.B21)
                    {
                        /* waiting */
                    }
                    TSIP.REG_18H.WORD = 0x00000004u;
                    TSIP.REG_24H.WORD = 0x00005004u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_18H.BIT.B10)
                    {
                        /* waiting */
                    }
                    TSIP.REG_24H.WORD = 0x00004804u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_18H.BIT.B10)
                    {
                        /* waiting */
                    }
                    TSIP.REG_18H.WORD = 0x00000000u;
                    TSIP.REG_104H.WORD = 0x00000058u;
                    TSIP.REG_E0H.WORD = 0x80010000u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x05080100u);
                    TSIP.REG_ECH.WORD = 0x00001011u;
                    RX72M_RX72N_RX66N_func103();
                    TSIP.REG_104H.WORD = 0x00000052u;
                    TSIP.REG_C4H.WORD = 0x01000c84u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_E0H.WORD = 0x80030020u;
                    TSIP.REG_00H.WORD = 0x0000820fu;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x00000207u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xcc6c3b64u), change_endian_long(0x01653a6cu), change_endian_long(0xfb6f2ba0u), change_endian_long(0x1b76edbfu));
                    TSIP.REG_C4H.WORD = 0x000c2b0du;
                    TSIP.REG_E0H.WORD = 0x81040000u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x00012303u;
                    TSIP.REG_2CH.WORD = 0x00000024u;
                    TSIP.REG_D0H.WORD = 0x00000f00u;
                    TSIP.REG_C4H.WORD = 0x02e087bfu;
                    TSIP.REG_04H.WORD = 0x00000202u;
                    for (iLoop = 4; iLoop < 68; iLoop = iLoop + 4)
                    {
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_04H.BIT.B30)
                        {
                            /* waiting */
                        }
                        ARG9[iLoop] = TSIP.REG_100H.WORD;
                        ARG9[iLoop+1] = TSIP.REG_100H.WORD;
                        ARG9[iLoop+2] = TSIP.REG_100H.WORD;
                        ARG9[iLoop+3] = TSIP.REG_100H.WORD;
                    }
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xdfa77245u), change_endian_long(0xf1477cdeu), change_endian_long(0xbb93eb64u), change_endian_long(0x57a05f10u));
                    TSIP.REG_00H.WORD = 0x00012303u;
                    TSIP.REG_2CH.WORD = 0x00000022u;
                    TSIP.REG_D0H.WORD = 0x00000f00u;
                    TSIP.REG_C4H.WORD = 0x00e087bfu;
                    TSIP.REG_04H.WORD = 0x00000202u;
                    for ( ; iLoop < 132; iLoop = iLoop + 4)
                    {
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_04H.BIT.B30)
                        {
                            /* waiting */
                        }
                        ARG9[iLoop] = TSIP.REG_100H.WORD;
                        ARG9[iLoop+1] = TSIP.REG_100H.WORD;
                        ARG9[iLoop+2] = TSIP.REG_100H.WORD;
                        ARG9[iLoop+3] = TSIP.REG_100H.WORD;
                    }
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xb3e6ea71u), change_endian_long(0x39c52dc5u), change_endian_long(0x74006437u), change_endian_long(0xdaf3b693u));
                    TSIP.REG_C4H.WORD = 0x00e007bcu;
                    TSIP.REG_E0H.WORD = 0x81010200u;
                    TSIP.REG_00H.WORD = 0x00002807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_04H.WORD = 0x00000212u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    ARG9[iLoop] = TSIP.REG_100H.WORD;
                    ARG9[iLoop+1] = TSIP.REG_100H.WORD;
                    ARG9[iLoop+2] = TSIP.REG_100H.WORD;
                    ARG9[iLoop+3] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x0b82a9e1u), change_endian_long(0x9e97b0b6u), change_endian_long(0xe8edc1e8u), change_endian_long(0x859be095u));
                    iLoop = iLoop+4;
                    TSIP.REG_104H.WORD = 0x00000052u;
                    TSIP.REG_C4H.WORD = 0x00000c84u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_C4H.WORD = 0x000009cdu;
                    TSIP.REG_00H.WORD = 0x00002213u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_04H.WORD = 0x00000212u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    ARG9[iLoop] = TSIP.REG_100H.WORD;
                    ARG9[iLoop+1] = TSIP.REG_100H.WORD;
                    ARG9[iLoop+2] = TSIP.REG_100H.WORD;
                    ARG9[iLoop+3] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x4b3770bbu), change_endian_long(0x4f66f4ceu), change_endian_long(0xe714e8dfu), change_endian_long(0x2fc61297u));
                    TSIP.REG_E0H.WORD = 0x81040000u;
                    TSIP.REG_04H.WORD = 0x00000612u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    ARG9[0] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    ARG9[1] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    ARG9[2] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    ARG9[3] = TSIP.REG_100H.WORD;
                    TSIP.REG_ECH.WORD = 0x00000800u;
                    RX72M_RX72N_RX66N_func101(change_endian_long(0x226c37f0u), change_endian_long(0x3e64914fu), change_endian_long(0xdd7629f6u), change_endian_long(0xb45c606eu));
                }
                else
                {
                    TSIP.REG_28H.WORD = 0x00870001u;
                    TSIP.REG_ECH.WORD = 0x00000b9cu;
                    RX72M_RX72N_RX66N_func004(ARG8);
                    TSIP.REG_24H.WORD = 0x0000dcd0u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_24H.BIT.B21)
                    {
                        /* waiting */
                    }
                    TSIP.REG_24H.WORD = 0x000084d0u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_24H.BIT.B21)
                    {
                        /* waiting */
                    }
                    TSIP.REG_24H.WORD = 0x00029008u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_24H.BIT.B21)
                    {
                        /* waiting */
                    }
                    TSIP.REG_34H.WORD = 0x00000800u;
                    TSIP.REG_24H.WORD = 0x8000c0c1u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_24H.BIT.B21)
                    {
                        /* waiting */
                    }
                    TSIP.REG_28H.WORD = 0x008f0001u;
                    TSIP.REG_D0H.WORD = 0x0000031cu;
                    TSIP.REG_C4H.WORD = 0x00008a83u;
                    TSIP.REG_00H.WORD = 0x00003243u;
                    TSIP.REG_2CH.WORD = 0x00000010u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_28H.WORD = 0x00870001u;
                    TSIP.REG_34H.WORD = 0x00000004u;
                    TSIP.REG_24H.WORD = 0x800070d0u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_24H.BIT.B21)
                    {
                        /* waiting */
                    }
                    TSIP.REG_34H.WORD = 0x00000800u;
                    TSIP.REG_24H.WORD = 0x800070d0u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_24H.BIT.B21)
                    {
                        /* waiting */
                    }
                    RX72M_RX72N_RX66N_func008();
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xce4ffe68u), change_endian_long(0x6faf2f8bu), change_endian_long(0x1379bf28u), change_endian_long(0x32ea8f7bu));
                    TSIP.REG_1CH.WORD = 0x00400000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (1u == (TSIP.REG_1CH.BIT.B22))
                    {
                        TSIP.REG_ECH.WORD = 0x0000b400u;
                        TSIP.REG_ECH.WORD = 0xffffffffu;
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x86d5588du), change_endian_long(0x3d9a6ae7u), change_endian_long(0x42fd0542u), change_endian_long(0x003823f4u));
                    }
                    else
                    {
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x1c8d5a84u), change_endian_long(0x24241e65u), change_endian_long(0x5243bee2u), change_endian_long(0xd912ba0du));
                        TSIP.REG_34H.WORD = 0x00000400u;
                        TSIP.REG_24H.WORD = 0x80008cd0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_34H.WORD = 0x00000404u;
                        TSIP.REG_24H.WORD = 0x80009008u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_34H.WORD = 0x00000002u;
                        TSIP.REG_24H.WORD = 0x80008cd0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_24H.WORD = 0x00009008u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_28H.WORD = 0x008f0001u;
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010000u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x31080100u);
                        TSIP.REG_ECH.WORD = 0x00001011u;
                        RX72M_RX72N_RX66N_func103();
                        TSIP.REG_104H.WORD = 0x00000052u;
                        TSIP.REG_C4H.WORD = 0x01000c84u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                        TSIP.REG_E0H.WORD = 0x80030020u;
                        TSIP.REG_00H.WORD = 0x0000820fu;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_00H.BIT.B25)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00001800u;
                        TSIP.REG_00H.WORD = 0x00000207u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_00H.BIT.B25)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00001800u;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0xcd201ae8u), change_endian_long(0xbcc2852cu), change_endian_long(0xd73966c8u), change_endian_long(0x82af332bu));
                        TSIP.REG_C4H.WORD = 0x000c2b0du;
                        TSIP.REG_E0H.WORD = 0x81040000u;
                        TSIP.REG_00H.WORD = 0x00002813u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_00H.BIT.B25)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00001800u;
                        TSIP.REG_00H.WORD = 0x00002343u;
                        TSIP.REG_2CH.WORD = 0x00000020u;
                        TSIP.REG_D0H.WORD = 0x00000300u;
                        TSIP.REG_C4H.WORD = 0x02e087bfu;
                        TSIP.REG_04H.WORD = 0x00000242u;
                        for (iLoop = 4; iLoop < 20; iLoop = iLoop + 4)
                        {
                            /* WAIT_LOOP */
                            while (1u != TSIP.REG_04H.BIT.B30)
                            {
                                /* waiting */
                            }
                            ARG9[iLoop] = TSIP.REG_100H.WORD;
                            ARG9[iLoop+1] = TSIP.REG_100H.WORD;
                            ARG9[iLoop+2] = TSIP.REG_100H.WORD;
                            ARG9[iLoop+3] = TSIP.REG_100H.WORD;
                        }
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_00H.BIT.B25)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00001800u;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0xa2a5962bu), change_endian_long(0xee38d0ceu), change_endian_long(0xef4165c0u), change_endian_long(0x5654a847u));
                        TSIP.REG_104H.WORD = 0x00000052u;
                        TSIP.REG_C4H.WORD = 0x00000c84u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                        TSIP.REG_C4H.WORD = 0x000009cdu;
                        TSIP.REG_00H.WORD = 0x00002213u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_00H.BIT.B25)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00001800u;
                        TSIP.REG_04H.WORD = 0x00000212u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_04H.BIT.B30)
                        {
                            /* waiting */
                        }
                        ARG9[iLoop] = TSIP.REG_100H.WORD;
                        ARG9[iLoop+1] = TSIP.REG_100H.WORD;
                        ARG9[iLoop+2] = TSIP.REG_100H.WORD;
                        ARG9[iLoop+3] = TSIP.REG_100H.WORD;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x432cd84fu), change_endian_long(0x3e9ccce5u), change_endian_long(0x90e9c07cu), change_endian_long(0x404584ccu));
                        TSIP.REG_E0H.WORD = 0x81040000u;
                        TSIP.REG_04H.WORD = 0x00000612u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_04H.BIT.B30)
                        {
                            /* waiting */
                        }
                        ARG9[0] = TSIP.REG_100H.WORD;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_04H.BIT.B30)
                        {
                            /* waiting */
                        }
                        ARG9[1] = TSIP.REG_100H.WORD;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_04H.BIT.B30)
                        {
                            /* waiting */
                        }
                        ARG9[2] = TSIP.REG_100H.WORD;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_04H.BIT.B30)
                        {
                            /* waiting */
                        }
                        ARG9[3] = TSIP.REG_100H.WORD;
                        TSIP.REG_ECH.WORD = 0x00000800u;
                        RX72M_RX72N_RX66N_func101(change_endian_long(0xe2608cfcu), change_endian_long(0x35ee7b66u), change_endian_long(0x48283927u), change_endian_long(0x2bdb1197u));
                    }
                }
            }
        }
    }
    TSIP.REG_ECH.WORD = 0x00007c14u;
    TSIP.REG_1CH.WORD = 0x00602000u;
}
/**********************************************************************************************************************
 End of function ./input_dir/RX72M/RX72M_func405.prc
 *********************************************************************************************************************/
