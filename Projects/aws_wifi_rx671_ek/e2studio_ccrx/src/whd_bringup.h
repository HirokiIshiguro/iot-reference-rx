/*
 * WHD bring-up entry point for EK-RX671 + Murata Type 1YN.
 */
#ifndef WHD_BRINGUP_H_
#define WHD_BRINGUP_H_

#include <stdbool.h>
#include <stdint.h>

#include "whd.h"

bool whd_bringup_run(void);
whd_interface_t whd_bringup_get_interface(void);
void whd_bringup_get_sta_mac(uint8_t mac[6]);

#endif /* WHD_BRINGUP_H_ */
