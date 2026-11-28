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
* Function Name: RX72M_RX72N_RX66N_func403
*******************************************************************************************************************/ /**
* @details       RX72M func403
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
void RX72M_RX72N_RX66N_func403(uint32_t *ARG1, uint32_t *ARG2, uint32_t *ARG3, uint32_t *ARG4, uint32_t *ARG5, uint32_t *ARG6, uint32_t *ARG7, const uint32_t *ARG8, uint32_t *ARG9)
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
    RX72M_RX72N_RX66N_func100(change_endian_long(0xccced9dfu), change_endian_long(0x9eb12f37u), change_endian_long(0x054500fdu), change_endian_long(0x1450ac84u));
    TSIP.REG_1CH.WORD = 0x00400000u;
    TSIP.REG_1D0H.WORD = 0x00000000u;
    if (1u == (TSIP.REG_1CH.BIT.B22))
    {
        TSIP.REG_ECH.WORD = 0x0000b400u;
        TSIP.REG_ECH.WORD = 0xffffffffu;
        RX72M_RX72N_RX66N_func101(change_endian_long(0xa64a24c1u), change_endian_long(0x8c07482bu), change_endian_long(0x91a24cc5u), change_endian_long(0xa0f4fd9bu));
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
        RX72M_RX72N_RX66N_func100(change_endian_long(0xbf00d357u), change_endian_long(0xefb9c5e5u), change_endian_long(0x36ffa3acu), change_endian_long(0x9aef88e2u));
        TSIP.REG_1CH.WORD = 0x00400000u;
        TSIP.REG_1D0H.WORD = 0x00000000u;
        if (1u == (TSIP.REG_1CH.BIT.B22))
        {
            RX72M_RX72N_RX66N_func100(change_endian_long(0x87fe948au), change_endian_long(0x25889cc9u), change_endian_long(0x2487c89cu), change_endian_long(0x0c784ffeu));
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
                RX72M_RX72N_RX66N_func100(change_endian_long(0x9dcac40du), change_endian_long(0x6eb3a2adu), change_endian_long(0x8595c911u), change_endian_long(0xefcdbb86u));
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
                    RX72M_RX72N_RX66N_func101(change_endian_long(0x0917f90fu), change_endian_long(0x19e7227au), change_endian_long(0xfb614021u), change_endian_long(0x5b9efd32u));
                }
                else
                {
                    TSIP.REG_ECH.WORD = 0x00003417u;
                    TSIP.REG_ECH.WORD = 0x0000a400u;
                    TSIP.REG_ECH.WORD = 0x000001ffu;
                    TSIP.REG_ECH.WORD = 0x08002818u;
                    TSIP.REG_E0H.WORD = 0x00000080u;
                    TSIP.REG_1CH.WORD = 0x00A60000u;
                    RX72M_RX72N_RX66N_func101(change_endian_long(0xe00f2e2fu), change_endian_long(0xac08472eu), change_endian_long(0xe7886111u), change_endian_long(0x5f114bb6u));
                }
                TSIP.REG_ECH.WORD = 0x00003419u;
                TSIP.REG_ECH.WORD = 0x0000a400u;
                TSIP.REG_ECH.WORD = 0x00000003u;
                TSIP.REG_ECH.WORD = 0x0c00281au;
                TSIP.REG_E0H.WORD = 0x00000080u;
                TSIP.REG_1CH.WORD = 0x00A60000u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0x726750b8u), change_endian_long(0x3fcc1e0bu), change_endian_long(0x20726791u), change_endian_long(0xb7c77bcdu));
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
                RX72M_RX72N_RX66N_func101(change_endian_long(0x138f1549u), change_endian_long(0x9b659dceu), change_endian_long(0x1080870cu), change_endian_long(0xecd38f86u));
            }
            RX72M_RX72N_RX66N_func101(change_endian_long(0xd93f8974u), change_endian_long(0x711b2dfdu), change_endian_long(0x00380894u), change_endian_long(0xb7fe5d3du));
        }
        else
        {
            RX72M_RX72N_RX66N_func101(change_endian_long(0x33c9c77bu), change_endian_long(0xec4dedfdu), change_endian_long(0xd49ed34eu), change_endian_long(0x98b2bda2u));
        }
        RX72M_RX72N_RX66N_func100(change_endian_long(0xb59a5aa0u), change_endian_long(0x7e31ac67u), change_endian_long(0xd1cf737bu), change_endian_long(0x678b5197u));
        TSIP.REG_1CH.WORD = 0x00400000u;
        TSIP.REG_1D0H.WORD = 0x00000000u;
        if (1u == (TSIP.REG_1CH.BIT.B22))
        {
            TSIP.REG_ECH.WORD = 0x0000b400u;
            TSIP.REG_ECH.WORD = 0xffffffffu;
            RX72M_RX72N_RX66N_func101(change_endian_long(0xf4aa0fc8u), change_endian_long(0xabe6fcd4u), change_endian_long(0x50c3deb6u), change_endian_long(0xe177ba32u));
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
            RX72M_RX72N_RX66N_func100(change_endian_long(0x32e3d645u), change_endian_long(0xe507cd29u), change_endian_long(0xaa31e719u), change_endian_long(0xd64899dcu));
            TSIP.REG_1CH.WORD = 0x00400000u;
            TSIP.REG_1D0H.WORD = 0x00000000u;
            if (1u == (TSIP.REG_1CH.BIT.B22))
            {
                TSIP.REG_ECH.WORD = 0x0000b400u;
                TSIP.REG_ECH.WORD = 0xffffffffu;
                RX72M_RX72N_RX66N_func101(change_endian_long(0x5e664747u), change_endian_long(0x66c032b1u), change_endian_long(0x338a2c97u), change_endian_long(0x0d7fd359u));
            }
            else
            {
                RX72M_RX72N_RX66N_func100(change_endian_long(0x300db02au), change_endian_long(0x6be56f55u), change_endian_long(0xff95a6e6u), change_endian_long(0x2b95de8cu));
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
                    RX72M_RX72N_RX66N_func101(change_endian_long(0xfd7e0bc0u), change_endian_long(0x303d2e1fu), change_endian_long(0x81b65448u), change_endian_long(0x505d5889u));
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
                    RX72M_RX72N_RX66N_func101(change_endian_long(0x248f4e6au), change_endian_long(0x6af498b3u), change_endian_long(0xda072fa8u), change_endian_long(0xff0f063eu));
                }
                RX72M_RX72N_RX66N_func100(change_endian_long(0x5cd6a6a7u), change_endian_long(0x56f05c8fu), change_endian_long(0x4f6a817cu), change_endian_long(0xb769bbcdu));
                TSIP.REG_1CH.WORD = 0x00400000u;
                TSIP.REG_1D0H.WORD = 0x00000000u;
                if (1u == (TSIP.REG_1CH.BIT.B22))
                {
                    TSIP.REG_ECH.WORD = 0x0000b400u;
                    TSIP.REG_ECH.WORD = 0xffffffffu;
                    RX72M_RX72N_RX66N_func101(change_endian_long(0xcfcf96cfu), change_endian_long(0x2e4a5352u), change_endian_long(0x70f967dbu), change_endian_long(0xc4b9ce17u));
                }
                else
                {
                    TSIP.REG_ECH.WORD = 0x380089e0u;
                    TSIP.REG_ECH.WORD = 0x00000005u;
                    TSIP.REG_E0H.WORD = 0x00000080u;
                    TSIP.REG_1CH.WORD = 0x00A60000u;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x04bb2edeu), change_endian_long(0xdaf5e045u), change_endian_long(0x76e7f93eu), change_endian_long(0x7f877842u));
                    TSIP.REG_1CH.WORD = 0x00400000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (1u == (TSIP.REG_1CH.BIT.B22))
                    {
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x8dafbb9cu), change_endian_long(0x2aa0f412u), change_endian_long(0x2873b577u), change_endian_long(0x34ae27a8u));
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
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x91cbffc3u), change_endian_long(0xe5218947u), change_endian_long(0xd7dd3d80u), change_endian_long(0x7137852bu));
                        }
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x6eed6338u), change_endian_long(0x332588c9u), change_endian_long(0xf636c2a2u), change_endian_long(0x7c347bdbu));
                        TSIP.REG_ECH.WORD = 0x38000805u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        TSIP.REG_1CH.WORD = 0x00402000u;
                        TSIP.REG_ECH.WORD = 0x00007c0du;
                        TSIP.REG_1CH.WORD = 0x00600000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                        {
                            RX72M_RX72N_RX66N_func100(change_endian_long(0x8be8c367u), change_endian_long(0xd99e200au), change_endian_long(0x9109e8b9u), change_endian_long(0xf932b4d0u));
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
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0x48b58647u), change_endian_long(0xe1d597c9u), change_endian_long(0x6e3a8e75u), change_endian_long(0x1e1a3004u));
                                    TSIP.REG_1CH.WORD = 0x00400000u;
                                    TSIP.REG_1D0H.WORD = 0x00000000u;
                                    if (1u == (TSIP.REG_1CH.BIT.B22))
                                    {
                                        TSIP.REG_ECH.WORD = 0x3420aa60u;
                                        TSIP.REG_ECH.WORD = 0x00000100u;
                                        TSIP.REG_E0H.WORD = 0x00000080u;
                                        TSIP.REG_1CH.WORD = 0x00260000u;
                                        RX72M_RX72N_RX66N_func100(change_endian_long(0x18ffb655u), change_endian_long(0x4310e385u), change_endian_long(0x94f3a968u), change_endian_long(0x59743e1eu));
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
                                            RX72M_RX72N_RX66N_func101(change_endian_long(0x395b641cu), change_endian_long(0x87c97497u), change_endian_long(0xb1495d06u), change_endian_long(0x2a4b6137u));
                                        }
                                        else
                                        {
                                            TSIP.REG_ECH.WORD = 0x02003cf2u;
                                            TSIP.REG_ECH.WORD = 0x0000a640u;
                                            TSIP.REG_ECH.WORD = 0x00000001u;
                                            RX72M_RX72N_RX66N_func101(change_endian_long(0x5801c364u), change_endian_long(0x5b7b109eu), change_endian_long(0x097b8422u), change_endian_long(0x18a7c5d3u));
                                        }
                                        RX72M_RX72N_RX66N_func101(change_endian_long(0x2430b6ffu), change_endian_long(0xa19189e3u), change_endian_long(0x82f284f7u), change_endian_long(0xd6a1ec46u));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00000863u;
                                    TSIP.REG_ECH.WORD = 0x3c0028c2u;
                                    TSIP.REG_ECH.WORD = 0x20002c60u;
                                    TSIP.REG_ECH.WORD = 0x38000c63u;
                                    TSIP.REG_E0H.WORD = 0x00000080u;
                                    TSIP.REG_1CH.WORD = 0x00260000u;
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0x5c06357cu), change_endian_long(0x408ccb1au), change_endian_long(0xbad04cd6u), change_endian_long(0xd26b0764u));
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
                                        RX72M_RX72N_RX66N_func101(change_endian_long(0xe65d8496u), change_endian_long(0x43b3e653u), change_endian_long(0xab448c40u), change_endian_long(0xf3542b51u));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00002c40u;
                                    RX72M_RX72N_RX66N_func101(change_endian_long(0x504f5af2u), change_endian_long(0x9cd57ee7u), change_endian_long(0xfa8e505eu), change_endian_long(0xf3f419fbu));
                                }
                                TSIP.REG_ECH.WORD = 0x08000c21u;
                                TSIP.REG_E0H.WORD = 0x00000080u;
                                TSIP.REG_1CH.WORD = 0x00260000u;
                                TSIP.REG_1CH.WORD = 0x00402000u;
                                TSIP.REG_ECH.WORD = 0x00002ca0u;
                                RX72M_RX72N_RX66N_func101(change_endian_long(0x86f805f5u), change_endian_long(0x22c28171u), change_endian_long(0x24a335fau), change_endian_long(0x66d12fd9u));
                            }
                            TSIP.REG_ECH.WORD = 0x38000805u;
                            TSIP.REG_E0H.WORD = 0x00000080u;
                            TSIP.REG_1CH.WORD = 0x00260000u;
                            TSIP.REG_1CH.WORD = 0x00402000u;
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x1923bcc2u), change_endian_long(0x7348e1e3u), change_endian_long(0x955cc061u), change_endian_long(0xd73a6775u));
                        }
                        else
                        {
                            RX72M_RX72N_RX66N_func100(change_endian_long(0x0b441495u), change_endian_long(0x7e763864u), change_endian_long(0x554d1f45u), change_endian_long(0xb73a75c3u));
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
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0x292c7a8bu), change_endian_long(0x081043b1u), change_endian_long(0xe39fa2bdu), change_endian_long(0x1fa737c3u));
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
                                        RX72M_RX72N_RX66N_func101(change_endian_long(0xaa9d3874u), change_endian_long(0xadc42854u), change_endian_long(0x2526934du), change_endian_long(0x39df854au));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00000863u;
                                    TSIP.REG_ECH.WORD = 0x3c002857u;
                                    TSIP.REG_ECH.WORD = 0x20002c60u;
                                    TSIP.REG_ECH.WORD = 0x3c002b02u;
                                    TSIP.REG_ECH.WORD = 0x20002c60u;
                                    TSIP.REG_ECH.WORD = 0x38000c63u;
                                    TSIP.REG_E0H.WORD = 0x00000080u;
                                    TSIP.REG_1CH.WORD = 0x00260000u;
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0x7c3c25e4u), change_endian_long(0x213a842au), change_endian_long(0x4a7da38fu), change_endian_long(0xa31c2bf3u));
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
                                        RX72M_RX72N_RX66N_func101(change_endian_long(0xf8c9d37bu), change_endian_long(0xcbad8bcau), change_endian_long(0xcd3a267eu), change_endian_long(0x297a7cd0u));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00000863u;
                                    TSIP.REG_ECH.WORD = 0x3c0028c2u;
                                    TSIP.REG_ECH.WORD = 0x20002c60u;
                                    TSIP.REG_ECH.WORD = 0x38000c63u;
                                    TSIP.REG_E0H.WORD = 0x00000080u;
                                    TSIP.REG_1CH.WORD = 0x00260000u;
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0x7749af36u), change_endian_long(0x4d190406u), change_endian_long(0xcdff61e6u), change_endian_long(0x77e5bde5u));
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
                                        RX72M_RX72N_RX66N_func101(change_endian_long(0x00157c62u), change_endian_long(0xacf00a7fu), change_endian_long(0x99fb9761u), change_endian_long(0x9397a44eu));
                                    }
                                    TSIP.REG_ECH.WORD = 0x00002c40u;
                                    RX72M_RX72N_RX66N_func101(change_endian_long(0x7bd2c3c8u), change_endian_long(0xdb021b44u), change_endian_long(0x54b5abf3u), change_endian_long(0xda9cfb0cu));
                                }
                                TSIP.REG_ECH.WORD = 0x08000c21u;
                                TSIP.REG_E0H.WORD = 0x00000080u;
                                TSIP.REG_1CH.WORD = 0x00260000u;
                                TSIP.REG_1CH.WORD = 0x00402000u;
                                TSIP.REG_ECH.WORD = 0x00002ca0u;
                                RX72M_RX72N_RX66N_func101(change_endian_long(0xbd103565u), change_endian_long(0x96e31a16u), change_endian_long(0xa6b5e16du), change_endian_long(0x9430deffu));
                            }
                            TSIP.REG_ECH.WORD = 0x38000805u;
                            TSIP.REG_E0H.WORD = 0x00000080u;
                            TSIP.REG_1CH.WORD = 0x00260000u;
                            TSIP.REG_1CH.WORD = 0x00402000u;
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x341b71beu), change_endian_long(0x8c6b5e65u), change_endian_long(0x70c52334u), change_endian_long(0xedb7d7e4u));
                        }
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x3e51838au), change_endian_long(0x299e6602u), change_endian_long(0xe7220c43u), change_endian_long(0x7a98e086u));
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
                        RX72M_RX72N_RX66N_func100(change_endian_long(0xd0945c7bu), change_endian_long(0xc2dd3bcfu), change_endian_long(0xeffd4f8eu), change_endian_long(0xb85a622fu));
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
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x3af3e4aeu), change_endian_long(0x09fa78abu), change_endian_long(0x45f37ff4u), change_endian_long(0x8fc5fcb5u));
                        }
                        TSIP.REG_ECH.WORD = 0x38000805u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        TSIP.REG_1CH.WORD = 0x00402000u;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x96bf685au), change_endian_long(0x3aaabd24u), change_endian_long(0xa84a6b9fu), change_endian_long(0xa81e093cu));
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
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x372b97e6u), change_endian_long(0x3669a192u), change_endian_long(0xa968eb8au), change_endian_long(0x1d034a91u));
                        }
                        TSIP.REG_ECH.WORD = 0x38000805u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        TSIP.REG_1CH.WORD = 0x00402000u;
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x144be482u), change_endian_long(0xbb32f325u), change_endian_long(0xdf8af87eu), change_endian_long(0x3a2a9779u));
                    }
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x66e4aa8du), change_endian_long(0xa9b6aba6u), change_endian_long(0x65d51b8au), change_endian_long(0x9dc5e96du));
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
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x7c57c3ecu), change_endian_long(0xe376df33u), change_endian_long(0xb5f62452u), change_endian_long(0x0b6458b3u));
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
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xc91aae58u), change_endian_long(0xe93a19d9u), change_endian_long(0xe60200eeu), change_endian_long(0x3fd048dbu));
                    RX72M_RX72N_RX66N_func103();
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xb753b116u), change_endian_long(0x3548d643u), change_endian_long(0x0b82b4a4u), change_endian_long(0x7b269975u));
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
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x40036eb0u), change_endian_long(0xb3bd3617u), change_endian_long(0x36bc8569u), change_endian_long(0x1d839a81u));
                    TSIP.REG_1CH.WORD = 0x00400000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (1u == (TSIP.REG_1CH.BIT.B22))
                    {
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x50584aadu), change_endian_long(0xb012a232u), change_endian_long(0xf72d3adeu), change_endian_long(0x124aaaccu));
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
                            RX72M_RX72N_RX66N_func100(change_endian_long(0x61e81770u), change_endian_long(0x0f000eb5u), change_endian_long(0x7b3e02e1u), change_endian_long(0x422ee317u));
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
                                RX72M_RX72N_RX66N_func101(change_endian_long(0x7d70fde9u), change_endian_long(0x2568614eu), change_endian_long(0x0aeb685du), change_endian_long(0xadd39140u));
                            }
                            else
                            {
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x273e96aau), change_endian_long(0x60e28b51u), change_endian_long(0x77118d81u), change_endian_long(0x28ea1837u));
                                TSIP.REG_ECH.WORD = 0x0000342bu;
                                RX72M_RX72N_RX66N_func080();
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x84b3dfaau), change_endian_long(0xb12d6e9au), change_endian_long(0x077cc064u), change_endian_long(0x6662bcadu));
                                TSIP.REG_00H.WORD = 0x00012303u;
                                TSIP.REG_2CH.WORD = 0x00000020u;
                                RX72M_RX72N_RX66N_func313(1496);
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x060422edu), change_endian_long(0x17ff43adu), change_endian_long(0x7658b396u), change_endian_long(0xa7d2694fu));
                                RX72M_RX72N_RX66N_func314(1496+64);
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x81c42738u), change_endian_long(0xab379337u), change_endian_long(0xaac5ea7bu), change_endian_long(0xdedaf76bu));
                                TSIP.REG_ECH.WORD = 0x0000342cu;
                                RX72M_RX72N_RX66N_func080();
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x207da201u), change_endian_long(0xca7a5857u), change_endian_long(0x85e36e3au), change_endian_long(0x9193ee6du));
                                TSIP.REG_ECH.WORD = 0x00000800u;
                                TSIP.REG_E0H.WORD = 0x81c00000u;
                                TSIP.REG_00H.WORD = 0x00012803u;
                                RX72M_RX72N_RX66N_func313(1496+68);
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x7eb38bddu), change_endian_long(0x87637371u), change_endian_long(0x589e4f56u), change_endian_long(0x5ad9c023u));
                                RX72M_RX72N_RX66N_func314(1496+132);
                                RX72M_RX72N_RX66N_func101(change_endian_long(0xa6931b92u), change_endian_long(0x21115dfbu), change_endian_long(0xd0b4d43eu), change_endian_long(0x335cd529u));
                            }
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x5e5245b0u), change_endian_long(0x45bd57c4u), change_endian_long(0x50f19464u), change_endian_long(0xc209d296u));
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
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x311f8708u), change_endian_long(0xe958b43du), change_endian_long(0x9bba65efu), change_endian_long(0xdc70ebfdu));
                        }
                        RX72M_RX72N_RX66N_func101(change_endian_long(0xfc08502au), change_endian_long(0x7cb1f986u), change_endian_long(0xe23318b9u), change_endian_long(0x95170163u));
                    }
                    else
                    {
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x94e35d0cu), change_endian_long(0xe1a9641bu), change_endian_long(0x7357fc84u), change_endian_long(0x0e602b73u));
                    }
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x7ab17609u), change_endian_long(0x37674197u), change_endian_long(0x0fee52bdu), change_endian_long(0x1beafde1u));
                    TSIP.REG_ECH.WORD = 0x00007c0eu;
                    TSIP.REG_1CH.WORD = 0x00600000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                    {
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x9a849708u), change_endian_long(0x43179362u), change_endian_long(0xae96dffdu), change_endian_long(0x804cb347u));
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
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x02d4bb22u), change_endian_long(0x49e14877u), change_endian_long(0xa1ae7b50u), change_endian_long(0xaaba8640u));
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
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x428f54deu), change_endian_long(0x543703e9u), change_endian_long(0x2ba61f13u), change_endian_long(0xe04d4ca5u));
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x5fe685f6u);
                        RX72M_RX72N_RX66N_func080();
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x0ddb7ff8u), change_endian_long(0xef3b424eu), change_endian_long(0x998ad1ddu), change_endian_long(0x14c4eec5u));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000020u;
                        RX72M_RX72N_RX66N_func313(748);
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x4763b568u), change_endian_long(0xb06bb285u), change_endian_long(0x09a6b922u), change_endian_long(0x5d086926u));
                        RX72M_RX72N_RX66N_func314(748+64);
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x54803cc4u), change_endian_long(0x72c31814u), change_endian_long(0xcae1668eu), change_endian_long(0x7c76e91eu));
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x1c5a2b81u);
                        RX72M_RX72N_RX66N_func080();
                        RX72M_RX72N_RX66N_func100(change_endian_long(0xb2373680u), change_endian_long(0x06335717u), change_endian_long(0xbbc7ba98u), change_endian_long(0x1b6f1322u));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000022u;
                        RX72M_RX72N_RX66N_func313(680);
                        RX72M_RX72N_RX66N_func100(change_endian_long(0xd6c7ebfau), change_endian_long(0x0b54a6cfu), change_endian_long(0xd26a17d8u), change_endian_long(0xdb64f6e9u));
                        RX72M_RX72N_RX66N_func314(680+64);
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x955abbf1u), change_endian_long(0x04cd9faeu), change_endian_long(0x4feb6ebau), change_endian_long(0x818bb136u));
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
                        RX72M_RX72N_RX66N_func080();
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x5deb05d6u), change_endian_long(0xf50c485fu), change_endian_long(0x344bb315u), change_endian_long(0x647228fcu));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000020u;
                        RX72M_RX72N_RX66N_func313(68);
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x08b85637u), change_endian_long(0x483fbd62u), change_endian_long(0xf80f62d5u), change_endian_long(0x5576c360u));
                        RX72M_RX72N_RX66N_func314(68+64);
                        RX72M_RX72N_RX66N_func100(change_endian_long(0xac35eefcu), change_endian_long(0x312c41eau), change_endian_long(0xfa7c9d5fu), change_endian_long(0xa4c1940au));
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
                        RX72M_RX72N_RX66N_func080();
                        RX72M_RX72N_RX66N_func100(change_endian_long(0x766019fau), change_endian_long(0x673a17a7u), change_endian_long(0x726f94b7u), change_endian_long(0xd7b0380du));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000024u;
                        RX72M_RX72N_RX66N_func313(0);
                        RX72M_RX72N_RX66N_func100(change_endian_long(0xc8721cb1u), change_endian_long(0x4505ad5au), change_endian_long(0xf61bbee2u), change_endian_long(0x36c6cf07u));
                        RX72M_RX72N_RX66N_func314(0+64);
                        TSIP.REG_ECH.WORD = 0x0000b400u;
                        TSIP.REG_ECH.WORD = 0x000000c1u;
                        RX72M_RX72N_RX66N_func101(change_endian_long(0xe83ad1ccu), change_endian_long(0xa66daf96u), change_endian_long(0xd059cd9du), change_endian_long(0x0a37efa6u));
                        RX72M_RX72N_RX66N_func307();
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
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x208cf546u), change_endian_long(0xaf90ab83u), change_endian_long(0xe165353fu), change_endian_long(0x2b391799u));
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
                        RX72M_RX72N_RX66N_func101(change_endian_long(0xd9b30d25u), change_endian_long(0x99accee9u), change_endian_long(0x3bf1a721u), change_endian_long(0xc4c7a914u));
                        RX72M_RX72N_RX66N_func003(ARG6);
                        RX72M_RX72N_RX66N_func101(change_endian_long(0xc9dba02au), change_endian_long(0x682079a2u), change_endian_long(0x441b62f5u), change_endian_long(0x8c755118u));
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
                        RX72M_RX72N_RX66N_func101(change_endian_long(0xcb2006d9u), change_endian_long(0x7cf26d7du), change_endian_long(0x56a98665u), change_endian_long(0x2bb2aae7u));
                        RX72M_RX72N_RX66N_func015();
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x1b0abcf9u), change_endian_long(0x5256b177u), change_endian_long(0x86447405u), change_endian_long(0x1fa4add3u));
                    }
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x05c51bddu), change_endian_long(0xa9066e20u), change_endian_long(0x78a6206du), change_endian_long(0x5cbc2b3fu));
                    TSIP.REG_1CH.WORD = 0x00400000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (1u == (TSIP.REG_1CH.BIT.B22))
                    {
                        TSIP.REG_ECH.WORD = 0x0000b400u;
                        TSIP.REG_ECH.WORD = 0xffffffffu;
                        RX72M_RX72N_RX66N_func101(change_endian_long(0x874caf00u), change_endian_long(0xa0fd5540u), change_endian_long(0x6dccbdbeu), change_endian_long(0xd146ff64u));
                    }
                    else
                    {
                        TSIP.REG_ECH.WORD = 0x380089e0u;
                        TSIP.REG_ECH.WORD = 0x00000005u;
                        TSIP.REG_E0H.WORD = 0x00000080u;
                        TSIP.REG_1CH.WORD = 0x00260000u;
                        RX72M_RX72N_RX66N_func100(change_endian_long(0xac44379cu), change_endian_long(0xa367fc1eu), change_endian_long(0xf8ef3d6bu), change_endian_long(0x5b09e919u));
                        TSIP.REG_1CH.WORD = 0x00400000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (1u == (TSIP.REG_1CH.BIT.B22))
                        {
                            TSIP.REG_ECH.WORD = 0x00000800u;
                            RX72M_RX72N_RX66N_func101(change_endian_long(0x73599ffcu), change_endian_long(0x230f6428u), change_endian_long(0x8ba9ef8bu), change_endian_long(0xe682701du));
                        }
                        else
                        {
                            RX72M_RX72N_RX66N_func100(change_endian_long(0xa2316124u), change_endian_long(0x6cd3052cu), change_endian_long(0xfb501151u), change_endian_long(0xf81dbc83u));
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
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x43d9717fu), change_endian_long(0xab494cecu), change_endian_long(0x5d54916du), change_endian_long(0xb321c044u));
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
                                    RX72M_RX72N_RX66N_func101(change_endian_long(0xcefcbbedu), change_endian_long(0x88f18c85u), change_endian_long(0x9bc6ef61u), change_endian_long(0xb77eba4eu));
                                }
                                else
                                {
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0xd569aa2bu), change_endian_long(0x955347efu), change_endian_long(0x7cccf6a2u), change_endian_long(0x10dee1b4u));
                                    TSIP.REG_C4H.WORD = 0x000c0805u;
                                    TSIP.REG_E0H.WORD = 0x810402e0u;
                                    TSIP.REG_00H.WORD = 0x00002813u;
                                    /* WAIT_LOOP */
                                    while (0u != TSIP.REG_00H.BIT.B25)
                                    {
                                        /* waiting */
                                    }
                                    TSIP.REG_1CH.WORD = 0x00001800u;
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0xacaa1cc1u), change_endian_long(0xd3de76e4u), change_endian_long(0xe1e0eba7u), change_endian_long(0x17f5e5d3u));
                                    TSIP.REG_ECH.WORD = 0x0000342bu;
                                    RX72M_RX72N_RX66N_func080();
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0x959381dcu), change_endian_long(0x159ac644u), change_endian_long(0xfe070820u), change_endian_long(0xf21c1b49u));
                                    TSIP.REG_00H.WORD = 0x00013203u;
                                    TSIP.REG_2CH.WORD = 0x00000014u;
                                    RX72M_RX72N_RX66N_func312(1496);
                                    TSIP.REG_ECH.WORD = 0x0000342cu;
                                    RX72M_RX72N_RX66N_func080();
                                    TSIP.REG_00H.WORD = 0x00013203u;
                                    TSIP.REG_2CH.WORD = 0x00000012u;
                                    RX72M_RX72N_RX66N_func312(1496+68);
                                    TSIP.REG_104H.WORD = 0x00000058u;
                                    TSIP.REG_E0H.WORD = 0x80010000u;
                                    /* WAIT_LOOP */
                                    while (1u != TSIP.REG_104H.BIT.B31)
                                    {
                                        /* waiting */
                                    }
                                    TSIP.REG_100H.WORD = change_endian_long(0x0a880100u);
                                    TSIP.REG_ECH.WORD = 0x00001009u;
                                    RX72M_RX72N_RX66N_func101(change_endian_long(0xc7f09822u), change_endian_long(0xd9bb96d6u), change_endian_long(0xa4f3b466u), change_endian_long(0xb430e291u));
                                }
                                RX72M_RX72N_RX66N_func100(change_endian_long(0xe5fba371u), change_endian_long(0xb26a590du), change_endian_long(0x465212e4u), change_endian_long(0x866a14deu));
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
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x31bd510bu), change_endian_long(0x7e34edc5u), change_endian_long(0xb60ace49u), change_endian_long(0x2812da97u));
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
                                RX72M_RX72N_RX66N_func100(change_endian_long(0xbfed1ff4u), change_endian_long(0x6806b185u), change_endian_long(0xb2382df7u), change_endian_long(0x7f36d0bfu));
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
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x31bebdd6u), change_endian_long(0xe494fdd8u), change_endian_long(0xf605f54eu), change_endian_long(0x1e086d8du));
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
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x43f62d87u), change_endian_long(0xd3c0f44eu), change_endian_long(0x427cb707u), change_endian_long(0x66cb6a20u));
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
                                RX72M_RX72N_RX66N_func100(change_endian_long(0xe95afd3cu), change_endian_long(0xb42252d2u), change_endian_long(0xe0f078bau), change_endian_long(0xffc52fc7u));
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
                                RX72M_RX72N_RX66N_func101(change_endian_long(0x9de7a840u), change_endian_long(0xd09aea49u), change_endian_long(0x52b7fcc0u), change_endian_long(0x47608c70u));
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
                                RX72M_RX72N_RX66N_func100(change_endian_long(0x7b633eeau), change_endian_long(0xe5c5533eu), change_endian_long(0xd796d20fu), change_endian_long(0x9b5d54cbu));
                                TSIP.REG_1CH.WORD = 0x00400000u;
                                TSIP.REG_1D0H.WORD = 0x00000000u;
                                if (1u == (TSIP.REG_1CH.BIT.B22))
                                {
                                    TSIP.REG_ECH.WORD = 0x0000b400u;
                                    TSIP.REG_ECH.WORD = 0xffffffffu;
                                    RX72M_RX72N_RX66N_func101(change_endian_long(0xff72a06fu), change_endian_long(0x081d621cu), change_endian_long(0xe20dad7eu), change_endian_long(0x4a2f8a1fu));
                                }
                                else
                                {
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0xf57c7830u), change_endian_long(0x9fc6d58bu), change_endian_long(0x6fb30611u), change_endian_long(0x2ee2e3e2u));
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
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0x171c8513u), change_endian_long(0x05d23580u), change_endian_long(0x48085e20u), change_endian_long(0x3dcf1094u));
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
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0x86e7a28du), change_endian_long(0xa2eaa74du), change_endian_long(0x5ec7a0bbu), change_endian_long(0xfed4cff1u));
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
                                    RX72M_RX72N_RX66N_func100(change_endian_long(0x62ed117eu), change_endian_long(0x9307131fu), change_endian_long(0xe96fb43eu), change_endian_long(0x30aa3286u));
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
                                    RX72M_RX72N_RX66N_func101(change_endian_long(0x781a902cu), change_endian_long(0xde7a6f86u), change_endian_long(0xbbae3349u), change_endian_long(0x7dd6b95cu));
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
 End of function ./input_dir/RX72M/RX72M_func403.prc
 *********************************************************************************************************************/
