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

The RX72N Envision Kit software-TLS project enables the demo. The matching TSIP
project compiles and links the shared source but leaves it disabled until TSIP's
global provisioning and handshake state has connection-safe synchronization.

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
