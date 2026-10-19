# CC-RX common-code extraction and FreeRTOS context restore

The five RTOS application projects retain linker optimization `all`, including
`symbol_delete`, and exclude only `_xPortStartScheduler` and
`_vSoftwareInterruptISR` from `same_code`. These functions contain expanded
FreeRTOS assembly that switches the stack pointer and ends in `RTE`. The three
non-RTOS bootloader projects do not need this exclusion.

## Observed failure and controlled comparison

The RX671 maintenance image did not produce its source witness after startup.
A diagnostic stopped at the main task entry, before TraceEnable, storage, or
provisioning. The same C source and compiler options gave these results:

| Linker setting | Linked restore | RX671 observation |
| --- | --- | --- |
| `all`, no exclusion | `BSR.A` into a common helper ending in `RTE` | 0 UART bytes in 45 seconds |
| `speed` (omit only `same_code`) | Inline context restore | Complete 156-byte task-entry frame |
| `all`, two function exclusions | Inline context restore; common helpers remain elsewhere | Complete 156-byte task-entry frame |

In the failing binary, the flag had already been popped before the helper call.
The helper consumed the seven accumulator/FPSW values and fifteen general
registers, but did not remove the four-byte return address added by `BSR.A`.
Its `RTE` therefore read the PC four bytes before the initialized PC slot.
The two-function exclusion restores the original inline sequence in both the
first-task and software-interrupt paths. The linked task-stack initializer was
identical across the comparison.

The narrow-setting native ABS SHA-256 was
`25c90ecdc2f5cf3e879931389a63815bb0cbecb5a443a793eabcc7ded2a48441`.
The actual RX671 receipt SHA-256 was
`ea52745fee40f103460b2e96027652b716319736f1a0c5430fdf9e4571518e02`:
SCI Open returned zero, IPL was zero, and the complete fixed frame arrived.
Program/verify, run, and final reset each completed once with exit zero; a new
one-second UART quiet interval and normal lock release were checked separately.

This establishes the RX671 diagnostic startup cause and the narrow remedy.
It does not establish normal application, TLS, OTA, benchmark, or RX72N success.
Those require their own current-source native and hardware results. The
diagnostic stop code is not part of the application change.

## Compiler and linker policy

Compiler optimization remains CC-RX's default level 2; the actual compiler
commands did not contain a level override. This is separate from linker `all`.
The supported e2 studio `samecodeForbid` string-list option produces:

```text
-samecode_forbid=_xPortStartScheduler,_vSoftwareInterruptISR
```

The static inline assembly helper names disappear after expansion, so the
exclusions name the two outer linked functions. Validate the effective map and
the actual restore instructions, rather than deciding from `_com_opt` symbol
names: those names can be reused for unrelated common sequences.

References: [default compiler level](https://tool-support.renesas.com/autoupdate/support/onlinehelp/ja-JP/csp/V8.16.00/CS%2B.chm/Compiler-CCRX.chm/Output/ccrx02c0501y0401.html),
[linker optimization categories](https://tool-support.renesas.com/autoupdate/support/onlinehelp/csp/V8.16.00/CS%2B.chm/Compiler-CCRX.chm/Output/ccrx02c0503y0401.html),
[function exclusion syntax](https://tool-support.renesas.com/autoupdate/support/onlinehelp/csp/V8.14.00/CS%2B.chm/Compiler-CCRX.chm/Output/ccrx02c0503y0405.html).

Tracked as part of [Issue 174](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/issues/174)
and [MR 227](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/merge_requests/227).
