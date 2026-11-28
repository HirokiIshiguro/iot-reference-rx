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
* Function Name: R_TSIP_EcdhP256SshKeyDerivationSub
*******************************************************************************************************************/ /**
* @details       RX72M KDF for SSH
* @param[in]     InData_KeyIndexType
* @param[in]     InData_KeyIndex
* @param[in]     InData_PaddedMsg
* @param[in]     InData_PaddedMsgLength
* @param[out]    OutData_KeyIndex1
* @param[out]    OutData_KeyIndex2
* @param[out]    OutData_KeyIndex3
* @param[out]    OutData_KeyIndex4
* @param[out]    OutData_IV1
* @param[out]    OutData_IV2
* @retval        TSIP_SUCCESS
* @retval        TSIP_ERR_FAIL
* @retval        TSIP_ERR_RESOURCE_CONFLICT
* @retval        TSIP_ERR_KEY_SET
* @note          None
*/
e_tsip_err_t R_TSIP_EcdhP256SshKeyDerivationSub(uint32_t *InData_KeyIndexType, uint32_t *InData_KeyIndex, uint32_t *InData_PaddedMsg, uint32_t *InData_PaddedMsgLength, uint32_t *OutData_KeyIndex1, uint32_t *OutData_KeyIndex2, uint32_t *OutData_KeyIndex3, uint32_t *OutData_KeyIndex4, uint32_t *OutData_IV1, uint32_t *OutData_IV2)
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
    if (0x0u != (TSIP.REG_1BCH.WORD & 0x1fu))
    {
        #if TSIP_MULTI_THREADING == 1
        TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
        #endif /* TSIP_MULTI_THREADING == 1 */
        return TSIP_ERR_RESOURCE_CONFLICT;
    }
    TSIP.REG_84H.WORD = 0x00005f01u;
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
    TSIP.REG_28H.WORD = 0x00870001u;
    TSIP.REG_C4H.WORD = 0x000c2b0du;
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = InData_KeyIndex[0];
    TSIP.REG_100H.WORD = InData_KeyIndex[1];
    TSIP.REG_100H.WORD = InData_KeyIndex[2];
    TSIP.REG_100H.WORD = InData_KeyIndex[3];
    TSIP.REG_C4H.WORD = 0x000c0b0cu;
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = change_endian_long(0x718cf94fu);
    TSIP.REG_104H.WORD = 0x00000762u;
    TSIP.REG_D0H.WORD = 0x00000100u;
    TSIP.REG_C4H.WORD = 0x02f087bfu;
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = InData_KeyIndex[4];
    TSIP.REG_100H.WORD = InData_KeyIndex[5];
    TSIP.REG_100H.WORD = InData_KeyIndex[6];
    TSIP.REG_100H.WORD = InData_KeyIndex[7];
    /* WAIT_LOOP */
    while (1u != TSIP.REG_104H.BIT.B31)
    {
        /* waiting */
    }
    TSIP.REG_100H.WORD = InData_KeyIndex[8];
    TSIP.REG_100H.WORD = InData_KeyIndex[9];
    TSIP.REG_100H.WORD = InData_KeyIndex[10];
    TSIP.REG_100H.WORD = InData_KeyIndex[11];
    TSIP.REG_00H.WORD = 0x00003223u;
    TSIP.REG_2CH.WORD = 0x00000012u;
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
    TSIP.REG_100H.WORD = InData_KeyIndex[12];
    TSIP.REG_100H.WORD = InData_KeyIndex[13];
    TSIP.REG_100H.WORD = InData_KeyIndex[14];
    TSIP.REG_100H.WORD = InData_KeyIndex[15];
    TSIP.REG_C4H.WORD = 0x00900c45u;
    TSIP.REG_00H.WORD = 0x00002213u;
    /* WAIT_LOOP */
    while (0u != TSIP.REG_00H.BIT.B25)
    {
        /* waiting */
    }
    TSIP.REG_1CH.WORD = 0x00001800u;
    RX72M_RX72N_RX66N_func100(change_endian_long(0xfdabee83u), change_endian_long(0xaa6a503au), change_endian_long(0xb0b114c6u), change_endian_long(0xb973dc7bu));
    TSIP.REG_1CH.WORD = 0x00400000u;
    TSIP.REG_1D0H.WORD = 0x00000000u;
    if (1u == (TSIP.REG_1CH.BIT.B22))
    {
        RX72M_RX72N_RX66N_func102(change_endian_long(0xbbb03a0fu), change_endian_long(0xf0682211u), change_endian_long(0x2e70f5c7u), change_endian_long(0xbf128835u));
        TSIP.REG_1BCH.WORD = 0x00000040u;
        /* WAIT_LOOP */
        while (0u != TSIP.REG_18H.BIT.B12)
        {
            /* waiting */
        }
        #if TSIP_MULTI_THREADING == 1
        TSIP_MULTI_THREADING_UNLOCK_FUNCTION();
        #endif /* TSIP_MULTI_THREADING == 1 */
        return TSIP_ERR_KEY_SET;
    }
    else
    {
        TSIP.REG_104H.WORD = 0x00000068u;
        TSIP.REG_E0H.WORD = 0x80010360u;
        /* WAIT_LOOP */
        while (1u != TSIP.REG_104H.BIT.B31)
        {
            /* waiting */
        }
        TSIP.REG_100H.WORD = InData_PaddedMsgLength[0];
        TSIP.REG_ECH.WORD = 0x38000f7bu;
        TSIP.REG_E0H.WORD = 0x00000080u;
        TSIP.REG_1CH.WORD = 0x00260000u;
        TSIP.REG_ECH.WORD = 0x38008f60u;
        TSIP.REG_ECH.WORD = 0xfc000000u;
        TSIP.REG_E0H.WORD = 0x00000080u;
        TSIP.REG_1CH.WORD = 0x00A60000u;
        RX72M_RX72N_RX66N_func100(change_endian_long(0x9f9ca0beu), change_endian_long(0x4b9eb088u), change_endian_long(0x9d7f7d07u), change_endian_long(0xe9006489u));
        TSIP.REG_1CH.WORD = 0x00400000u;
        TSIP.REG_1D0H.WORD = 0x00000000u;
        if (1u == (TSIP.REG_1CH.BIT.B22))
        {
            RX72M_RX72N_RX66N_func102(change_endian_long(0x571a0793u), change_endian_long(0xda76e39bu), change_endian_long(0x7a4486d6u), change_endian_long(0x69c7a4c2u));
            TSIP.REG_1BCH.WORD = 0x00000040u;
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
            RX72M_RX72N_RX66N_func100(change_endian_long(0xd1a0f95fu), change_endian_long(0x927cf9c2u), change_endian_long(0x49190206u), change_endian_long(0x68b1f661u));
            TSIP.REG_ECH.WORD = 0x0000373bu;
            TSIP.REG_ECH.WORD = 0x0000a720u;
            TSIP.REG_ECH.WORD = 0x00000003u;
            TSIP.REG_ECH.WORD = 0x00026b39u;
            TSIP.REG_ECH.WORD = 0x00003619u;
            TSIP.REG_ECH.WORD = 0x00003200u;
            TSIP.REG_ECH.WORD = 0x00046a10u;
            TSIP.REG_ECH.WORD = 0x00046e10u;
            TSIP.REG_E0H.WORD = 0x81010200u;
            TSIP.REG_04H.WORD = 0x00000606u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
            TSIP.REG_ECH.WORD = 0x00000bffu;
            for (iLoop = 0; iLoop < S_RAM[0]; iLoop = iLoop + 16)
            {
                TSIP.REG_104H.WORD = 0x00000f64u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 0];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 1];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 2];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 3];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 4];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 5];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 6];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 7];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 8];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 9];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 10];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 11];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 12];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 13];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 14];
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 15];
                TSIP.REG_ECH.WORD = 0x0000a7e0u;
                TSIP.REG_ECH.WORD = 0x00000010u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0xe89d80f7u), change_endian_long(0x1a871abdu), change_endian_long(0x52165bd6u), change_endian_long(0xab573261u));
            }
            RX72M_RX72N_RX66N_func100(change_endian_long(0xaf212244u), change_endian_long(0x77e8de37u), change_endian_long(0x82e0ba6au), change_endian_long(0xfb03b2b6u));
            TSIP.REG_ECH.WORD = 0x38000a1fu;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_1CH.WORD = 0x00402000u;
            TSIP.REG_E0H.WORD = 0x81010320u;
            TSIP.REG_04H.WORD = 0x00000606u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
            TSIP.REG_ECH.WORD = 0x00000a10u;
            TSIP.REG_ECH.WORD = 0x0000b6c0u;
            TSIP.REG_ECH.WORD = 0x00000004u;
            for (iLoop = iLoop; iLoop < S_RAM[0]; iLoop = iLoop + 1)
            {
                TSIP.REG_104H.WORD = 0x00000068u;
                TSIP.REG_E0H.WORD = 0x80810010u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = InData_PaddedMsg[iLoop + 0];
                TSIP.REG_ECH.WORD = 0x00002616u;
                TSIP.REG_ECH.WORD = 0x00002fe0u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0xffd805d7u), change_endian_long(0xd57054c8u), change_endian_long(0xbcbe41cdu), change_endian_long(0x002696b0u));
            }
            RX72M_RX72N_RX66N_func100(change_endian_long(0x8778da06u), change_endian_long(0x4304e8c4u), change_endian_long(0xef63fd6cu), change_endian_long(0x767b1041u));
            TSIP.REG_ECH.WORD = 0x38000b3fu;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_1CH.WORD = 0x00402000u;
            TSIP.REG_ECH.WORD = 0x0000375bu;
            TSIP.REG_ECH.WORD = 0x00003340u;
            TSIP.REG_ECH.WORD = 0x001a6f5au;
            TSIP.REG_ECH.WORD = 0x001a6b5au;
            TSIP.REG_ECH.WORD = 0x00002f40u;
            TSIP.REG_ECH.WORD = 0x0000b700u;
            TSIP.REG_ECH.WORD = 0x00000004u;
            TSIP.REG_ECH.WORD = 0x00000b9cu;
            TSIP.REG_ECH.WORD = 0x00000a52u;
            TSIP.REG_2CH.WORD = 0x00000022u;
            for (iLoop = 0; iLoop < 32; iLoop = iLoop + 1)
            {
                TSIP.REG_E0H.WORD = 0x80010000u;
                TSIP.REG_00H.WORD = 0x0800800fu;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x08008307u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_ECH.WORD = 0x30000f9cu;
                TSIP.REG_ECH.WORD = 0x00030020u;
                TSIP.REG_ECH.WORD = 0x30000c00u;
                TSIP.REG_ECH.WORD = 0x00020020u;
                TSIP.REG_ECH.WORD = 0x3000d807u;
                TSIP.REG_ECH.WORD = 0x00010020u;
                TSIP.REG_ECH.WORD = 0x0000363au;
                TSIP.REG_ECH.WORD = 0x00002638u;
                TSIP.REG_ECH.WORD = 0x02003e51u;
                TSIP.REG_ECH.WORD = 0x00002e20u;
                TSIP.REG_ECH.WORD = 0x02003c11u;
                TSIP.REG_ECH.WORD = 0x0000a700u;
                TSIP.REG_ECH.WORD = 0x00000002u;
                TSIP.REG_ECH.WORD = 0x00000060u;
                TSIP.REG_ECH.WORD = 0x0000363au;
                TSIP.REG_ECH.WORD = 0x00002638u;
                TSIP.REG_ECH.WORD = 0x02003c11u;
                TSIP.REG_ECH.WORD = 0x00002f00u;
                TSIP.REG_ECH.WORD = 0x00000080u;
                TSIP.REG_ECH.WORD = 0x00002f80u;
                TSIP.REG_ECH.WORD = 0x00000080u;
                TSIP.REG_ECH.WORD = 0x00000060u;
                TSIP.REG_ECH.WORD = 0x0000363au;
                TSIP.REG_ECH.WORD = 0x00002638u;
                TSIP.REG_ECH.WORD = 0x02003c11u;
                TSIP.REG_ECH.WORD = 0x00002f00u;
                TSIP.REG_ECH.WORD = 0x00000080u;
            }
            TSIP.REG_ECH.WORD = 0x00003618u;
            TSIP.REG_ECH.WORD = 0x0020aa00u;
            TSIP.REG_ECH.WORD = 0x00000004u;
            TSIP.REG_ECH.WORD = 0x0000363au;
            TSIP.REG_ECH.WORD = 0x0000a620u;
            TSIP.REG_ECH.WORD = 0x00000003u;
            for (iLoop = 0; iLoop < 4; iLoop = iLoop + 1)
            {
                TSIP.REG_ECH.WORD = 0x02003e11u;
                TSIP.REG_ECH.WORD = 0x00003220u;
                TSIP.REG_ECH.WORD = 0x00086a10u;
            }
            TSIP.REG_ECH.WORD = 0x0000363au;
            TSIP.REG_ECH.WORD = 0x00002638u;
            TSIP.REG_ECH.WORD = 0x00003651u;
            TSIP.REG_ECH.WORD = 0x0000a640u;
            TSIP.REG_ECH.WORD = 0x00000003u;
            TSIP.REG_ECH.WORD = 0x0000b600u;
            TSIP.REG_ECH.WORD = 0x80000000u;
            for (iLoop = 0; iLoop < 4; iLoop = iLoop + 1)
            {
                TSIP.REG_ECH.WORD = 0x02003e12u;
                TSIP.REG_ECH.WORD = 0x00003240u;
                TSIP.REG_ECH.WORD = 0x00086a10u;
            }
            TSIP.REG_ECH.WORD = 0x00003611u;
            TSIP.REG_ECH.WORD = 0x00026a10u;
            TSIP.REG_ECH.WORD = 0x00002e00u;
            TSIP.REG_E0H.WORD = 0x81010200u;
            TSIP.REG_04H.WORD = 0x00000606u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
            TSIP.REG_ECH.WORD = 0x00000bffu;
            TSIP.REG_ECH.WORD = 0x00000a52u;
            for (iLoop = 0; iLoop < S_RAM[0]; iLoop = iLoop + 1)
            {
                TSIP.REG_E0H.WORD = 0x81810012u;
                TSIP.REG_00H.WORD = 0x00005807u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_ECH.WORD = 0x00002656u;
                TSIP.REG_ECH.WORD = 0x00002fe0u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0x7e02c911u), change_endian_long(0x50740296u), change_endian_long(0xa8bff8f3u), change_endian_long(0x64dbea55u));
            }
            RX72M_RX72N_RX66N_func100(change_endian_long(0x92463d16u), change_endian_long(0xb8b6afbau), change_endian_long(0x11a8c21fu), change_endian_long(0xe5044397u));
            TSIP.REG_ECH.WORD = 0x38000a1fu;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_1CH.WORD = 0x00402000u;
            TSIP.REG_F8H.WORD = 0x00000040u;
            TSIP.REG_ECH.WORD = 0x000036bbu;
            TSIP.REG_ECH.WORD = 0x000026b8u;
            TSIP.REG_ECH.WORD = 0x00036eb5u;
            TSIP.REG_00H.WORD = 0x00005007u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_E0H.WORD = 0x810102a0u;
            TSIP.REG_00H.WORD = 0x00005807u;
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
            TSIP.REG_00H.WORD = 0x00003523u;
            TSIP.REG_74H.WORD = 0x00000008u;
            TSIP.REG_2CH.WORD = 0x00000019u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            TSIP.REG_ECH.WORD = 0x00000a73u;
            TSIP.REG_ECH.WORD = 0x0000369au;
            TSIP.REG_E0H.WORD = 0x81010300u;
            TSIP.REG_04H.WORD = 0x00000606u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
            TSIP.REG_ECH.WORD = 0x00000bffu;
            for (iLoop = 0; iLoop < S_RAM[0]; iLoop = iLoop + 1)
            {
                TSIP.REG_ECH.WORD = 0x02003814u;
                TSIP.REG_ECH.WORD = 0x02003c13u;
                TSIP.REG_ECH.WORD = 0x00002e60u;
                TSIP.REG_ECH.WORD = 0x00002e80u;
                TSIP.REG_ECH.WORD = 0x00002fe0u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0xc4884c9bu), change_endian_long(0xa57e2a44u), change_endian_long(0x0d469cf5u), change_endian_long(0x6275eec9u));
            }
            RX72M_RX72N_RX66N_func100(change_endian_long(0x90e32f6bu), change_endian_long(0xb4f6fc2fu), change_endian_long(0xe3006efau), change_endian_long(0x6e54b504u));
            TSIP.REG_ECH.WORD = 0x38000b1fu;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_1CH.WORD = 0x00402000u;
            TSIP.REG_ECH.WORD = 0x00003618u;
            TSIP.REG_ECH.WORD = 0x00003630u;
            TSIP.REG_ECH.WORD = 0x0000a620u;
            TSIP.REG_ECH.WORD = 0x00000021u;
            TSIP.REG_2CH.WORD = 0x00000029u;
            for (iLoop = 0; iLoop < 32; iLoop = iLoop + 1)
            {
                TSIP.REG_E0H.WORD = 0x80010240u;
                TSIP.REG_00H.WORD = 0x0800800fu;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x08008307u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_ECH.WORD = 0x02003e50u;
                TSIP.REG_ECH.WORD = 0x02003e51u;
                TSIP.REG_ECH.WORD = 0x00002e00u;
                TSIP.REG_ECH.WORD = 0x00002e20u;
            }
            TSIP.REG_ECH.WORD = 0x00003638u;
            TSIP.REG_ECH.WORD = 0x0000a620u;
            TSIP.REG_ECH.WORD = 0x00000044u;
            TSIP.REG_ECH.WORD = 0x0000b600u;
            TSIP.REG_ECH.WORD = 0x80000000u;
            for (iLoop = 0; iLoop < 4; iLoop = iLoop + 1)
            {
                TSIP.REG_ECH.WORD = 0x02003e11u;
                TSIP.REG_ECH.WORD = 0x00003220u;
                TSIP.REG_ECH.WORD = 0x00086a10u;
            }
            TSIP.REG_ECH.WORD = 0x00003618u;
            TSIP.REG_ECH.WORD = 0x0000a600u;
            TSIP.REG_ECH.WORD = 0x00000045u;
            TSIP.REG_ECH.WORD = 0x00026a10u;
            TSIP.REG_E0H.WORD = 0x81010200u;
            TSIP.REG_04H.WORD = 0x00000606u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            S_RAM[0] = change_endian_long(TSIP.REG_100H.WORD);
            TSIP.REG_ECH.WORD = 0x00003698u;
            TSIP.REG_ECH.WORD = 0x0000a680u;
            TSIP.REG_ECH.WORD = 0x00000041u;
            TSIP.REG_ECH.WORD = 0x00036e94u;
            TSIP.REG_ECH.WORD = 0x0000b620u;
            TSIP.REG_ECH.WORD = 0x00000041u;
            TSIP.REG_ECH.WORD = 0x00000bffu;
            TSIP.REG_ECH.WORD = 0x00003658u;
            TSIP.REG_ECH.WORD = 0x0000a640u;
            TSIP.REG_ECH.WORD = 0x00000020u;
            TSIP.REG_28H.WORD = 0x00af0001u;
            TSIP.REG_2CH.WORD = 0x00000010u;
            for (iLoop = 0; iLoop < 6; iLoop = iLoop + 1)
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
                TSIP.REG_ECH.WORD = 0x00000af7u;
                TSIP.REG_ECH.WORD = 0x00000ab5u;
                TSIP.REG_ECH.WORD = 0x02003e32u;
                for (jLoop = 0; jLoop < S_RAM[0]; jLoop = jLoop + 1)
                {
                    TSIP.REG_E0H.WORD = 0x81810015u;
                    TSIP.REG_00H.WORD = 0x00005807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_ECH.WORD = 0x000026b6u;
                    TSIP.REG_ECH.WORD = 0x00002ee0u;
                    RX72M_RX72N_RX66N_func101(change_endian_long(0x2e9420a6u), change_endian_long(0xbde93cf9u), change_endian_long(0xcb9c1c13u), change_endian_long(0x3e343d16u));
                }
                TSIP.REG_ECH.WORD = 0x38000a17u;
                TSIP.REG_E0H.WORD = 0x00000080u;
                TSIP.REG_1CH.WORD = 0x00260000u;
                TSIP.REG_1CH.WORD = 0x00402000u;
                TSIP.REG_F8H.WORD = 0x00000040u;
                TSIP.REG_00H.WORD = 0x00005007u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_E0H.WORD = 0x81010280u;
                TSIP.REG_00H.WORD = 0x00005807u;
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
                TSIP.REG_00H.WORD = 0x00003523u;
                TSIP.REG_74H.WORD = 0x00000008u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_ECH.WORD = 0x00002e20u;
                TSIP.REG_ECH.WORD = 0x00002fe0u;
                RX72M_RX72N_RX66N_func101(change_endian_long(0x360fe40bu), change_endian_long(0x3206c8d0u), change_endian_long(0x5a80b3aeu), change_endian_long(0x4042f21cu));
            }
            RX72M_RX72N_RX66N_func100(change_endian_long(0x1dd61f6cu), change_endian_long(0x4f3e1830u), change_endian_long(0x1cd3bd2eu), change_endian_long(0x226fa184u));
            TSIP.REG_ECH.WORD = 0x38008be0u;
            TSIP.REG_ECH.WORD = 0x00000006u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00260000u;
            TSIP.REG_1CH.WORD = 0x00402000u;
            RX72M_RX72N_RX66N_func103();
            RX72M_RX72N_RX66N_func100(change_endian_long(0xcffbc79au), change_endian_long(0xef79ba72u), change_endian_long(0xd963aa90u), change_endian_long(0x2f45428bu));
            TSIP.REG_104H.WORD = 0x00000052u;
            TSIP.REG_C4H.WORD = 0x01000c84u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
            TSIP.REG_E0H.WORD = 0x80040000u;
            TSIP.REG_00H.WORD = 0x00008213u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            RX72M_RX72N_RX66N_func103();
            RX72M_RX72N_RX66N_func100(change_endian_long(0xb3e9cd35u), change_endian_long(0xc29d1215u), change_endian_long(0x527d70a2u), change_endian_long(0x16c9ce2cu));
            TSIP.REG_104H.WORD = 0x00000052u;
            TSIP.REG_C4H.WORD = 0x01000c84u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
            TSIP.REG_E0H.WORD = 0x80040080u;
            TSIP.REG_00H.WORD = 0x00008213u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            RX72M_RX72N_RX66N_func103();
            RX72M_RX72N_RX66N_func100(change_endian_long(0x3d18b11eu), change_endian_long(0x7fb34584u), change_endian_long(0xbdbdb7bdu), change_endian_long(0x93636f3bu));
            TSIP.REG_104H.WORD = 0x00000052u;
            TSIP.REG_C4H.WORD = 0x01000c84u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
            TSIP.REG_E0H.WORD = 0x80040100u;
            TSIP.REG_00H.WORD = 0x00008213u;
            /* WAIT_LOOP */
            while (0u != TSIP.REG_00H.BIT.B25)
            {
                /* waiting */
            }
            TSIP.REG_1CH.WORD = 0x00001800u;
            RX72M_RX72N_RX66N_func103();
            TSIP.REG_104H.WORD = 0x00000052u;
            TSIP.REG_C4H.WORD = 0x01000c84u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_104H.BIT.B31)
            {
                /* waiting */
            }
            TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
            TSIP.REG_E0H.WORD = 0x80040180u;
            TSIP.REG_00H.WORD = 0x00008213u;
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
            TSIP.REG_100H.WORD = InData_KeyIndexType[0];
            TSIP.REG_ECH.WORD = 0x3020abc0u;
            TSIP.REG_ECH.WORD = 0x00000003u;
            TSIP.REG_ECH.WORD = 0x00060020u;
            TSIP.REG_ECH.WORD = 0x0000b7c0u;
            TSIP.REG_ECH.WORD = 0x00000002u;
            TSIP.REG_ECH.WORD = 0x00000080u;
            RX72M_RX72N_RX66N_func060();
            TSIP.REG_28H.WORD = 0x00870001u;
            TSIP.REG_ECH.WORD = 0x3420abc0u;
            TSIP.REG_ECH.WORD = 0x00000002u;
            TSIP.REG_E0H.WORD = 0x00000080u;
            TSIP.REG_1CH.WORD = 0x00A60000u;
            RX72M_RX72N_RX66N_func100(change_endian_long(0x5d243823u), change_endian_long(0xce64e940u), change_endian_long(0xe98c6391u), change_endian_long(0x74c5ae82u));
            TSIP.REG_1CH.WORD = 0x00400000u;
            TSIP.REG_1D0H.WORD = 0x00000000u;
            if (1u == (TSIP.REG_1CH.BIT.B22))
            {
                RX72M_RX72N_RX66N_func100(change_endian_long(0xc24c8636u), change_endian_long(0x761a3740u), change_endian_long(0xfc5b2473u), change_endian_long(0xa5c961f6u));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040080u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_C4H.WORD = 0x000c0b0cu;
                TSIP.REG_E0H.WORD = 0x810103a0u;
                TSIP.REG_00H.WORD = 0x00002807u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                TSIP.REG_2CH.WORD = 0x000000a0u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_104H.WORD = 0x00000352u;
                TSIP.REG_C4H.WORD = 0x000009cdu;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_100H.WORD = change_endian_long(0x00000002u);
                TSIP.REG_04H.WORD = 0x00000232u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                OutData_KeyIndex3[4] = TSIP.REG_100H.WORD;
                OutData_KeyIndex3[5] = TSIP.REG_100H.WORD;
                OutData_KeyIndex3[6] = TSIP.REG_100H.WORD;
                OutData_KeyIndex3[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                OutData_KeyIndex3[8] = TSIP.REG_100H.WORD;
                OutData_KeyIndex3[9] = TSIP.REG_100H.WORD;
                OutData_KeyIndex3[10] = TSIP.REG_100H.WORD;
                OutData_KeyIndex3[11] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                OutData_KeyIndex3[12] = TSIP.REG_100H.WORD;
                OutData_KeyIndex3[13] = TSIP.REG_100H.WORD;
                OutData_KeyIndex3[14] = TSIP.REG_100H.WORD;
                OutData_KeyIndex3[15] = TSIP.REG_100H.WORD;
                RX72M_RX72N_RX66N_func100(change_endian_long(0xc251d35fu), change_endian_long(0xe643cce0u), change_endian_long(0x661e0e92u), change_endian_long(0x621cc57eu));
                TSIP.REG_C4H.WORD = 0x000c2b0du;
                TSIP.REG_E0H.WORD = 0x81040000u;
                TSIP.REG_00H.WORD = 0x00002813u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_C4H.WORD = 0x000c0b0cu;
                TSIP.REG_E0H.WORD = 0x810103a0u;
                TSIP.REG_00H.WORD = 0x00002807u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x02e087bfu;
                TSIP.REG_00H.WORD = 0x00002323u;
                TSIP.REG_2CH.WORD = 0x00000020u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_104H.WORD = 0x00000352u;
                TSIP.REG_C4H.WORD = 0x000009cdu;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_104H.BIT.B31)
                {
                    /* waiting */
                }
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                TSIP.REG_100H.WORD = change_endian_long(0x00000002u);
                TSIP.REG_04H.WORD = 0x00000232u;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                OutData_KeyIndex4[4] = TSIP.REG_100H.WORD;
                OutData_KeyIndex4[5] = TSIP.REG_100H.WORD;
                OutData_KeyIndex4[6] = TSIP.REG_100H.WORD;
                OutData_KeyIndex4[7] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                OutData_KeyIndex4[8] = TSIP.REG_100H.WORD;
                OutData_KeyIndex4[9] = TSIP.REG_100H.WORD;
                OutData_KeyIndex4[10] = TSIP.REG_100H.WORD;
                OutData_KeyIndex4[11] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                OutData_KeyIndex4[12] = TSIP.REG_100H.WORD;
                OutData_KeyIndex4[13] = TSIP.REG_100H.WORD;
                OutData_KeyIndex4[14] = TSIP.REG_100H.WORD;
                OutData_KeyIndex4[15] = TSIP.REG_100H.WORD;
                RX72M_RX72N_RX66N_func101(change_endian_long(0x357a37fau), change_endian_long(0x8ce153bcu), change_endian_long(0x488d5fb4u), change_endian_long(0x1c0c769au));
            }
            else
            {
                TSIP.REG_ECH.WORD = 0x38000fdeu;
                TSIP.REG_E0H.WORD = 0x00000080u;
                TSIP.REG_1CH.WORD = 0x00260000u;
                RX72M_RX72N_RX66N_func100(change_endian_long(0xb005f07cu), change_endian_long(0xa45dbd80u), change_endian_long(0x8750548eu), change_endian_long(0x8bd58eb3u));
                TSIP.REG_1CH.WORD = 0x00400000u;
                TSIP.REG_1D0H.WORD = 0x00000000u;
                if (1u == (TSIP.REG_1CH.BIT.B22))
                {
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x3f1c3805u), change_endian_long(0x54723842u), change_endian_long(0x8c2cecfcu), change_endian_long(0x54e16e42u));
                    TSIP.REG_C4H.WORD = 0x000c2b0du;
                    TSIP.REG_E0H.WORD = 0x81040180u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x000c0b0cu;
                    TSIP.REG_E0H.WORD = 0x810103a0u;
                    TSIP.REG_00H.WORD = 0x00002807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x02e007bdu;
                    TSIP.REG_00H.WORD = 0x00002313u;
                    TSIP.REG_2CH.WORD = 0x000000a8u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x00000313u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_104H.WORD = 0x00000352u;
                    TSIP.REG_C4H.WORD = 0x000009cdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000001u);
                    TSIP.REG_04H.WORD = 0x00000222u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex1[4] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[5] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[6] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[7] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex1[8] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[9] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[10] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[11] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xf517a1fbu), change_endian_long(0x9eac998bu), change_endian_long(0x9dee040eu), change_endian_long(0x7137f721u));
                    TSIP.REG_C4H.WORD = 0x000c2b0du;
                    TSIP.REG_E0H.WORD = 0x81040100u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x000c0b0cu;
                    TSIP.REG_E0H.WORD = 0x810103a0u;
                    TSIP.REG_00H.WORD = 0x00002807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x02e007bdu;
                    TSIP.REG_00H.WORD = 0x00002313u;
                    TSIP.REG_2CH.WORD = 0x00000028u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x00000313u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_104H.WORD = 0x00000352u;
                    TSIP.REG_C4H.WORD = 0x000009cdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000001u);
                    TSIP.REG_04H.WORD = 0x00000222u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex2[4] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[5] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[6] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[7] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex2[8] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[9] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[10] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[11] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x8810875cu), change_endian_long(0x353add06u), change_endian_long(0x76b4c01du), change_endian_long(0x35b73f1cu));
                    TSIP.REG_C4H.WORD = 0x000c2b0du;
                    TSIP.REG_E0H.WORD = 0x81040080u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x000c0b0cu;
                    TSIP.REG_E0H.WORD = 0x810103a0u;
                    TSIP.REG_00H.WORD = 0x00002807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x02e007bdu;
                    TSIP.REG_00H.WORD = 0x00002313u;
                    TSIP.REG_2CH.WORD = 0x000000a0u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x00000313u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_104H.WORD = 0x00000352u;
                    TSIP.REG_C4H.WORD = 0x000009cdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000001u);
                    TSIP.REG_04H.WORD = 0x00000222u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex3[4] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[5] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[6] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[7] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex3[8] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[9] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[10] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[11] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x1c1b95ceu), change_endian_long(0x4602ca56u), change_endian_long(0xc9e4e4e9u), change_endian_long(0x6d6913f8u));
                    TSIP.REG_C4H.WORD = 0x000c2b0du;
                    TSIP.REG_E0H.WORD = 0x81040000u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x000c0b0cu;
                    TSIP.REG_E0H.WORD = 0x810103a0u;
                    TSIP.REG_00H.WORD = 0x00002807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x02e007bdu;
                    TSIP.REG_00H.WORD = 0x00002313u;
                    TSIP.REG_2CH.WORD = 0x00000020u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_00H.WORD = 0x00000313u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_104H.WORD = 0x00000352u;
                    TSIP.REG_C4H.WORD = 0x000009cdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000001u);
                    TSIP.REG_04H.WORD = 0x00000222u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex4[4] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[5] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[6] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[7] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex4[8] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[9] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[10] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[11] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func101(change_endian_long(0x369a3476u), change_endian_long(0x1967dd98u), change_endian_long(0x2586aa64u), change_endian_long(0xe1541d7bu));
                }
                else
                {
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x100282f9u), change_endian_long(0x5c49d652u), change_endian_long(0x9a5ac178u), change_endian_long(0xdb431b88u));
                    TSIP.REG_C4H.WORD = 0x000c2b0du;
                    TSIP.REG_E0H.WORD = 0x81040180u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x000c0b0cu;
                    TSIP.REG_E0H.WORD = 0x810103a0u;
                    TSIP.REG_00H.WORD = 0x00002807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_D0H.WORD = 0x00000100u;
                    TSIP.REG_C4H.WORD = 0x02e087bfu;
                    TSIP.REG_00H.WORD = 0x00002323u;
                    TSIP.REG_2CH.WORD = 0x000000a8u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_104H.WORD = 0x00000352u;
                    TSIP.REG_C4H.WORD = 0x000009cdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000002u);
                    TSIP.REG_04H.WORD = 0x00000232u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex1[4] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[5] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[6] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[7] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex1[8] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[9] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[10] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[11] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex1[12] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[13] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[14] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex1[15] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xf32246cbu), change_endian_long(0x9a749ae5u), change_endian_long(0x9ca6dff8u), change_endian_long(0x4c449475u));
                    TSIP.REG_C4H.WORD = 0x000c2b0du;
                    TSIP.REG_E0H.WORD = 0x81040100u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x000c0b0cu;
                    TSIP.REG_E0H.WORD = 0x810103a0u;
                    TSIP.REG_00H.WORD = 0x00002807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_D0H.WORD = 0x00000100u;
                    TSIP.REG_C4H.WORD = 0x02e087bfu;
                    TSIP.REG_00H.WORD = 0x00002323u;
                    TSIP.REG_2CH.WORD = 0x00000028u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_104H.WORD = 0x00000352u;
                    TSIP.REG_C4H.WORD = 0x000009cdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000002u);
                    TSIP.REG_04H.WORD = 0x00000232u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex2[4] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[5] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[6] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[7] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex2[8] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[9] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[10] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[11] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex2[12] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[13] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[14] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex2[15] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0x5d21444cu), change_endian_long(0x3a4ece4au), change_endian_long(0xa5942457u), change_endian_long(0x298ee385u));
                    TSIP.REG_C4H.WORD = 0x000c2b0du;
                    TSIP.REG_E0H.WORD = 0x81040080u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x000c0b0cu;
                    TSIP.REG_E0H.WORD = 0x810103a0u;
                    TSIP.REG_00H.WORD = 0x00002807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_D0H.WORD = 0x00000100u;
                    TSIP.REG_C4H.WORD = 0x02e087bfu;
                    TSIP.REG_00H.WORD = 0x00002323u;
                    TSIP.REG_2CH.WORD = 0x000000a0u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_104H.WORD = 0x00000352u;
                    TSIP.REG_C4H.WORD = 0x000009cdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000002u);
                    TSIP.REG_04H.WORD = 0x00000232u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex3[4] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[5] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[6] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[7] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex3[8] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[9] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[10] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[11] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex3[12] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[13] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[14] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex3[15] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func100(change_endian_long(0xa5979c2cu), change_endian_long(0x05961d2bu), change_endian_long(0xbfbecfcbu), change_endian_long(0x36840713u));
                    TSIP.REG_C4H.WORD = 0x000c2b0du;
                    TSIP.REG_E0H.WORD = 0x81040000u;
                    TSIP.REG_00H.WORD = 0x00002813u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_C4H.WORD = 0x000c0b0cu;
                    TSIP.REG_E0H.WORD = 0x810103a0u;
                    TSIP.REG_00H.WORD = 0x00002807u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_D0H.WORD = 0x00000100u;
                    TSIP.REG_C4H.WORD = 0x02e087bfu;
                    TSIP.REG_00H.WORD = 0x00002323u;
                    TSIP.REG_2CH.WORD = 0x00000020u;
                    /* WAIT_LOOP */
                    while (0u != TSIP.REG_00H.BIT.B25)
                    {
                        /* waiting */
                    }
                    TSIP.REG_1CH.WORD = 0x00001800u;
                    TSIP.REG_104H.WORD = 0x00000352u;
                    TSIP.REG_C4H.WORD = 0x000009cdu;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_104H.BIT.B31)
                    {
                        /* waiting */
                    }
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000000u);
                    TSIP.REG_100H.WORD = change_endian_long(0x00000002u);
                    TSIP.REG_04H.WORD = 0x00000232u;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex4[4] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[5] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[6] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[7] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex4[8] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[9] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[10] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[11] = TSIP.REG_100H.WORD;
                    /* WAIT_LOOP */
                    while (1u != TSIP.REG_04H.BIT.B30)
                    {
                        /* waiting */
                    }
                    OutData_KeyIndex4[12] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[13] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[14] = TSIP.REG_100H.WORD;
                    OutData_KeyIndex4[15] = TSIP.REG_100H.WORD;
                    RX72M_RX72N_RX66N_func101(change_endian_long(0xf7aeff99u), change_endian_long(0x130a4b0bu), change_endian_long(0xcbb88ca8u), change_endian_long(0xaf6580dcu));
                }
                RX72M_RX72N_RX66N_func100(change_endian_long(0x8cbf6287u), change_endian_long(0x1ce14fa4u), change_endian_long(0xfaab75deu), change_endian_long(0x19074d8du));
                TSIP.REG_D0H.WORD = 0x00000100u;
                TSIP.REG_C4H.WORD = 0x00008887u;
                TSIP.REG_00H.WORD = 0x00002313u;
                TSIP.REG_2CH.WORD = 0x000000a1u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x00000313u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x00002313u;
                TSIP.REG_2CH.WORD = 0x00000021u;
                /* WAIT_LOOP */
                while (0u != TSIP.REG_00H.BIT.B25)
                {
                    /* waiting */
                }
                TSIP.REG_1CH.WORD = 0x00001800u;
                TSIP.REG_00H.WORD = 0x00000313u;
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
                OutData_IV1[0] = TSIP.REG_100H.WORD;
                OutData_IV1[1] = TSIP.REG_100H.WORD;
                OutData_IV1[2] = TSIP.REG_100H.WORD;
                OutData_IV1[3] = TSIP.REG_100H.WORD;
                /* WAIT_LOOP */
                while (1u != TSIP.REG_04H.BIT.B30)
                {
                    /* waiting */
                }
                OutData_IV2[0] = TSIP.REG_100H.WORD;
                OutData_IV2[1] = TSIP.REG_100H.WORD;
                OutData_IV2[2] = TSIP.REG_100H.WORD;
                OutData_IV2[3] = TSIP.REG_100H.WORD;
                RX72M_RX72N_RX66N_func101(change_endian_long(0x249427f4u), change_endian_long(0x4deb3bacu), change_endian_long(0xf7761b2fu), change_endian_long(0x54827586u));
            }
            RX72M_RX72N_RX66N_func100(change_endian_long(0x15ecfd35u), change_endian_long(0x5d2ca022u), change_endian_long(0x9fbb8a35u), change_endian_long(0xba016108u));
            TSIP.REG_E0H.WORD = 0x81100000u;
            TSIP.REG_04H.WORD = 0x00000642u;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex4[0] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex4[1] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex4[2] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex4[3] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex3[0] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex3[1] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex3[2] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex3[3] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex2[0] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex2[1] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex2[2] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex2[3] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex1[0] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex1[1] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex1[2] = TSIP.REG_100H.WORD;
            /* WAIT_LOOP */
            while (1u != TSIP.REG_04H.BIT.B30)
            {
                /* waiting */
            }
            OutData_KeyIndex1[3] = TSIP.REG_100H.WORD;
            RX72M_RX72N_RX66N_func102(change_endian_long(0xfd3cb889u), change_endian_long(0xeac083b8u), change_endian_long(0x29a8fcb7u), change_endian_long(0xde5d6f89u));
            TSIP.REG_1BCH.WORD = 0x00000040u;
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
/**********************************************************************************************************************
 End of function ./input_dir/RX72M/RX72M_p5f.prc
 *********************************************************************************************************************/
