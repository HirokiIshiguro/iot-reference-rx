# Tracealyzer SPI Output Experiment

## Purpose

The RTT/FINE Tracealyzer experiment proved that streaming is possible, but the missed-event count remains high on AWS-connected FreeRTOS workloads. This branch starts the replacement transport: Tracealyzer Recorder bytes leave the RX72N Envision Kit through PMOD SPI and are bridged to Ethernet by GR-ROSE.

## Hardware Topology

```text
RX72N Envision Kit -> PMOD SPI -> GR-ROSE -> Ethernet -> Tracealyzer PC
```

The RX72N Envision Kit is the SPI master. GR-ROSE is the SPI slave and TCP bridge.

## Candidate PMODs

From `EnvisionKitRX72N_V1.03.bcdf`:

- PMOD1 SPI uses SCI2: `SCK2`, `SMISO2`, `SMOSI2`
- PMOD2 SPI uses SCI7: `SCK7`, `SMISO7`, `SMOSI7`

The current project already has SCI2 and SCI7 enabled as SCI channels, while `SCI_CFG_SSPI_INCLUDED` is still `0`. Do not hand-edit generated FIT code. Use Smart Configurator to switch one PMOD path to `r_sci_rx#spi` and regenerate.

Recommended first path: PMOD1 / SCI2, unless the command UART bring-up needs SCI2. If SCI2 must remain reserved, move the experiment to PMOD2 / SCI7.

## SPI Contract

- Target role: master
- Clock mode: mode 0 for first test
- Initial clock: 2 MHz
- Goal clock after signal check: 8 MHz or higher
- Frame payload: Tracealyzer stream bytes
- Downlink: Tracealyzer host commands are returned by GR-ROSE in full-duplex response frames

The shared frame header is staged under:

```text
e2studio_ccrx/src/application_code/tracealyzer_spi_transport/
```

## Implementation Stages

1. Enable SCI SSPI on the selected PMOD in Smart Configurator and regenerate.
2. Add a synthetic frame sender task that emits sequence-numbered frames.
3. Confirm GR-ROSE receives every sequence number over SPI.
4. Forward frame payload to GR-ROSE TCP and confirm PC reception.
5. Replace synthetic payload with Tracealyzer Recorder stream bytes.
6. Add downstream command polling so Tracealyzer can start/stop streaming.

## Acceptance Criteria

- No SPI sequence gaps during a 10-minute synthetic transfer.
- GR-ROSE TCP client receives the same byte count as the target reports sent.
- Tracealyzer starts streaming over TCP without RTT/J-Link.
- Missed events are materially lower than the RTT/FINE baseline.
