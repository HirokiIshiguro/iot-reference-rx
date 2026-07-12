# Persistent multi-TLS demo

This demo keeps two independent MQTT-over-TLS connections active on one MCU:

- session 1 uses the existing MQTT Agent connection;
- session 2 owns a separate coreMQTT context, network context, TLS context,
  socket, network buffer, client ID, and FreeRTOS task.

Both sessions publish to and receive from their own heartbeat topic. After an
initial overlap of at least 35 seconds, session 2 deliberately reconnects while
session 1 continues exchanging heartbeats. The demo then requires another
35-second overlap before emitting `TEST_COMPLETE`.

## Integration

Define `ENABLE_MULTI_TLS_DEMO` in the board's `demo_config.h`, add this directory
to the compiler include paths, link `multi_tls_demo.obj`, and call
`vStartMultiTlsDemo()` immediately after `vStartMQTTAgent()`.

The RX72N Envision Kit software-TLS and TSIP projects both enable the demo. The
TSIP project enables the FIT driver's official `TSIP_MULTI_THREADING` callbacks,
maps them to the same recursive mutex used across public Init/Update/Final
sequences, and reports callback balance, owner errors, and distinct task count
in `TEST_COMPLETE`. The WAIT_LOOP hook is disabled during this experiment so
the official callback behavior is measured with the driver's original polling.

Two simultaneous software-TLS handshakes exceed the original single 320 KiB
FreeRTOS heap. The software-TLS RX72N project therefore uses `heap_5` with its
existing 320 KiB lower-RAM region plus a 248 KiB region in the mapped upper-RAM
gap. The linker keeps that region below the fixed framebuffer at `0x0085E000`.

## AWS IoT policy requirement

The primary MQTT client ID is the provisioned Thing name and must be at most
128 bytes. The secondary ID is the first 123 bytes of that ID plus `-tls2`.
The attached AWS IoT policy must authorize `iot:Connect` for both client IDs and
must allow publish, subscribe, and receive access to:

```text
multi_tls/<thing-name>/session/1
multi_tls/<thing-name>/session/2
```

The repository's `tools/iot_policy.json` wildcard reference policy satisfies
this experiment contract. A production policy should grant the two explicit
client/topic resource patterns instead.

## Hardware evidence

`tools/ci/monitor_multi_tls.py` consumes the machine-readable `[MULTI_TLS]`
UART markers. Client IDs are represented by compact FNV-1a fingerprints so the
complete marker stays below the RX72N UART log limit. The monitor verifies
distinct client-ID fingerprints, network contexts, TLS contexts, and sockets;
matching TX/RX heartbeat sequences; both overlap windows; session 1 traffic
during the forced session 2 outage; and a clean session 2 reconnect.

Evidence markers use the synchronous `configPRINT_STRING` path rather than the
nonblocking general logging queue, preventing one-shot state transitions from
being silently dropped when normal application logging is busy.

The opt-in GitLab job is enabled with:

```text
RX72N_TEST_SCOPE=mqtt
RX72N_TLS_BACKEND=software
RUN_RX72N_MULTI_TLS_TEST=true
```

Use `RX72N_TLS_BACKEND=tsip` for the TSIP variant. In that mode the monitor also
requires `tsip_mt=1`, balanced non-zero lock/unlock callback counts, at least two
observed tasks, zero owner errors, and `wait_mode=polling`.

## RX72N TSIP multithreading experiment (2026-07-12)

GitLab [pipeline #7679](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/7679)
tested commit `2bb79cb4` with `TSIP_MULTI_THREADING=1` and the WAIT_LOOP hook
disabled. Build, flash, provisioning, baseline MQTT, and the multi-TLS hardware
test all passed. The multi-TLS job was then retried twice against the same
firmware and provisioned RX72N Envision Kit.

| Job | Evidence duration | Start to both sessions up | Session 2 reconnect | Lock / unlock callbacks | Tasks | Owner errors | Result |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| [#51238](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/51238) | 119.357 s | 12.901 s | 13.970 s | 1218 / 1218 | 3 | 0 | PASS |
| [#51239](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/51239) | 119.953 s | 11.703 s | 13.981 s | 1214 / 1214 | 3 | 0 | PASS |
| [#51240](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/jobs/51240) | 120.039 s | 11.293 s | 14.530 s | 1218 / 1218 | 3 | 0 | PASS |

All three runs proved distinct TLS contexts and sockets, two bounded overlap
windows, continued session 1 traffic while session 2 reconnected, balanced
official FIT callbacks, and no mutex timeout or monitor runtime failure. The
mean evidence duration was 119.783 seconds with a 0.682-second range.

For reference, the earlier polling baseline in
[pipeline #7659](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/7659)
was 125.874 seconds, while the hybrid WAIT_LOOP experiment in
[pipeline #7663](https://gitlab.saffti.jp/oss/import/github/renesas/iot-reference-rx/-/pipelines/7663)
was 121.284 seconds. These AWS-connected runs include network variation and the
baseline conditions have not yet been repeated three times, so the timing
difference is not treated as proof of a throughput improvement. This experiment
proves multithreaded correctness; CPU-load reduction still requires a separate
interrupt/sleep or trace-based measurement.
