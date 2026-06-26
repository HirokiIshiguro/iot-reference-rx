# SEGGER RTT control block

This directory carries the minimal SEGGER RTT source needed to expose the RTT
control block in the `aws_wifi_rx671_ek` map file for J-Link / Tracealyzer CLI
address lookup.

Source:

- `SEGGER_RTT.c`
- `include/SEGGER_RTT.h`
- `include/SEGGER_RTT_Conf.h`

The files are copied from the Percepio Tracealyzer 4.12 J-Link RTT streamport
reference tree at:

`C:\ai\codex\Tracealyzer4-JLink942\FreeRTOS\TraceRecorder\streamports\Jlink_RTT`

Only SEGGER RTT itself is linked here. Tracealyzer Recorder streamport files are
intentionally not linked by this project yet. The current purpose is to make
the CC-RX map include `__SEGGER_RTT`, which Tracealyzer CLI can use as the
RTT block address.
