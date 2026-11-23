/* SPDX-License-Identifier: MIT
 * Product configuration through Unity's documented public output hooks.
 */
#ifndef RX_IDT_UNITY_CONFIG_H
#define RX_IDT_UNITY_CONFIG_H

#include "rx_idt_unity_output.h"

#ifndef UNITY_OUTPUT_CHAR
    #define UNITY_OUTPUT_CHAR( character ) RxIdt_UnityOutputChar( character )
#endif
#ifndef UNITY_OUTPUT_FLUSH
    #define UNITY_OUTPUT_FLUSH() RxIdt_UnityOutputFlush()
#endif
#ifndef UNITY_OUTPUT_START
    #define UNITY_OUTPUT_START() RxIdt_UnityOutputStart()
#endif
#ifndef UNITY_OUTPUT_COMPLETE
    #define UNITY_OUTPUT_COMPLETE() RxIdt_UnityOutputComplete()
#endif

#endif
