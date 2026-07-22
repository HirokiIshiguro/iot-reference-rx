/*
 * Build-time Fleet Provisioning configuration for EK-RX671 + Type 1YN.
 *
 * Credential-bearing values live only in rx671_fleet_config_local.h.  The
 * build helper generates that ignored file and enables it with
 * RX671_FLEET_USE_LOCAL_CONFIG.
 */
#ifndef RX671_FLEET_CONFIG_H_
#define RX671_FLEET_CONFIG_H_

#if defined(RX671_FLEET_USE_LOCAL_CONFIG)
#include "rx671_fleet_config_local.h"
#endif

#ifndef RX671_FLEET_PROVISIONING_ENABLE
#define RX671_FLEET_PROVISIONING_ENABLE       (0)
#endif

#ifndef RX671_FLEET_ENDPOINT
#define RX671_FLEET_ENDPOINT                  ""
#endif

#ifndef RX671_FLEET_TEMPLATE_NAME
#define RX671_FLEET_TEMPLATE_NAME             ""
#endif

#ifndef RX671_FLEET_CLAIM_CERTIFICATE_PEM
#define RX671_FLEET_CLAIM_CERTIFICATE_PEM     ""
#endif

#ifndef RX671_FLEET_CLAIM_PRIVATE_KEY_PEM
#define RX671_FLEET_CLAIM_PRIVATE_KEY_PEM     ""
#endif

#endif /* RX671_FLEET_CONFIG_H_ */
