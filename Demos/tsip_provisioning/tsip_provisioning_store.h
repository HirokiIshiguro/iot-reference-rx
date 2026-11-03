/*
 * Runtime accessors for TSIP provisioning blobs stored in littlefs.
 */

#ifndef TSIP_PROVISIONING_STORE_H_
#define TSIP_PROVISIONING_STORE_H_

#include <stdint.h>

#include "FreeRTOS.h"

#define TSIP_PROVISIONING_ROOT_CA_SIGNATURE_SIZE        (256U)

typedef enum TsipProvisioningSlot
{
    TSIP_PROVISIONING_SLOT_ROOT_CA_SIGNATURE = 0,
    TSIP_PROVISIONING_SLOT_ROOT_SIGNER_PUBLIC_KEY,
    TSIP_PROVISIONING_SLOT_CLIENT_PUBLIC_KEY,
    TSIP_PROVISIONING_SLOT_CLIENT_PRIVATE_KEY,
    TSIP_PROVISIONING_SLOT_ROOT_CA_DER,
    TSIP_PROVISIONING_SLOT_COUNT
} TsipProvisioningSlot_t;

const char * pcTsipProvisioningSlotCliName(TsipProvisioningSlot_t xSlot);
const char * pcTsipProvisioningSlotStorageName(TsipProvisioningSlot_t xSlot);
uint32_t ulTsipProvisioningSlotExpectedSize(TsipProvisioningSlot_t xSlot);
uint32_t ulTsipProvisioningGetStoredLength(TsipProvisioningSlot_t xSlot);
BaseType_t xTsipProvisioningReadSlot(TsipProvisioningSlot_t xSlot,
                                     uint8_t * pucBuffer,
                                     uint32_t ulBufferSize,
                                     uint32_t * pulActualSize);
void vTsipProvisioningEraseSlot(TsipProvisioningSlot_t xSlot);

BaseType_t xTsipProvisioningReadRootCaSignature(uint8_t * pucBuffer,
                                                uint32_t ulBufferSize,
                                                uint32_t * pulActualSize);
BaseType_t xTsipProvisioningPrepareTlsRootCaTrustAnchor(void);
BaseType_t xTsipProvisioningLoadClientRsa2048KeyPair(void);

#endif /* TSIP_PROVISIONING_STORE_H_ */
