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
* Function Name: RX671_func403
*******************************************************************************************************************/ /**
* @details       RX671 func403
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
void RX671_func403(uint32_t *ARG1, uint32_t *ARG2, uint32_t *ARG3, uint32_t *ARG4, uint32_t *ARG5, uint32_t *ARG6, uint32_t *ARG7, const uint32_t *ARG8, uint32_t *ARG9)
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
    TSIP.REG_104H.WORD = 0x00000168u;
    TSIP.REG_E0H.WORD = 0x800201c0u;
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = ARG1[0];
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = ARG2[0];
    TSIP.REG_ECH.WORD = 0x3420a9c0u;
    TSIP.REG_ECH.WORD = 0x00000004u;
    TSIP.REG_E0H.WORD = 0x00000080u;
    TSIP.REG_1CH.WORD = 0x00A60000u;
    TSIP.REG_ECH.WORD = 0x380089e0u;
    TSIP.REG_ECH.WORD = 0x00000004u;
    TSIP.REG_E0H.WORD = 0x00000080u;
    TSIP.REG_1CH.WORD = 0x00260000u;
    TSIP.REG_ECH.WORD = 0x3420a9e0u;
    TSIP.REG_ECH.WORD = 0x00000006u;
    TSIP.REG_E0H.WORD = 0x00000080u;
    TSIP.REG_1CH.WORD = 0x00A60000u;
    RX671_func100(change_endian_long(0x41ee9d7bu), change_endian_long(0x56e825b2u), change_endian_long(0x6f14c7a4u), change_endian_long(0x75ffe5f1u));
    TSIP.REG_1CH.WORD = 0x00400000u;
    TSIP.REG_1D0H.WORD = 0x00000000u;
    if (1u == (TSIP.REG_1CH.BIT.B22))
    {
        TSIP.REG_ECH.WORD = 0x0000b400u;
        TSIP.REG_ECH.WORD = 0xffffffffu;
        RX671_func101(change_endian_long(0x6e1c95cfu), change_endian_long(0x093a4424u), change_endian_long(0xda304d9cu), change_endian_long(0x76ad5dc7u));
    }
    else
    {
        TSIP.REG_ECH.WORD = 0x000035afu;
        TSIP.REG_ECH.WORD = 0x380089a0u;
        TSIP.REG_ECH.WORD = 0x00000002u;
        TSIP.REG_ECH.WORD = 0x2000b5a0u;
        TSIP.REG_ECH.WORD = 0x00000000u;
        TSIP.REG_104H.WORD = 0x00000068u;
        TSIP.REG_E0H.WORD = 0x800102c0u;
        /* WAIT_LOOP */
        while (1u != TSIP.REG_104H.BIT.B31)
        {
            /* waiting */
        }
        TSIP.REG_100H.WORD = ARG5[0];
        TSIP.REG_ECH.WORD = 0x380089e0u;
        TSIP.REG_ECH.WORD = 0x00000005u;
        TSIP.REG_E0H.WORD = 0x00000080u;
        TSIP.REG_1CH.WORD = 0x00A60000u;
        RX671_func100(change_endian_long(0xdb5f89b4u), change_endian_long(0x6a3ee3bdu), change_endian_long(0xa8881927u), change_endian_long(0xc9856746u));
        TSIP.REG_1CH.WORD = 0x00400000u;
        TSIP.REG_1D0H.WORD = 0x00000000u;
        if (1u == (TSIP.REG_1CH.BIT.B22))
        {
            RX671_func100(change_endian_long(0x35745501u), change_endian_long(0xf7e286bfu), change_endian_long(0xc01f1887u), change_endian_long(0x781d56d0u));
            TSIP.REG_104H.WORD = 0x00000368u;
            TSIP.REG_E0H.WORD = 0x800402e0u;
            for (iLoop = 0; iLoop < 4; iLoop = iLoop + 1)
            {
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = ARG7[iLoop];
            }
            TSIP.REG_ECH.WORD = 0x00007c0du;
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
                TSIP.REG_ECH.WORD = 0x38000defu;
                TSIP.REG_E0H.WORD = 0x00000080u;
                TSIP.REG_1CH.WORD = 0x00260000u;
                TSIP.REG_ECH.WORD = 0x380089e0u;
                TSIP.REG_ECH.WORD = 0x00000003u;
                TSIP.REG_E0H.WORD = 0x00000080u;
                TSIP.REG_1CH.WORD = 0x00260000u;
                RX671_func100(change_endian_long(0x07261f54u), change_endian_long(0xb17bf92fu), change_endian_long(0xd2e7b045u), change_endian_long(0x0baf7003u));
                TSIP.REG_1CH.WORD = 0x00400000u;
                TSIP.REG_1D0H.WORD = 0x00000000u;
                if (1u == (TSIP.REG_1CH.BIT.B22))
                {
                    TSIP.REG_ECH.WORD = 0x00003417u;
                    TSIP.REG_ECH.WORD = 0x0000a400u;
                    TSIP.REG_ECH.WORD = 0x000000ffu;
                    TSIP.REG_ECH.WORD = 0x08002818u;
                    TSIP.REG_E0H.WORD = 0x00000080u;
                    TSIP.REG_1CH.WORD = 0x00A60000u;
                    RX671_func101(change_endian_long(0xf963bfa7u), change_endian_long(0x45835f11u), change_endian_long(0x0e264d23u), change_endian_long(0x1d6b1b30u));
                }
                else
                {
                    TSIP.REG_ECH.WORD = 0x00003417u;
                    TSIP.REG_ECH.WORD = 0x0000a400u;
                    TSIP.REG_ECH.WORD = 0x000001ffu;
                    TSIP.REG_ECH.WORD = 0x08002818u;
                    TSIP.REG_E0H.WORD = 0x00000080u;
                    TSIP.REG_1CH.WORD = 0x00A60000u;
                    RX671_func101(change_endian_long(0x7e6171d2u), change_endian_long(0x9777e366u), change_endian_long(0x5b5b514cu), change_endian_long(0xa368eebau));
                }
                TSIP.REG_ECH.WORD = 0x00003419u;
                TSIP.REG_ECH.WORD = 0x0000a400u;
                TSIP.REG_ECH.WORD = 0x00000003u;
                TSIP.REG_ECH.WORD = 0x0c00281au;
                TSIP.REG_E0H.WORD = 0x00000080u;
                TSIP.REG_1CH.WORD = 0x00A60000u;
                RX671_func101(change_endian_long(0x9a1a2a75u), change_endian_long(0x23b0a137u), change_endian_long(0x0e9c6417u), change_endian_long(0xefcf7454u));
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
                RX671_func101(change_endian_long(0x4b0c49efu), change_endian_long(0x7b5d82d3u), change_endian_long(0xe536ae1au), change_endian_long(0x95d64b41u));
            }
            RX671_func101(change_endian_long(0x4ac5005du), change_endian_long(0xba23eabeu), change_endian_long(0xa15a65f7u), change_endian_long(0xe165fccdu));
        }
        else
        {
            RX671_func101(change_endian_long(0x7f3776c5u), change_endian_long(0xf7c5b90fu), change_endian_long(0x494dc01fu), change_endian_long(0xa0db7632u));
        }
        RX671_func100(change_endian_long(0x8e085347u), change_endian_long(0x046d8b28u), change_endian_long(0x6bdbd8a1u), change_endian_long(0x87fe9b11u));
        TSIP.REG_1CH.WORD = 0x00400000u;
        TSIP.REG_1D0H.WORD = 0x00000000u;
        if (1u == (TSIP.REG_1CH.BIT.B22))
        {
            TSIP.REG_ECH.WORD = 0x0000b400u;
            TSIP.REG_ECH.WORD = 0xffffffffu;
            RX671_func101(change_endian_long(0x242edec3u), change_endian_long(0xb17f47b6u), change_endian_long(0xf88a206cu), change_endian_long(0x4fe599c8u));
        }
        else
        {
            TSIP.REG_104H.WORD = 0x00000368u;
            TSIP.REG_E0H.WORD = 0x80040000u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = ARG3[0];
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = ARG3[1];
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = ARG3[2];
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = ARG3[3];
            TSIP.REG_ECH.WORD = 0x00000bdeu;
            TSIP.REG_ECH.WORD = 0x000037e0u;
            TSIP.REG_ECH.WORD = 0x00008fe0u;
            TSIP.REG_ECH.WORD = 0xff000000u;
            TSIP.REG_ECH.WORD = 0x00003629u;
            TSIP.REG_ECH.WORD = 0x00009220u;
            TSIP.REG_ECH.WORD = 0x05000000u;
            TSIP.REG_ECH.WORD = 0x38000bf1u;
            TSIP.REG_ECH.WORD = 0x1000d3c0u;
            TSIP.REG_ECH.WORD = 0x00003629u;
            TSIP.REG_ECH.WORD = 0x00009220u;
            TSIP.REG_ECH.WORD = 0x0a000000u;
            TSIP.REG_ECH.WORD = 0x38000bf1u;
            TSIP.REG_ECH.WORD = 0x1000d3c0u;
            TSIP.REG_ECH.WORD = 0x00003629u;
            TSIP.REG_ECH.WORD = 0x00009220u;
            TSIP.REG_ECH.WORD = 0x31000000u;
            TSIP.REG_ECH.WORD = 0x38000bf1u;
            TSIP.REG_ECH.WORD = 0x1000d3c0u;
            TSIP.REG_ECH.WORD = 0x3800d813u;
            TSIP.REG_ECH.WORD = 0x2000d3c1u;
            TSIP.REG_ECH.WORD = 0x000037e0u;
            TSIP.REG_ECH.WORD = 0x00008fe0u;
            TSIP.REG_ECH.WORD = 0x0000ff00u;
            TSIP.REG_ECH.WORD = 0x38008be0u;
            TSIP.REG_ECH.WORD = 0x00000100u;
            TSIP.REG_ECH.WORD = 0x1000d3c2u;
            TSIP.REG_ECH.WORD = 0x38008bc0u;
            TSIP.REG_ECH.WORD = 0x00000007u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00A60000u;
            RX671_func100(change_endian_long(0x06c6bad0u), change_endian_long(0x2e435838u), change_endian_long(0xc131a004u), change_endian_long(0x8ad51256u));
            TSIP.REG_1CH.WORD = 0x00400000u;
            TSIP.REG_1D0H.WORD = 0x00000000u;
            if (1u == (TSIP.REG_1CH.BIT.B22))
            {
                TSIP.REG_ECH.WORD = 0x0000b400u;
                TSIP.REG_ECH.WORD = 0xffffffffu;
                RX671_func101(change_endian_long(0x5e613205u), change_endian_long(0x64a199feu), change_endian_long(0xb2d64ed3u), change_endian_long(0xf952e0c5u));
            }
            else
            {
                RX671_func100(change_endian_long(0x6c7f3fb1u), change_endian_long(0xa996b7e4u), change_endian_long(0xb39e5806u), change_endian_long(0x5863dff6u));
                TSIP.REG_C4H.WORD = 0x00082b8du;
                TSIP.REG_E0H.WORD = 0x81040000u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_ECH.WORD = 0x0000362eu;
                TSIP.REG_ECH.WORD = 0x38008a20u;
                TSIP.REG_ECH.WORD = 0x00000002u;
                TSIP.REG_ECH.WORD = 0x2000b620u;
                TSIP.REG_ECH.WORD = 0x00000000u;
                TSIP.REG_ECH.WORD = 0x00007c11u;
                TSIP.REG_1CH.WORD = 0x00600000u;
                TSIP.REG_1D0H.WORD = 0x00000000u;
                if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                {
                    TSIP.REG_28H.WORD = 0x00bf0001u;
                    TSIP.REG_104H.WORD = 0x00008362u;
                    TSIP.REG_D0H.WORD = 0x00001f00u;
                    TSIP.REG_C4H.WORD = 0x42f087bfu;
                    TSIP.REG_00H.WORD = 0x00013203u;
                    TSIP.REG_2CH.WORD = 0x00000014u;
                    for (iLoop = 0; iLoop < 64; iLoop = iLoop + 4)
                    {
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = ARG3[iLoop+4];
                        TSIP.REG_100H.WORD = ARG3[iLoop+5];
                        TSIP.REG_100H.WORD = ARG3[iLoop+6];
                        TSIP.REG_100H.WORD = ARG3[iLoop+7];
                    }
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x00013203u;
                    TSIP.REG_2CH.WORD = 0x00000012u;
                    for (iLoop = 0; iLoop < 64; iLoop = iLoop + 4)
                    {
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = ARG3[iLoop+68];
                        TSIP.REG_100H.WORD = ARG3[iLoop+69];
                        TSIP.REG_100H.WORD = ARG3[iLoop+70];
                        TSIP.REG_100H.WORD = ARG3[iLoop+71];
                    }
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x40f007bdu;
                    for (iLoop = 0; iLoop < 4; iLoop = iLoop + 4)
                    {
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = ARG3[iLoop+132];
                        TSIP.REG_100H.WORD = ARG3[iLoop+133];
                        TSIP.REG_100H.WORD = ARG3[iLoop+134];
                        TSIP.REG_100H.WORD = ARG3[iLoop+135];
                    }
                    TSIP.REG_E0H.WORD = 0x80010140u;
                    TSIP.REG_00H.WORD = 0x00008207u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x0000020fu;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x400007bdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = ARG3[136];
                    TSIP.REG_100H.WORD = ARG3[137];
                    TSIP.REG_100H.WORD = ARG3[138];
                    TSIP.REG_100H.WORD = ARG3[139];
                    TSIP.REG_C4H.WORD = 0x00900c45u;
                    TSIP.REG_00H.WORD = 0x00002213u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    RX671_func101(change_endian_long(0xb5b1b52bu), change_endian_long(0xd84018a5u), change_endian_long(0xc188dffcu), change_endian_long(0xb2a80d43u));
                }
                else
                {
                    TSIP.REG_28H.WORD = 0x00870001u;
                    TSIP.REG_104H.WORD = 0x00000f62u;
                    TSIP.REG_D0H.WORD = 0x00000300u;
                    TSIP.REG_C4H.WORD = 0x42f087bfu;
                    TSIP.REG_00H.WORD = 0x00003223u;
                    TSIP.REG_2CH.WORD = 0x0000009bu;
                    for (iLoop = 0; iLoop < 8; iLoop = iLoop + 4)
                    {
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = ARG3[iLoop+4];
                        TSIP.REG_100H.WORD = ARG3[iLoop+5];
                        TSIP.REG_100H.WORD = ARG3[iLoop+6];
                        TSIP.REG_100H.WORD = ARG3[iLoop+7];
                    }
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x00003223u;
                    TSIP.REG_2CH.WORD = 0x00000012u;
                    for (iLoop = 8; iLoop < 16; iLoop = iLoop + 4)
                    {
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = ARG3[iLoop+4];
                        TSIP.REG_100H.WORD = ARG3[iLoop+5];
                        TSIP.REG_100H.WORD = ARG3[iLoop+6];
                        TSIP.REG_100H.WORD = ARG3[iLoop+7];
                    }
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x400007bdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = ARG3[20];
                    TSIP.REG_100H.WORD = ARG3[21];
                    TSIP.REG_100H.WORD = ARG3[22];
                    TSIP.REG_100H.WORD = ARG3[23];
                    TSIP.REG_C4H.WORD = 0x00900c45u;
                    TSIP.REG_00H.WORD = 0x00002213u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    RX671_func101(change_endian_long(0x7bfbaec5u), change_endian_long(0xc812747bu), change_endian_long(0x61d5234au), change_endian_long(0xadfb64a0u));
                }
                RX671_func100(change_endian_long(0x450d2bfeu), change_endian_long(0x9d867b8eu), change_endian_long(0x337f5f6fu), change_endian_long(0xa11a2ad1u));
                TSIP.REG_1CH.WORD = 0x00400000u;
                TSIP.REG_1D0H.WORD = 0x00000000u;
                if (1u == (TSIP.REG_1CH.BIT.B22))
                {
                    TSIP.REG_ECH.WORD = 0x0000b400u;
                    TSIP.REG_ECH.WORD = 0xffffffffu;
                    RX671_func101(change_endian_long(0x060f90f6u), change_endian_long(0xf2d3aa24u), change_endian_long(0xac1c8742u), change_endian_long(0x58eafc61u));
                }
                else
                {
                    TSIP.REG_ECH.WORD = 0x380089e0u;
                    TSIP.REG_ECH.WORD = 0x00000005u;
                    TSIP.REG_E0H.WORD = 0x00000080u;
                    TSIP.REG_1CH.WORD = 0x00A60000u;
                    RX671_func100(change_endian_long(0x1c582b10u), change_endian_long(0x2d103016u), change_endian_long(0x5d56feb6u), change_endian_long(0xca1847b5u));
                    TSIP.REG_1CH.WORD = 0x00400000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (1u == (TSIP.REG_1CH.BIT.B22))
                    {
                        RX671_func100(change_endian_long(0x77f0f70eu), change_endian_long(0x51c0d934u), change_endian_long(0x16dc56e3u), change_endian_long(0x03347322u));
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
                            RX671_func101(change_endian_long(0x067dd8a3u), change_endian_long(0xfa99e4aeu), change_endian_long(0xae4c5f65u), change_endian_long(0x855cd74du));
                        }
                        RX671_func100(change_endian_long(0xa031d56du), change_endian_long(0xc85b4744u), change_endian_long(0x90a29328u), change_endian_long(0x589f62bdu));
                        TSIP.REG_ECH.WORD = 0x38000805u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        TSIP.REG_1CH.WORD = 0x00402000u;
                        TSIP.REG_ECH.WORD = 0x00007c0du;
                        TSIP.REG_1CH.WORD = 0x00600000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                        {
                            RX671_func100(change_endian_long(0xc5957cb0u), change_endian_long(0xa5b20555u), change_endian_long(0x14315a5bu), change_endian_long(0xa826b7b7u));
                            TSIP.REG_ECH.WORD = 0x00000a52u;
                            TSIP.REG_ECH.WORD = 0x00000a73u;
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
                                    RX671_func100(change_endian_long(0x9bbe2e9eu), change_endian_long(0x7453faa4u), change_endian_long(0xb060a01bu), change_endian_long(0xc11608c7u));
                                    TSIP.REG_1CH.WORD = 0x00400000u;
                                    TSIP.REG_1D0H.WORD = 0x00000000u;
                                    if (1u == (TSIP.REG_1CH.BIT.B22))
                                    {
                                        TSIP.REG_ECH.WORD = 0x3420aa60u;
                                        TSIP.REG_ECH.WORD = 0x00000100u;
                                        TSIP.REG_E0H.WORD = 0x00000080u;
                                        TSIP.REG_1CH.WORD = 0x00260000u;
                                        RX671_func100(change_endian_long(0xe3d50722u), change_endian_long(0x46bee655u), change_endian_long(0xca7b7fd2u), change_endian_long(0x2bc15c66u));
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
                                            TSIP.REG_ECH.WORD = 0x0000a660u;
                                            TSIP.REG_ECH.WORD = 0x00000001u;
                                            RX671_func101(change_endian_long(0x6f0590e5u), change_endian_long(0x7b759f1au), change_endian_long(0xfa4ab07cu), change_endian_long(0x2bd2d66au));
                                        }
                                        else
                                        {
                                            TSIP.REG_ECH.WORD = 0x02003cf2u;
                                            TSIP.REG_ECH.WORD = 0x0000a640u;
                                            TSIP.REG_ECH.WORD = 0x00000001u;
                                            RX671_func101(change_endian_long(0x28f5c243u), change_endian_long(0xd14c0b8cu), change_endian_long(0x060c151bu), change_endian_long(0x62351deau));
                                        }
                                        RX671_func101(change_endian_long(0x8bd3c6acu), change_endian_long(0x3bde915du), change_endian_long(0xdd300331u), change_endian_long(0x157265fbu));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00000863u;
                                    TSIP.REG_ECH.WORD = 0x3c0028c2u;
                                    TSIP.REG_ECH.WORD = 0x20002c60u;
                                    TSIP.REG_ECH.WORD = 0x38000c63u;
                                    TSIP.REG_E0H.WORD = 0x00000080u;
                                    TSIP.REG_1CH.WORD = 0x00260000u;
                                    RX671_func100(change_endian_long(0xf3ca440au), change_endian_long(0xeb48d949u), change_endian_long(0xba32d7f6u), change_endian_long(0x09522079u));
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
                                        RX671_func101(change_endian_long(0x2a158fb7u), change_endian_long(0xfb2c8080u), change_endian_long(0xd7a1e9acu), change_endian_long(0xe2ec202au));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00002c40u;
                                    RX671_func101(change_endian_long(0x761a8385u), change_endian_long(0x14c86f5fu), change_endian_long(0x1abfedbau), change_endian_long(0xd60c31cfu));
                                }
                                TSIP.REG_ECH.WORD = 0x08000c21u;
                                TSIP.REG_E0H.WORD = 0x00000080u;
                                TSIP.REG_1CH.WORD = 0x00260000u;
                                TSIP.REG_1CH.WORD = 0x00402000u;
                                TSIP.REG_ECH.WORD = 0x00002ca0u;
                                RX671_func101(change_endian_long(0xa7f266ebu), change_endian_long(0x88158b44u), change_endian_long(0xaf41afcdu), change_endian_long(0xb6f32b72u));
                            }
                            TSIP.REG_ECH.WORD = 0x38000805u;
                            TSIP.REG_E0H.WORD = 0x00000080u;
                            TSIP.REG_1CH.WORD = 0x00260000u;
                            TSIP.REG_1CH.WORD = 0x00402000u;
                            RX671_func101(change_endian_long(0x5b8d5716u), change_endian_long(0x437dd1bfu), change_endian_long(0x4c4efb17u), change_endian_long(0xaa4f151au));
                        }
                        else
                        {
                            RX671_func100(change_endian_long(0x73188d97u), change_endian_long(0x38cee4feu), change_endian_long(0x43c0eecbu), change_endian_long(0xc3a0b098u));
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
                                    RX671_func100(change_endian_long(0xb8bcdb7bu), change_endian_long(0xb39f39ecu), change_endian_long(0xa7312f78u), change_endian_long(0x64b85922u));
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
                                        RX671_func101(change_endian_long(0xb3e16f08u), change_endian_long(0x2b43db30u), change_endian_long(0x3df60907u), change_endian_long(0x1b9ad876u));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00000863u;
                                    TSIP.REG_ECH.WORD = 0x3c002857u;
                                    TSIP.REG_ECH.WORD = 0x20002c60u;
                                    TSIP.REG_ECH.WORD = 0x3c002b02u;
                                    TSIP.REG_ECH.WORD = 0x20002c60u;
                                    TSIP.REG_ECH.WORD = 0x38000c63u;
                                    TSIP.REG_E0H.WORD = 0x00000080u;
                                    TSIP.REG_1CH.WORD = 0x00260000u;
                                    RX671_func100(change_endian_long(0xd12ab374u), change_endian_long(0x048335feu), change_endian_long(0x3e4c5a8du), change_endian_long(0x01200628u));
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
                                        RX671_func101(change_endian_long(0xeb0e80a2u), change_endian_long(0x24306463u), change_endian_long(0xd4a12d4bu), change_endian_long(0xbe725f81u));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00000863u;
                                    TSIP.REG_ECH.WORD = 0x3c0028c2u;
                                    TSIP.REG_ECH.WORD = 0x20002c60u;
                                    TSIP.REG_ECH.WORD = 0x38000c63u;
                                    TSIP.REG_E0H.WORD = 0x00000080u;
                                    TSIP.REG_1CH.WORD = 0x00260000u;
                                    RX671_func100(change_endian_long(0x773c84d2u), change_endian_long(0xaa41986du), change_endian_long(0x7aff016bu), change_endian_long(0xd71bca92u));
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
                                        RX671_func101(change_endian_long(0xf881b698u), change_endian_long(0xb2d6a196u), change_endian_long(0xa1eb0890u), change_endian_long(0x3469ccdfu));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00002c40u;
                                    RX671_func101(change_endian_long(0xf38c3225u), change_endian_long(0xe2f880f3u), change_endian_long(0xb292b268u), change_endian_long(0x35a977a5u));
                                }
                                TSIP.REG_ECH.WORD = 0x08000c21u;
                                TSIP.REG_E0H.WORD = 0x00000080u;
                                TSIP.REG_1CH.WORD = 0x00260000u;
                                TSIP.REG_1CH.WORD = 0x00402000u;
                                TSIP.REG_ECH.WORD = 0x00002ca0u;
                                RX671_func101(change_endian_long(0x4977182bu), change_endian_long(0x7f49adb2u), change_endian_long(0x6ca50c92u), change_endian_long(0x280aa662u));
                            }
                            TSIP.REG_ECH.WORD = 0x38000805u;
                            TSIP.REG_E0H.WORD = 0x00000080u;
                            TSIP.REG_1CH.WORD = 0x00260000u;
                            TSIP.REG_1CH.WORD = 0x00402000u;
                            RX671_func101(change_endian_long(0xc420797bu), change_endian_long(0x6b84f076u), change_endian_long(0xc3289aecu), change_endian_long(0x5f2f31b2u));
                        }
                        RX671_func101(change_endian_long(0x83dd3d30u), change_endian_long(0x65d90c1bu), change_endian_long(0x6b5250d9u), change_endian_long(0xb3ec4192u));
                    }
                    else
                    {
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
                        RX671_func100(change_endian_long(0x1e857024u), change_endian_long(0x9bad94f3u), change_endian_long(0xc0082ecfu), change_endian_long(0xb1957de0u));
                        TSIP.REG_ECH.WORD = 0x00003416u;
                        TSIP.REG_ECH.WORD = 0x0000a400u;
                        TSIP.REG_ECH.WORD = 0x00000003u;
                        TSIP.REG_ECH.WORD = 0x00026800u;
                        TSIP.REG_ECH.WORD = 0x00003000u;
                        TSIP.REG_E0H.WORD = 0x81010000u;
                        TSIP.REG_04H.WORD = 0x00000606u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_04H.BIT.B30)
                        {
                            /* waiting */
                        }
                        S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
                        TSIP.REG_ECH.WORD = 0x000008a5u;
                        for (iLoop = 0; iLoop < S_RAM[0]; iLoop = iLoop + 1)
                        {
                            TSIP.REG_104H.WORD = 0x00000064u;
                            /* WAIT_LOOP */
                            while (1u != TSIP.REG_104H.BIT.B31)
                            {
                                /* waiting */
                            }
                            TSIP.REG_100H.WORD = ARG4[iLoop];
                            TSIP.REG_ECH.WORD = 0x0000a4a0u;
                            TSIP.REG_ECH.WORD = 0x00000001u;
                            RX671_func101(change_endian_long(0x7f6bd024u), change_endian_long(0x506303beu), change_endian_long(0x554f3f14u), change_endian_long(0x2acf3f93u));
                        }
                        TSIP.REG_ECH.WORD = 0x38000805u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        TSIP.REG_1CH.WORD = 0x00402000u;
                        RX671_func100(change_endian_long(0x164c6af0u), change_endian_long(0xc40b19a3u), change_endian_long(0x627a1365u), change_endian_long(0x63f9ccceu));
                        TSIP.REG_104H.WORD = 0x00000068u;
                        TSIP.REG_E0H.WORD = 0x80010060u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = ARG4[iLoop];
                        TSIP.REG_ECH.WORD = 0x00003416u;
                        TSIP.REG_ECH.WORD = 0x00008c00u;
                        TSIP.REG_ECH.WORD = 0x00000003u;
                        TSIP.REG_ECH.WORD = 0x38000c00u;
                        TSIP.REG_ECH.WORD = 0x00030020u;
                        TSIP.REG_ECH.WORD = 0x0000b400u;
                        TSIP.REG_ECH.WORD = 0x00000004u;
                        TSIP.REG_ECH.WORD = 0x00000080u;
                        TSIP.REG_E0H.WORD = 0x81010000u;
                        TSIP.REG_04H.WORD = 0x00000606u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_04H.BIT.B30)
                        {
                            /* waiting */
                        }
                        S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
                        TSIP.REG_ECH.WORD = 0x000008a5u;
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
                            RX671_func101(change_endian_long(0x177706c4u), change_endian_long(0x5db828b5u), change_endian_long(0x97da6d42u), change_endian_long(0x882f8418u));
                        }
                        TSIP.REG_ECH.WORD = 0x38000805u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        TSIP.REG_1CH.WORD = 0x00402000u;
                        RX671_func101(change_endian_long(0xb10b0f4bu), change_endian_long(0xffcf9155u), change_endian_long(0xc10dd619u), change_endian_long(0xaec7dc06u));
                    }
                    RX671_func100(change_endian_long(0x7e95ded3u), change_endian_long(0x5dbcea3cu), change_endian_long(0x2c21d95eu), change_endian_long(0xe792bb23u));
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
                        RX671_func101(change_endian_long(0x776ac7cfu), change_endian_long(0xc0fbd234u), change_endian_long(0x3edeae29u), change_endian_long(0x1060e32eu));
                    }
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
                    RX671_func100(change_endian_long(0xabc12025u), change_endian_long(0xc25171bbu), change_endian_long(0x458ece61u), change_endian_long(0x05ae7a94u));
                    RX671_func103();
                    RX671_func100(change_endian_long(0xba18c675u), change_endian_long(0xc6596a81u), change_endian_long(0x9a423982u), change_endian_long(0x956292cfu));
                    TSIP.REG_104H.WORD = 0x00000052u;
                    TSIP.REG_C4H.WORD = 0x01000c84u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_E0H.WORD = 0x800402e0u;
                    TSIP.REG_00H.WORD = 0x00008213u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x000c0805u;
                    TSIP.REG_E0H.WORD = 0x810402e0u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_ECH.WORD = 0x380089e0u;
                    TSIP.REG_ECH.WORD = 0x00000005u;
                    TSIP.REG_E0H.WORD = 0x00000080u;
                    TSIP.REG_1CH.WORD = 0x00A60000u;
                    RX671_func100(change_endian_long(0x65b50a52u), change_endian_long(0xc8b78db2u), change_endian_long(0x7e33e49eu), change_endian_long(0xa2f4ccecu));
                    TSIP.REG_1CH.WORD = 0x00400000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (1u == (TSIP.REG_1CH.BIT.B22))
                    {
                        RX671_func100(change_endian_long(0x6c84ba89u), change_endian_long(0xd469a889u), change_endian_long(0xf902987cu), change_endian_long(0xccbb6b92u));
                        TSIP.REG_ECH.WORD = 0x00007c0du;
                        TSIP.REG_1CH.WORD = 0x00600000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                        {
                            TSIP.REG_ECH.WORD = 0x38000defu;
                            TSIP.REG_E0H.WORD = 0x00000080u;
                            TSIP.REG_1CH.WORD = 0x00260000u;
                            TSIP.REG_ECH.WORD = 0x380089e0u;
                            TSIP.REG_ECH.WORD = 0x00000003u;
                            TSIP.REG_E0H.WORD = 0x00000080u;
                            TSIP.REG_1CH.WORD = 0x00260000u;
                            RX671_func100(change_endian_long(0x96883062u), change_endian_long(0x58d6ac0fu), change_endian_long(0x480835fau), change_endian_long(0x28c91bdeu));
                            TSIP.REG_1CH.WORD = 0x00400000u;
                            TSIP.REG_1D0H.WORD = 0x00000000u;
                            if (1u == (TSIP.REG_1CH.BIT.B22))
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
                                RX671_func101(change_endian_long(0x597227c8u), change_endian_long(0x3154a18bu), change_endian_long(0xd860bacfu), change_endian_long(0x82cc21c9u));
                            }
                            else
                            {
                                RX671_func100(change_endian_long(0x38d8979du), change_endian_long(0x81fe1a88u), change_endian_long(0x61b008c7u), change_endian_long(0x3ff3c0d8u));
                                TSIP.REG_ECH.WORD = 0x0000342bu;
                                RX671_func080();
                                RX671_func100(change_endian_long(0x859e6333u), change_endian_long(0xa78b8e6fu), change_endian_long(0xfda9c0fdu), change_endian_long(0xfe525416u));
                                TSIP.REG_00H.WORD = 0x00012303u;
                                TSIP.REG_2CH.WORD = 0x00000020u;
                                RX671_func313(1496);
                                RX671_func100(change_endian_long(0x3d4dbed8u), change_endian_long(0x9fe99d94u), change_endian_long(0x72733fe3u), change_endian_long(0xd84a5174u));
                                RX671_func314(1496+64);
                                RX671_func100(change_endian_long(0xb272001bu), change_endian_long(0x63a3f774u), change_endian_long(0x696f82d1u), change_endian_long(0x809f373du));
                                TSIP.REG_ECH.WORD = 0x0000342cu;
                                RX671_func080();
                                RX671_func100(change_endian_long(0x871c730du), change_endian_long(0x814593bau), change_endian_long(0x8cffa333u), change_endian_long(0xde18a891u));
                                TSIP.REG_ECH.WORD = 0x00000800u;
                                TSIP.REG_E0H.WORD = 0x81c00000u;
                                TSIP.REG_00H.WORD = 0x00012803u;
                                RX671_func313(1496+68);
                                RX671_func100(change_endian_long(0xf529414fu), change_endian_long(0x6311f1f8u), change_endian_long(0xad8880edu), change_endian_long(0x13de029fu));
                                RX671_func314(1496+132);
                                RX671_func101(change_endian_long(0x844310c5u), change_endian_long(0x18e56bbeu), change_endian_long(0x32e4658cu), change_endian_long(0x96b60665u));
                            }
                            RX671_func101(change_endian_long(0x6a9090b0u), change_endian_long(0xf2335409u), change_endian_long(0xf2880babu), change_endian_long(0x1e4eacb3u));
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
                            RX671_func101(change_endian_long(0xfdaf17e4u), change_endian_long(0xa1ce5ba1u), change_endian_long(0xffb4ba2du), change_endian_long(0x95bd527bu));
                        }
                        RX671_func101(change_endian_long(0x599943bfu), change_endian_long(0x51660a24u), change_endian_long(0x10b61b97u), change_endian_long(0xc9d8de8eu));
                    }
                    else
                    {
                        RX671_func101(change_endian_long(0xff90ae69u), change_endian_long(0xfbd776b9u), change_endian_long(0x12536838u), change_endian_long(0xfca7a4b9u));
                    }
                    RX671_func100(change_endian_long(0xc858101du), change_endian_long(0x7d86db63u), change_endian_long(0xc0c0f0c4u), change_endian_long(0xd7290bceu));
                    TSIP.REG_ECH.WORD = 0x00007c0eu;
                    TSIP.REG_1CH.WORD = 0x00600000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                    {
                        RX671_func100(change_endian_long(0xc513c0f9u), change_endian_long(0x5f144789u), change_endian_long(0x6b2db03cu), change_endian_long(0xfda6e909u));
                        TSIP.REG_28H.WORD = 0x00bf0001u;
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
                        TSIP.REG_18H.WORD = 0x00000004u;
                        TSIP.REG_34H.WORD = 0x00000000u;
                        TSIP.REG_38H.WORD = 0x00000338u;
                        TSIP.REG_E0H.WORD = 0x81010140u;
                        TSIP.REG_00H.WORD = 0x00003807u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_00H.BIT.B25)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00001800u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_18H.BIT.B10)
                        {
                            /* waiting */
                        }
                        TSIP.REG_18H.WORD = 0x00000000u;
                        TSIP.REG_104H.WORD = 0x00003757u;
                        TSIP.REG_2CH.WORD = 0x00000012u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x0001ffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0x00303130u);
                        TSIP.REG_100H.WORD = change_endian_long(0x0d060960u);
                        TSIP.REG_100H.WORD = change_endian_long(0x86480165u);
                        TSIP.REG_100H.WORD = change_endian_long(0x03040201u);
                        TSIP.REG_100H.WORD = change_endian_long(0x05000420u);
                        TSIP.REG_00H.WORD = 0x00003523u;
                        TSIP.REG_74H.WORD = 0x00000008u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_00H.BIT.B25)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00001800u;
                        TSIP.REG_24H.WORD = 0x000009c0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_24H.WORD = 0x00001191u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00210000u;
                        TSIP.REG_24H.WORD = 0x000011c0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_24H.WORD = 0x00000991u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00210000u;
                        RX671_func101(change_endian_long(0xb4d69953u), change_endian_long(0x3e58f3b8u), change_endian_long(0x21730b01u), change_endian_long(0x8ca7b514u));
                    }
                    else if (0x01000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                    {
                        TSIP.REG_28H.WORD = 0x00bf0001u;
                        TSIP.REG_24H.WORD = 0x000098d0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_ECH.WORD = 0x0000368au;
                        TSIP.REG_ECH.WORD = 0x000034b7u;
                        TSIP.REG_ECH.WORD = 0x000034d8u;
                        TSIP.REG_ECH.WORD = 0x000034f9u;
                        TSIP.REG_ECH.WORD = 0x0000351au;
                        RX671_func100(change_endian_long(0x7dd2d055u), change_endian_long(0xa5121977u), change_endian_long(0xdba18a04u), change_endian_long(0xf350ca21u));
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x5fe685f6u);
                        RX671_func080();
                        RX671_func100(change_endian_long(0xbc72a415u), change_endian_long(0xa982a672u), change_endian_long(0xda6798b4u), change_endian_long(0xaca4089fu));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000020u;
                        RX671_func313(748);
                        RX671_func100(change_endian_long(0x07bc8169u), change_endian_long(0xaab4e65eu), change_endian_long(0x6a43f747u), change_endian_long(0x8201449cu));
                        RX671_func314(748+64);
                        RX671_func100(change_endian_long(0xa1a0907au), change_endian_long(0xffa12a08u), change_endian_long(0x7b632896u), change_endian_long(0xba08946cu));
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x1c5a2b81u);
                        RX671_func080();
                        RX671_func100(change_endian_long(0x9f74e4bdu), change_endian_long(0x1cf1bc93u), change_endian_long(0x4d3ed03au), change_endian_long(0xa0bb6ecau));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000022u;
                        RX671_func313(680);
                        RX671_func100(change_endian_long(0x4d3f90aau), change_endian_long(0x8c6bd49cu), change_endian_long(0xee93a03du), change_endian_long(0xe6278ab1u));
                        RX671_func314(680+64);
                        RX671_func100(change_endian_long(0x04764cc0u), change_endian_long(0xfbd05ed7u), change_endian_long(0xd3dbe62cu), change_endian_long(0x20635a56u));
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
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x5dd049feu);
                        RX671_func080();
                        RX671_func100(change_endian_long(0x629d6366u), change_endian_long(0x20719066u), change_endian_long(0x4c9facadu), change_endian_long(0x9d85354cu));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000020u;
                        RX671_func313(68);
                        RX671_func100(change_endian_long(0x6eba3329u), change_endian_long(0x8a5122d1u), change_endian_long(0x09d70c4bu), change_endian_long(0xd04cb6d0u));
                        RX671_func314(68+64);
                        RX671_func100(change_endian_long(0x03941ea2u), change_endian_long(0x45bef795u), change_endian_long(0x2208757fu), change_endian_long(0x3c588999u));
                        TSIP.REG_2CH.WORD = 0x00000014u;
                        TSIP.REG_104H.WORD = 0x00003f67u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = ARG6[64];
                        TSIP.REG_100H.WORD = ARG6[65];
                        TSIP.REG_100H.WORD = ARG6[66];
                        TSIP.REG_100H.WORD = ARG6[67];
                        TSIP.REG_100H.WORD = ARG6[68];
                        TSIP.REG_100H.WORD = ARG6[69];
                        TSIP.REG_100H.WORD = ARG6[70];
                        TSIP.REG_100H.WORD = ARG6[71];
                        TSIP.REG_100H.WORD = ARG6[72];
                        TSIP.REG_100H.WORD = ARG6[73];
                        TSIP.REG_100H.WORD = ARG6[74];
                        TSIP.REG_100H.WORD = ARG6[75];
                        TSIP.REG_100H.WORD = ARG6[76];
                        TSIP.REG_100H.WORD = ARG6[77];
                        TSIP.REG_100H.WORD = ARG6[78];
                        TSIP.REG_100H.WORD = ARG6[79];
                        TSIP.REG_100H.WORD = ARG6[80];
                        TSIP.REG_100H.WORD = ARG6[81];
                        TSIP.REG_100H.WORD = ARG6[82];
                        TSIP.REG_100H.WORD = ARG6[83];
                        TSIP.REG_100H.WORD = ARG6[84];
                        TSIP.REG_100H.WORD = ARG6[85];
                        TSIP.REG_100H.WORD = ARG6[86];
                        TSIP.REG_100H.WORD = ARG6[87];
                        TSIP.REG_100H.WORD = ARG6[88];
                        TSIP.REG_100H.WORD = ARG6[89];
                        TSIP.REG_100H.WORD = ARG6[90];
                        TSIP.REG_100H.WORD = ARG6[91];
                        TSIP.REG_100H.WORD = ARG6[92];
                        TSIP.REG_100H.WORD = ARG6[93];
                        TSIP.REG_100H.WORD = ARG6[94];
                        TSIP.REG_100H.WORD = ARG6[95];
                        TSIP.REG_100H.WORD = ARG6[96];
                        TSIP.REG_100H.WORD = ARG6[97];
                        TSIP.REG_100H.WORD = ARG6[98];
                        TSIP.REG_100H.WORD = ARG6[99];
                        TSIP.REG_100H.WORD = ARG6[100];
                        TSIP.REG_100H.WORD = ARG6[101];
                        TSIP.REG_100H.WORD = ARG6[102];
                        TSIP.REG_100H.WORD = ARG6[103];
                        TSIP.REG_100H.WORD = ARG6[104];
                        TSIP.REG_100H.WORD = ARG6[105];
                        TSIP.REG_100H.WORD = ARG6[106];
                        TSIP.REG_100H.WORD = ARG6[107];
                        TSIP.REG_100H.WORD = ARG6[108];
                        TSIP.REG_100H.WORD = ARG6[109];
                        TSIP.REG_100H.WORD = ARG6[110];
                        TSIP.REG_100H.WORD = ARG6[111];
                        TSIP.REG_100H.WORD = ARG6[112];
                        TSIP.REG_100H.WORD = ARG6[113];
                        TSIP.REG_100H.WORD = ARG6[114];
                        TSIP.REG_100H.WORD = ARG6[115];
                        TSIP.REG_100H.WORD = ARG6[116];
                        TSIP.REG_100H.WORD = ARG6[117];
                        TSIP.REG_100H.WORD = ARG6[118];
                        TSIP.REG_100H.WORD = ARG6[119];
                        TSIP.REG_100H.WORD = ARG6[120];
                        TSIP.REG_100H.WORD = ARG6[121];
                        TSIP.REG_100H.WORD = ARG6[122];
                        TSIP.REG_100H.WORD = ARG6[123];
                        TSIP.REG_100H.WORD = ARG6[124];
                        TSIP.REG_100H.WORD = ARG6[125];
                        TSIP.REG_100H.WORD = ARG6[126];
                        TSIP.REG_100H.WORD = ARG6[127];
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x945d2158u);
                        RX671_func080();
                        RX671_func100(change_endian_long(0x4ce0c576u), change_endian_long(0x7ab2ea58u), change_endian_long(0xf0a0bc1du), change_endian_long(0xfc801b0au));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000024u;
                        RX671_func313(0);
                        RX671_func100(change_endian_long(0xe3bf0533u), change_endian_long(0x34ca07cbu), change_endian_long(0xc36ee158u), change_endian_long(0xaec1a748u));
                        RX671_func314(0+64);
                        TSIP.REG_ECH.WORD = 0x0000b400u;
                        TSIP.REG_ECH.WORD = 0x000000c1u;
                        RX671_func101(change_endian_long(0x8b5708cfu), change_endian_long(0x659d4e28u), change_endian_long(0x50b80dc5u), change_endian_long(0x089d1b1cu));
                        RX671_func307();
                        TSIP.REG_104H.WORD = 0x00003f57u;
                        TSIP.REG_2CH.WORD = 0x00000014u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x0001ffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_24H.WORD = 0x000019c0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_24H.WORD = 0x00001191u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00210000u;
                        TSIP.REG_24H.WORD = 0x000011c0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_24H.WORD = 0x00001991u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00210000u;
                        TSIP.REG_104H.WORD = 0x00003757u;
                        TSIP.REG_2CH.WORD = 0x00000014u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0xffffffffu);
                        TSIP.REG_100H.WORD = change_endian_long(0x00303130u);
                        TSIP.REG_100H.WORD = change_endian_long(0x0d060960u);
                        TSIP.REG_100H.WORD = change_endian_long(0x86480165u);
                        TSIP.REG_100H.WORD = change_endian_long(0x03040201u);
                        TSIP.REG_100H.WORD = change_endian_long(0x05000420u);
                        TSIP.REG_00H.WORD = 0x00003523u;
                        TSIP.REG_74H.WORD = 0x00000008u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_00H.BIT.B25)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00001800u;
                        TSIP.REG_24H.WORD = 0x000019c0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_24H.WORD = 0x00000991u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00210000u;
                        TSIP.REG_24H.WORD = 0x000009c0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_24H.WORD = 0x00001991u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_1CH.WORD = 0x00210000u;
                        TSIP.REG_ECH.WORD = 0x000036e5u;
                        TSIP.REG_ECH.WORD = 0x00003706u;
                        TSIP.REG_ECH.WORD = 0x00003727u;
                        TSIP.REG_ECH.WORD = 0x00003748u;
                        RX671_func101(change_endian_long(0x73767f12u), change_endian_long(0xd6c7e9d9u), change_endian_long(0x4f5f2f74u), change_endian_long(0xd20c0862u));
                    }
                    else if (0x02000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                    {
                        TSIP.REG_28H.WORD = 0x00870001u;
                        TSIP.REG_34H.WORD = 0x00000400u;
                        TSIP.REG_24H.WORD = 0x8000a8d0u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_24H.BIT.B21)
                        {
                            /* waiting */
                        }
                        TSIP.REG_ECH.WORD = 0x00000b9cu;
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x800103a0u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x000000c1u);
                        RX671_func101(change_endian_long(0x941b7bc7u), change_endian_long(0x4dbf7e71u), change_endian_long(0x16c72f7bu), change_endian_long(0xf0f9d93bu));
                        RX671_func003(ARG6);
                        RX671_func101(change_endian_long(0x5ef7c379u), change_endian_long(0x59f65cd4u), change_endian_long(0xcd0a5efbu), change_endian_long(0xbd673ecau));
                    }
                    else if (0x03000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                    {
                        TSIP.REG_28H.WORD = 0x00bf0001u;
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
                        TSIP.REG_ECH.WORD = 0x000000c1u;
                        TSIP.REG_ECH.WORD = 0x0000b440u;
                        TSIP.REG_ECH.WORD = 0x00000020u;
                        RX671_func101(change_endian_long(0x8a9d8d9cu), change_endian_long(0x4003acc6u), change_endian_long(0x26381138u), change_endian_long(0xf0a8e848u));
                        RX671_func015();
                        RX671_func101(change_endian_long(0x235f17b1u), change_endian_long(0x28a39b9du), change_endian_long(0xecd6806au), change_endian_long(0x1bfd1edeu));
                    }
                    RX671_func100(change_endian_long(0xd0a00214u), change_endian_long(0x22beb786u), change_endian_long(0x8c3ff737u), change_endian_long(0xe96f5140u));
                    TSIP.REG_1CH.WORD = 0x00400000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (1u == (TSIP.REG_1CH.BIT.B22))
                    {
                        TSIP.REG_ECH.WORD = 0x0000b400u;
                        TSIP.REG_ECH.WORD = 0xffffffffu;
                        RX671_func101(change_endian_long(0x736d7fe8u), change_endian_long(0x4d483a76u), change_endian_long(0x6f4a98c6u), change_endian_long(0x236209d3u));
                    }
                    else
                    {
                        TSIP.REG_ECH.WORD = 0x380089e0u;
                        TSIP.REG_ECH.WORD = 0x00000005u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        RX671_func100(change_endian_long(0x3e6fab2fu), change_endian_long(0x9c691434u), change_endian_long(0x3be9d863u), change_endian_long(0x06e5992cu));
                        TSIP.REG_1CH.WORD = 0x00400000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (1u == (TSIP.REG_1CH.BIT.B22))
                        {
                            TSIP.REG_ECH.WORD = 0x00000800u;
                            RX671_func101(change_endian_long(0xfe913df1u), change_endian_long(0xe3dd828fu), change_endian_long(0x2c7af8f3u), change_endian_long(0xf848ed4du));
                        }
                        else
                        {
                            RX671_func100(change_endian_long(0xf5fc9454u), change_endian_long(0x69acc5b2u), change_endian_long(0xe4379602u), change_endian_long(0x18f79056u));
                            TSIP.REG_ECH.WORD = 0x00007c0du;
                            TSIP.REG_1CH.WORD = 0x00600000u;
                            TSIP.REG_1D0H.WORD = 0x00000000u;
                            if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                            {
                                TSIP.REG_28H.WORD = 0x00bf0001u;
                                TSIP.REG_ECH.WORD = 0x38000defu;
                                TSIP.REG_E0H.WORD = 0x00000080u;
                                TSIP.REG_1CH.WORD = 0x00260000u;
                                TSIP.REG_ECH.WORD = 0x380089e0u;
                                TSIP.REG_ECH.WORD = 0x00000003u;
                                TSIP.REG_E0H.WORD = 0x00000080u;
                                TSIP.REG_1CH.WORD = 0x00260000u;
                                RX671_func100(change_endian_long(0x74ffb8feu), change_endian_long(0x5c521118u), change_endian_long(0xa3c0ce4eu), change_endian_long(0x07e22b86u));
                                TSIP.REG_1CH.WORD = 0x00400000u;
                                TSIP.REG_1D0H.WORD = 0x00000000u;
                                if (1u == (TSIP.REG_1CH.BIT.B22))
                                {
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
                                    TSIP.REG_100H.WORD = change_endian_long(0x05880100u);
                                    TSIP.REG_ECH.WORD = 0x00001009u;
                                    RX671_func101(change_endian_long(0x77636b43u), change_endian_long(0x8de88a54u), change_endian_long(0xfc998200u), change_endian_long(0x699db34fu));
                                }
                                else
                                {
                                    RX671_func100(change_endian_long(0xe88d902bu), change_endian_long(0xd4ab818eu), change_endian_long(0x028cd18eu), change_endian_long(0x3dd52943u));
                                    TSIP.REG_C4H.WORD = 0x000c0805u;
                                    TSIP.REG_E0H.WORD = 0x810402e0u;
                                    TSIP.REG_00H.WORD = 0x00002813u;
                                    /* WAIT_LOOP */
                                    while (0u != TSIP.REG_00H.BIT.B25)
                                    {
                                        /* waiting */
                                    }
                                    TSIP.REG_1CH.WORD = 0x00001800u;
                                    RX671_func100(change_endian_long(0x87857a00u), change_endian_long(0x1c4b3ee2u), change_endian_long(0x532b1c53u), change_endian_long(0xdf56ac96u));
                                    TSIP.REG_ECH.WORD = 0x0000342bu;
                                    RX671_func080();
                                    RX671_func100(change_endian_long(0xee08c6d8u), change_endian_long(0xc775d96au), change_endian_long(0xbf0f0693u), change_endian_long(0xe520634bu));
                                    TSIP.REG_00H.WORD = 0x00013203u;
                                    TSIP.REG_2CH.WORD = 0x00000014u;
                                    RX671_func312(1496);
                                    TSIP.REG_ECH.WORD = 0x0000342cu;
                                    RX671_func080();
                                    TSIP.REG_00H.WORD = 0x00013203u;
                                    TSIP.REG_2CH.WORD = 0x00000012u;
                                    RX671_func312(1496+68);
                                    TSIP.REG_104H.WORD = 0x00000058u;
                                    TSIP.REG_E0H.WORD = 0x80010000u;
                                    /* WAIT_LOOP */
                                    while (1u != TSIP.REG_104H.BIT.B31)
                                    {
                                        /* waiting */
                                    }
                                    TSIP.REG_100H.WORD = change_endian_long(0x0a880100u);
                                    TSIP.REG_ECH.WORD = 0x00001009u;
                                    RX671_func101(change_endian_long(0xeb055eccu), change_endian_long(0xc33618f4u), change_endian_long(0xd25cf1afu), change_endian_long(0x7b630539u));
                                }
                                RX671_func100(change_endian_long(0x3f2aa926u), change_endian_long(0xe6485938u), change_endian_long(0x744ea229u), change_endian_long(0xf8f3eedcu));
                                RX671_func103();
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
                                RX671_func100(change_endian_long(0x5ae6098eu), change_endian_long(0x7915f339u), change_endian_long(0x7abb8f5bu), change_endian_long(0xe882ece6u));
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
                                RX671_func100(change_endian_long(0xb75c5be1u), change_endian_long(0x4c5193c3u), change_endian_long(0x5f3ba53fu), change_endian_long(0x99c2be3du));
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
                                RX671_func100(change_endian_long(0xfc1f6c58u), change_endian_long(0x8a66f3deu), change_endian_long(0xccc1a674u), change_endian_long(0x60e0c2aau));
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
                                RX671_func100(change_endian_long(0xd3dd7abcu), change_endian_long(0xbf34a5c9u), change_endian_long(0x7a9bf93au), change_endian_long(0x7ba0bd81u));
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
                                RX671_func100(change_endian_long(0xb745cb55u), change_endian_long(0xcd573e47u), change_endian_long(0xb11009eau), change_endian_long(0x4a2f13efu));
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
                                RX671_func101(change_endian_long(0x8b3bf8f3u), change_endian_long(0x425b0fdeu), change_endian_long(0xf0314084u), change_endian_long(0x2e74db24u));
                            }
                            else
                            {
                                TSIP.REG_28H.WORD = 0x00870001u;
                                TSIP.REG_ECH.WORD = 0x00000b9cu;
                                RX671_func004(ARG8);
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
                                RX671_func008();
                                RX671_func100(change_endian_long(0xa05154ceu), change_endian_long(0x32a76e8du), change_endian_long(0xa8156bfcu), change_endian_long(0x7ccfd9fau));
                                TSIP.REG_1CH.WORD = 0x00400000u;
                                TSIP.REG_1D0H.WORD = 0x00000000u;
                                if (1u == (TSIP.REG_1CH.BIT.B22))
                                {
                                    TSIP.REG_ECH.WORD = 0x0000b400u;
                                    TSIP.REG_ECH.WORD = 0xffffffffu;
                                    RX671_func101(change_endian_long(0x5e1d148bu), change_endian_long(0x27323eccu), change_endian_long(0xc04f0f16u), change_endian_long(0x848507ceu));
                                }
                                else
                                {
                                    RX671_func100(change_endian_long(0xda23dae3u), change_endian_long(0xba97424du), change_endian_long(0x89338a97u), change_endian_long(0x37a77a7bu));
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
                                    TSIP.REG_ECH.WORD = 0x00001009u;
                                    RX671_func103();
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
                                    RX671_func100(change_endian_long(0x523a3086u), change_endian_long(0xf88869b3u), change_endian_long(0xad291985u), change_endian_long(0x3d6209cdu));
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
                                    RX671_func100(change_endian_long(0x11704644u), change_endian_long(0xb4899dbdu), change_endian_long(0x02c002b2u), change_endian_long(0x8d643a92u));
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
                                    RX671_func100(change_endian_long(0xab15fa70u), change_endian_long(0xd78b4e5fu), change_endian_long(0xf284b219u), change_endian_long(0x41c37e1bu));
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
                                    RX671_func101(change_endian_long(0xe02dec20u), change_endian_long(0xfeda877au), change_endian_long(0x6eaae8e0u), change_endian_long(0xb333a708u));
                                }
                            }
                        }
                    }
                }
            }
        }
    }
    TSIP.REG_ECH.WORD = 0x00007c15u;
    TSIP.REG_1CH.WORD = 0x00602000u;
}
/**********************************************************************************************************************
 End of function ./input_dir/RX671/RX671_func403.prc
 *********************************************************************************************************************/
