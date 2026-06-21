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
* Function Name: RX671_func404
*******************************************************************************************************************/ /**
* @details       RX671 func404
* @param[in]     ARG1
* @param[in]     ARG2
* @param[in]     ARG3
* @param[in]     ARG4
* @param[in]     ARG5
* @param[in]     ARG6
* @param[in]     ARG7
* @param[in]     ARG8
* @param[in]     ARG9
* @param[in]     ARG10
* @note          None
*/
void RX671_func404(uint32_t *ARG1, uint32_t *ARG2, uint32_t *ARG3, uint32_t *ARG4, uint32_t *ARG5, uint32_t *ARG6, uint32_t *ARG7, uint32_t *ARG8, uint32_t *ARG9, uint32_t *ARG10)
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
    TSIP.REG_E0H.WORD = 0x800103e0u;
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = ARG1[0];
    TSIP.REG_ECH.WORD = 0x3420abe0u;
    TSIP.REG_ECH.WORD = 0x00000008u;
    TSIP.REG_E0H.WORD = 0x00000080u;
    TSIP.REG_1CH.WORD = 0x00A60000u;
    RX671_func100(change_endian_long(0x34315994u), change_endian_long(0x0169f391u), change_endian_long(0x0dc3b37bu), change_endian_long(0x251c6bfeu));
    TSIP.REG_1CH.WORD = 0x00400000u;
    TSIP.REG_1D0H.WORD = 0x00000000u;
    if (1u == (TSIP.REG_1CH.BIT.B22))
    {
        TSIP.REG_ECH.WORD = 0x0000b400u;
        TSIP.REG_ECH.WORD = 0xffffffffu;
        RX671_func101(change_endian_long(0xee002219u), change_endian_long(0xbca5f06fu), change_endian_long(0x05bf5de7u), change_endian_long(0xfacff701u));
    }
    else
    {
        TSIP.REG_C4H.WORD = 0x00082b8du;
        /* WAIT_LOOP */
        while (1u != TSIP.REG_104H.BIT.B31)
        {
            /* waiting */
        }
        TSIP.REG_100H.WORD = ARG2[0];
        TSIP.REG_100H.WORD = ARG2[1];
        TSIP.REG_100H.WORD = ARG2[2];
        TSIP.REG_100H.WORD = ARG2[3];
        TSIP.REG_C4H.WORD = 0x400c0b0cu;
        TSIP.REG_E0H.WORD = 0x81010380u;
        TSIP.REG_00H.WORD = 0x00002807u;
        /* WAIT_LOOP */
        while (0u != TSIP.REG_00H.BIT.B25)
        {
            /* waiting */
        }
        TSIP.REG_1CH.WORD = 0x00001800u;
        TSIP.REG_104H.WORD = 0x00000b62u;
        TSIP.REG_D0H.WORD = 0x00000200u;
        TSIP.REG_C4H.WORD = 0x02f087bfu;
        /* WAIT_LOOP */
        while (1u != TSIP.REG_104H.BIT.B31)
        {
            /* waiting */
        }
        TSIP.REG_100H.WORD = ARG2[4];
        TSIP.REG_100H.WORD = ARG2[5];
        TSIP.REG_100H.WORD = ARG2[6];
        TSIP.REG_100H.WORD = ARG2[7];
        /* WAIT_LOOP */
        while (1u != TSIP.REG_104H.BIT.B31)
        {
            /* waiting */
        }
        TSIP.REG_100H.WORD = ARG2[8];
        TSIP.REG_100H.WORD = ARG2[9];
        TSIP.REG_100H.WORD = ARG2[10];
        TSIP.REG_100H.WORD = ARG2[11];
        /* WAIT_LOOP */
        while (1u != TSIP.REG_104H.BIT.B31)
        {
            /* waiting */
        }
        TSIP.REG_100H.WORD = ARG2[12];
        TSIP.REG_100H.WORD = ARG2[13];
        TSIP.REG_100H.WORD = ARG2[14];
        TSIP.REG_100H.WORD = ARG2[15];
        TSIP.REG_ECH.WORD = 0x0000b400u;
        TSIP.REG_ECH.WORD = 0x00000070u;
        TSIP.REG_E0H.WORD = 0x808c0000u;
        TSIP.REG_00H.WORD = 0x00008233u;
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
        TSIP.REG_100H.WORD = ARG2[16];
        TSIP.REG_100H.WORD = ARG2[17];
        TSIP.REG_100H.WORD = ARG2[18];
        TSIP.REG_100H.WORD = ARG2[19];
        TSIP.REG_C4H.WORD = 0x00900c45u;
        TSIP.REG_00H.WORD = 0x00002213u;
        /* WAIT_LOOP */
        while (0u != TSIP.REG_00H.BIT.B25)
        {
            /* waiting */
        }
        TSIP.REG_1CH.WORD = 0x00001800u;
        RX671_func100(change_endian_long(0x942e03e5u), change_endian_long(0x814e1795u), change_endian_long(0xe9213cbbu), change_endian_long(0x06e8a4a6u));
        TSIP.REG_1CH.WORD = 0x00400000u;
        TSIP.REG_1D0H.WORD = 0x00000000u;
        if (1u == (TSIP.REG_1CH.BIT.B22))
        {
            TSIP.REG_ECH.WORD = 0x0000b400u;
            TSIP.REG_ECH.WORD = 0xffffffffu;
            RX671_func101(change_endian_long(0xb6b49949u), change_endian_long(0x31f74f9bu), change_endian_long(0x3b1d7795u), change_endian_long(0xec184038u));
        }
        else
        {
            TSIP.REG_104H.WORD = 0x00000352u;
            TSIP.REG_C4H.WORD = 0x00000885u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = change_endian_long(0x6b657920u);
            TSIP.REG_100H.WORD = change_endian_long(0x65787061u);
            TSIP.REG_100H.WORD = change_endian_long(0x6e73696fu);
            TSIP.REG_100H.WORD = change_endian_long(0x6e000000u);
            TSIP.REG_ECH.WORD = 0x0000b460u;
            TSIP.REG_ECH.WORD = 0x00000020u;
            TSIP.REG_E0H.WORD = 0x80830003u;
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
            TSIP.REG_104H.WORD = 0x00000068u;
            TSIP.REG_E0H.WORD = 0x80010000u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = change_endian_long(0x0000006eu);
            TSIP.REG_D0H.WORD = 0x00000100u;
            TSIP.REG_C4H.WORD = 0x00008887u;
            TSIP.REG_00H.WORD = 0x00002323u;
            TSIP.REG_2CH.WORD = 0x00000022u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_ECH.WORD = 0x0000b460u;
            TSIP.REG_ECH.WORD = 0x0000002cu;
            for (iLoop = 0; iLoop < 8; iLoop = iLoop + 1)
            {
                TSIP.REG_E0H.WORD = 0x80010020u;
                TSIP.REG_00H.WORD = 0x00008207u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_ECH.WORD = 0x01986c01u;
                TSIP.REG_ECH.WORD = 0x00003c03u;
                TSIP.REG_ECH.WORD = 0x00003401u;
                TSIP.REG_ECH.WORD = 0x0000a460u;
                TSIP.REG_ECH.WORD = 0x00000004u;
            }
            TSIP.REG_104H.WORD = 0x00000762u;
            TSIP.REG_D0H.WORD = 0x00000100u;
            TSIP.REG_C4H.WORD = 0x00008887u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = ARG3[0];
            TSIP.REG_100H.WORD = ARG3[1];
            TSIP.REG_100H.WORD = ARG3[2];
            TSIP.REG_100H.WORD = ARG3[3];
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = ARG3[4];
            TSIP.REG_100H.WORD = ARG3[5];
            TSIP.REG_100H.WORD = ARG3[6];
            TSIP.REG_100H.WORD = ARG3[7];
            for (iLoop = 0; iLoop < 8; iLoop = iLoop + 1)
            {
                TSIP.REG_E0H.WORD = 0x80010020u;
                TSIP.REG_00H.WORD = 0x00008207u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_ECH.WORD = 0x01986c01u;
                TSIP.REG_ECH.WORD = 0x00003c03u;
                TSIP.REG_ECH.WORD = 0x00003401u;
                TSIP.REG_ECH.WORD = 0x0000a460u;
                TSIP.REG_ECH.WORD = 0x00000004u;
            }
            TSIP.REG_ECH.WORD = 0x00186c00u;
            TSIP.REG_ECH.WORD = 0x00003c03u;
            TSIP.REG_ECH.WORD = 0x0000b420u;
            TSIP.REG_ECH.WORD = 0x00000020u;
            TSIP.REG_ECH.WORD = 0x0000b560u;
            TSIP.REG_ECH.WORD = 0x00000020u;
            TSIP.REG_ECH.WORD = 0x0000098cu;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x0000004du;
            RX671_func101(change_endian_long(0x1b383af4u), change_endian_long(0x798b5baau), change_endian_long(0x55e3ef47u), change_endian_long(0xaa100dd0u));
            RX671_func032();
            TSIP.REG_ECH.WORD = 0x00002c20u;
            TSIP.REG_ECH.WORD = 0x0000096bu;
            TSIP.REG_ECH.WORD = 0x0000b580u;
            TSIP.REG_ECH.WORD = 0x000000a0u;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x0000006du;
            RX671_func101(change_endian_long(0x4d62411bu), change_endian_long(0x804ef143u), change_endian_long(0x825d8e31u), change_endian_long(0x3a16ad7au));
            RX671_func032();
            TSIP.REG_E0H.WORD = 0x8188000cu;
            TSIP.REG_00H.WORD = 0x00003823u;
            TSIP.REG_2CH.WORD = 0x00000013u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_ECH.WORD = 0x00002c20u;
            TSIP.REG_ECH.WORD = 0x0000096bu;
            TSIP.REG_ECH.WORD = 0x0000098cu;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x00000020u;
            RX671_func101(change_endian_long(0x96fa44a6u), change_endian_long(0xff70e1ccu), change_endian_long(0x30521446u), change_endian_long(0xbe147d4du));
            RX671_func032();
            TSIP.REG_ECH.WORD = 0x00002c20u;
            TSIP.REG_ECH.WORD = 0x0000096bu;
            TSIP.REG_ECH.WORD = 0x0000b580u;
            TSIP.REG_ECH.WORD = 0x000000a0u;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x0000006du;
            RX671_func101(change_endian_long(0x6049e301u), change_endian_long(0x4e0a8caeu), change_endian_long(0xf926d605u), change_endian_long(0xdb90c475u));
            RX671_func032();
            TSIP.REG_E0H.WORD = 0x8188000cu;
            TSIP.REG_00H.WORD = 0x00003823u;
            TSIP.REG_2CH.WORD = 0x0000009au;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_ECH.WORD = 0x00002c20u;
            TSIP.REG_ECH.WORD = 0x0000096bu;
            TSIP.REG_ECH.WORD = 0x0000098cu;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x00000020u;
            RX671_func101(change_endian_long(0x4384a457u), change_endian_long(0x268613d0u), change_endian_long(0x238ac9f8u), change_endian_long(0x4e00a652u));
            RX671_func032();
            TSIP.REG_ECH.WORD = 0x00002c20u;
            TSIP.REG_ECH.WORD = 0x0000096bu;
            TSIP.REG_ECH.WORD = 0x0000b580u;
            TSIP.REG_ECH.WORD = 0x000000a0u;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x0000006du;
            RX671_func101(change_endian_long(0xcdcb2935u), change_endian_long(0xeb4b322cu), change_endian_long(0xa2505382u), change_endian_long(0x1106c2f5u));
            RX671_func032();
            TSIP.REG_E0H.WORD = 0x8188000cu;
            TSIP.REG_00H.WORD = 0x00003823u;
            TSIP.REG_2CH.WORD = 0x0000001au;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_ECH.WORD = 0x00002c20u;
            TSIP.REG_ECH.WORD = 0x0000096bu;
            TSIP.REG_ECH.WORD = 0x0000098cu;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x00000020u;
            RX671_func101(change_endian_long(0x6fda945du), change_endian_long(0xf791b143u), change_endian_long(0xe9ca2976u), change_endian_long(0x24072dc0u));
            RX671_func032();
            TSIP.REG_ECH.WORD = 0x00002c20u;
            TSIP.REG_ECH.WORD = 0x0000096bu;
            TSIP.REG_ECH.WORD = 0x0000b580u;
            TSIP.REG_ECH.WORD = 0x000000a0u;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x0000006du;
            RX671_func101(change_endian_long(0xcb4c8decu), change_endian_long(0x1f9ef44eu), change_endian_long(0xe3fee300u), change_endian_long(0xeeaf0a6fu));
            RX671_func032();
            TSIP.REG_E0H.WORD = 0x8188000cu;
            TSIP.REG_00H.WORD = 0x00003823u;
            TSIP.REG_2CH.WORD = 0x00000092u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_ECH.WORD = 0x00002c20u;
            TSIP.REG_ECH.WORD = 0x0000096bu;
            TSIP.REG_ECH.WORD = 0x0000098cu;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x00000020u;
            RX671_func101(change_endian_long(0x56cc200eu), change_endian_long(0xa9fb3993u), change_endian_long(0x1681582bu), change_endian_long(0x0f28c5feu));
            RX671_func032();
            TSIP.REG_ECH.WORD = 0x00002c20u;
            TSIP.REG_ECH.WORD = 0x0000096bu;
            TSIP.REG_ECH.WORD = 0x0000b580u;
            TSIP.REG_ECH.WORD = 0x000000a0u;
            TSIP.REG_ECH.WORD = 0x0000b5c0u;
            TSIP.REG_ECH.WORD = 0x0000006du;
            RX671_func101(change_endian_long(0x39377082u), change_endian_long(0x66ab4d6cu), change_endian_long(0x3027a4c5u), change_endian_long(0x5722b450u));
            RX671_func032();
            RX671_func100(change_endian_long(0x4428e20cu), change_endian_long(0xd95f91e6u), change_endian_long(0xede99370u), change_endian_long(0xffe3d40eu));
            TSIP.REG_E0H.WORD = 0x8188000cu;
            TSIP.REG_00H.WORD = 0x00003823u;
            TSIP.REG_2CH.WORD = 0x00000012u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_28H.WORD = 0x00a70001u;
            TSIP.REG_ECH.WORD = 0x000034dfu;
            TSIP.REG_ECH.WORD = 0x3420abe0u;
            TSIP.REG_ECH.WORD = 0x00000004u;
            TSIP.REG_ECH.WORD = 0x2000b4c0u;
            TSIP.REG_ECH.WORD = 0x00000002u;
            TSIP.REG_ECH.WORD = 0x3420abe0u;
            TSIP.REG_ECH.WORD = 0x00000006u;
            TSIP.REG_ECH.WORD = 0x2000b4c0u;
            TSIP.REG_ECH.WORD = 0x00000006u;
            TSIP.REG_ECH.WORD = 0x00007c06u;
            TSIP.REG_1CH.WORD = 0x00600000u;
            TSIP.REG_1D0H.WORD = 0x00000000u;
            if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
            {
                RX671_func100(change_endian_long(0xbd67dfacu), change_endian_long(0xdf01faf6u), change_endian_long(0x90d31399u), change_endian_long(0xe598479fu));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x03000100u);
                TSIP.REG_ECH.WORD = 0x00001058u;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x97b1f9d2u), change_endian_long(0x477c4d0eu), change_endian_long(0x7d1000ebu), change_endian_long(0xdcd76134u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002317u;
                TSIP.REG_2CH.WORD = 0x00000022u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x0000200fu;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[4] = TSIP.REG_100H.WORD;
                ARG5[5] = TSIP.REG_100H.WORD;
                ARG5[6] = TSIP.REG_100H.WORD;
                ARG5[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[8] = TSIP.REG_100H.WORD;
                ARG5[9] = TSIP.REG_100H.WORD;
                ARG5[10] = TSIP.REG_100H.WORD;
                ARG5[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x4cbf0c65u), change_endian_long(0x85bedefeu), change_endian_long(0x2ca916ecu), change_endian_long(0x42507310u));
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
                ARG5[12] = TSIP.REG_100H.WORD;
                ARG5[13] = TSIP.REG_100H.WORD;
                ARG5[14] = TSIP.REG_100H.WORD;
                ARG5[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x248521dbu), change_endian_long(0xe92fa426u), change_endian_long(0x5fc1c75bu), change_endian_long(0xd8a29577u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x66128cb1u), change_endian_long(0x5b521815u), change_endian_long(0xb9c34935u), change_endian_long(0xb0f9e65fu));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x03000100u);
                TSIP.REG_ECH.WORD = 0x00001059u;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x4ac64e34u), change_endian_long(0x23d9bd7eu), change_endian_long(0x6a15e2a9u), change_endian_long(0x834a5cb4u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002317u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x0000200fu;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[4] = TSIP.REG_100H.WORD;
                ARG6[5] = TSIP.REG_100H.WORD;
                ARG6[6] = TSIP.REG_100H.WORD;
                ARG6[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[8] = TSIP.REG_100H.WORD;
                ARG6[9] = TSIP.REG_100H.WORD;
                ARG6[10] = TSIP.REG_100H.WORD;
                ARG6[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xc3df0badu), change_endian_long(0x44e7894du), change_endian_long(0xf4250130u), change_endian_long(0xc6c92386u));
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
                ARG6[12] = TSIP.REG_100H.WORD;
                ARG6[13] = TSIP.REG_100H.WORD;
                ARG6[14] = TSIP.REG_100H.WORD;
                ARG6[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x0dfce07cu), change_endian_long(0x984ae158u), change_endian_long(0x89606c19u), change_endian_long(0x35b380ffu));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xea5c6655u), change_endian_long(0x746822c1u), change_endian_long(0x368a4c7du), change_endian_long(0x716bdb27u));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000100u);
                TSIP.REG_ECH.WORD = 0x0000105au;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x123f7a08u), change_endian_long(0x33e4a24au), change_endian_long(0xde75d7f4u), change_endian_long(0xdf45e8aau));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_C4H.WORD = 0x02e007bdu;
                TSIP.REG_00H.WORD = 0x00002313u;
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
                ARG7[4] = TSIP.REG_100H.WORD;
                ARG7[5] = TSIP.REG_100H.WORD;
                ARG7[6] = TSIP.REG_100H.WORD;
                ARG7[7] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x3d0bbd92u), change_endian_long(0x16483ca7u), change_endian_long(0x59280336u), change_endian_long(0xc8cd5866u));
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
                ARG7[8] = TSIP.REG_100H.WORD;
                ARG7[9] = TSIP.REG_100H.WORD;
                ARG7[10] = TSIP.REG_100H.WORD;
                ARG7[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x7f9a5f36u), change_endian_long(0xc392f623u), change_endian_long(0xe292f19cu), change_endian_long(0xb64e1571u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x4beff952u), change_endian_long(0x2fa38812u), change_endian_long(0xd0153d4bu), change_endian_long(0x807c8207u));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000100u);
                TSIP.REG_ECH.WORD = 0x0000105bu;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x4777c007u), change_endian_long(0xade0aa5eu), change_endian_long(0x61ae095au), change_endian_long(0x98af6bfdu));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_C4H.WORD = 0x02e007bdu;
                TSIP.REG_00H.WORD = 0x00002313u;
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
                ARG8[4] = TSIP.REG_100H.WORD;
                ARG8[5] = TSIP.REG_100H.WORD;
                ARG8[6] = TSIP.REG_100H.WORD;
                ARG8[7] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xc26cbde6u), change_endian_long(0xb0dcd8b7u), change_endian_long(0xf84838a2u), change_endian_long(0xa99ef04au));
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
                ARG8[8] = TSIP.REG_100H.WORD;
                ARG8[9] = TSIP.REG_100H.WORD;
                ARG8[10] = TSIP.REG_100H.WORD;
                ARG8[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x5aa72de2u), change_endian_long(0x2682ef5cu), change_endian_long(0x61ddbb3eu), change_endian_long(0xe2232047u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xaaddb119u), change_endian_long(0x6e554ca5u), change_endian_long(0x87f16325u), change_endian_long(0x9006e1f6u));
                TSIP.REG_C4H.WORD = 0x00000885u;
                TSIP.REG_00H.WORD = 0x00002313u;
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
                ARG9[0] = TSIP.REG_100H.WORD;
                ARG9[1] = TSIP.REG_100H.WORD;
                ARG9[2] = TSIP.REG_100H.WORD;
                ARG9[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xb4166899u), change_endian_long(0x18cf6fddu), change_endian_long(0x0e8dc982u), change_endian_long(0xcae9f5e0u));
                TSIP.REG_C4H.WORD = 0x00000885u;
                TSIP.REG_00H.WORD = 0x00002313u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x0000033bu;
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
                ARG10[0] = TSIP.REG_100H.WORD;
                ARG10[1] = TSIP.REG_100H.WORD;
                ARG10[2] = TSIP.REG_100H.WORD;
                ARG10[3] = TSIP.REG_100H.WORD;
                RX671_func101(change_endian_long(0x7c36b008u), change_endian_long(0x36ec52fau), change_endian_long(0xdbc16a46u), change_endian_long(0xae40026fu));
            }
            else if (0x01000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
            {
                RX671_func100(change_endian_long(0x2cb0295cu), change_endian_long(0x0dadcc37u), change_endian_long(0x3ff3680fu), change_endian_long(0x49866470u));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x03000100u);
                TSIP.REG_ECH.WORD = 0x00001058u;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x5feed285u), change_endian_long(0x1b384bd7u), change_endian_long(0xbddbe904u), change_endian_long(0xd198b9f4u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002317u;
                TSIP.REG_2CH.WORD = 0x00000022u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x0000200fu;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[4] = TSIP.REG_100H.WORD;
                ARG5[5] = TSIP.REG_100H.WORD;
                ARG5[6] = TSIP.REG_100H.WORD;
                ARG5[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[8] = TSIP.REG_100H.WORD;
                ARG5[9] = TSIP.REG_100H.WORD;
                ARG5[10] = TSIP.REG_100H.WORD;
                ARG5[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x6b5caf20u), change_endian_long(0xd36c2ebbu), change_endian_long(0xc07f2352u), change_endian_long(0xa123a5b9u));
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
                ARG5[12] = TSIP.REG_100H.WORD;
                ARG5[13] = TSIP.REG_100H.WORD;
                ARG5[14] = TSIP.REG_100H.WORD;
                ARG5[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x5d0150b5u), change_endian_long(0x43070d59u), change_endian_long(0x670f9315u), change_endian_long(0xddb7a2d2u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x1ee003d5u), change_endian_long(0x5650e5a3u), change_endian_long(0x9bb7b9afu), change_endian_long(0x71bb582au));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x03000100u);
                TSIP.REG_ECH.WORD = 0x00001059u;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0xa551aa04u), change_endian_long(0x21bb782eu), change_endian_long(0xf01af8b7u), change_endian_long(0x8436f7edu));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002317u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x0000200fu;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[4] = TSIP.REG_100H.WORD;
                ARG6[5] = TSIP.REG_100H.WORD;
                ARG6[6] = TSIP.REG_100H.WORD;
                ARG6[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[8] = TSIP.REG_100H.WORD;
                ARG6[9] = TSIP.REG_100H.WORD;
                ARG6[10] = TSIP.REG_100H.WORD;
                ARG6[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x41240afau), change_endian_long(0x8d88f146u), change_endian_long(0xbecb557fu), change_endian_long(0xb8e3ab95u));
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
                ARG6[12] = TSIP.REG_100H.WORD;
                ARG6[13] = TSIP.REG_100H.WORD;
                ARG6[14] = TSIP.REG_100H.WORD;
                ARG6[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xd39e06a1u), change_endian_long(0x36081979u), change_endian_long(0xb3aed78du), change_endian_long(0x3bf6312eu));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x08cf91f3u), change_endian_long(0x1aecc96au), change_endian_long(0x1ea39915u), change_endian_long(0xad55a2e3u));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x01000100u);
                TSIP.REG_ECH.WORD = 0x0000105au;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x2bf4f7d1u), change_endian_long(0x9282e745u), change_endian_long(0xb175de75u), change_endian_long(0x705cc6d3u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[4] = TSIP.REG_100H.WORD;
                ARG7[5] = TSIP.REG_100H.WORD;
                ARG7[6] = TSIP.REG_100H.WORD;
                ARG7[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[8] = TSIP.REG_100H.WORD;
                ARG7[9] = TSIP.REG_100H.WORD;
                ARG7[10] = TSIP.REG_100H.WORD;
                ARG7[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xde00cc00u), change_endian_long(0x8383f40eu), change_endian_long(0xeb3f46abu), change_endian_long(0xdc921288u));
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
                ARG7[12] = TSIP.REG_100H.WORD;
                ARG7[13] = TSIP.REG_100H.WORD;
                ARG7[14] = TSIP.REG_100H.WORD;
                ARG7[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x7ef3345cu), change_endian_long(0xca414473u), change_endian_long(0x3bee682bu), change_endian_long(0xa910489au));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x16c6c1d7u), change_endian_long(0x9eaad315u), change_endian_long(0x6a5d3b87u), change_endian_long(0xc47c0a8bu));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x01000100u);
                TSIP.REG_ECH.WORD = 0x0000105bu;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x0415c4feu), change_endian_long(0x95c7b924u), change_endian_long(0x6e1f6f69u), change_endian_long(0x2c46afe6u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[4] = TSIP.REG_100H.WORD;
                ARG8[5] = TSIP.REG_100H.WORD;
                ARG8[6] = TSIP.REG_100H.WORD;
                ARG8[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[8] = TSIP.REG_100H.WORD;
                ARG8[9] = TSIP.REG_100H.WORD;
                ARG8[10] = TSIP.REG_100H.WORD;
                ARG8[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xdbd12e83u), change_endian_long(0x0e028518u), change_endian_long(0xab738586u), change_endian_long(0xc93f8215u));
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
                ARG8[12] = TSIP.REG_100H.WORD;
                ARG8[13] = TSIP.REG_100H.WORD;
                ARG8[14] = TSIP.REG_100H.WORD;
                ARG8[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x549b6410u), change_endian_long(0xf95310d4u), change_endian_long(0x8055145au), change_endian_long(0xe3344497u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x57fe6ff8u), change_endian_long(0xe2fe2224u), change_endian_long(0xd7762d6eu), change_endian_long(0x07d0470au));
                TSIP.REG_C4H.WORD = 0x00000885u;
                TSIP.REG_00H.WORD = 0x00002313u;
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
                ARG9[0] = TSIP.REG_100H.WORD;
                ARG9[1] = TSIP.REG_100H.WORD;
                ARG9[2] = TSIP.REG_100H.WORD;
                ARG9[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x5213260eu), change_endian_long(0x0dfd35beu), change_endian_long(0xa9095549u), change_endian_long(0x2a863eb0u));
                TSIP.REG_C4H.WORD = 0x00000885u;
                TSIP.REG_00H.WORD = 0x00002313u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x0000031bu;
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
                ARG10[0] = TSIP.REG_100H.WORD;
                ARG10[1] = TSIP.REG_100H.WORD;
                ARG10[2] = TSIP.REG_100H.WORD;
                ARG10[3] = TSIP.REG_100H.WORD;
                RX671_func101(change_endian_long(0xb8e36046u), change_endian_long(0x82d0e16eu), change_endian_long(0x619f3e5bu), change_endian_long(0xaa72b544u));
            }
            else if (0x02000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
            {
                RX671_func100(change_endian_long(0xf8f50cb6u), change_endian_long(0xcc644712u), change_endian_long(0x58c95bd2u), change_endian_long(0x6558567au));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x02000100u);
                TSIP.REG_ECH.WORD = 0x00001058u;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x4ce8aaffu), change_endian_long(0x9feb34eeu), change_endian_long(0x097a473eu), change_endian_long(0xb3d32862u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                TSIP.REG_2CH.WORD = 0x00000022u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[4] = TSIP.REG_100H.WORD;
                ARG5[5] = TSIP.REG_100H.WORD;
                ARG5[6] = TSIP.REG_100H.WORD;
                ARG5[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[8] = TSIP.REG_100H.WORD;
                ARG5[9] = TSIP.REG_100H.WORD;
                ARG5[10] = TSIP.REG_100H.WORD;
                ARG5[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xecaf79afu), change_endian_long(0x86777924u), change_endian_long(0x15445923u), change_endian_long(0x41844279u));
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
                ARG5[12] = TSIP.REG_100H.WORD;
                ARG5[13] = TSIP.REG_100H.WORD;
                ARG5[14] = TSIP.REG_100H.WORD;
                ARG5[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xf283c8d0u), change_endian_long(0x74070f5du), change_endian_long(0x1ceb01ebu), change_endian_long(0xe6582e85u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x4c724982u), change_endian_long(0xc6014fa7u), change_endian_long(0xd88298abu), change_endian_long(0x1da48680u));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x02000100u);
                TSIP.REG_ECH.WORD = 0x00001059u;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x4c7acebeu), change_endian_long(0xf7301e83u), change_endian_long(0x1be5d4aau), change_endian_long(0xb6787b50u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[4] = TSIP.REG_100H.WORD;
                ARG6[5] = TSIP.REG_100H.WORD;
                ARG6[6] = TSIP.REG_100H.WORD;
                ARG6[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[8] = TSIP.REG_100H.WORD;
                ARG6[9] = TSIP.REG_100H.WORD;
                ARG6[10] = TSIP.REG_100H.WORD;
                ARG6[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xb3ad9f1cu), change_endian_long(0xbe7f87e8u), change_endian_long(0x56e3ef8bu), change_endian_long(0xedcc229du));
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
                ARG6[12] = TSIP.REG_100H.WORD;
                ARG6[13] = TSIP.REG_100H.WORD;
                ARG6[14] = TSIP.REG_100H.WORD;
                ARG6[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x15f9f665u), change_endian_long(0xf23ee776u), change_endian_long(0x5c2aeb52u), change_endian_long(0xa8d874d8u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x13f77998u), change_endian_long(0x11c1d8a5u), change_endian_long(0x4adeb94du), change_endian_long(0x6cc0e280u));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000100u);
                TSIP.REG_ECH.WORD = 0x0000105au;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0xfc5b327eu), change_endian_long(0x5fca1145u), change_endian_long(0x9a8413cbu), change_endian_long(0xdfc0f744u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_C4H.WORD = 0x02e007bdu;
                TSIP.REG_00H.WORD = 0x00002313u;
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
                ARG7[4] = TSIP.REG_100H.WORD;
                ARG7[5] = TSIP.REG_100H.WORD;
                ARG7[6] = TSIP.REG_100H.WORD;
                ARG7[7] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xb484cdc1u), change_endian_long(0x5194e374u), change_endian_long(0xa6a9c14au), change_endian_long(0xf2da3629u));
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
                ARG7[8] = TSIP.REG_100H.WORD;
                ARG7[9] = TSIP.REG_100H.WORD;
                ARG7[10] = TSIP.REG_100H.WORD;
                ARG7[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x949ab9c6u), change_endian_long(0x4cbdec9au), change_endian_long(0x9a3f1500u), change_endian_long(0xa9c4064du));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x7a5cd573u), change_endian_long(0x37e59113u), change_endian_long(0x9432ffc1u), change_endian_long(0x5561903bu));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000100u);
                TSIP.REG_ECH.WORD = 0x0000105bu;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0xf2d1ebfcu), change_endian_long(0x5fa329bdu), change_endian_long(0xce8e074au), change_endian_long(0xbbcd86d2u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_C4H.WORD = 0x02e007bdu;
                TSIP.REG_00H.WORD = 0x00002313u;
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
                ARG8[4] = TSIP.REG_100H.WORD;
                ARG8[5] = TSIP.REG_100H.WORD;
                ARG8[6] = TSIP.REG_100H.WORD;
                ARG8[7] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x061315abu), change_endian_long(0x2b9f0f8du), change_endian_long(0x3f23587cu), change_endian_long(0x627349ceu));
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
                ARG8[8] = TSIP.REG_100H.WORD;
                ARG8[9] = TSIP.REG_100H.WORD;
                ARG8[10] = TSIP.REG_100H.WORD;
                ARG8[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x3186b53eu), change_endian_long(0x4b81e1f0u), change_endian_long(0xf19f72c2u), change_endian_long(0x89132df3u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x96768898u), change_endian_long(0x4a9d067au), change_endian_long(0x5c51b5fau), change_endian_long(0x9683087bu));
                TSIP.REG_C4H.WORD = 0x00000885u;
                TSIP.REG_00H.WORD = 0x00002313u;
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
                ARG9[0] = TSIP.REG_100H.WORD;
                ARG9[1] = TSIP.REG_100H.WORD;
                ARG9[2] = TSIP.REG_100H.WORD;
                ARG9[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x3f0ec1dcu), change_endian_long(0x089a7923u), change_endian_long(0x92d782abu), change_endian_long(0x7453af37u));
                TSIP.REG_C4H.WORD = 0x00000885u;
                TSIP.REG_00H.WORD = 0x00002313u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x00000323u;
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
                ARG10[0] = TSIP.REG_100H.WORD;
                ARG10[1] = TSIP.REG_100H.WORD;
                ARG10[2] = TSIP.REG_100H.WORD;
                ARG10[3] = TSIP.REG_100H.WORD;
                RX671_func101(change_endian_long(0xdace1ceeu), change_endian_long(0x223f2aa3u), change_endian_long(0x04f2880du), change_endian_long(0xfe1999f5u));
            }
            else if (0x03000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
            {
                RX671_func100(change_endian_long(0x3e1645aau), change_endian_long(0x4308ee32u), change_endian_long(0xdccedbb1u), change_endian_long(0x8429c508u));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x02000100u);
                TSIP.REG_ECH.WORD = 0x00001058u;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x6fa02af6u), change_endian_long(0xdafa4547u), change_endian_long(0xa38bbc49u), change_endian_long(0x7e28028cu));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                TSIP.REG_2CH.WORD = 0x00000022u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[4] = TSIP.REG_100H.WORD;
                ARG5[5] = TSIP.REG_100H.WORD;
                ARG5[6] = TSIP.REG_100H.WORD;
                ARG5[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[8] = TSIP.REG_100H.WORD;
                ARG5[9] = TSIP.REG_100H.WORD;
                ARG5[10] = TSIP.REG_100H.WORD;
                ARG5[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x8aaf7bbfu), change_endian_long(0x112a834eu), change_endian_long(0x73b78d2fu), change_endian_long(0x9200bcf2u));
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
                ARG5[12] = TSIP.REG_100H.WORD;
                ARG5[13] = TSIP.REG_100H.WORD;
                ARG5[14] = TSIP.REG_100H.WORD;
                ARG5[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xb86345ecu), change_endian_long(0x035a3318u), change_endian_long(0xd1801275u), change_endian_long(0x6d0404fdu));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG5[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xb38b7881u), change_endian_long(0x8dd5be14u), change_endian_long(0xad757c93u), change_endian_long(0xfde17935u));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x02000100u);
                TSIP.REG_ECH.WORD = 0x00001059u;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x5e494965u), change_endian_long(0x6a5fc4feu), change_endian_long(0x60a91f22u), change_endian_long(0x17026629u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[4] = TSIP.REG_100H.WORD;
                ARG6[5] = TSIP.REG_100H.WORD;
                ARG6[6] = TSIP.REG_100H.WORD;
                ARG6[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[8] = TSIP.REG_100H.WORD;
                ARG6[9] = TSIP.REG_100H.WORD;
                ARG6[10] = TSIP.REG_100H.WORD;
                ARG6[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x8fa72af7u), change_endian_long(0xc0c9b5ccu), change_endian_long(0x39a89dbeu), change_endian_long(0x28c9f07fu));
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
                ARG6[12] = TSIP.REG_100H.WORD;
                ARG6[13] = TSIP.REG_100H.WORD;
                ARG6[14] = TSIP.REG_100H.WORD;
                ARG6[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x73ac587bu), change_endian_long(0x84c77577u), change_endian_long(0x3cddfc38u), change_endian_long(0x138b621bu));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG6[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xd7ba5ab7u), change_endian_long(0x67429ebfu), change_endian_long(0xb9081c88u), change_endian_long(0x2f4d234cu));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x01000100u);
                TSIP.REG_ECH.WORD = 0x0000105au;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0x5cbd4bf7u), change_endian_long(0x1a80b751u), change_endian_long(0xfb7523f0u), change_endian_long(0x7048ad33u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[4] = TSIP.REG_100H.WORD;
                ARG7[5] = TSIP.REG_100H.WORD;
                ARG7[6] = TSIP.REG_100H.WORD;
                ARG7[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[8] = TSIP.REG_100H.WORD;
                ARG7[9] = TSIP.REG_100H.WORD;
                ARG7[10] = TSIP.REG_100H.WORD;
                ARG7[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x79fd0a8bu), change_endian_long(0x14da2515u), change_endian_long(0xa6b4ea74u), change_endian_long(0x00be8e77u));
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
                ARG7[12] = TSIP.REG_100H.WORD;
                ARG7[13] = TSIP.REG_100H.WORD;
                ARG7[14] = TSIP.REG_100H.WORD;
                ARG7[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x41086bf1u), change_endian_long(0x5476b138u), change_endian_long(0x9189feb8u), change_endian_long(0x41e4f11fu));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x85ab9bccu), change_endian_long(0x7086bab3u), change_endian_long(0x0986ff2du), change_endian_long(0xe5229401u));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x01000100u);
                TSIP.REG_ECH.WORD = 0x0000105bu;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0xd68bce83u), change_endian_long(0x9e25027au), change_endian_long(0x172b9397u), change_endian_long(0x91e9a28fu));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[4] = TSIP.REG_100H.WORD;
                ARG8[5] = TSIP.REG_100H.WORD;
                ARG8[6] = TSIP.REG_100H.WORD;
                ARG8[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[8] = TSIP.REG_100H.WORD;
                ARG8[9] = TSIP.REG_100H.WORD;
                ARG8[10] = TSIP.REG_100H.WORD;
                ARG8[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xfe100d87u), change_endian_long(0x947d70d4u), change_endian_long(0x630c26c3u), change_endian_long(0x903e45b8u));
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
                ARG8[12] = TSIP.REG_100H.WORD;
                ARG8[13] = TSIP.REG_100H.WORD;
                ARG8[14] = TSIP.REG_100H.WORD;
                ARG8[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x8b205c27u), change_endian_long(0x65d880e9u), change_endian_long(0xb698f8a0u), change_endian_long(0x19fe6fadu));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x56f63065u), change_endian_long(0x85078c84u), change_endian_long(0x2ed7e52du), change_endian_long(0xfb275ab5u));
                TSIP.REG_C4H.WORD = 0x00000885u;
                TSIP.REG_00H.WORD = 0x00002313u;
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
                ARG9[0] = TSIP.REG_100H.WORD;
                ARG9[1] = TSIP.REG_100H.WORD;
                ARG9[2] = TSIP.REG_100H.WORD;
                ARG9[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x436551fau), change_endian_long(0x92cbc566u), change_endian_long(0x5385ababu), change_endian_long(0xa1cb179fu));
                TSIP.REG_C4H.WORD = 0x00000885u;
                TSIP.REG_00H.WORD = 0x00002313u;
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
                ARG10[0] = TSIP.REG_100H.WORD;
                ARG10[1] = TSIP.REG_100H.WORD;
                ARG10[2] = TSIP.REG_100H.WORD;
                ARG10[3] = TSIP.REG_100H.WORD;
                RX671_func101(change_endian_long(0xa1aa864au), change_endian_long(0x95f7f38fu), change_endian_long(0x5146990du), change_endian_long(0x9f01af88u));
            }
            else if (0x06000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
            {
                RX671_func100(change_endian_long(0x6b40fa60u), change_endian_long(0x64908bbcu), change_endian_long(0x6c735ae2u), change_endian_long(0xb5c9c84du));
                TSIP.REG_A4H.WORD = 0x00040805u;
                TSIP.REG_00H.WORD = 0x00001313u;
                TSIP.REG_2CH.WORD = 0x00000022u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_A4H.WORD = 0x00050805u;
                TSIP.REG_00H.WORD = 0x00001313u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_E0H.WORD = 0x80010280u;
                TSIP.REG_00H.WORD = 0x00008307u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_E0H.WORD = 0x800202a0u;
                TSIP.REG_104H.WORD = 0x00000168u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = ARG4[0];
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = ARG4[1];
                TSIP.REG_ECH.WORD = 0x0000b6e0u;
                TSIP.REG_ECH.WORD = 0x00000001u;
                TSIP.REG_E0H.WORD = 0x81040280u;
                TSIP.REG_A4H.WORD = 0x00060805u;
                TSIP.REG_00H.WORD = 0x00001813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_E0H.WORD = 0x80010280u;
                TSIP.REG_00H.WORD = 0x00008307u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x0000037bu;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_E0H.WORD = 0x81040280u;
                TSIP.REG_A4H.WORD = 0x00070805u;
                TSIP.REG_00H.WORD = 0x00001813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x12000100u);
                TSIP.REG_ECH.WORD = 0x0000105au;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0xfe73f3f3u), change_endian_long(0xa93cf1b2u), change_endian_long(0x2c346925u), change_endian_long(0xabbe1ad0u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_104H.WORD = 0x00000151u;
                TSIP.REG_A4H.WORD = 0x00000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_00H.WORD = 0x00002113u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_A4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_00H.WORD = 0x00002113u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[4] = TSIP.REG_100H.WORD;
                ARG7[5] = TSIP.REG_100H.WORD;
                ARG7[6] = TSIP.REG_100H.WORD;
                ARG7[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[8] = TSIP.REG_100H.WORD;
                ARG7[9] = TSIP.REG_100H.WORD;
                ARG7[10] = TSIP.REG_100H.WORD;
                ARG7[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xefbfa9b4u), change_endian_long(0xab8b1ca3u), change_endian_long(0x09c83fdeu), change_endian_long(0x74c4e215u));
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
                ARG7[12] = TSIP.REG_100H.WORD;
                ARG7[13] = TSIP.REG_100H.WORD;
                ARG7[14] = TSIP.REG_100H.WORD;
                ARG7[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xc6db6459u), change_endian_long(0x4234ea34u), change_endian_long(0x75e233abu), change_endian_long(0xa0301204u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG7[3] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x91de4842u), change_endian_long(0x034e2d05u), change_endian_long(0x442d8607u), change_endian_long(0x3907016du));
                TSIP.REG_104H.WORD = 0x00000058u;
                TSIP.REG_E0H.WORD = 0x80010040u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x12000100u);
                TSIP.REG_ECH.WORD = 0x0000105bu;
                RX671_func103();
                TSIP.REG_104H.WORD = 0x00000052u;
                TSIP.REG_C4H.WORD = 0x01000c84u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_E0H.WORD = 0x80030060u;
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
                RX671_func100(change_endian_long(0xdf23db8au), change_endian_long(0x9a1f9cafu), change_endian_long(0x0eee96d4u), change_endian_long(0x959a0e78u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_104H.WORD = 0x00000151u;
                TSIP.REG_A4H.WORD = 0x00000cc4u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_00H.WORD = 0x00002113u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_A4H.WORD = 0x01000cc4u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_00H.WORD = 0x00002113u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_04H.WORD = 0x00000222u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[4] = TSIP.REG_100H.WORD;
                ARG8[5] = TSIP.REG_100H.WORD;
                ARG8[6] = TSIP.REG_100H.WORD;
                ARG8[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[8] = TSIP.REG_100H.WORD;
                ARG8[9] = TSIP.REG_100H.WORD;
                ARG8[10] = TSIP.REG_100H.WORD;
                ARG8[11] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0x92a54f2eu), change_endian_long(0xd78dbc8eu), change_endian_long(0x11ead458u), change_endian_long(0xf86e83c6u));
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
                ARG8[12] = TSIP.REG_100H.WORD;
                ARG8[13] = TSIP.REG_100H.WORD;
                ARG8[14] = TSIP.REG_100H.WORD;
                ARG8[15] = TSIP.REG_100H.WORD;
                RX671_func100(change_endian_long(0xd36fc0d6u), change_endian_long(0x424c1597u), change_endian_long(0x5a586e0au), change_endian_long(0xac67ad62u));
                TSIP.REG_E0H.WORD = 0x81040040u;
                TSIP.REG_04H.WORD = 0x00000612u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[0] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[1] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[2] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                ARG8[3] = TSIP.REG_100H.WORD;
                RX671_func101(change_endian_long(0x84e90970u), change_endian_long(0xcd154f91u), change_endian_long(0xec269710u), change_endian_long(0xaa7b9befu));
            }
            TSIP.REG_ECH.WORD = 0x00000800u;
            RX671_func101(change_endian_long(0xeb806398u), change_endian_long(0x63b39767u), change_endian_long(0xbfdf2158u), change_endian_long(0xc776e4bau));
        }
    }
    TSIP.REG_ECH.WORD = 0x00007c1du;
    TSIP.REG_1CH.WORD = 0x00602000u;
}
/**********************************************************************************************************************
 End of function ./input_dir/RX671/RX671_func404.prc
 *********************************************************************************************************************/
