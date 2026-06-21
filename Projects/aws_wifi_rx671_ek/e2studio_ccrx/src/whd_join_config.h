/*
 * Local WHD bring-up configuration.
 *
 * Keep real access-point credentials out of git. For an AP JOIN run, set these
 * values locally or pass equivalent compiler defines in e2 studio.
 */
#ifndef WHD_JOIN_CONFIG_H_
#define WHD_JOIN_CONFIG_H_

#include "whd_types.h"

#if defined(WHD_JOIN_USE_LOCAL_CONFIG)
#include "whd_join_config_local.h"
#endif

#ifndef WHD_BRINGUP_ENABLE
#define WHD_BRINGUP_ENABLE             (1)
#endif

#ifndef WHD_JOIN_ENABLE
#define WHD_JOIN_ENABLE                (0)
#endif

#ifndef WHD_SCAN_ENABLE
#define WHD_SCAN_ENABLE                (1)
#endif

#ifndef WHD_SCAN_RESULT_LIMIT
#define WHD_SCAN_RESULT_LIMIT          (32U)
#endif

#ifndef WHD_JOIN_SSID
#define WHD_JOIN_SSID                  ""
#endif

#ifndef WHD_JOIN_PASSPHRASE
#define WHD_JOIN_PASSPHRASE            ""
#endif

#ifndef WHD_JOIN_SECURITY
#define WHD_JOIN_SECURITY              WHD_SECURITY_WPA2_AES_PSK
#endif

#ifndef WHD_JOIN_USE_SCAN_RESULT
#define WHD_JOIN_USE_SCAN_RESULT       (1)
#endif

#ifndef WHD_SDIO_SOFTIRQ_POLL_MS
#define WHD_SDIO_SOFTIRQ_POLL_MS       (0U)
#endif

#ifndef WHD_SDIO_USE_SDHI_IRQ
#define WHD_SDIO_USE_SDHI_IRQ          (1)
#endif

#ifndef WHD_SDIO_SOFTIRQ_ALWAYS_NOTIFY
#define WHD_SDIO_SOFTIRQ_ALWAYS_NOTIFY (0)
#endif

#ifndef WHD_SDIO_DIAG_FAIL_LIMIT
#define WHD_SDIO_DIAG_FAIL_LIMIT       (16U)
#endif

#ifndef WHD_SDIO_PRE_CMD53_CLOCKS
#define WHD_SDIO_PRE_CMD53_CLOCKS      (1)
#endif

#endif /* WHD_JOIN_CONFIG_H_ */


