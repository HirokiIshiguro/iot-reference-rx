/*
 * FreeRTOS V202112.00
 * Copyright (C) 2020 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
 * Modifications Copyright (C) 2023-2025 Renesas Electronics Corporation or its affiliates.
 *
 * SPDX-License-Identifier: MIT
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of
 * this software and associated documentation files (the "Software"), to deal in
 * the Software without restriction, including without limitation the rights to
 * use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
 * the Software, and to permit persons to whom the Software is furnished to do so,
 * subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
 * FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
 * COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
 * IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 *
 * https://www.FreeRTOS.org
 * https://github.com/FreeRTOS
 *
 */

/**
 * @file pkcs11_operations.c
 *
 * @brief This file provides wrapper functions for PKCS11 operations.
 */

/* Standard includes. */
#include <errno.h>
#include <assert.h>

/* Config include. */
#include "demo_config.h"

/* Interface include. */
#include "pkcs11_operations.h"

/* PKCS #11 include. */
#include "core_pkcs11_config_defaults.h"
#include "core_pkcs11_config.h"
#include "core_pki_utils.h"
#include "mbedtls_utils.h"
#include "mbedtls_pk_pkcs11.h"

/* MbedTLS include. */
#include "mbedtls/error.h"
#include "mbedtls/oid.h"
#include "mbedtls/pk.h"
#include "mbedtls/sha256.h"
#include "mbedtls/x509_crt.h"
#include "mbedtls/x509_csr.h"
#include "mbedtls/ctr_drbg.h"
#include "mbedtls/entropy.h"

/* strnlen includes for CC-RX compiler. */
#if defined(__CCRX__)
#include "strnlen.h"
#endif

/* Length parameters for importing RSA-2048 private keys. */
#define MODULUS_LENGTH        (pkcs11RSA_2048_MODULUS_BITS / 8)
#define E_LENGTH              (3)
#define D_LENGTH              (pkcs11RSA_2048_MODULUS_BITS / 8)
#define PRIME_1_LENGTH        (128)
#define PRIME_2_LENGTH        (128)
#define EXPONENT_1_LENGTH     (128)
#define EXPONENT_2_LENGTH     (128)
#define COEFFICIENT_LENGTH    (128)

#define EC_PARAMS_LENGTH      (10)
#define EC_D_LENGTH           (32)

/**
 * @brief Struct for holding parsed RSA-2048 private keys.
 */
typedef struct RsaParams_t
{
    CK_BYTE modulus[MODULUS_LENGTH+1];
    CK_BYTE e[E_LENGTH+1];
    CK_BYTE d[D_LENGTH+1];
    CK_BYTE prime1[PRIME_1_LENGTH+1];
    CK_BYTE prime2[PRIME_2_LENGTH+1];
    CK_BYTE exponent1[EXPONENT_1_LENGTH+1];
    CK_BYTE exponent2[EXPONENT_2_LENGTH+1];
    CK_BYTE coefficient[COEFFICIENT_LENGTH+1];
} RsaParams_t;

/*-----------------------------------------------------------*/

/**
 * @brief Delete the specified crypto object from storage.
 *
 * @param[in] xSession The PKCS #11 session.
 * @param[in] pxPkcsLabelsPtr The list of labels to remove.
 * @param[in] pxClass The list of corresponding classes.
 * @param[in] xCount The length of #pxPkcsLabelsPtr and #pxClass.
 */
static CK_RV prvDestroyProvidedObjects (CK_SESSION_HANDLE xSession,
                                        CK_BYTE_PTR *pxPkcsLabelsPtr,
                                        CK_OBJECT_CLASS *pxClass,
                                        CK_ULONG xCount);

/**
 * @brief Generate a new ECDSA key pair using PKCS #11.
 *
 * @param[in] xSession The PKCS #11 session.
 * @param[in] pcPrivateKeyLabel The label to store the private key.
 * @param[in] pcPublicKeyLabel The label to store the public key.
 * @param[out] xPrivateKeyHandlePtr The handle of the private key.
 * @param[out] xPublicKeyHandlePtr The handle of the public key.
 */
static CK_RV prvGenerateKeyPairEC (CK_SESSION_HANDLE xSession,
                                   const char *pcPrivateKeyLabel,
                                   const char *pcPublicKeyLabel,
                                   CK_OBJECT_HANDLE_PTR xPrivateKeyHandlePtr,
                                   CK_OBJECT_HANDLE_PTR xPublicKeyHandlePtr);

/**
 * @brief Import the specified ECDSA private key into storage.
 *
 * @param[in] session The PKCS #11 session.
 * @param[in] label The label to store the key.
 * @param[in] mbedPkContext The private key to store.
 */
static CK_RV provisionPrivateECKey (CK_SESSION_HANDLE session,
                                    const char *label,
                                    mbedtls_pk_context *mbedPkContext);

/**
 * @brief Import the specified RSA private key into storage.
 *
 * @param[in] session The PKCS #11 session.
 * @param[in] label The label to store the key.
 * @param[in] mbedPkContext The private key to store.
 */
static CK_RV provisionPrivateRSAKey (CK_SESSION_HANDLE session,
                                     const char *label,
                                     mbedtls_pk_context *mbedPkContext);

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvDestroyProvidedObjects
 * Description  : .
 * Arguments    : xSession
 *              : pxPkcsLabelsPtr
 *              : pxClass
 *              : xCount
 * Return Value : .
 *********************************************************************************************************************/
static CK_RV prvDestroyProvidedObjects (CK_SESSION_HANDLE xSession,
                                        CK_BYTE_PTR *pxPkcsLabelsPtr,
                                        CK_OBJECT_CLASS *pxClass,
                                        CK_ULONG xCount)
{
    CK_RV xResult;
    CK_FUNCTION_LIST_PTR xFunctionList;
    CK_OBJECT_HANDLE xObjectHandle;
    CK_BYTE *pxLabelPtr;
    CK_ULONG xIndex = 0;

    xResult = C_GetFunctionList(&xFunctionList);

    if (CKR_OK != xResult)
    {
        LogError(("Could not get a PKCS #11 function pointer."));
    }
    else
    {
        for (xIndex = 0; xIndex < xCount; xIndex++)
        {
            pxLabelPtr = pxPkcsLabelsPtr[xIndex];

            xResult = xFindObjectWithLabelAndClass(xSession, (char *)pxLabelPtr,
                                                   strnlen((char *)pxLabelPtr, pkcs11configMAX_LABEL_LENGTH),
                                                   pxClass[xIndex], &xObjectHandle);

            while ((CKR_OK == xResult) && (CK_INVALID_HANDLE != xObjectHandle))
            {
                xResult = xFunctionList->C_DestroyObject(xSession, xObjectHandle);

                /* PKCS #11 allows a module to maintain multiple objects with the same
                 * label and type. The intent of this loop is to try to delete all of
                 * them. However, to avoid getting stuck, we won't try to find another
                 * object of the same label/type if the previous delete failed. */
                if (CKR_OK == xResult)
                {
                    xResult = xFindObjectWithLabelAndClass(xSession, (char *)pxLabelPtr,
                                                           strnlen((char *)pxLabelPtr, pkcs11configMAX_LABEL_LENGTH),
                                                           pxClass[xIndex], &xObjectHandle);
                }
                else
                {
                    break;
                }
            }
        }
    }

    return xResult;
}
/**********************************************************************************************************************
 End of function prvDestroyProvidedObjects
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: prvGenerateKeyPairEC
 * Description  : .
 * Arguments    : xSession
 *              : pcPrivateKeyLabel
 *              : pcPublicKeyLabel
 *              : xPrivateKeyHandlePtr
 *              : xPublicKeyHandlePtr
 * Return Value : .
 *********************************************************************************************************************/
static CK_RV prvGenerateKeyPairEC(CK_SESSION_HANDLE xSession,
                                  const char *pcPrivateKeyLabel,
                                  const char *pcPublicKeyLabel,
                                  CK_OBJECT_HANDLE_PTR xPrivateKeyHandlePtr,
                                  CK_OBJECT_HANDLE_PTR xPublicKeyHandlePtr)
{
    CK_RV xResult;
    CK_MECHANISM xMechanism = {CKM_EC_KEY_PAIR_GEN, NULL_PTR, 0};
    CK_FUNCTION_LIST_PTR xFunctionList;
    CK_BYTE pxEcParams[] = pkcs11DER_ENCODED_OID_P256; /* prime256v1 */
    CK_KEY_TYPE xKeyType = CKK_EC;

    CK_BBOOL xTrueObject = CK_TRUE;
    CK_ATTRIBUTE pxPublicKeyTemplate[] =
        {
            {CKA_KEY_TYPE, NULL /* &keyType */, sizeof(xKeyType)},
            {CKA_VERIFY, NULL /* &trueObject */, sizeof(xTrueObject)},
            {CKA_EC_PARAMS, NULL /* ecParams */, sizeof(pxEcParams)},
            {CKA_LABEL, (void *)pcPublicKeyLabel, strnlen(pcPublicKeyLabel, pkcs11configMAX_LABEL_LENGTH)}};

    /* Aggregate initializers must not use the address of an automatic variable. */
    pxPublicKeyTemplate[0].pValue = &xKeyType;
    pxPublicKeyTemplate[1].pValue = &xTrueObject;
    pxPublicKeyTemplate[2].pValue = &pxEcParams;

    CK_ATTRIBUTE privateKeyTemplate[] =
        {
            {CKA_KEY_TYPE, NULL /* &keyType */, sizeof(xKeyType)},
            {CKA_TOKEN, NULL /* &trueObject */, sizeof(xTrueObject)},
            {CKA_PRIVATE, NULL /* &trueObject */, sizeof(xTrueObject)},
            {CKA_SIGN, NULL /* &trueObject */, sizeof(xTrueObject)},
            {CKA_LABEL, (void *)pcPrivateKeyLabel, strnlen(pcPrivateKeyLabel, pkcs11configMAX_LABEL_LENGTH)}};

    /* Aggregate initializers must not use the address of an automatic variable. */
    privateKeyTemplate[0].pValue = &xKeyType;
    privateKeyTemplate[1].pValue = &xTrueObject;
    privateKeyTemplate[2].pValue = &xTrueObject;
    privateKeyTemplate[3].pValue = &xTrueObject;

    xResult = C_GetFunctionList(&xFunctionList);

    if (CKR_OK != xResult)
    {
        LogError(("Could not get a PKCS #11 function pointer."));
    }
    else
    {
        xResult = xFunctionList->C_GenerateKeyPair(xSession,
                                                   &xMechanism,
                                                   pxPublicKeyTemplate,
                                                   (sizeof(pxPublicKeyTemplate)) / sizeof(CK_ATTRIBUTE),
                                                   privateKeyTemplate, (sizeof(privateKeyTemplate)) / sizeof(CK_ATTRIBUTE),
                                                   xPublicKeyHandlePtr,
                                                   xPrivateKeyHandlePtr);
    }

    return xResult;
}
/**********************************************************************************************************************
 End of function prvGenerateKeyPairEC
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xGenerateKeyAndCsr
 * Description  : .
 * Arguments    : xP11Session
 *              : pcPrivKeyLabel
 *              : pcPubKeyLabel
 *              : pcCsrBuffer
 *              : xCsrBufferLength
 *              : pxOutCsrLength
 *              : pcCsrsubjectname
 * Return Value : .
 *********************************************************************************************************************/
bool xGenerateKeyAndCsr(CK_SESSION_HANDLE xP11Session,
                        const char *pcPrivKeyLabel,
                        const char *pcPubKeyLabel,
                        char *pcCsrBuffer,
                        size_t xCsrBufferLength,
                        size_t *pxOutCsrLength,
                        const char *pcCsrsubjectname)
{
    CK_OBJECT_HANDLE xPrivKeyHandle;
    CK_OBJECT_HANDLE xPubKeyHandle;
    CK_RV xPkcs11Ret = CKR_OK;
    mbedtls_pk_context xPrivKey;
    mbedtls_x509write_csr xReq;
    int32_t ulMbedtlsRet = -1;
    const mbedtls_pk_info_t *pxHeader = mbedtls_pk_info_from_type(MBEDTLS_PK_ECKEY);

    configASSERT(pcPrivKeyLabel != NULL);
    configASSERT(pcPubKeyLabel != NULL);
    configASSERT(pcCsrBuffer != NULL);
    configASSERT(pxOutCsrLength != NULL);

    xPkcs11Ret = prvGenerateKeyPairEC(xP11Session,
                                      pcPrivKeyLabel,
                                      pcPubKeyLabel,
                                      &xPrivKeyHandle,
                                      &xPubKeyHandle);

    if (CKR_OK == xPkcs11Ret)
    {
        xPkcs11Ret = xPKCS11_initMbedtlsPkContext(&xPrivKey, xP11Session, xPrivKeyHandle);
    }

    if (CKR_OK == xPkcs11Ret)
    {
        mbedtls_x509write_csr_init(&xReq);
        mbedtls_x509write_csr_set_md_alg(&xReq, MBEDTLS_MD_SHA256);

        ulMbedtlsRet = mbedtls_x509write_csr_set_key_usage(&xReq, MBEDTLS_X509_KU_DIGITAL_SIGNATURE);

        if (0 == ulMbedtlsRet)
        {
            ulMbedtlsRet = mbedtls_x509write_csr_set_ns_cert_type(&xReq, MBEDTLS_X509_NS_CERT_TYPE_SSL_CLIENT);
        }

        if (0 == ulMbedtlsRet)
        {
            ulMbedtlsRet = mbedtls_x509write_csr_set_subject_name(&xReq, pcCsrsubjectname);
        }

        if (0 == ulMbedtlsRet)
        {
            mbedtls_x509write_csr_set_key(&xReq, &xPrivKey);

            ulMbedtlsRet = mbedtls_x509write_csr_pem(&xReq, (unsigned char *)pcCsrBuffer,
                                                     xCsrBufferLength, &lPKCS11RandomCallback,
                                                     &xP11Session);
        }

        mbedtls_x509write_csr_free(&xReq);

        mbedtls_pk_free(&xPrivKey);
    }

    *pxOutCsrLength = strlen(pcCsrBuffer);

    return (0 == ulMbedtlsRet);
}
/**********************************************************************************************************************
 End of function xGenerateKeyAndCsr
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xLoadCertificate
 * Description  : .
 * Arguments    : xP11Session
 *              : pcCertificate
 *              : pcLabel
 *              : xCertificateLength
 * Return Value : .
 *********************************************************************************************************************/
bool xLoadCertificate(CK_SESSION_HANDLE xP11Session,
                      const char *pcCertificate,
                      const char *pcLabel,
                      size_t xCertificateLength)
{
    PKCS11_CertificateTemplate_t xCertificateTemplate;
    CK_OBJECT_CLASS xCertificateClass = CKO_CERTIFICATE;
    CK_CERTIFICATE_TYPE xCertificateType = CKC_X_509;
    CK_FUNCTION_LIST_PTR xFunctionList = NULL;
    CK_RV xResult = CKR_OK;
    uint8_t *pucDerObject = NULL;
    int32_t ulConversion = 0;
    size_t xDerLen = 0;
    CK_BBOOL xTokenStorage = CK_TRUE;
    CK_BYTE pxSubject[] = "TestSubject";
    CK_OBJECT_HANDLE xObjectHandle = CK_INVALID_HANDLE;

    configASSERT(pcLabel != NULL);

    if (NULL == pcCertificate)
    {
        LogError(("Certificate cannot be null."));
        xResult = CKR_ATTRIBUTE_VALUE_INVALID;
    }

    if (CKR_OK == xResult)
    {
        /* Convert the certificate to DER format from PEM. The DER key should
         * be about 3/4 the size of the PEM key, so mallocing the PEM key size
         * is sufficient. */
        pucDerObject = (uint8_t *)malloc(xCertificateLength+1);
        xDerLen = xCertificateLength+1;

        if (NULL != pucDerObject)
        {
            ulConversion = convert_pem_to_der((unsigned char *)pcCertificate,
                                              xCertificateLength+1,
                                              pucDerObject, &xDerLen);

            if (0 != ulConversion)
            {
                LogError(("Failed to convert provided certificate."));
                xResult = CKR_ARGUMENTS_BAD;
            }
        }
        else
        {
            LogError(("Failed to allocate buffer for converting certificate to DER."));
            xResult = CKR_HOST_MEMORY;
        }
    }

    if (CKR_OK == xResult)
    {
        xResult = C_GetFunctionList(&xFunctionList);

        if (CKR_OK != xResult)
        {
            LogError(("Could not get a PKCS #11 function pointer."));
        }
    }

    if (CKR_OK == xResult)
    {
        /* Initialize the client certificate template. */
        xCertificateTemplate.xObjectClass.type = CKA_CLASS;
        xCertificateTemplate.xObjectClass.pValue = &xCertificateClass;
        xCertificateTemplate.xObjectClass.ulValueLen = sizeof(xCertificateClass);
        xCertificateTemplate.xSubject.type = CKA_SUBJECT;
        xCertificateTemplate.xSubject.pValue = pxSubject;
        xCertificateTemplate.xSubject.ulValueLen = strlen((const char *)pxSubject);
        xCertificateTemplate.xValue.type = CKA_VALUE;
        xCertificateTemplate.xValue.pValue = pucDerObject;
        xCertificateTemplate.xValue.ulValueLen = xDerLen;
        xCertificateTemplate.xLabel.type = CKA_LABEL;
        xCertificateTemplate.xLabel.pValue = (CK_VOID_PTR)pcLabel;
        xCertificateTemplate.xLabel.ulValueLen = strnlen(pcLabel, pkcs11configMAX_LABEL_LENGTH);
        xCertificateTemplate.xCertificateType.type = CKA_CERTIFICATE_TYPE;
        xCertificateTemplate.xCertificateType.pValue = &xCertificateType;
        xCertificateTemplate.xCertificateType.ulValueLen = sizeof(CK_CERTIFICATE_TYPE);
        xCertificateTemplate.xTokenObject.type = CKA_TOKEN;
        xCertificateTemplate.xTokenObject.pValue = &xTokenStorage;
        xCertificateTemplate.xTokenObject.ulValueLen = sizeof(xTokenStorage);

        /* Best effort clean-up of the existing object, if it exists. */
        prvDestroyProvidedObjects(xP11Session, (CK_BYTE_PTR *)&pcLabel, &xCertificateClass, 1);

        /* Create an object using the encoded client certificate. */
        LogInfo(("Writing certificate into label \"%s\".", pcLabel));

        xResult = xFunctionList->C_CreateObject(xP11Session,
                                                (CK_ATTRIBUTE_PTR)&xCertificateTemplate,
                                                (sizeof(xCertificateTemplate)) / sizeof(CK_ATTRIBUTE),
                                                &xObjectHandle);
    }

    if (NULL != pucDerObject)
    {
        free(pucDerObject);
    }

    return (CKR_OK == xResult);
}
/**********************************************************************************************************************
 End of function xLoadCertificate
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xPkcs11CloseSession
 * Description  : .
 * Argument     : xP11Session
 * Return Value : .
 *********************************************************************************************************************/
bool xPkcs11CloseSession(CK_SESSION_HANDLE xP11Session)
{
    CK_RV xResult = CKR_OK;
    CK_FUNCTION_LIST_PTR xFunctionList = NULL;

    xResult = C_GetFunctionList(&xFunctionList);

    if (CKR_OK == xResult)
    {
        xResult = xFunctionList->C_CloseSession(xP11Session);
    }

    return (CKR_OK == xResult);
}
/**********************************************************************************************************************
 End of function xPkcs11CloseSession
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: provisionPrivateECKey
 * Description  : .
 * Arguments    : session
 *              : label
 *              : mbedPkContext
 * Return Value : .
 *********************************************************************************************************************/
static CK_RV provisionPrivateECKey(CK_SESSION_HANDLE session,
                                   const char *label,
                                   mbedtls_pk_context *mbedPkContext)
{
    CK_RV result = CKR_OK;
    CK_FUNCTION_LIST_PTR functionList = NULL;
    CK_BYTE *DPtr = NULL;        /* Private value D. */
    CK_BYTE *ecParamsPtr = NULL; /* DER-encoding of an ANSI X9.62 Parameters value */
    int mbedResult = 0;
    CK_BBOOL trueObject = CK_TRUE;
    CK_KEY_TYPE privateKeyType = CKK_EC;
    CK_OBJECT_CLASS privateKeyClass = CKO_PRIVATE_KEY;
    CK_OBJECT_HANDLE objectHandle = CK_INVALID_HANDLE;
    mbedtls_ecp_keypair *keyPair = (mbedtls_ecp_keypair *)mbedPkContext->pk_ctx;

    result = C_GetFunctionList(&functionList);

    if (CKR_OK != result)
    {
        LogError(("Could not get a PKCS #11 function pointer."));
    }
    else
    {
        DPtr = (CK_BYTE *)pvPortMalloc(EC_D_LENGTH);

        if (NULL == DPtr)
        {
            result = CKR_HOST_MEMORY;
        }
    }

    if (CKR_OK == result)
    {
        mbedResult = mbedtls_mpi_write_binary(&(keyPair->d), DPtr, EC_D_LENGTH);

        if (0 != mbedResult)
        {
            LogError(("Failed to parse EC private key components."));
            result = CKR_ATTRIBUTE_VALUE_INVALID;
        }
    }

    if (CKR_OK == result)
    {
        if (MBEDTLS_ECP_DP_SECP256R1 == keyPair->grp.id)
        {
            ecParamsPtr = (const CK_BYTE *)("\x06\x08" MBEDTLS_OID_EC_GRP_SECP256R1);
        }
        else
        {
            result = CKR_CURVE_NOT_SUPPORTED;
        }
    }

    if (CKR_OK == result)
    {
        CK_ATTRIBUTE privateKeyTemplate[] =
            {
                {CKA_CLASS, NULL /* &privateKeyClass*/, sizeof(CK_OBJECT_CLASS)},
                {CKA_KEY_TYPE, NULL /* &privateKeyType*/, sizeof(CK_KEY_TYPE)},
                {CKA_LABEL, (void *)label, (CK_ULONG)strlen(label)},
                {CKA_TOKEN, NULL /* &trueObject*/, sizeof(CK_BBOOL)},
                {CKA_SIGN, NULL /* &trueObject*/, sizeof(CK_BBOOL)},
                {CKA_EC_PARAMS, NULL /* ecParamsPtr*/, EC_PARAMS_LENGTH},
                {CKA_VALUE, NULL /* DPtr*/, EC_D_LENGTH}};

        /* Aggregate initializers must not use the address of an automatic variable. */
        privateKeyTemplate[0].pValue = &privateKeyClass;
        privateKeyTemplate[1].pValue = &privateKeyType;
        privateKeyTemplate[3].pValue = &trueObject;
        privateKeyTemplate[4].pValue = &trueObject;
        privateKeyTemplate[5].pValue = ecParamsPtr;
        privateKeyTemplate[6].pValue = DPtr;

        result = functionList->C_CreateObject(session,
                                              (CK_ATTRIBUTE_PTR)&privateKeyTemplate,
                                              (sizeof(privateKeyTemplate)) / sizeof(CK_ATTRIBUTE),
                                              &objectHandle);
    }

    if (NULL != DPtr)
    {
        vPortFree(DPtr);
        DPtr = NULL;
    }

    return result;
}
/**********************************************************************************************************************
 End of function provisionPrivateECKey
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: provisionPrivateRSAKey
 * Description  : .
 * Arguments    : session
 *              : label
 *              : mbedPkContext
 * Return Value : .
 *********************************************************************************************************************/
static CK_RV provisionPrivateRSAKey(CK_SESSION_HANDLE session,
                                    const char *label,
                                    mbedtls_pk_context *mbedPkContext)
{
    CK_RV result = CKR_OK;
    CK_FUNCTION_LIST_PTR functionList = NULL;
    int mbedResult = 0;
    CK_KEY_TYPE privateKeyType = CKK_RSA;
    mbedtls_rsa_context *rsaContext = (mbedtls_rsa_context *)mbedPkContext->pk_ctx;
    CK_OBJECT_CLASS privateKeyClass = CKO_PRIVATE_KEY;
    RsaParams_t *rsaParams = NULL;
    CK_BBOOL trueObject = CK_TRUE;
    CK_OBJECT_HANDLE objectHandle = CK_INVALID_HANDLE;

    result = C_GetFunctionList(&functionList);

    if (CKR_OK != result)
    {
        LogError(("Could not get a PKCS #11 function pointer."));
    }
    else
    {
        rsaParams = (RsaParams_t *)pvPortMalloc(sizeof(RsaParams_t));

        if (NULL == rsaParams)
        {
            result = CKR_HOST_MEMORY;
        }
    }

    if (CKR_OK == result)
    {
        memset(rsaParams, 0, sizeof(RsaParams_t));

        mbedResult = mbedtls_rsa_export_raw(rsaContext,
                                            rsaParams->modulus, MODULUS_LENGTH+1,
                                            rsaParams->prime1, PRIME_1_LENGTH+1,
                                            rsaParams->prime2, PRIME_2_LENGTH+1,
                                            rsaParams->d, D_LENGTH+1,
                                            rsaParams->e, E_LENGTH+1);

        if (0 != mbedResult)
        {
            LogError(("Failed to parse RSA private key components."));
            result = CKR_ATTRIBUTE_VALUE_INVALID;
        }

        /* Export Exponent 1, Exponent 2, Coefficient. */
        mbedResult |= mbedtls_mpi_write_binary((mbedtls_mpi const *)&rsaContext->DP, rsaParams->exponent1, EXPONENT_1_LENGTH+1);
        mbedResult |= mbedtls_mpi_write_binary((mbedtls_mpi const *)&rsaContext->DQ, rsaParams->exponent2, EXPONENT_2_LENGTH+1);
        mbedResult |= mbedtls_mpi_write_binary((mbedtls_mpi const *)&rsaContext->QP, rsaParams->coefficient, COEFFICIENT_LENGTH+1);

        if (0 != mbedResult)
        {
            LogError(("Failed to parse RSA private key Chinese Remainder Theorem variables."));
            result = CKR_ATTRIBUTE_VALUE_INVALID;
        }
    }

    if (CKR_OK == result)
    {
        /* When importing the fields, the pointer is incremented by 1
         * to remove the leading 0 padding (if it existed) and the original field
         * length is used */

        CK_ATTRIBUTE privateKeyTemplate[] =
            {
                {CKA_CLASS, NULL /* &privateKeyClass */, sizeof(CK_OBJECT_CLASS)},
                {CKA_KEY_TYPE, NULL /* &privateKeyType */, sizeof(CK_KEY_TYPE)},
                {CKA_LABEL, (void *)label, (CK_ULONG)strlen(label)},
                {CKA_TOKEN, NULL /* &trueObject */, sizeof(CK_BBOOL)},
                {CKA_SIGN, NULL /* &trueObject */, sizeof(CK_BBOOL)},
                {CKA_MODULUS, rsaParams->modulus+1, MODULUS_LENGTH},
                {CKA_PRIVATE_EXPONENT, rsaParams->d+1, D_LENGTH},
                {CKA_PUBLIC_EXPONENT, rsaParams->e+1, E_LENGTH},
                {CKA_PRIME_1, rsaParams->prime1+1, PRIME_1_LENGTH},
                {CKA_PRIME_2, rsaParams->prime2+1, PRIME_2_LENGTH},
                {CKA_EXPONENT_1, rsaParams->exponent1+1, EXPONENT_1_LENGTH},
                {CKA_EXPONENT_2, rsaParams->exponent2+1, EXPONENT_2_LENGTH},
                {CKA_COEFFICIENT, rsaParams->coefficient+1, COEFFICIENT_LENGTH}};

        /* Aggregate initializers must not use the address of an automatic variable. */
        privateKeyTemplate[0].pValue = &privateKeyClass;
        privateKeyTemplate[1].pValue = &privateKeyType;
        privateKeyTemplate[3].pValue = &trueObject;
        privateKeyTemplate[4].pValue = &trueObject;

        result = functionList->C_CreateObject(session,
                                              (CK_ATTRIBUTE_PTR)&privateKeyTemplate,
                                              (sizeof(privateKeyTemplate)) / sizeof(CK_ATTRIBUTE),
                                              &objectHandle);
    }

    if (NULL != rsaParams)
    {
        vPortFree(rsaParams);
        rsaParams = NULL;
    }

    return result;
}
/**********************************************************************************************************************
 End of function provisionPrivateRSAKey
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: provisionPrivateKey
 * Description  : .
 * Arguments    : session
 *              : privateKey
 *              : privateKeyLength
 *              : label
 * Return Value : .
 *********************************************************************************************************************/
CK_RV provisionPrivateKey(CK_SESSION_HANDLE session,
                          const char *privateKey,
                          size_t privateKeyLength,
                          const char *label)
{
    CK_RV result = CKR_OK;
    mbedtls_pk_type_t mbedKeyType = MBEDTLS_PK_NONE;
    int mbedResult = 0;
    mbedtls_pk_context mbedPkContext = {0};
#if MBEDTLS_VERSION_NUMBER >= 0x03000000
    mbedtls_entropy_context xEntropyContext;
    mbedtls_ctr_drbg_context xDrbgContext;
#endif

    mbedtls_pk_init(&mbedPkContext);

/* Try parsing the private key using mbedtls_pk_parse_key. */
#if MBEDTLS_VERSION_NUMBER < 0x03000000
    mbedResult = mbedtls_pk_parse_key(&mbedPkContext, (const uint8_t *)privateKey, privateKeyLength, NULL, 0);
#else
    mbedtls_entropy_init(&xEntropyContext);
    mbedtls_ctr_drbg_init(&xDrbgContext);
    mbedResult = mbedtls_ctr_drbg_seed(&xDrbgContext, mbedtls_entropy_func, &xEntropyContext, NULL, 0);
    if (0 == mbedResult)
    {
        mbedResult = mbedtls_pk_parse_key(&mbedPkContext, (const uint8_t *)privateKey, privateKeyLength, NULL, 0,
                                          mbedtls_ctr_drbg_random, &xDrbgContext);
    }
    mbedtls_ctr_drbg_free(&xDrbgContext);
    mbedtls_entropy_free(&xEntropyContext);
#endif /* MBEDTLS_VERSION_NUMBER < 0x03000000 */

    if (0 != mbedResult)
    {
        LogError(("Unable to parse private key."));
        result = CKR_ARGUMENTS_BAD;
    }

    /* Determine whether the key to be imported is RSA or EC. */
    if (CKR_OK == result)
    {
        mbedKeyType = mbedtls_pk_get_type(&mbedPkContext);

        if (MBEDTLS_PK_RSA == mbedKeyType)
        {
            result = provisionPrivateRSAKey(session, label, &mbedPkContext);
        }
        else if ((MBEDTLS_PK_ECDSA == mbedKeyType) ||
                 (MBEDTLS_PK_ECKEY == mbedKeyType) ||
                 (MBEDTLS_PK_ECKEY_DH == mbedKeyType))
        {
            result = provisionPrivateECKey(session, label, &mbedPkContext);
        }
        else
        {
            LogError(("Invalid private key type provided. Only RSA-2048 and "
                      "EC P-256 keys are supported."));
            result = CKR_ARGUMENTS_BAD;
        }
    }

    mbedtls_pk_free(&mbedPkContext);

    return result;
}
/**********************************************************************************************************************
 End of function provisionPrivateKey
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: provisionCertificate
 * Description  : .
 * Arguments    : session
 *              : certificate
 *              : certificateLength
 *              : label
 * Return Value : .
 *********************************************************************************************************************/
CK_RV provisionCertificate(CK_SESSION_HANDLE session,
                           const char *certificate,
                           size_t certificateLength,
                           const char *label)
{
    PKCS11_CertificateTemplate_t certificateTemplate;
    CK_OBJECT_CLASS certificateClass = CKO_CERTIFICATE;
    CK_CERTIFICATE_TYPE certificateType = CKC_X_509;
    CK_FUNCTION_LIST_PTR functionList = NULL;
    CK_RV result = CKR_OK;
    uint8_t *derObject = NULL;
    int32_t conversion = 0;
    size_t derLen = 0;
    CK_BBOOL tokenStorage = CK_TRUE;
    CK_BYTE subject[] = "TestSubject";
    CK_OBJECT_HANDLE objectHandle = CK_INVALID_HANDLE;

    /* Initialize the client certificate template. */
    certificateTemplate.xObjectClass.type = CKA_CLASS;
    certificateTemplate.xObjectClass.pValue = &certificateClass;
    certificateTemplate.xObjectClass.ulValueLen = sizeof(certificateClass);
    certificateTemplate.xSubject.type = CKA_SUBJECT;
    certificateTemplate.xSubject.pValue = subject;
    certificateTemplate.xSubject.ulValueLen = strlen((const char *)subject);
    certificateTemplate.xValue.type = CKA_VALUE;
    certificateTemplate.xValue.pValue = (CK_VOID_PTR)certificate;
    certificateTemplate.xValue.ulValueLen = (CK_ULONG)certificateLength;
    certificateTemplate.xLabel.type = CKA_LABEL;
    certificateTemplate.xLabel.pValue = (CK_VOID_PTR)label;
    certificateTemplate.xLabel.ulValueLen = strlen(label);
    certificateTemplate.xCertificateType.type = CKA_CERTIFICATE_TYPE;
    certificateTemplate.xCertificateType.pValue = &certificateType;
    certificateTemplate.xCertificateType.ulValueLen = sizeof(CK_CERTIFICATE_TYPE);
    certificateTemplate.xTokenObject.type = CKA_TOKEN;
    certificateTemplate.xTokenObject.pValue = &tokenStorage;
    certificateTemplate.xTokenObject.ulValueLen = sizeof(tokenStorage);

    if (NULL == certificate)
    {
        LogError(("Certificate cannot be null."));
        result = CKR_ATTRIBUTE_VALUE_INVALID;
    }

    if (CKR_OK == result)
    {
        result = C_GetFunctionList(&functionList);

        if (CKR_OK != result)
        {
            LogError(("Could not get a PKCS #11 function pointer."));
        }
    }

    if (CKR_OK == result)
    {
        /* Convert the certificate to DER format from PEM. The DER key should
         * be about 3/4 the size of the PEM key, so mallocing the PEM key size
         * is sufficient. */
        derObject = (uint8_t *)pvPortMalloc(certificateTemplate.xValue.ulValueLen);
        derLen = certificateTemplate.xValue.ulValueLen;

        if (NULL != derObject)
        {
            conversion = convert_pem_to_der((unsigned char *)certificateTemplate.xValue.pValue,
                                            certificateTemplate.xValue.ulValueLen,
                                            derObject, &derLen);

            if (0 != conversion)
            {
                LogError(("Failed to convert provided certificate."));
                result = CKR_ARGUMENTS_BAD;
            }
        }
        else
        {
            LogError(("Failed to allocate buffer for converting certificate to DER."));
            result = CKR_HOST_MEMORY;
        }
    }

    if (CKR_OK == result)
    {
        /* Set the template pointers to refer to the DER converted objects. */
        certificateTemplate.xValue.pValue = derObject;
        certificateTemplate.xValue.ulValueLen = derLen;

        /* Best effort clean-up of the existing object, if it exists. */
        prvDestroyProvidedObjects(session, (CK_BYTE_PTR *)&label, &certificateClass, 1);

        /* Create an object using the encoded client certificate. */
        /* LogInfo( ( "Writing certificate into label \"%s\".", label ) ); */

        result = functionList->C_CreateObject(session,
                                              (CK_ATTRIBUTE_PTR)&certificateTemplate,
                                              (sizeof(certificateTemplate)) / sizeof(CK_ATTRIBUTE),
                                              &objectHandle);
    }

    if (NULL != derObject)
    {
        vPortFree(derObject);
        derObject = NULL;
    }

    return result;
}
/**********************************************************************************************************************
 End of function provisionCertificate
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xLoadClaimCredentials
 * Description  : .
 * Arguments    : xP11Session
 *              : pClaimCert
 *              : ClaimCertLength
 *              : pClaimPrivKey
 *              : ClaimPrivKeyLength
 * Return Value : .
 *********************************************************************************************************************/
bool xLoadClaimCredentials(CK_SESSION_HANDLE xP11Session,
                           const char *pClaimCert,
                           size_t ClaimCertLength,
                           const char *pClaimPrivKey,
                           size_t ClaimPrivKeyLength)
{
    bool status;
    CK_RV ret;

    assert(pClaimCert != NULL);
    assert(ClaimCertLength != 0);
    assert(pClaimPrivKey != NULL);
    assert(ClaimPrivKeyLength != 0);

    status = true;

    if (true == status)
    {
        ret = provisionPrivateKey(xP11Session, pClaimPrivKey,
                                  ClaimPrivKeyLength, /* MbedTLS includes null character in length for PEM objects. */
                                  pkcs11configLABEL_CLAIM_PRIVATE_KEY);
        status = (CKR_OK == ret);
    }

    if (true == status)
    {
        ret = provisionCertificate(xP11Session, pClaimCert,
                                   ClaimCertLength, /* MbedTLS includes null character in length for PEM objects. */
                                   pkcs11configLABEL_CLAIM_CERTIFICATE);
        status = (CKR_OK == ret);
    }

    return status;
}
/**********************************************************************************************************************
 End of function xLoadClaimCredentials
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xGetCertificateAndKeyState
 * Description  : .
 * Arguments    : xP11Session
 *              : pxClientCertificate
 *              : pxPrivateKey
 * Return Value : .
 *********************************************************************************************************************/
CK_RV xGetCertificateAndKeyState(CK_SESSION_HANDLE xP11Session,
                                 CK_OBJECT_HANDLE_PTR pxClientCertificate,
                                 CK_OBJECT_HANDLE_PTR pxPrivateKey)
{
    CK_RV xResult;
    CK_FUNCTION_LIST_PTR pxFunctionList;

    xResult = C_GetFunctionList(&pxFunctionList);

    /* Check for a private key. */
    if (CKR_OK == xResult)
    {
        xResult = xFindObjectWithLabelAndClass(xP11Session,
                                               pkcs11configLABEL_DEVICE_PRIVATE_KEY_FOR_TLS,
                                               (sizeof(pkcs11configLABEL_DEVICE_PRIVATE_KEY_FOR_TLS)) - 1,
                                               CKO_PRIVATE_KEY,
                                               pxPrivateKey);
    }

    /* Check for the client certificate. */
    if (CKR_OK == xResult)
    {
        xResult = xFindObjectWithLabelAndClass(xP11Session,
                                               pkcs11configLABEL_DEVICE_CERTIFICATE_FOR_TLS,
                                               (sizeof(pkcs11configLABEL_DEVICE_CERTIFICATE_FOR_TLS)) - 1,
                                               CKO_CERTIFICATE,
                                               pxClientCertificate);
    }

    return xResult;
}
/**********************************************************************************************************************
 End of function xGetCertificateAndKeyState
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/

/**********************************************************************************************************************
 * Function Name: xDestroyCertificateAndKey
 * Description  : .
 * Argument     : xP11Session
 * Return Value : .
 *********************************************************************************************************************/
CK_RV xDestroyCertificateAndKey(CK_SESSION_HANDLE xP11Session)
{
    CK_RV xResult;
    CK_FUNCTION_LIST_PTR pxFunctionList;
    CK_OBJECT_CLASS certificateClass = CKO_CERTIFICATE;
    CK_OBJECT_CLASS privatekeyClass = CKO_PRIVATE_KEY;
    CK_OBJECT_CLASS publickeyClass = CKO_PUBLIC_KEY;

    xResult = C_GetFunctionList(&pxFunctionList);

    /* Destroy for a private key. */
    if (CKR_OK == xResult)
    {
        prvDestroyProvidedObjects(xP11Session, (CK_BYTE_PTR *)pkcs11configLABEL_DEVICE_PRIVATE_KEY_FOR_TLS, &privatekeyClass, 1);
    }

    /* Destroy for a public key. */
    if (CKR_OK == xResult)
    {
        prvDestroyProvidedObjects(xP11Session, (CK_BYTE_PTR *)pkcs11configLABEL_DEVICE_PUBLIC_KEY_FOR_TLS, &publickeyClass, 1);
    }

    /* Destroy for the client certificate. */
    if (CKR_OK == xResult)
    {
        prvDestroyProvidedObjects(xP11Session, (CK_BYTE_PTR *)pkcs11configLABEL_DEVICE_CERTIFICATE_FOR_TLS, &certificateClass, 1);
    }

    return xResult;
}
/**********************************************************************************************************************
 End of function xDestroyCertificateAndKey
 *********************************************************************************************************************/

/*-----------------------------------------------------------*/
