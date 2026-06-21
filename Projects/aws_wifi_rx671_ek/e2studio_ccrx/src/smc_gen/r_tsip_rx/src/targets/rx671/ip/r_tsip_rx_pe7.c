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

#if TSIP_TLS == 1
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
* Function Name: R_TSIP_TlsServersEphemeralEcdhPublicKeyRetrievesSub
*******************************************************************************************************************/ /**
* @details       RX671 TLS Ephemeral Key Generation
* @param[in]     InData_Sel_PubKeyType
* @param[in]     InData_ClientRandom
* @param[in]     InData_ServerRandom
* @param[in]     InData_Sel_CompressType
* @param[in]     InData_SKE_Message
* @param[in]     InData_SKE_Signature
* @param[in]     InData_PubKey
* @param[in]     InData_DomainParam
* @param[out]    OutData_EphemeralPubKey
* @retval        TSIP_SUCCESS
* @retval        TSIP_ERR_FAIL
* @retval        TSIP_ERR_RESOURCE_CONFLICT
* @note          None
*/
e_tsip_err_t R_TSIP_TlsServersEphemeralEcdhPublicKeyRetrievesSub(uint32_t *InData_Sel_PubKeyType, uint32_t *InData_ClientRandom, uint32_t *InData_ServerRandom, uint32_t *InData_Sel_CompressType, uint32_t *InData_SKE_Message, uint32_t *InData_SKE_Signature, uint32_t *InData_PubKey, const uint32_t *InData_DomainParam, uint32_t *OutData_EphemeralPubKey)
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
    #if TSIP_MULTI_THREADING == 1
    TSIP_MULTI_THREADING_LOCK_FUNCTION();
    #endif /* TSIP_MULTI_THREADING == 1 */
    if (0x0u != (TSIP.REG_1B8H.WORD & 0x1eu))
    {
        #if TSIP_MULTI_THREADING == 1
        TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
        #endif /* TSIP_MULTI_THREADING == 1 */
        return TSIP_ERR_RESOURCE_CONFLICT;
    }
    TSIP.REG_84H.WORD = 0x0000e701u;
    TSIP.REG_108H.WORD = 0x00000000u;
    TSIP.REG_C4H.WORD = 0x200e1a0du;
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = S_RAM[16+0 + 0];
    TSIP.REG_100H.WORD = S_RAM[16+0 + 1];
    TSIP.REG_100H.WORD = S_RAM[16+0 + 2];
    TSIP.REG_100H.WORD = S_RAM[16+0 + 3];
    TSIP.REG_104H.WORD = 0x00000068u;
    TSIP.REG_E0H.WORD = 0x800101c0u;
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = InData_Sel_PubKeyType[0];
    TSIP.REG_ECH.WORD = 0x3420a9c0u;
    TSIP.REG_ECH.WORD = 0x00000004u;
    TSIP.REG_E0H.WORD = 0x00000080u;
    TSIP.REG_1CH.WORD = 0x00A60000u;
    RX671_func100(change_endian_long(0x3de091e7u), change_endian_long(0xa2efb3f3u), change_endian_long(0x466a8ebeu), change_endian_long(0x33b9c522u));
    TSIP.REG_1CH.WORD = 0x00400000u;
    TSIP.REG_1D0H.WORD = 0x00000000u;
    if (1u == (TSIP.REG_1CH.BIT.B22))
    {
        RX671_func102(change_endian_long(0x316847eeu), change_endian_long(0xea932591u), change_endian_long(0xe037a933u), change_endian_long(0x0e501c0cu));
        TSIP.REG_1B8H.WORD = 0x00000040u;
        /* WAIT_LOOP */
        while (0u != TSIP.REG_18H.BIT.B12)
        {
            /* waiting */
        }
        #if TSIP_MULTI_THREADING == 1
        TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
        #endif /* TSIP_MULTI_THREADING == 1 */
        return TSIP_ERR_FAIL;
    }
    else
    {
        TSIP.REG_104H.WORD = 0x00000068u;
        TSIP.REG_E0H.WORD = 0x80010200u;
        /* WAIT_LOOP */
        while (1u != TSIP.REG_104H.BIT.B31)
        {
            /* waiting */
        }
        TSIP.REG_100H.WORD = InData_Sel_CompressType[0];
        TSIP.REG_ECH.WORD = 0x00000bffu;
        TSIP.REG_ECH.WORD = 0x38000e10u;
        TSIP.REG_ECH.WORD = 0x1000d3e0u;
        TSIP.REG_ECH.WORD = 0x38000fffu;
        TSIP.REG_E0H.WORD = 0x00000080u;
        TSIP.REG_1CH.WORD = 0x00260000u;
        RX671_func100(change_endian_long(0x9461e081u), change_endian_long(0xd3794720u), change_endian_long(0x5528efe5u), change_endian_long(0x4570be48u));
        TSIP.REG_1CH.WORD = 0x00400000u;
        TSIP.REG_1D0H.WORD = 0x00000000u;
        if (1u == (TSIP.REG_1CH.BIT.B22))
        {
            RX671_func102(change_endian_long(0x9687714au), change_endian_long(0xac89829au), change_endian_long(0x5c24bb3fu), change_endian_long(0xc98519c3u));
            TSIP.REG_1B8H.WORD = 0x00000040u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_18H.BIT.B12)
            {
                /* waiting */
            }
            #if TSIP_MULTI_THREADING == 1
            TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
            #endif /* TSIP_MULTI_THREADING == 1 */
            return TSIP_ERR_FAIL;
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
            TSIP.REG_100H.WORD = InData_PubKey[0];
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = InData_PubKey[1];
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = InData_PubKey[2];
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = InData_PubKey[3];
            TSIP.REG_ECH.WORD = 0x00000bdeu;
            TSIP.REG_ECH.WORD = 0x000037e0u;
            TSIP.REG_ECH.WORD = 0x00008fe0u;
            TSIP.REG_ECH.WORD = 0xff000000u;
            TSIP.REG_ECH.WORD = 0x38008be0u;
            TSIP.REG_ECH.WORD = 0x05000000u;
            TSIP.REG_ECH.WORD = 0x1000d3c0u;
            TSIP.REG_ECH.WORD = 0x38008be0u;
            TSIP.REG_ECH.WORD = 0x0a000000u;
            TSIP.REG_ECH.WORD = 0x1000d3c0u;
            TSIP.REG_ECH.WORD = 0x38008be0u;
            TSIP.REG_ECH.WORD = 0x31000000u;
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
            RX671_func100(change_endian_long(0x1c7f94dcu), change_endian_long(0x3a690025u), change_endian_long(0xd9564382u), change_endian_long(0x3be43791u));
            TSIP.REG_1CH.WORD = 0x00400000u;
            TSIP.REG_1D0H.WORD = 0x00000000u;
            if (1u == (TSIP.REG_1CH.BIT.B22))
            {
                RX671_func102(change_endian_long(0x84bc2794u), change_endian_long(0xfa37c6f4u), change_endian_long(0x84585827u), change_endian_long(0xfe3e6310u));
                TSIP.REG_1B8H.WORD = 0x00000040u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_18H.BIT.B12)
                {
                    /* waiting */
                }
                #if TSIP_MULTI_THREADING == 1
                TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
                #endif /* TSIP_MULTI_THREADING == 1 */
                return TSIP_ERR_FAIL;
            }
            else
            {
                RX671_func100(change_endian_long(0xa4900261u), change_endian_long(0x25bf1019u), change_endian_long(0xf62ffd4au), change_endian_long(0x0a713616u));
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
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 0];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 1];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 2];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 3];
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
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+68 + 0];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+68 + 1];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+68 + 2];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+68 + 3];
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
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+132 + 0];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+132 + 1];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+132 + 2];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+132 + 3];
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
                    TSIP.REG_100H.WORD = InData_PubKey[136];
                    TSIP.REG_100H.WORD = InData_PubKey[137];
                    TSIP.REG_100H.WORD = InData_PubKey[138];
                    TSIP.REG_100H.WORD = InData_PubKey[139];
                    TSIP.REG_C4H.WORD = 0x00900c45u;
                    TSIP.REG_00H.WORD = 0x00002213u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    RX671_func101(change_endian_long(0x438db124u), change_endian_long(0xf2970550u), change_endian_long(0xc081b17bu), change_endian_long(0x2a618558u));
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
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 0];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 1];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 2];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 3];
                    }
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x00003223u;
                    TSIP.REG_2CH.WORD = 0x00000091u;
                    for (iLoop = 8; iLoop < 16; iLoop = iLoop + 4)
                    {
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 0];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 1];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 2];
                        TSIP.REG_100H.WORD = InData_PubKey[iLoop+4 + 3];
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
                    TSIP.REG_100H.WORD = InData_PubKey[20];
                    TSIP.REG_100H.WORD = InData_PubKey[21];
                    TSIP.REG_100H.WORD = InData_PubKey[22];
                    TSIP.REG_100H.WORD = InData_PubKey[23];
                    TSIP.REG_C4H.WORD = 0x00900c45u;
                    TSIP.REG_00H.WORD = 0x00002213u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    RX671_func101(change_endian_long(0x822e05c1u), change_endian_long(0x25e0e580u), change_endian_long(0x67633bb3u), change_endian_long(0x21671ff2u));
                }
                RX671_func100(change_endian_long(0x81b7619au), change_endian_long(0xf406a0ffu), change_endian_long(0xec47e611u), change_endian_long(0xc640de23u));
                TSIP.REG_1CH.WORD = 0x00400000u;
                TSIP.REG_1D0H.WORD = 0x00000000u;
                if (1u == (TSIP.REG_1CH.BIT.B22))
                {
                    RX671_func102(change_endian_long(0xd6705353u), change_endian_long(0x9a870afeu), change_endian_long(0x7d6247fcu), change_endian_long(0x17101159u));
                    TSIP.REG_1B8H.WORD = 0x00000040u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_18H.BIT.B12)
                    {
                        /* waiting */
                    }
                    #if TSIP_MULTI_THREADING == 1
                    TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
                    #endif /* TSIP_MULTI_THREADING == 1 */
                    return TSIP_ERR_FAIL;
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
                    TSIP.REG_104H.WORD = 0x00000f64u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = InData_ClientRandom[0];
                    TSIP.REG_100H.WORD = InData_ClientRandom[1];
                    TSIP.REG_100H.WORD = InData_ClientRandom[2];
                    TSIP.REG_100H.WORD = InData_ClientRandom[3];
                    TSIP.REG_100H.WORD = InData_ClientRandom[4];
                    TSIP.REG_100H.WORD = InData_ClientRandom[5];
                    TSIP.REG_100H.WORD = InData_ClientRandom[6];
                    TSIP.REG_100H.WORD = InData_ClientRandom[7];
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = InData_ServerRandom[0];
                    TSIP.REG_100H.WORD = InData_ServerRandom[1];
                    TSIP.REG_100H.WORD = InData_ServerRandom[2];
                    TSIP.REG_100H.WORD = InData_ServerRandom[3];
                    TSIP.REG_100H.WORD = InData_ServerRandom[4];
                    TSIP.REG_100H.WORD = InData_ServerRandom[5];
                    TSIP.REG_100H.WORD = InData_ServerRandom[6];
                    TSIP.REG_100H.WORD = InData_ServerRandom[7];
                    TSIP.REG_ECH.WORD = 0x0000b7c0u;
                    TSIP.REG_ECH.WORD = 0x03001741u;
                    TSIP.REG_E0H.WORD = 0x810103c0u;
                    TSIP.REG_00H.WORD = 0x00005807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_104H.WORD = 0x00000068u;
                    TSIP.REG_E0H.WORD = 0x800103c0u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = InData_SKE_Message[0];
                    TSIP.REG_E0H.WORD = 0x810103c0u;
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
                    TSIP.REG_D0H.WORD = 0x00000314u;
                    TSIP.REG_C4H.WORD = 0x00008a07u;
                    TSIP.REG_104H.WORD = 0x00000f62u;
                    for (iLoop = 0; iLoop < 16; iLoop = iLoop + 4)
                    {
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = InData_SKE_Message[iLoop+1 + 0];
                        TSIP.REG_100H.WORD = InData_SKE_Message[iLoop+1 + 1];
                        TSIP.REG_100H.WORD = InData_SKE_Message[iLoop+1 + 2];
                        TSIP.REG_100H.WORD = InData_SKE_Message[iLoop+1 + 3];
                    }
                    TSIP.REG_D0H.WORD = 0x0000031cu;
                    TSIP.REG_C4H.WORD = 0x00008a83u;
                    TSIP.REG_00H.WORD = 0x08015203u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_ECH.WORD = 0x0000b7c0u;
                    TSIP.REG_ECH.WORD = 0x80000000u;
                    TSIP.REG_E0H.WORD = 0x810103c0u;
                    TSIP.REG_00H.WORD = 0x0800580fu;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x08000807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_F8H.WORD = 0x00000040u;
                    TSIP.REG_104H.WORD = 0x00000154u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000428u);
                    RX671_func100(change_endian_long(0xabf7211au), change_endian_long(0xf68a1a32u), change_endian_long(0xf6909f3bu), change_endian_long(0xb8812f4bu));
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_74H.BIT.B18)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001600u;
                    TSIP.REG_74H.WORD = 0x00000000u;
                    TSIP.REG_ECH.WORD = 0x00007c0eu;
                    TSIP.REG_1CH.WORD = 0x00600000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (0x00000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                    {
                        RX671_func100(change_endian_long(0x757f1940u), change_endian_long(0xa262daa1u), change_endian_long(0x1ecce856u), change_endian_long(0x5fbd4d33u));
                        TSIP.REG_28H.WORD = 0x00bf0001u;
                        TSIP.REG_2CH.WORD = 0x00000010u;
                        TSIP.REG_104H.WORD = 0x00003f67u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = InData_SKE_Signature[0];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[1];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[2];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[3];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[4];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[5];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[6];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[7];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[8];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[9];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[10];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[11];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[12];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[13];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[14];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[15];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[16];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[17];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[18];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[19];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[20];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[21];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[22];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[23];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[24];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[25];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[26];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[27];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[28];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[29];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[30];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[31];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[32];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[33];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[34];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[35];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[36];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[37];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[38];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[39];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[40];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[41];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[42];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[43];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[44];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[45];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[46];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[47];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[48];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[49];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[50];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[51];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[52];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[53];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[54];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[55];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[56];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[57];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[58];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[59];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[60];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[61];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[62];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[63];
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
                        RX671_func101(change_endian_long(0x80a76fbau), change_endian_long(0x323c4543u), change_endian_long(0xe6da93aeu), change_endian_long(0xeeddd00cu));
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
                        RX671_func100(change_endian_long(0x1081de5au), change_endian_long(0x222cb4d8u), change_endian_long(0x366fdb12u), change_endian_long(0x3ac04034u));
                        RX671_func103();
                        RX671_func100(change_endian_long(0x358427deu), change_endian_long(0xacfb7638u), change_endian_long(0x5e70a652u), change_endian_long(0x81da6b4bu));
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
                        RX671_func100(change_endian_long(0x030d74c7u), change_endian_long(0x0de1cdc4u), change_endian_long(0xf83bd36cu), change_endian_long(0x97ffe953u));
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x5fe685f6u);
                        RX671_func080();
                        RX671_func100(change_endian_long(0x79f6ffd3u), change_endian_long(0xb67f1a74u), change_endian_long(0x48a1e466u), change_endian_long(0x52e9d5c4u));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000020u;
                        RX671_func313(748);
                        RX671_func100(change_endian_long(0xbb76ed56u), change_endian_long(0x2aea18b2u), change_endian_long(0x0b67ec76u), change_endian_long(0xf91961c6u));
                        RX671_func314(748+64);
                        RX671_func100(change_endian_long(0x64f53445u), change_endian_long(0x558346e1u), change_endian_long(0xc3d028bfu), change_endian_long(0x7bcf728au));
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x1c5a2b81u);
                        RX671_func080();
                        RX671_func100(change_endian_long(0x634f8300u), change_endian_long(0x550c8049u), change_endian_long(0xe1abd9b0u), change_endian_long(0xfb6a6c24u));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000022u;
                        RX671_func313(680);
                        RX671_func100(change_endian_long(0x363eed80u), change_endian_long(0x3435c31du), change_endian_long(0xa6f4c177u), change_endian_long(0x8390072du));
                        RX671_func314(680+64);
                        RX671_func100(change_endian_long(0x44b7df96u), change_endian_long(0x67d9d9a9u), change_endian_long(0xb71f9b73u), change_endian_long(0x1c7b58cfu));
                        TSIP.REG_2CH.WORD = 0x00000010u;
                        TSIP.REG_104H.WORD = 0x00003f67u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = InData_SKE_Signature[0];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[1];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[2];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[3];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[4];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[5];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[6];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[7];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[8];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[9];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[10];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[11];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[12];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[13];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[14];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[15];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[16];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[17];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[18];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[19];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[20];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[21];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[22];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[23];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[24];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[25];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[26];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[27];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[28];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[29];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[30];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[31];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[32];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[33];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[34];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[35];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[36];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[37];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[38];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[39];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[40];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[41];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[42];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[43];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[44];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[45];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[46];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[47];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[48];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[49];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[50];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[51];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[52];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[53];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[54];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[55];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[56];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[57];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[58];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[59];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[60];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[61];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[62];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[63];
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x5dd049feu);
                        RX671_func080();
                        RX671_func100(change_endian_long(0x171e66d1u), change_endian_long(0x8e48c869u), change_endian_long(0xa4ec6596u), change_endian_long(0xaf619a37u));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000020u;
                        RX671_func313(68);
                        RX671_func100(change_endian_long(0xd8426cb3u), change_endian_long(0x20f7d800u), change_endian_long(0x87a34a82u), change_endian_long(0xc053fa88u));
                        RX671_func314(68+64);
                        RX671_func100(change_endian_long(0xbef4048eu), change_endian_long(0x4006bbb8u), change_endian_long(0xeb3e989cu), change_endian_long(0xcf89e570u));
                        TSIP.REG_2CH.WORD = 0x00000014u;
                        TSIP.REG_104H.WORD = 0x00003f67u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = InData_SKE_Signature[64];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[65];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[66];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[67];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[68];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[69];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[70];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[71];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[72];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[73];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[74];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[75];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[76];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[77];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[78];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[79];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[80];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[81];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[82];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[83];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[84];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[85];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[86];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[87];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[88];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[89];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[90];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[91];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[92];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[93];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[94];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[95];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[96];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[97];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[98];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[99];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[100];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[101];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[102];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[103];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[104];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[105];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[106];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[107];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[108];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[109];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[110];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[111];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[112];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[113];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[114];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[115];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[116];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[117];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[118];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[119];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[120];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[121];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[122];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[123];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[124];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[125];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[126];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[127];
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x80010020u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x945d2158u);
                        RX671_func080();
                        RX671_func100(change_endian_long(0x44be3fe7u), change_endian_long(0x8bb187eau), change_endian_long(0xbe97e1d2u), change_endian_long(0x0ca87e2bu));
                        TSIP.REG_00H.WORD = 0x00012303u;
                        TSIP.REG_2CH.WORD = 0x00000024u;
                        RX671_func313(0);
                        RX671_func100(change_endian_long(0x60f058b2u), change_endian_long(0xc1487ad0u), change_endian_long(0x9021a0bcu), change_endian_long(0xd43de486u));
                        RX671_func314(0+64);
                        TSIP.REG_ECH.WORD = 0x0000b400u;
                        TSIP.REG_ECH.WORD = 0x000000e7u;
                        RX671_func101(change_endian_long(0x89ed0b53u), change_endian_long(0x118161aau), change_endian_long(0x5ff3cf42u), change_endian_long(0xda191fdeu));
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
                        RX671_func101(change_endian_long(0x69b5cb37u), change_endian_long(0xc2a35bfau), change_endian_long(0xf6e81e23u), change_endian_long(0x1dd82a1cu));
                    }
                    else if (0x02000000u == (TSIP.REG_1CH.WORD & 0xff000000u))
                    {
                        TSIP.REG_28H.WORD = 0x00870001u;
                        TSIP.REG_ECH.WORD = 0x00000b9cu;
                        TSIP.REG_104H.WORD = 0x00000058u;
                        TSIP.REG_E0H.WORD = 0x800103a0u;
                        /* WAIT_LOOP */
                        while (1u != TSIP.REG_104H.BIT.B31)
                        {
                            /* waiting */
                        }
                        TSIP.REG_100H.WORD = change_endian_long(0x000000e7u);
                        RX671_func101(change_endian_long(0xa15c6f22u), change_endian_long(0x6890744bu), change_endian_long(0x9d4f24bcu), change_endian_long(0x892e69a5u));
                        RX671_func003(InData_SKE_Signature);
                        RX671_func101(change_endian_long(0x6549cb5eu), change_endian_long(0xc0799260u), change_endian_long(0x53077fd7u), change_endian_long(0x0d2dc964u));
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
                        TSIP.REG_100H.WORD = InData_SKE_Signature[0];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[1];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[2];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[3];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[4];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[5];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[6];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[7];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[8];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[9];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[10];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[11];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[12];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[13];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[14];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[15];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[16];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[17];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[18];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[19];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[20];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[21];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[22];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[23];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[24];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[25];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[26];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[27];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[28];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[29];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[30];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[31];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[32];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[33];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[34];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[35];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[36];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[37];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[38];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[39];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[40];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[41];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[42];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[43];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[44];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[45];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[46];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[47];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[48];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[49];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[50];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[51];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[52];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[53];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[54];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[55];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[56];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[57];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[58];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[59];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[60];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[61];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[62];
                        TSIP.REG_100H.WORD = InData_SKE_Signature[63];
                        TSIP.REG_ECH.WORD = 0x0000342au;
                        TSIP.REG_ECH.WORD = 0x0000b400u;
                        TSIP.REG_ECH.WORD = 0x000000e7u;
                        TSIP.REG_ECH.WORD = 0x0000b440u;
                        TSIP.REG_ECH.WORD = 0x00000020u;
                        RX671_func101(change_endian_long(0xb14fbf21u), change_endian_long(0x1157ca5eu), change_endian_long(0x08e40e03u), change_endian_long(0x2e881e6fu));
                        RX671_func015();
                        RX671_func101(change_endian_long(0x38947c4cu), change_endian_long(0xadb6665eu), change_endian_long(0xd470ce97u), change_endian_long(0xc207423du));
                    }
                    RX671_func100(change_endian_long(0x76ed7ae4u), change_endian_long(0xc4710341u), change_endian_long(0x0913ca25u), change_endian_long(0x596212d3u));
                    TSIP.REG_1CH.WORD = 0x00400000u;
                    TSIP.REG_1D0H.WORD = 0x00000000u;
                    if (1u == (TSIP.REG_1CH.BIT.B22))
                    {
                        RX671_func102(change_endian_long(0xf57c7955u), change_endian_long(0xf768c63du), change_endian_long(0x11e782e9u), change_endian_long(0xbf8f96bcu));
                        TSIP.REG_1B8H.WORD = 0x00000040u;
                        /* WAIT_LOOP */
                        while (0u != TSIP.REG_18H.BIT.B12)
                        {
                            /* waiting */
                        }
                        #if TSIP_MULTI_THREADING == 1
                        TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
                        #endif /* TSIP_MULTI_THREADING == 1 */
                        return TSIP_ERR_FAIL;
                    }
                    else
                    {
                        TSIP.REG_28H.WORD = 0x00870001u;
                        TSIP.REG_ECH.WORD = 0x00000b9cu;
                        RX671_func004(InData_DomainParam);
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
                        RX671_func100(change_endian_long(0x9182332eu), change_endian_long(0x4aeca179u), change_endian_long(0xb0c5c4f9u), change_endian_long(0x23723b18u));
                        TSIP.REG_1CH.WORD = 0x00400000u;
                        TSIP.REG_1D0H.WORD = 0x00000000u;
                        if (1u == (TSIP.REG_1CH.BIT.B22))
                        {
                            RX671_func102(change_endian_long(0x2a2ea3abu), change_endian_long(0x3fd6914au), change_endian_long(0x961e3951u), change_endian_long(0x4f4e6cc7u));
                            TSIP.REG_1B8H.WORD = 0x00000040u;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_18H.BIT.B12)
                            {
                                /* waiting */
                            }
                            #if TSIP_MULTI_THREADING == 1
                            TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
                            #endif /* TSIP_MULTI_THREADING == 1 */
                            return TSIP_ERR_FAIL;
                        }
                        else
                        {
                            RX671_func100(change_endian_long(0x31477a7fu), change_endian_long(0x7d9ad35cu), change_endian_long(0x4c71fa31u), change_endian_long(0x683d8cc9u));
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
                            TSIP.REG_100H.WORD = change_endian_long(0x31020100u);
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
                            RX671_func100(change_endian_long(0x457b5bd7u), change_endian_long(0x3357b9b4u), change_endian_long(0x267f305du), change_endian_long(0xd5ad3ba5u));
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
                                OutData_EphemeralPubKey[iLoop + 0] = TSIP.REG_100H.WORD;
                                OutData_EphemeralPubKey[iLoop + 1] = TSIP.REG_100H.WORD;
                                OutData_EphemeralPubKey[iLoop + 2] = TSIP.REG_100H.WORD;
                                OutData_EphemeralPubKey[iLoop + 3] = TSIP.REG_100H.WORD;
                            }
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_00H.BIT.B25)
                            {
                                /* waiting */
                            }
                            TSIP.REG_1CH.WORD = 0x00001800u;
                            RX671_func100(change_endian_long(0x66dd3c00u), change_endian_long(0x126f787bu), change_endian_long(0xbc9307fcu), change_endian_long(0xe0f15da5u));
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
                            OutData_EphemeralPubKey[iLoop + 0] = TSIP.REG_100H.WORD;
                            OutData_EphemeralPubKey[iLoop + 1] = TSIP.REG_100H.WORD;
                            OutData_EphemeralPubKey[iLoop + 2] = TSIP.REG_100H.WORD;
                            OutData_EphemeralPubKey[iLoop + 3] = TSIP.REG_100H.WORD;
                            RX671_func100(change_endian_long(0x14ec7dd3u), change_endian_long(0x2aa3a6cdu), change_endian_long(0x9e51e941u), change_endian_long(0x77e2717fu));
                            TSIP.REG_E0H.WORD = 0x81040000u;
                            TSIP.REG_04H.WORD = 0x00000612u;
                            /* WAIT_LOOP */
                            while (1u != TSIP.REG_04H.BIT.B30)
                            {
                                /* waiting */
                            }
                            OutData_EphemeralPubKey[0] = TSIP.REG_100H.WORD;
                            /* WAIT_LOOP */
                            while (1u != TSIP.REG_04H.BIT.B30)
                            {
                                /* waiting */
                            }
                            OutData_EphemeralPubKey[1] = TSIP.REG_100H.WORD;
                            /* WAIT_LOOP */
                            while (1u != TSIP.REG_04H.BIT.B30)
                            {
                                /* waiting */
                            }
                            OutData_EphemeralPubKey[2] = TSIP.REG_100H.WORD;
                            /* WAIT_LOOP */
                            while (1u != TSIP.REG_04H.BIT.B30)
                            {
                                /* waiting */
                            }
                            OutData_EphemeralPubKey[3] = TSIP.REG_100H.WORD;
                            RX671_func102(change_endian_long(0xb72c9073u), change_endian_long(0x8bd0caf0u), change_endian_long(0xbf78fd55u), change_endian_long(0x140f320du));
                            TSIP.REG_1B8H.WORD = 0x00000040u;
                            /* WAIT_LOOP */
                            while (0u != TSIP.REG_18H.BIT.B12)
                            {
                                /* waiting */
                            }
                            #if TSIP_MULTI_THREADING == 1
                            TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
                            #endif /* TSIP_MULTI_THREADING == 1 */
                            return TSIP_SUCCESS;
                        }
                    }
                }
            }
        }
    }
}
/**********************************************************************************************************************
 End of function ./input_dir/RX671/RX671_pe7_r1.prc
 *********************************************************************************************************************/
#endif /* #if TSIP_TLS == 1 */
