# RX671 + Type 1YN SDIO Bring-up Notes

Date: 2026-05-30

This note captures the bring-up plan before the EK-RX671 board arrives. The
initial target is Wi-Fi over SDIO. Bluetooth UART/HCI wiring is intentionally
kept separate for a later phase.

## Equipment

- Renesas EK-RX671 evaluation kit.
- Embedded Artists 1YN M.2 Module, EAR00389.
- Murata uSD-M.2 Adapter, Rev B1/B2 preferred.
- SparkFun microSD Sniffer.
- Logic analyzer with at least 8 digital channels.
- Optional bench supply for the Murata adapter if the EK-RX671 microSD supply
  current margin is not enough during WLAN startup/calibration.

## References

- Renesas EK-RX671 product page:
  https://www.renesas.com/en/design-resources/boards-kits/ek-rx671
- EK-RX671 v1 User's Manual:
  https://www.renesas.com/en/document/mat/ek-rx671-v1-users-manual
- Embedded Artists 1YN M.2 Module:
  https://www.embeddedartists.com/products/1yn-m-2-module/
- Murata uSD-M.2 Adapter:
  https://www.murata.com/ja-jp/products/connectivitymodule/wi-fi-bluetooth/overview/lineup/usd-m2-adapter
- SparkFun microSD Sniffer Hookup Guide:
  https://learn.sparkfun.com/tutorials/microsd-sniffer-hookup-guide/all
- SD Association Simplified Specifications:
  https://www.sdcard.org/downloads/pls/

## Physical Signal Path

```text
RX671 SDHI
  -> EK-RX671 microSD slot J28
  -> SparkFun microSD Sniffer
  -> Murata uSD-M.2 Adapter microSD connector J4
  -> Murata adapter M.2 connector J3
  -> Embedded Artists 1YN M.2 Module
  -> Murata Type 1YN / Infineon CYW43439
```

The SDIO evaluation can be done by inserting the uSD-M.2 Adapter through the
SparkFun microSD Sniffer into EK-RX671 J28. The Bluetooth UART pins are not
part of this path and should be wired later from the Murata adapter headers.

## Voltage And Jumper Assumptions

The EK-RX671 microSD slot is a 3.3 V SDHI interface. The Murata uSD-M.2 Adapter
defaults to M.2 SDIO at 1.8 V, which is not the desired first bring-up mode for
EK-RX671.

Use the Murata adapter 3.3 V override configuration for the first RX671 test:

| Item | Setting | Reason |
|---|---:|---|
| Murata J12 | pins 2-3 | Sets M.2 VDDIO override to 3.3 V. |
| Murata J13 | pins 1-2 | Host I/O remains 3.3 V. |
| Murata J1 | pins 2-3 initially | Power from EK-RX671 microSD VDD, unless current margin is insufficient. |
| Murata J11 | installed for Wi-Fi-only tests | Holds BT_REG_ON low and reduces Bluetooth-side variables. Remove for BLE work. |
| EK-RX671 S4 pin 3 | ON | Selects microSD through the EK-RX671 bus switches. |
| EK-RX671 S4 pin 4 | ON | Selects microSD through the EK-RX671 bus switches. |

The Embedded Artists 1YN M.2 datasheet states that 3.3 V VDDIO override supports
DS and HS SDIO modes. Keep the first software target to Default Speed and High
Speed. Do not attempt SDR12, SDR25, or DDR50 during initial RX671 bring-up.

If the module resets or the EK-RX671 reports overcurrent during WLAN startup,
switch the Murata adapter to an external power option:

- Move Murata J1 to pins 1-2 for USB/J7 power, or remove J1 and feed J5 pin 16
  with 3.3 V and J5 pin 15 with GND as documented by Murata.
- Keep grounds common between EK-RX671, the adapter, the logic analyzer, and
  the external supply.
- Confirm the 3.3 V rail does not dip more than the module allows during
  startup calibration and transmit bursts.

## SDIO Pin Map

| SDIO signal | EK-RX671 microSD J28 | RX671 port | SparkFun sniffer label | Murata adapter J4 | M.2 J3 / 1YN side |
|---|---:|---|---|---:|---|
| DAT2 | J28-1 | PD2 / SDHI_D2-B | DAT2 | J4-1 | J3-17 / USD_DATA2_M2 |
| DAT3 | J28-2 | PD3 / SDHI_D3-B | CD/DAT3 | J4-2 | J3-19 / USD_DATA3_M2 |
| CMD | J28-3 | PD4 / SDHI_CMD-B | CMD | J4-3 | J3-11 / USD_CMD_M2 |
| VDD | J28-4 | +3V3_SD | VDD/VCC | J4-4 | Adapter power input |
| CLK | J28-5 | PD5 / SDHI_CLK-B | CLK | J4-5 | J3-9 / USD_CLK_M2 |
| GND | J28-6 | GND | GND | J4-6 | GND |
| DAT0 | J28-7 | PD6 / SDHI_D0-B | DAT0 | J4-7 | J3-13 / USD_DATA0_M2 |
| DAT1 / SDIO IRQ | J28-8 | PD7 / SDHI_D1-B | DAT1 | J4-8 | J3-15 / USD_DATA1_M2 |
| Card detect SW_A | J28-9 | GND | CD switch | n/a | n/a |
| Card detect SW_B | J28-10 | P81 / SDHI_CD | CD switch | n/a | n/a |

Before relying on card-detect logic, confirm whether the SparkFun sniffer plus
Murata adapter mechanically closes EK-RX671 J28 SW_A/SW_B. If not, either drive
P81 to the expected state or bypass card-detect in the SDIO probe build.

## Control And Wake Signals

These are outside the microSD SDIO path but matter for Wi-Fi power-up.

| Signal | Murata adapter access | Direction | Initial handling |
|---|---|---|---|
| WL_REG_ON | J9 pin 3 / M.2 J3-56 | Host to module | Hold low while rails settle, then drive high. |
| WL_HOST_WAKE | J9 pin 5 / M.2 J3-21 | Module to host | Optional OOB IRQ. SDIO DAT1 IRQ should be enough for first probe. |
| WL_DEV_WAKE | J9 pin 7 / M.2 J3-66 | Host to module | Leave inactive unless the selected Wi-Fi driver requires it. |
| BT_REG_ON | J9 pin 4 / M.2 J3-54 | Host to module | Keep low via J11 for Wi-Fi-only tests. |
| BT UART TX/RX | J9 pins 1/2 | Module/host UART | Leave unconnected for first Wi-Fi bring-up. |
| BT UART RTS/CTS | J8 pins 3/4 | UART flow control | Wire later for BLE/HCI phase. |

Power sequencing from the 1YN M.2 datasheet:

- The 3.3 V supply ramp should be slower than 40 us and faster than 100 ms.
- Keep WL_REG_ON and BT_REG_ON low for at least 700 us after the rail reaches
  the valid range.
- Ensure at least two 32.768 kHz sleep-clock cycles have passed before raising
  WL_REG_ON or BT_REG_ON. The Murata adapter provides the sleep clock in the
  normal configuration.

## Logic Analyzer Plan

Minimum channels:

| Analyzer channel | Probe |
|---:|---|
| 0 | CLK |
| 1 | CMD |
| 2 | DAT0 |
| 3 | DAT1 / SDIO IRQ |
| 4 | DAT2 |
| 5 | DAT3 |
| 6 | WL_REG_ON |
| 7 | +3V3_SD enable or module 3.3 V presence |

Useful extra channels:

- P81 / SDHI_CD.
- P51 / +3V3_SD supply enable.
- P73 / overcurrent detect.
- WL_HOST_WAKE.
- BT_REG_ON when BLE wiring starts.

Probe locations:

- Use the SparkFun microSD Sniffer for the first low-speed enumeration captures.
- For 25 MHz or 50 MHz captures, prefer the Murata adapter or 1YN M.2 test
  points if practical, and keep ground leads very short.
- The 1YN M.2 module test point order is documented as:
  `SDIO_CLK`, `SDIO_CMD`, `SDIO_DATA2`, `SDIO_DATA0`, `SDIO_DATA3`,
  `SDIO_DATA1`.

Sample-rate guidance:

| SDIO phase | Clock | Analyzer sample rate |
|---|---:|---:|
| Identification | 400 kHz | 10 MS/s or higher |
| Default Speed | up to 25 MHz | 100 MS/s minimum, 200 MS/s preferred |
| High Speed | up to 50 MHz | 200 MS/s minimum, 500 MS/s preferred |

The SparkFun sniffer is convenient but adds stubs and capacitance. If 50 MHz
capture or operation is unstable, repeat the test without the sniffer or slow
the SDIO clock until the software stack is proven.

## Expected First Capture

The first useful capture should show this coarse sequence:

1. `+3V3_SD` becomes valid after firmware enables EK-RX671 U12 through P51.
2. `WL_REG_ON` remains low for the guard time, then rises.
3. SDIO clock starts at identification speed.
4. Host sends `CMD0`.
5. Host sends `CMD5` repeatedly until R4 reports card ready.
6. Host assigns/selects RCA with `CMD3` and `CMD7`.
7. Host uses `CMD52` to read CCCR/FBR and configure function enable, bus width,
   interrupt enable, and block sizes.
8. Host may switch to 4-bit mode and High Speed.
9. Host uses `CMD53` for larger transfers.

For Wi-Fi driver bring-up, stop at known-good CCCR/FBR/CIS reads before trying
firmware download. That creates a clean hardware/software boundary.

## Initial Bring-up Checklist

### Before Power

- Confirm EK-RX671 S4 pin 3 and pin 4 are ON for microSD selection.
- Confirm QSPI/SDRAM examples are not being used in the same firmware image.
- Confirm Murata J12 is pins 2-3 for 3.3 V override.
- Confirm Murata J13 is pins 1-2 for 3.3 V host I/O.
- Confirm Murata J11 is installed for Wi-Fi-only tests.
- Confirm logic analyzer threshold is set for 3.3 V CMOS.
- Confirm all grounds are common.

### Power-only Test

- Build firmware that only enables EK-RX671 U12, keeps WL_REG_ON low, and does
  not start SDHI.
- Measure +3V3_SD at the sniffer/adapter.
- Confirm Murata adapter power LED behavior.
- Confirm no overcurrent signal on P73.

### SDIO Identification Test

- Raise WL_REG_ON after the guard time.
- Start SDHI at identification clock.
- Capture `CMD0` and `CMD5`.
- Record the `CMD5` R4 fields: card ready, number of I/O functions, memory
  present, and I/O OCR.

### Register Access Test

- Read CCCR revision at function 0 address `0x00` with `CMD52`.
- Read I/O enable/ready registers at `0x02` and `0x03`.
- Read CIS pointer registers.
- Keep the clock slow until these reads are repeatable.

### 4-bit And High-speed Test

- Write bus interface control with `CMD52` to enable 4-bit operation.
- Confirm the analyzer decoder sees valid traffic on DAT0-DAT3.
- Enable High Speed only after stable Default Speed transfer.

### Stop Condition

Stop and capture artifacts when any of these happen:

- No response to `CMD5`.
- R5 reports a command error, function number error, or out-of-range error.
- DAT1 interrupt is stuck asserted.
- P73 overcurrent is asserted.
- The 3.3 V rail drops or resets the module.

Store the capture with firmware commit/hash, jumper settings, SDIO clock, and
whether the SparkFun sniffer was in the path.

