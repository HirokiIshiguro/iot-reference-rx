/*
 * sdio_host - SDHI host bring-up for the EK-RX671 WHD project (Type 1YN /
 * CYW43439).
 *
 * Polled SDHI host on the corrected PORTD pins (CLK=PD5 / CMD=PD4 / D0-D3=
 * PD6/PD7/PD2/PD3): enumerate (CMD0/5/3/7), the r_sdio_rx CMD52 host, and the
 * CMD53 byte-mode data path (increment 4a). No SDHI interrupt is used; command
 * and data completion are polled from SDSTS1/2 directly. This is the same host
 * layer the WHD bus backend will call.
 *
 * The CMD53 byte data path needs the Broadcom backplane clocks *forced* on
 * (sdio_host_brcm_force_clocks) - requesting ALP alone leaves the data phase
 * un-clocked and the card never returns data.
 */
#ifndef SDIO_HOST_H_
#define SDIO_HOST_H_

#include <stdint.h>
#include <stdbool.h>

/* Initialize the SDHI peripheral for the SDIO identification phase (1-bit bus,
 * ~400 kHz). Returns true once the SD clock is being supplied. */
bool sdio_host_init(void);

/* CMD0 then CMD5 x2 (voltage probe + window select). On success, writes the
 * 32-bit R4 response and the IO function count (R4[30:28]) and returns true;
 * returns false on a command timeout or bus error. */
bool sdio_host_first_contact(uint32_t * p_r4, uint8_t * p_func_count);

/* CMD3 (SEND_RELATIVE_ADDR) then CMD7 (SELECT_CARD): read the card's relative
 * address (R6[31:16]) and move it to the transfer state. Writes the RCA and
 * returns true on success. Call after sdio_host_first_contact() succeeds. */
bool sdio_host_select_card(uint16_t * p_rca);

/* Open the r_sdio_rx protocol layer over the SDHI CMD52 host (CMD53 is stubbed
 * for now). Call after the card is selected. Returns true on R_SDIO_Open OK. */
bool sdio_host_protocol_open(void);

/* CMD52 single-register read through r_sdio_rx (e.g. CCCR on function 0).
 * Returns true and writes *p_data on success. */
bool sdio_host_cmd52_read(uint8_t function, uint32_t address, uint8_t * p_data);

/* Enable an IO function via r_sdio_rx (CCCR IO_ENABLE + IO_READY poll). Writes
 * the IO_READY byte and returns true once the function reports ready. */
bool sdio_host_enable_function(uint8_t function, uint8_t * p_ready);

/* CMD52 single-register write through r_sdio_rx (read-after-write). Writes the
 * readback byte and returns true on success. */
bool sdio_host_cmd52_write(uint8_t function, uint32_t address, uint8_t data, uint8_t * p_readback);

/* Abort an in-flight SDIO transfer for one IO function through CCCR IO_ABORT.
 * This is intended for recovery paths after the SDHI command/data engine has
 * already been force-stopped. */
bool sdio_host_abort_function(uint8_t function);

/* Enable SDIO high speed if the card supports it (CCCR 0x13). Part of the
 * proven pre-CMD53 setup; call after F1 enable. Returns true on success. */
bool sdio_host_set_high_speed(void);

/* Set the F0/F1 SDIO block sizes (64). Part of the proven pre-CMD53 setup;
 * call after F1 enable. Returns true on success. */
bool sdio_host_set_block_size(void);

/* Reflect a CMD52 register write into the host's per-function block-size cache.
 * When the upper layer (e.g. WHD) programs a function's FBR/CCCR block-size
 * register directly via CMD52 - rather than through sdio_host_set_block_size -
 * the cache used by block-mode CMD53 would otherwise stay 0 for that function
 * and reject the transfer. Call after any CMD52 write so the cache tracks the
 * size actually programmed for every function (notably F2/WLAN). function and
 * address are the CMD52 field values; value is the byte written. */
void sdio_host_note_cmd52_write(uint8_t function, uint32_t address, uint8_t value);

/* Switch the SDIO bus to 4-bit (CCCR bus interface control + R_SDHI_SetBus)
 * before any CMD53 data transfer. Returns true on success. The 1-bit data
 * phase does not start on this board, so call this after F1 enable and before
 * backplane reads. */
bool sdio_host_set_bus_4bit(void);

/* Raise the SDHI clock from the identification divider to the configured run
 * divider before any CMD53 data transfer. The default is the Smart Configurator
 * high-speed divider (SDHI_CFG_DIV_HIGH_SPEED); define
 * SDIO_HOST_CFG_RUN_CLOCK_DIV at build time only for a sweep or fallback
 * comparison. Returns true on success. Call after switching to 4-bit and before
 * backplane reads. */
bool sdio_host_set_run_clock(void);
bool sdio_host_set_clock_div(uint32_t div);

/* Request the ALP backplane clock (F1 CHIPCLKCSR) and poll for ALP_AVAIL.
 * Writes the final CSR byte. Sets the ALP_AVAIL status bit but is NOT enough on
 * its own to clock the backplane data phase - sdio_host_brcm_force_clocks()
 * must follow. */
bool sdio_host_request_alp(uint8_t * p_csr);

/* Force the backplane clocks the way perf does before its first CMD53 read:
 * FORCE_ALP + WAKEUPCTRL(WAKE_TILL_HT) + FORCE_HT (no wait for HT_AVAIL).
 * Requesting ALP alone does not clock the backplane data phase; this is the
 * precondition the CMD53 byte read depends on. Writes the final CHIPCLKCSR
 * byte; call after sdio_host_request_alp(). */
bool sdio_host_brcm_force_clocks(uint8_t * p_csr);

/* Keep the WLAN SDIO core on (SLEEPCSR KEEP_WL_KSO) and poll for the bit to read
 * back. Writes the final SLEEPCSR byte; call before backplane reads. */
bool sdio_host_request_kso(uint8_t * p_slp);

/* Read a 32-bit little-endian word from the Broadcom backplane via the CMD53
 * byte path (increment 4a). Writes *p_value and returns true on success.
 * Reading the chipcommon base returns the chip ID, the first end-to-end test. */
bool sdio_host_backplane_read32(uint32_t address, uint32_t * p_value);

/* Read an arbitrary-length block from the Broadcom backplane via the CMD53 byte
 * path. Writes p_data[0..length-1] and returns true on success. */
bool sdio_host_backplane_read(uint32_t address, uint8_t * p_data, uint32_t length);

/* Read block_count blocks (F1 block size each) from the Broadcom backplane via
 * the CMD53 block-mode path (increment 4b). Writes p_data and returns true on
 * success. Exercises the block transfer the firmware download will use. */
bool sdio_host_backplane_read_block(uint32_t address, uint8_t * p_data, uint32_t block_count);

/* Write length bytes / block_count blocks to the Broadcom backplane via the
 * CMD53 byte / block path (increment 4c). Return true on success. */
bool sdio_host_backplane_write(uint32_t address, uint8_t * p_data, uint32_t length);
bool sdio_host_backplane_write_block(uint32_t address, uint8_t * p_data, uint32_t block_count);

/* Raw CMD53 (no backplane windowing) for the WHD SDIO bus backend: dispatch to
 * the r_sdio_rx byte / block transfer for the given function and SDIO address.
 * The WHD bus driver owns the backplane window (programmed via CMD52), so this
 * issues the CMD53 exactly as asked. count is bytes (byte mode) or blocks (block
 * mode). Writes the R5 response (p_r5 may be NULL). The primitive that
 * cyhal_sdio_bulk_transfer maps onto. */
bool sdio_host_cmd53(bool write, uint8_t function, uint32_t address, bool increment,
                     bool block_mode, uint8_t * p_data, uint32_t count, uint32_t * p_r5);

/* Prepare SOCRAM for the firmware download: halt the WLAN ARM core, reset the
 * SOCRAM core, power up the bank, and prove the SOCRAM data path with a
 * write/read-back round-trip (increment 4c-1). Returns true once it matches. */
bool sdio_host_socram_init(void);

/* Firmware download + boot (increment 4c-2, the de-risk gate): stream the
 * firmware/NVRAM blobs (resident in flash) into SOCRAM, release the WLAN ARM
 * core, and wait for the chip to come alive (HT_AVAIL + function 2 ready).
 * Writes the HT/IOR settle times (ms). Returns true on chip-alive. */
bool sdio_host_fw_download_and_boot(uint32_t * p_ht_ms, uint32_t * p_ior_ms);

/* Bring-up diagnostics for the last CMD53 byte read: the stage reached
 * (1=command, 2=BRE wait, 3=ACEND wait, 0xFF=success, 0=not entered) and the
 * SDSTS1/SDSTS2/R5 snapshot at the failure point. Any pointer may be NULL. */
void sdio_host_cmd53_diag(uint8_t * p_stage, uint32_t * p_s1, uint32_t * p_s2, uint32_t * p_r5);
void sdio_host_cmd53_diag_ext(uint8_t * p_stage, uint32_t * p_s1, uint32_t * p_s2,
                              uint32_t * p_er1, uint32_t * p_er2,
                              uint32_t * p_r5, uint32_t * p_data0);

/* CMD53 transfer-engine diagnostics. engine: 0=CPU, 1=DTC, 2=DMACA. */
void sdio_host_cmd53_xfer_diag(uint32_t * p_engine, uint32_t * p_done,
                               uint32_t * p_ok, uint32_t * p_fail,
                               uint32_t * p_fallback, uint32_t * p_error);

/* CMD53 transfer-engine fallback diagnostics. */
void sdio_host_cmd53_xfer_fallback_diag(uint32_t * p_function, uint32_t * p_disabled,
                                        uint32_t * p_small, uint32_t * p_ineligible,
                                        uint32_t * p_prepare);

#endif /* SDIO_HOST_H_ */
