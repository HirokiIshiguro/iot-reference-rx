# r_sdio_rx API Draft

Date: 2026-05-30

This is a pre-hardware API sketch for a small SDIO FIT-style module for RX671.
The driver should sit above the official `r_sdhi_rx` FIT module and below any
Wi-Fi host driver port.

The goal is not to copy the retired `r_sdc_sdio_rx` module or WICED sources.
Use current BSD-3-Clause Renesas driver package material where applicable, and
keep the RX-side SDIO/FreeRTOS/TCP integration as the open-source deliverable.

## Current Driver Package Observation

The current `renesas/rx-driver-package` contains active `r_sdhi_rx`. It also
contains `r_sdc_sdmem_rx` public declarations for SDIO APIs such as:

- `R_SDC_SDIO_ReadDirect`
- `R_SDC_SDIO_WriteDirect`
- `R_SDC_SDIO_ReadSoftwareTrans`
- `R_SDC_SDIO_WriteSoftwareTrans`
- `R_SDC_SDIO_SetBlocklen`
- `R_SDC_SDIO_EnableInt`

However, the corresponding `src/sdio` implementation files are not present in
the checked source tree. Treat those declarations as useful API archaeology,
not as an implementation dependency.

## Layering

```text
Wi-Fi host driver port or CYW43439 experiment
  -> r_sdio_rx public API
  -> r_sdhi_rx low-level SDHI register/block/interrupt API
  -> RX671 SDHI peripheral
```

The first milestone should be an SDIO enumeration utility that can run without a
Wi-Fi driver:

```text
power rail + WL_REG_ON
  -> CMD0/CMD5/CMD3/CMD7
  -> CCCR/FBR/CIS reads
  -> 4-bit mode
  -> block-size setup
  -> DAT1/IOIRQ callback
```

## Proposed File Layout

```text
Middleware/
  sdio/
    r_sdio_rx/
      r_sdio_rx_if.h
      src/
        r_sdio_rx.c
        r_sdio_rx_cmd.c
        r_sdio_rx_cccr.c
        r_sdio_rx_cis.c
        r_sdio_rx_transfer.c
        r_sdio_rx_irq.c
        targets/
          rx671/
            r_sdio_rx_target.h

Projects/
  aws_wifi_ek_rx671_type1yn/
    e2studio_ccrx/
      src/
        r_config/
          r_sdio_rx_config.h
```

The exact project name can change when the e2 studio project is added.

## Public Types

```c
typedef enum e_sdio_status
{
    SDIO_SUCCESS = 0,
    SDIO_ERR_INVALID_ARG,
    SDIO_ERR_NOT_OPEN,
    SDIO_ERR_TIMEOUT,
    SDIO_ERR_CRC,
    SDIO_ERR_R5_COM_CRC_ERROR,
    SDIO_ERR_R5_ILLEGAL_COMMAND,
    SDIO_ERR_R5_IO_CURRENT_STATE,
    SDIO_ERR_R5_ERROR,
    SDIO_ERR_R5_FUNCTION_NUMBER,
    SDIO_ERR_R5_OUT_OF_RANGE,
    SDIO_ERR_UNSUPPORTED,
    SDIO_ERR_SDHI
} sdio_status_t;

typedef enum e_sdio_bus_width
{
    SDIO_BUS_WIDTH_1 = 1,
    SDIO_BUS_WIDTH_4 = 4
} sdio_bus_width_t;

typedef enum e_sdio_transfer_addr
{
    SDIO_ADDR_FIXED,
    SDIO_ADDR_INCREMENT
} sdio_transfer_addr_t;

typedef struct st_sdio_cfg
{
    uint32_t channel;
    uint32_t identify_hz;
    uint32_t default_hz;
    uint32_t high_speed_hz;
    void (* delay_us)(uint32_t usec);
    void (* lock)(void);
    void (* unlock)(void);
} sdio_cfg_t;

typedef struct st_sdio_cmd5_result
{
    bool card_ready;
    bool memory_present;
    uint8_t num_io_functions;
    uint32_t io_ocr;
    bool s18a;
} sdio_cmd5_result_t;

typedef void (* sdio_irq_callback_t)(uint32_t status, void * context);
```

## Public API

```c
sdio_status_t R_SDIO_Open(sdio_cfg_t const * cfg);
sdio_status_t R_SDIO_Close(void);

sdio_status_t R_SDIO_Probe(sdio_cmd5_result_t * result);
sdio_status_t R_SDIO_SelectCard(void);
sdio_status_t R_SDIO_IoReset(void);

sdio_status_t R_SDIO_ReadDirect(uint8_t function,
                                uint32_t address,
                                uint8_t * value);

sdio_status_t R_SDIO_WriteDirect(uint8_t function,
                                 uint32_t address,
                                 uint8_t value,
                                 bool read_after_write,
                                 uint8_t * readback);

sdio_status_t R_SDIO_ReadExtended(uint8_t function,
                                  uint32_t address,
                                  sdio_transfer_addr_t addr_mode,
                                  void * buffer,
                                  size_t length);

sdio_status_t R_SDIO_WriteExtended(uint8_t function,
                                   uint32_t address,
                                   sdio_transfer_addr_t addr_mode,
                                   void const * buffer,
                                   size_t length);

sdio_status_t R_SDIO_SetBlockSize(uint8_t function, uint16_t block_size);
sdio_status_t R_SDIO_EnableFunction(uint8_t function);
sdio_status_t R_SDIO_DisableFunction(uint8_t function);
sdio_status_t R_SDIO_WaitFunctionReady(uint8_t function, uint32_t timeout_ms);

sdio_status_t R_SDIO_SetBusWidth(sdio_bus_width_t width);
sdio_status_t R_SDIO_SetHighSpeed(bool enable);

sdio_status_t R_SDIO_EnableIoInterrupt(uint8_t function, bool enable);
sdio_status_t R_SDIO_RegisterIrqCallback(sdio_irq_callback_t cb, void * context);
sdio_status_t R_SDIO_ReadCis(uint8_t function, void * buffer, size_t buffer_len);
```

Keep the first implementation synchronous. Add DMA/DTC hooks only after the
single-threaded command path is proven on a logic analyzer.

## SDIO Command Responsibilities

| API | SDIO command(s) | Notes |
|---|---|---|
| `R_SDIO_Probe` | `CMD0`, `CMD5`, `CMD3`, `CMD7` | Parse R4 and RCA/select state. |
| `R_SDIO_ReadDirect` | `CMD52` | Function 0 register reads and simple F1/F2 reads. |
| `R_SDIO_WriteDirect` | `CMD52` | Supports RAW/read-after-write mode. |
| `R_SDIO_ReadExtended` | `CMD53` | Byte or block mode selected internally from length/block size. |
| `R_SDIO_WriteExtended` | `CMD53` | Fixed/incrementing address selectable. |
| `R_SDIO_SetBusWidth` | `CMD52` | Writes CCCR bus interface control. |
| `R_SDIO_SetHighSpeed` | `CMD52` | Reads/writes CCCR speed control. |
| `R_SDIO_EnableIoInterrupt` | `CMD52` + SDHI IOIRQ | Enables CCCR interrupt bits and SDHI SDIO interrupt mask. |

## Initial CCCR/FBR Constants

The implementation should define only the minimum constants first:

```c
#define SDIO_CCCR_REV             (0x00u)
#define SDIO_CCCR_SDREV           (0x01u)
#define SDIO_CCCR_IOEN            (0x02u)
#define SDIO_CCCR_IORDY           (0x03u)
#define SDIO_CCCR_INTEN           (0x04u)
#define SDIO_CCCR_INTPEND         (0x05u)
#define SDIO_CCCR_IOABORT         (0x06u)
#define SDIO_CCCR_BICTRL          (0x07u)
#define SDIO_CCCR_CAPS            (0x08u)
#define SDIO_CCCR_CISPTR_0        (0x09u)
#define SDIO_CCCR_CISPTR_1        (0x0au)
#define SDIO_CCCR_CISPTR_2        (0x0bu)
#define SDIO_CCCR_F0_BLKSIZE_0    (0x10u)
#define SDIO_CCCR_F0_BLKSIZE_1    (0x11u)
#define SDIO_CCCR_POWER_CONTROL   (0x12u)
#define SDIO_CCCR_SPEED_CONTROL   (0x13u)
```

Function-specific FBR offsets are based at `0x100 * function`.

## Bring-up Test Plan

### Host Unit Tests

These tests can run before hardware exists, using a mock SDHI backend.

| Test | Purpose |
|---|---|
| CMD52 argument encode/decode | Verify R/W flag, function, RAW flag, 17-bit address, and write data placement. |
| CMD53 argument encode/decode | Verify block/byte mode, fixed/increment address, function, address, and count placement. |
| CMD5 R4 parser | Verify ready bit, function count, memory-present bit, S18A, and OCR parsing. |
| R5 status parser | Map SDIO R5 error bits to `sdio_status_t`. |
| CCCR function enable sequence | Write IOEN, poll IORDY, timeout if ready never appears. |
| Bus width sequence | Read-modify-write CCCR bus interface control for 1-bit and 4-bit. |
| High-speed sequence | Require support bit before setting the high-speed enable bit. |
| Block-size sequence | Write low/high block-size bytes for function 0/1/2. |
| IOIRQ callback | Mock SDHI SDIO status and confirm callback dispatch and clear behavior. |

### Hardware Smoke Tests

Run these before connecting a Wi-Fi host driver:

1. Power-only firmware: enable +3V3_SD, keep WL_REG_ON low, verify no
   overcurrent.
2. Identification firmware: raise WL_REG_ON, issue `CMD0` and `CMD5`, print R4.
3. Selection firmware: complete `CMD3`/`CMD7`.
4. CCCR dump: read function 0 registers `0x00..0x13`.
5. Function scan: read FBR/CIS pointers for available functions.
6. Bus width test: switch to 4-bit at low clock and confirm analyzer decode.
7. High-speed test: switch to HS only after stable 4-bit Default Speed.
8. IRQ test: enable DAT1/IOIRQ and confirm SDHI callback path.

## Wi-Fi Driver Boundary

The RX-side port should expose a narrow bus abstraction so the selected Wi-Fi
driver can be changed later:

```c
typedef struct st_wifi_sdio_bus_ops
{
    sdio_status_t (* read8)(uint8_t function, uint32_t address, uint8_t * value);
    sdio_status_t (* write8)(uint8_t function, uint32_t address, uint8_t value);
    sdio_status_t (* read)(uint8_t function, uint32_t address, bool increment, void * buffer, size_t length);
    sdio_status_t (* write)(uint8_t function, uint32_t address, bool increment, void const * buffer, size_t length);
    sdio_status_t (* set_block_size)(uint8_t function, uint16_t block_size);
    sdio_status_t (* enable_irq)(uint8_t function, sdio_irq_callback_t cb, void * context);
} wifi_sdio_bus_ops_t;
```

If Infineon WHD is used later, do not vendor WHD/WICED sources into this
repository. Keep WHD as an optional official submodule with EULA notice, and
make this bus/RTOS/TCP integration layer the repository-owned code.

## Open Questions For Hardware

- Does EK-RX671 U12 supply enough current for Type 1YN startup and transmit
  bursts through the microSD path?
- Does the SparkFun sniffer preserve EK-RX671 card-detect behavior?
- Are the uSD-M.2 Adapter SDIO pull-ups sufficient in 3.3 V override mode, or
  does the EK-RX671 microSD slot add pull-ups that need to be accounted for?
- Does the extra stub length from the sniffer remain stable at 50 MHz?
- Which RX671 pin should be reserved for WL_REG_ON in the first test harness?
- Should WL_HOST_WAKE be wired for early testing, or should the first pass rely
  only on SDIO DAT1 interrupts?

