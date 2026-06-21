/*
 * sdio_host - SDHI host bring-up. See sdio_host.h.
 *
 * Ported (polled subset) from the perf project's SDHI command/data path; the
 * scope_pulse / status-LED / Tracealyzer / probe-text instrumentation is left
 * out. Command and data completion are polled directly from SDSTS1/SDSTS2 - no
 * SDHI ISR is registered.
 *
 * The CMD53 byte-mode data phase works once the Broadcom backplane clocks are
 * *forced* on (FORCE_ALP / WAKEUPCTRL / FORCE_HT - see sdio_host_brcm_force_
 * clocks). Requesting ALP alone sets the ALP_AVAIL status bit but does not run
 * the backplane data clock, so the card ACKs CMD53 yet never clocks data into
 * the SDHI buffer (SDSTS2 stuck at CBSY, SDSTS2.RE never asserts). Verified
 * byte-for-byte against a known-good perf run on this bench.
 */
#include <stdint.h>
#include <stdbool.h>

#include "platform.h"
#include "r_sdhi_rx_if.h"
#include "r_sdhi_rx_pinset.h"
#include "r_sdio_rx_if.h"
#include "sdio_host.h"

/* SDHI command-word fields not exported by r_sdhi_rx_if.h (local in the perf
 * project too). */
#define SDHI_CMDIDX_MASK        (0x3fU)
#define SDHI_SDCMD_RSP_NONE     (3U << 8)         /* no response (CMD0)        */
#define SDHI_SDCMD_RSP_R1_R5_R6_R7 (4U << 8)      /* 48-bit short (CMD52 = R5) */
#define SDHI_SDCMD_RSP_R3_R4    (7U << 8)         /* 32-bit no-CRC (CMD5)      */
#define SDHI_SDSTS1_RSPEND      (0x0001U)         /* response end              */
#define SDHI_SDSTS1_ACEND       (0x0004U)         /* command (access) end      */
#define SDHI_SDSTS2_ERR_BITS    (0x807fU)         /* all SDSTS2 error bits      */
#define SDHI_CMD_TIMEOUT        (4000000UL)       /* polling budget per wait   */
#define SDIO_R4_OCR_MASK        (0x00ffffffUL)    /* OCR voltage window in R4  */

/* CMD53 command words (index 53 = 0x35 plus the data-enable / direction bits
 * the perf project uses). Local to the perf project too; not exported by
 * r_sdhi_rx_if.h. */
#define SDHI_CMD53_SINGLE_READ  (0x1c35UL)        /* CMD53 single read         */
#define SDHI_CMD53_SINGLE_WRITE (0x0c35UL)        /* CMD53 single write        */
#define SDHI_CMD53_BLOCK_READ   (0x7c35UL)        /* CMD53 multi-block read     */
#define SDHI_CMD53_BLOCK_WRITE  (0x6c35UL)        /* CMD53 multi-block write    */

/* Block-mode read CRC handling: the CYW43439 backplane returns valid data with
 * a read-CRC error flagged; perf tolerates it (relaxed CRC). */
#define SDHI_SDSTS2_READ_CRC_ERR (SDHI_SDIMSK2_ERR1)  /* read CRC error in SDSTS2 */
#define SDHI_SDSTS2_ILLEGAL_READ_ERR (SDHI_SDIMSK2_ERR5) /* illegal SDBUFR read */
#define SDHI_SDERSTS1_RDCRCE    (0x0400U)         /* read-data CRC error (SDERSTS1) */
#define SDHI_SDSTS1_DETECT_BITS (0x0318U)         /* DAT3/CD detect latch bits  */

/* CCCR bus interface control (F0 reg 0x07) fields for the 4-bit switch. */
#define SDIO_CCCR_BUS_IF_CONTROL (0x07UL)         /* CCCR bus interface control */
#define SDIO_BUS_WIDTH_MASK     (0x03U)           /* bus width field           */
#define SDIO_BUS_WIDTH_4BIT     (0x02U)           /* 4-bit bus                 */
#define SDIO_BUS_CD_DISABLE     (0x80U)           /* disable DAT3 CD pull-up   */

/* Broadcom force-HT and WAKEUPCTRL bits (the header carries only the ALP /
 * FORCE_ALP set). perf FORCEs the clocks (not just requests ALP) before the
 * first CMD53 backplane read. */
#define SDIO_BRCM_FORCE_HT          (0x02U)       /* force the HT clock        */
#define SDIO_BRCM_WCTRL_WAKE_TILL_HT (0x02U)      /* WAKEUPCTRL: wake till HT  */
#define SDIO_BRCM_HT_AVAIL          (0x80U)       /* HT clock available (CSR)  */

/* Broadcom SLEEPCSR (F1 0x1001f) bit: keep the WLAN SDIO core on (KSO). */
#define SDIO_BRCM_SLPCSR_KEEP_WL_KSO (0x01U)

/* Broadcom backplane core addresses for the firmware-download bring-up
 * (CYW43439). The ARM (WLAN CPU) and SOCRAM cores are controlled through their
 * AI wrapper (core base + 0x100000); the firmware/RAM lives at RAM base 0. */
#define BRCM_RAM_BASE              (0x00000000UL) /* SOCRAM/firmware RAM base   */
#define BRCM_SDIOD_CORE_BASE       (0x18002000UL)
#define BRCM_ARM_CORE_BASE         (0x18003000UL)
#define BRCM_SOCSRAM_BASE          (0x18004000UL)
#define BRCM_WRAPPER_OFFSET        (0x00100000UL)
#define BRCM_ARM_WRAP_BASE         (BRCM_ARM_CORE_BASE + BRCM_WRAPPER_OFFSET)    /* 0x18103000 */
#define BRCM_SOCRAM_WRAP_BASE      (BRCM_SOCSRAM_BASE + BRCM_WRAPPER_OFFSET)     /* 0x18104000 */
#define BRCM_AI_IOCTRL_OFFSET      (0x408UL)      /* core ioctrl in wrapper     */
#define BRCM_AI_RESETCTRL_OFFSET   (0x800UL)      /* core reset ctrl in wrapper */
#define BRCM_SICF_FGC              (0x02U)        /* force gated clocks         */
#define BRCM_SICF_CLOCK_EN         (0x01U)        /* clock enable               */
#define BRCM_AIRC_RESET            (0x01U)        /* core in reset              */
#define BRCM_SOCSRAM_BANKX_INDEX   (BRCM_SOCSRAM_BASE + 0x10UL)
#define BRCM_SOCSRAM_BANKX_PDA     (BRCM_SOCSRAM_BASE + 0x44UL)

/* Firmware/NVRAM blobs, loaded into MCU flash at runtime via J-Link (kept out
 * of the repo per project policy). The download streams them into SOCRAM. */
#define SDIO_FW_BLOB_ADDR          (0xFFF00000UL) /* 43439A0.bin in flash       */
#define SDIO_FW_BLOB_SIZE          (249066UL)
#define SDIO_NVRAM_IMAGE_ADDR      (0xFFF80000UL) /* nvram_1yn.bin in flash      */
#define SDIO_NVRAM_IMAGE_SIZE      (816UL)
#define SDIO_FW_BLOCK_SIZE         (64UL)         /* F1 block size for the stream */
#define SDIO_BRCM_FUNC1_FRAMECTRL  (0x0001000dUL) /* F1 frame control            */
#define SDIO_CCCR_IO_ABORT         (0x06UL)       /* CCCR IO abort (F0)          */
#define SDIO_CCCR_IO_READY_FN2     (0x04U)        /* F2 ready bit in IO_READY    */
#define SDIO_CCCR_IO_ENABLE_FN2    (0x04U)        /* F2 enable bit in IO_ENABLE  */

static bool sdhi_can_read_crc_error_block(uint32_t sdsts2);
static bool sdhi_can_accept_read_done_error(uint32_t sdsts1, uint32_t sdsts2);

/*
 * EK-RX671 SD slot power enable. P51 drives the +3V3_SD power switch. Cycle it
 * off (1 s) then on (settle 500 ms) so the card boots from a clean power state
 * - the perf project's sd_slot_power_on() sequence. Without this the card is
 * unpowered and never answers CMD5.
 */
static void sd_slot_power_on(void)
{
    PORT5.PMR.BIT.B1 = 0U;     /* P51 as GPIO */
    PORT5.PDR.BIT.B1 = 1U;     /* output      */
    PORT5.PODR.BIT.B1 = 0U;    /* power off   */
    R_BSP_SoftwareDelay(1000U, BSP_DELAY_MILLISECS);
    PORT5.PODR.BIT.B1 = 1U;    /* power on    */
    R_BSP_SoftwareDelay(500U, BSP_DELAY_MILLISECS);
}

static uint32_t sdhi_make_cmd(uint8_t index, uint32_t response)
{
    return ((uint32_t)index & SDHI_CMDIDX_MASK) | response;
}

/* Wait until the command buffer is free (SDSTS2.CBSY == 0). */
static bool sdhi_wait_command_ready(void)
{
    uint32_t timeout = SDHI_CMD_TIMEOUT;
    uint32_t sdsts2 = 0U;

    while (0UL != timeout)
    {
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS2, &sdsts2);
        if (0U == (sdsts2 & SDHI_SDIMSK2_CBSY))
        {
            return true;
        }
        timeout--;
    }
    return false;
}

/*
 * Poll SDSTS1/SDSTS2 until the requested bits are set, an error bit appears, or
 * the budget runs out. This single helper serves every command-completion
 * (RSPEND/ACEND) and data-phase (RE/WE/ACEND) wait.
 */
static bool sdhi_wait_status(uint32_t sdsts1_mask, uint32_t sdsts2_mask,
                             uint32_t * p_sdsts1, uint32_t * p_sdsts2)
{
    uint32_t timeout = SDHI_CMD_TIMEOUT;
    uint32_t sdsts1 = 0U;
    uint32_t sdsts2 = 0U;
    bool s1_ok;
    bool s2_ok;

    while (0UL != timeout)
    {
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS1, &sdsts1);
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS2, &sdsts2);
        if (0U != (sdsts2 & SDHI_SDSTS2_ERR_BITS))
        {
            break;
        }
        s1_ok = (0U == sdsts1_mask) || (0U != (sdsts1 & sdsts1_mask));
        s2_ok = (0U == sdsts2_mask) || (0U != (sdsts2 & sdsts2_mask));
        if (s1_ok && s2_ok)
        {
            break;
        }
        timeout--;
    }

    *p_sdsts1 = sdsts1;
    *p_sdsts2 = sdsts2;
    s1_ok = (0U == sdsts1_mask) || (0U != (sdsts1 & sdsts1_mask));
    s2_ok = (0U == sdsts2_mask) || (0U != (sdsts2 & sdsts2_mask));
    return ((0UL != timeout) && (0U == (sdsts2 & SDHI_SDSTS2_ERR_BITS)) && s1_ok && s2_ok);
}

static bool sdhi_issue_command(uint8_t index, uint32_t argument, uint32_t response,
                               bool response_expected, uint32_t * p_sdsts1, uint32_t * p_sdsts2)
{
    uint32_t cmd = sdhi_make_cmd(index, response);

    /* Clear the previous response/command-end and error flags so the wait sees
     * a fresh 0->1 transition. */
    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, SDHI_SDIMSK1_TRNS_RESP, SDHI_SDIMSK2_CLEAR);

    if (!sdhi_wait_command_ready())
    {
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS1, p_sdsts1);
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS2, p_sdsts2);
        return false;
    }

    /* Writing SDCMD after SDARG launches the command. */
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDARG, argument);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDCMD, cmd);

    return sdhi_wait_status(response_expected ? SDHI_SDSTS1_RSPEND : SDHI_SDSTS1_ACEND, 0U,
                            p_sdsts1, p_sdsts2);
}

bool sdio_host_init(void)
{
    uint32_t sdclkcr = 0U;

    /* Power the SD slot before touching the SDHI peripheral. */
    sd_slot_power_on();

    R_SDHI_PinSetInit();

    if (SDHI_SUCCESS != R_SDHI_Open(SDHI_CH0))
    {
        return false;
    }

    (void)R_SDHI_SetBus(SDHI_CH0, SDHI_PORT_1BIT);
    R_SDHI_PinSetTransfer();

    /* ~400 kHz identification clock. */
    if (SDHI_SUCCESS != R_SDHI_SetClock(SDHI_CH0, SDHI_DIV_256, SDHI_CLOCK_ENABLE))
    {
        return false;
    }

    (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDCLKCR, &sdclkcr);
    return (0U != (sdclkcr & SDHI_CLOCK_MASK_SCLKEN));
}

bool sdio_host_first_contact(uint32_t * p_r4, uint8_t * p_func_count)
{
    uint32_t sdsts1 = 0U;
    uint32_t sdsts2 = 0U;
    uint32_t ocr;
    sdhi_get_resp_t resp = {0};

    if ((NULL == p_r4) || (NULL == p_func_count))
    {
        return false;
    }

    /* CMD0 GO_IDLE: reset the card to the idle state (no response). */
    R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);
    (void)sdhi_issue_command(0U, 0U, SDHI_SDCMD_RSP_NONE, false, &sdsts1, &sdsts2);
    R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);

    /* CMD5 IO_SEND_OP_COND, first call: OCR = 0 probes the supported voltage
     * window (returned in R4[23:0]). */
    if (!sdhi_issue_command(5U, 0U, SDHI_SDCMD_RSP_R3_R4, true, &sdsts1, &sdsts2))
    {
        return false;
    }
    (void)R_SDHI_GetResp(SDHI_CH0, &resp);
    ocr = resp.sdrsp10 & SDIO_R4_OCR_MASK;

    /* CMD5 second call: echo the OCR window back to select the voltage range;
     * the card returns R4 with the ready bit (31) and IO function count
     * (30:28). */
    if (!sdhi_issue_command(5U, ocr, SDHI_SDCMD_RSP_R3_R4, true, &sdsts1, &sdsts2))
    {
        return false;
    }
    (void)R_SDHI_GetResp(SDHI_CH0, &resp);

    *p_r4 = resp.sdrsp10;
    *p_func_count = (uint8_t)((resp.sdrsp10 >> 28) & 0x07U);
    return true;
}

bool sdio_host_select_card(uint16_t * p_rca)
{
    uint32_t sdsts1 = 0U;
    uint32_t sdsts2 = 0U;
    uint16_t rca;
    sdhi_get_resp_t resp = {0};

    if (NULL == p_rca)
    {
        return false;
    }

    /* CMD3 SEND_RELATIVE_ADDR: the card publishes its RCA in R6[31:16].
     * Response type 0 lets the SDHI controller auto-select the R6 response. */
    if (!sdhi_issue_command(3U, 0U, 0U, true, &sdsts1, &sdsts2))
    {
        return false;
    }
    (void)R_SDHI_GetResp(SDHI_CH0, &resp);
    rca = (uint16_t)(resp.sdrsp10 >> 16);

    /* CMD7 SELECT_CARD with the RCA: move the addressed card to the transfer
     * state (R1b). */
    if (!sdhi_issue_command(7U, ((uint32_t)rca << 16), 0U, true, &sdsts1, &sdsts2))
    {
        return false;
    }

    *p_rca = rca;
    return true;
}

/* ---- r_sdio_rx protocol layer wiring (increment 3 + 4a + 4b) ---------------
 *
 * r_sdio_rx is a pure protocol layer: it issues CMD52/CMD53 through host
 * callbacks. The CMD52 callback bridges to the polled SDHI command path above;
 * the CMD53 callback drives the data phase (SDSIZE / SDARG / CMD53 -> poll
 * BRE/BWE -> SDBUFR -> ACEND) in both byte mode (increment 4a) and block mode
 * (increment 4b, the firmware-download de-risk gate's transfer primitive). This
 * is the same host the WHD bus backend will sit on. */
static sdio_ctrl_t g_sdio_ctrl;
static sdio_cfg_t  g_sdio_cfg;

/* Host-side CMD52: build the argument, issue it, and return the R5 data byte. */
static bool sdio_cmd52_read(uint8_t function, uint32_t address, uint8_t * p_data, uint32_t * p_r5)
{
    uint32_t sdsts1 = 0U;
    uint32_t sdsts2 = 0U;
    uint32_t arg = R_SDIO_MakeCmd52Arg(false, function, address, false, 0U);
    sdhi_get_resp_t resp = {0};
    bool ok;

    ok = sdhi_issue_command(52U, arg, SDHI_SDCMD_RSP_R1_R5_R6_R7, true, &sdsts1, &sdsts2);
    (void)R_SDHI_GetResp(SDHI_CH0, &resp);
    *p_r5 = resp.sdrsp10;
    *p_data = (uint8_t)resp.sdrsp10;
    return ok;
}

static bool sdio_cmd52_write_raw(uint8_t function, uint32_t address, uint8_t data, bool raw,
                                 uint8_t * p_readback, uint32_t * p_r5)
{
    uint32_t sdsts1 = 0U;
    uint32_t sdsts2 = 0U;
    uint32_t arg = R_SDIO_MakeCmd52Arg(true, function, address, raw, data);
    sdhi_get_resp_t resp = {0};
    bool ok;

    ok = sdhi_issue_command(52U, arg, SDHI_SDCMD_RSP_R1_R5_R6_R7, true, &sdsts1, &sdsts2);
    (void)R_SDHI_GetResp(SDHI_CH0, &resp);
    *p_r5 = resp.sdrsp10;
    *p_readback = (uint8_t)resp.sdrsp10;
    return ok;
}

static sdio_err_t sdio_rx_cmd52_callback(void * p_context, sdio_cmd52_t * p_args)
{
    bool ok;
    uint32_t r5 = 0U;
    uint8_t data = 0U;

    (void)p_context;
    if (NULL == p_args)
    {
        return SDIO_ERR_NULL_PTR;
    }

    if (p_args->write)
    {
        ok = sdio_cmd52_write_raw(p_args->function, p_args->address, p_args->write_data, p_args->raw, &data, &r5);
    }
    else
    {
        ok = sdio_cmd52_read(p_args->function, p_args->address, &data, &r5);
    }

    p_args->read_data = data;
    p_args->r5 = r5;
    return ok ? SDIO_SUCCESS : SDIO_ERR_HOST;
}

/* CMD53 byte-path diagnostics (bring-up). g_cmd53_diag_stage marks how far the
 * last read got: 1 = command/R5, 2 = BRE (RE) wait, 3 = ACEND wait, 0xFF =
 * success; stage 0 means CMD53 was never entered. The SDSTS1/SDSTS2/R5 snapshot
 * is captured at the failure point so the UART log can pinpoint a stall. */
static uint8_t  g_cmd53_diag_stage = 0U;
static uint32_t g_cmd53_diag_s1 = 0U;
static uint32_t g_cmd53_diag_s2 = 0U;
static uint32_t g_cmd53_diag_er1 = 0U;
static uint32_t g_cmd53_diag_er2 = 0U;
static uint32_t g_cmd53_diag_r5 = 0U;
static uint32_t g_cmd53_diag_data0 = 0U;

/* Per-function SDIO block size (bytes), set by sdio_host_set_block_size and used
 * by the CMD53 block-mode transfer. */
static uint16_t g_sdio_block_size[SDIO_MAX_FUNCTION + 1U];

/*
 * Issue #28 force-stop: a CMD53 whose data phase never starts leaves the
 * command engine CBSY, and a busy host then silently swallows every later
 * CMD52 - including the abort the SDPCM layer would send next. Pulse SDSTOP
 * (STP) to free the controller before returning the failure.
 */
static void sdhi_cmd53_force_stop(uint32_t * p_sdsts2)
{
    uint32_t timeout = SDHI_CMD_TIMEOUT;
    uint32_t sdsts2 = 0U;

    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSTOP, SDHI_SDSTOP_SEC_ENABLE | SDHI_SDSTOP_STP_STOP);
    while (0UL != timeout)
    {
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS2, &sdsts2);
        if (0U == (sdsts2 & SDHI_SDIMSK2_CBSY))
        {
            break;
        }
        timeout--;
    }
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSTOP, SDHI_SDSTOP_INIT);
    if (NULL != p_sdsts2)
    {
        *p_sdsts2 = sdsts2;
    }
}

static void sdhi_cmd53_capture_diag(uint32_t sdsts1, uint32_t sdsts2, uint32_t r5)
{
    g_cmd53_diag_s1 = sdsts1;
    g_cmd53_diag_s2 = sdsts2;
    g_cmd53_diag_r5 = r5;
    (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDERSTS1, &g_cmd53_diag_er1);
    (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDERSTS2, &g_cmd53_diag_er2);
}

/* Launch a CMD53 and poll for the R5 response. The command word already carries
 * the index, response type, and data-direction bits, so it is written raw (not
 * built through sdhi_make_cmd). */
static bool sdhi_cmd53_issue(uint32_t arg, uint32_t cmd, uint32_t * p_r5,
                             uint32_t * p_sdsts1, uint32_t * p_sdsts2)
{
    bool ok;
    sdhi_get_resp_t resp = {0};

    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, SDHI_SDIMSK1_TRNS_RESP, SDHI_SDIMSK2_CLEAR);
    if (!sdhi_wait_command_ready())
    {
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS1, p_sdsts1);
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS2, p_sdsts2);
        return false;
    }

    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDARG, arg);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDCMD, cmd);

    ok = sdhi_wait_status(SDHI_SDSTS1_RSPEND, 0U, p_sdsts1, p_sdsts2);
    (void)R_SDHI_GetResp(SDHI_CH0, &resp);
    *p_r5 = resp.sdrsp10;
    return ok;
}

/*
 * CMD53 byte-mode read: transfer up to 512 bytes from one IO function into
 * p_data. SDSIZE holds the byte count; after the command the receive buffer
 * fills (SDSTS2.RE), then it is drained 32-bit-word at a time from SDBUFR, and
 * the transfer ends on SDSTS1.ACEND.
 */
static bool sdio_cmd53_read_bytes(uint8_t function, uint32_t address, bool increment,
                                  uint8_t * p_data, uint32_t length, uint32_t * p_r5)
{
    bool ok;
    uint32_t sdsts1 = 0U;
    uint32_t sdsts2 = 0U;
    uint32_t arg;
    uint32_t word = 0U;
    uint32_t byte_index;
    uint32_t word_index;
    uint32_t word_count = (length + 3UL) / 4UL;
    bool relaxed_read_crc = false;

    if ((0UL == length) || (512UL < length))
    {
        *p_r5 = 0U;
        return false;
    }

    arg = R_SDIO_MakeCmd53Arg(false, function, address, increment, false, length);

    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSTOP, SDHI_SDSTOP_INIT);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSIZE, length);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDIOMD, SDHI_SDIOMD_INTEN);

    g_cmd53_diag_stage = 1U;
    g_cmd53_diag_data0 = 0U;
    ok = sdhi_cmd53_issue(arg, SDHI_CMD53_SINGLE_READ, p_r5, &sdsts1, &sdsts2);
    if (!ok)
    {
        uint32_t live1 = 0U;
        uint32_t live2 = 0U;

        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS1, &live1);
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS2, &live2);
        if ((0U != (sdsts1 & SDHI_SDSTS1_RSPEND)) || (0U != (live1 & SDHI_SDSTS1_RSPEND)) ||
            sdhi_can_read_crc_error_block(sdsts2))
        {
            sdsts1 = live1;
            sdsts2 = live2;
            ok = true;
        }
    }
    if (!ok)
    {
        sdhi_cmd53_capture_diag(sdsts1, sdsts2, *p_r5);
        sdhi_cmd53_force_stop(&sdsts2);
        return false;
    }

    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, SDHI_SDIMSK1_RESP, 0U);

    /* Wait for the receive buffer to fill (BRE = SDSTS2.RE). */
    g_cmd53_diag_stage = 2U;
    ok = sdhi_wait_status(0U, SDHI_SDIMSK2_RE, &sdsts1, &sdsts2);
    relaxed_read_crc = (!ok) && sdhi_can_read_crc_error_block(sdsts2);
    if (relaxed_read_crc)
    {
        ok = true;
    }
    if (!ok)
    {
        sdhi_cmd53_capture_diag(sdsts1, sdsts2, *p_r5);
        sdhi_cmd53_force_stop(&sdsts2);
        return false;
    }
    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, 0U,
                               SDHI_SDIMSK2_RE | (relaxed_read_crc ? SDHI_SDSTS2_READ_CRC_ERR : 0U));

    byte_index = 0UL;
    for (word_index = 0UL; word_index < word_count; word_index++)
    {
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDBUFR, &word);
        if (0UL == word_index)
        {
            g_cmd53_diag_data0 = word;
        }
        while ((byte_index < length) && (byte_index < ((word_index + 1UL) * 4UL)))
        {
            p_data[byte_index] = (uint8_t)(word >> ((byte_index & 0x03UL) * 8UL));
            byte_index++;
        }
    }

    g_cmd53_diag_stage = 3U;
    ok = sdhi_wait_status(SDHI_SDSTS1_ACEND, 0U, &sdsts1, &sdsts2);
    if ((!ok) && sdhi_can_accept_read_done_error(sdsts1, sdsts2))
    {
        ok = true;
    }
    if (!ok)
    {
        sdhi_cmd53_capture_diag(sdsts1, sdsts2, *p_r5);
        sdhi_cmd53_force_stop(&sdsts2);
    }
    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, SDHI_SDSTS1_ACEND,
                               ok ? (sdsts2 & SDHI_SDSTS2_ERR_BITS) : 0U);
    if (ok)
    {
        g_cmd53_diag_stage = 0xFFU;
    }
    return ok;
}

/*
 * CMD53 byte-mode write: transfer up to 512 bytes from p_data to one IO
 * function. The transmit buffer is fed through the raw SDBUFR address (the
 * controller wants successive writes to the same word port), waiting on
 * SDSTS2.WE for buffer space and SDSTS1.ACEND for completion.
 */
static bool sdio_cmd53_write_bytes(uint8_t function, uint32_t address, bool increment,
                                   uint8_t * p_data, uint32_t length, uint32_t * p_r5)
{
    bool ok;
    uint32_t sdsts1 = 0U;
    uint32_t sdsts2 = 0U;
    uint32_t arg;
    uint32_t word;
    uint32_t byte_index;
    uint32_t word_index;
    uint32_t word_count = (length + 3UL) / 4UL;
    uint32_t buff_reg;
    volatile uint32_t * p_sdbufr;

    if ((0UL == length) || (512UL < length))
    {
        *p_r5 = 0U;
        return false;
    }

    if (SDHI_SUCCESS != R_SDHI_GetBuffRegAddress(SDHI_CH0, &buff_reg))
    {
        *p_r5 = 0U;
        return false;
    }
    p_sdbufr = (volatile uint32_t *)buff_reg;

    arg = R_SDIO_MakeCmd53Arg(true, function, address, increment, false, length);

    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSTOP, SDHI_SDSTOP_INIT);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSIZE, length);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDIOMD, SDHI_SDIOMD_INTEN);

    ok = sdhi_cmd53_issue(arg, SDHI_CMD53_SINGLE_WRITE, p_r5, &sdsts1, &sdsts2);
    if (!ok)
    {
        sdhi_cmd53_force_stop(&sdsts2);
        return false;
    }

    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, SDHI_SDIMSK1_RESP, 0U);

    /* Wait for the transmit buffer to accept data (BWE = SDSTS2.WE). */
    ok = sdhi_wait_status(0U, SDHI_SDIMSK2_WE, &sdsts1, &sdsts2);
    if (!ok)
    {
        sdhi_cmd53_force_stop(&sdsts2);
        return false;
    }
    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, 0U, SDHI_SDIMSK2_WE);

    byte_index = 0UL;
    for (word_index = 0UL; word_index < word_count; word_index++)
    {
        word = 0UL;
        while ((byte_index < length) && (byte_index < ((word_index + 1UL) * 4UL)))
        {
            word |= ((uint32_t)p_data[byte_index]) << ((byte_index & 0x03UL) * 8UL);
            byte_index++;
        }
        p_sdbufr[0] = word;
    }

    ok = sdhi_wait_status(SDHI_SDSTS1_ACEND, 0U, &sdsts1, &sdsts2);
    if (!ok)
    {
        sdhi_cmd53_force_stop(&sdsts2);
    }
    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, SDHI_SDSTS1_ACEND, 0U);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSTOP, SDHI_SDSTOP_INIT);
    return ok;
}

/* A backplane block read can finish with a read-CRC error flagged while the
 * data in the buffer is still valid (CYW43439 quirk). Treat that one specific
 * condition - buffer-read-ready set, the only SDSTS2 error is the read-CRC bit,
 * and SDERSTS1 confirms RDCRCE - as recoverable, like perf does. */
static bool sdhi_can_read_crc_error_block(uint32_t sdsts2)
{
    uint32_t sdersts1 = 0U;

    if (0U == (sdsts2 & SDHI_SDIMSK2_RE))
    {
        return false;
    }
    if (SDHI_SDSTS2_READ_CRC_ERR != (sdsts2 & SDHI_SDSTS2_ERR_BITS))
    {
        return false;
    }
    (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDERSTS1, &sdersts1);
    return (0U != (sdersts1 & SDHI_SDERSTS1_RDCRCE));
}

/* A byte/block read may finish with ACEND set while SDSTS2 latches ILR after
 * SDBUFR was drained and SDERSTS1 still reports the CYW43439 read-CRC quirk.
 * Accept only that narrow final-state combination; timeouts or command/end
 * errors still fail. */
static bool sdhi_can_accept_read_done_error(uint32_t sdsts1, uint32_t sdsts2)
{
    uint32_t err_bits = sdsts2 & SDHI_SDSTS2_ERR_BITS;
    uint32_t sdersts1 = 0U;
    uint32_t sdersts2 = 0U;

    if (0U == (sdsts1 & SDHI_SDSTS1_ACEND))
    {
        return false;
    }
    if ((SDHI_SDSTS2_ILLEGAL_READ_ERR != err_bits) &&
        ((SDHI_SDSTS2_ILLEGAL_READ_ERR | SDHI_SDSTS2_READ_CRC_ERR) != err_bits))
    {
        return false;
    }

    (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDERSTS1, &sdersts1);
    (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDERSTS2, &sdersts2);
    return ((0U != (sdersts1 & SDHI_SDERSTS1_RDCRCE)) && (0U == sdersts2));
}

/*
 * CMD53 block-mode transfer (read or write) of block_count blocks of the
 * function's configured block size. SDSIZE = block size, SDBLKCNT = block count,
 * SDSTOP = block-count-enable; the command then runs one block at a time,
 * waiting on SDSTS2.RE/WE per block and SDBUFR for the data, ending on
 * SDSTS1.ACEND. A single-block transfer uses the SINGLE command word (matching
 * perf). Read CRC errors are tolerated (sdhi_can_read_crc_error_block).
 */
static bool sdio_cmd53_transfer_blocks(bool write, uint8_t function, uint32_t address, bool increment,
                                       uint8_t * p_data, uint32_t block_count, uint32_t * p_r5)
{
    bool ok;
    uint32_t sdsts1 = 0U;
    uint32_t sdsts2 = 0U;
    uint32_t arg;
    uint32_t block_index;
    uint32_t byte_index;
    uint32_t word_index;
    uint32_t word;
    uint32_t clear_mask;
    uint32_t block_size = g_sdio_block_size[function];
    uint32_t length = block_size * block_count;
    uint32_t buff_reg;
    uint32_t ready_mask = write ? SDHI_SDIMSK2_WE : SDHI_SDIMSK2_RE;
    uint32_t cmd;
    bool relaxed_read_crc;
    volatile uint32_t * p_sdbufr;

    if ((function > SDIO_MAX_FUNCTION) || (0UL == block_count) || (511UL < block_count))
    {
        *p_r5 = 0U;
        return false;
    }
    if ((0UL == block_size) || (0UL != (block_size & 0x03UL)) || (0UL == length))
    {
        *p_r5 = 0U;
        return false;
    }
    if (SDHI_SUCCESS != R_SDHI_GetBuffRegAddress(SDHI_CH0, &buff_reg))
    {
        *p_r5 = 0U;
        return false;
    }
    p_sdbufr = (volatile uint32_t *)buff_reg;

    arg = R_SDIO_MakeCmd53Arg(write, function, address, increment, true, block_count);
    /* A single block uses the SINGLE command word; multi-block uses BLOCK. */
    if (1UL == block_count)
    {
        cmd = write ? SDHI_CMD53_SINGLE_WRITE : SDHI_CMD53_SINGLE_READ;
    }
    else
    {
        cmd = write ? SDHI_CMD53_BLOCK_WRITE : SDHI_CMD53_BLOCK_READ;
    }

    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, SDHI_SDIMSK1_TRNS_RESP | SDHI_SDSTS1_DETECT_BITS,
                               SDHI_SDIMSK2_CLEAR | ready_mask);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSIZE, block_size);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSTOP, SDHI_SDSTOP_SEC_ENABLE);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDBLKCNT, block_count);
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDIOMD, SDHI_SDIOMD_INTEN);

    g_cmd53_diag_stage = 1U;
    g_cmd53_diag_data0 = 0U;
    ok = sdhi_cmd53_issue(arg, cmd, p_r5, &sdsts1, &sdsts2);
    /* A read that the command engine flagged can still carry good data if RSPEND
     * was seen or only a read-CRC error is set. */
    if ((!write) && (!ok))
    {
        uint32_t live1 = 0U;
        uint32_t live2 = 0U;

        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS1, &live1);
        (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDSTS2, &live2);
        if ((0U != (sdsts1 & SDHI_SDSTS1_RSPEND)) || (0U != (live1 & SDHI_SDSTS1_RSPEND)) ||
            sdhi_can_read_crc_error_block(sdsts2))
        {
            sdsts1 = live1;
            sdsts2 = live2;
            ok = true;
        }
    }
    if (!ok)
    {
        sdhi_cmd53_capture_diag(sdsts1, sdsts2, *p_r5);
        sdhi_cmd53_force_stop(&sdsts2);
        (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSTOP, SDHI_SDSTOP_INIT);
        return false;
    }

    (void)R_SDHI_ClearSdstsReg(SDHI_CH0, SDHI_SDIMSK1_RESP, 0U);

    g_cmd53_diag_stage = 2U;
    for (block_index = 0UL; block_index < block_count; block_index++)
    {
        ok = sdhi_wait_status(0U, ready_mask, &sdsts1, &sdsts2);
        relaxed_read_crc = (!write) && (!ok) && sdhi_can_read_crc_error_block(sdsts2);
        if (relaxed_read_crc)
        {
            ok = true;
        }
        if (!ok)
        {
            sdhi_cmd53_capture_diag(sdsts1, sdsts2, *p_r5);
            break;
        }

        clear_mask = ready_mask;
        if (relaxed_read_crc)
        {
            clear_mask |= SDHI_SDSTS2_READ_CRC_ERR;
        }
        (void)R_SDHI_ClearSdstsReg(SDHI_CH0, 0U, clear_mask);

        byte_index = block_index * block_size;
        for (word_index = 0UL; word_index < (block_size / 4UL); word_index++)
        {
            if (write)
            {
                word = ((uint32_t)p_data[byte_index]) |
                       ((uint32_t)p_data[byte_index + 1UL] << 8) |
                       ((uint32_t)p_data[byte_index + 2UL] << 16) |
                       ((uint32_t)p_data[byte_index + 3UL] << 24);
                p_sdbufr[0] = word;
            }
            else
            {
                (void)R_SDHI_InReg(SDHI_CH0, SDHI_SDBUFR, &word);
                if ((0UL == block_index) && (0UL == word_index))
                {
                    g_cmd53_diag_data0 = word;
                }
                p_data[byte_index]       = (uint8_t)word;
                p_data[byte_index + 1UL] = (uint8_t)(word >> 8);
                p_data[byte_index + 2UL] = (uint8_t)(word >> 16);
                p_data[byte_index + 3UL] = (uint8_t)(word >> 24);
            }
            byte_index += 4UL;
        }
    }

    if (ok)
    {
        g_cmd53_diag_stage = 3U;
        ok = sdhi_wait_status(SDHI_SDSTS1_ACEND, 0U, &sdsts1, &sdsts2);
        if ((!ok) && (!write) && sdhi_can_accept_read_done_error(sdsts1, sdsts2))
        {
            ok = true;
        }
        if (!ok)
        {
            sdhi_cmd53_capture_diag(sdsts1, sdsts2, *p_r5);
        }
        (void)R_SDHI_ClearSdstsReg(SDHI_CH0, SDHI_SDSTS1_ACEND,
                                   ok ? (sdsts2 & SDHI_SDSTS2_ERR_BITS) : 0U);
    }

    if (!ok)
    {
        sdhi_cmd53_force_stop(&sdsts2);
    }
    (void)R_SDHI_OutReg(SDHI_CH0, SDHI_SDSTOP, SDHI_SDSTOP_INIT);
    if (ok)
    {
        g_cmd53_diag_stage = 0xFFU;
    }
    return ok;
}

/* Host-side CMD53: byte mode bridges to the byte primitives, block mode to the
 * block transfer. Both go through the same r_sdio_rx callback. */
static sdio_err_t sdio_rx_cmd53_callback(void * p_context, sdio_cmd53_t * p_args)
{
    bool ok;
    uint32_t r5 = 0U;

    (void)p_context;
    if ((NULL == p_args) || (NULL == p_args->p_data))
    {
        return SDIO_ERR_NULL_PTR;
    }

    if (p_args->block_mode)
    {
        ok = sdio_cmd53_transfer_blocks(p_args->write, p_args->function, p_args->address,
                                        p_args->increment, p_args->p_data, p_args->count, &r5);
    }
    else if (p_args->write)
    {
        ok = sdio_cmd53_write_bytes(p_args->function, p_args->address, p_args->increment,
                                    p_args->p_data, p_args->count, &r5);
    }
    else
    {
        ok = sdio_cmd53_read_bytes(p_args->function, p_args->address, p_args->increment,
                                   p_args->p_data, p_args->count, &r5);
    }

    p_args->r5 = r5;
    return ok ? SDIO_SUCCESS : SDIO_ERR_HOST;
}

static void sdio_rx_delay_ms(void * p_context, uint32_t delay_ms)
{
    (void)p_context;
    R_BSP_SoftwareDelay(delay_ms, BSP_DELAY_MILLISECS);
}

bool sdio_host_protocol_open(void)
{
    if (g_sdio_ctrl.open)
    {
        (void)R_SDIO_Close(&g_sdio_ctrl);
    }

    g_sdio_cfg.p_context           = NULL;
    g_sdio_cfg.p_cmd52             = sdio_rx_cmd52_callback;
    g_sdio_cfg.p_cmd53             = sdio_rx_cmd53_callback;
    g_sdio_cfg.p_delay_ms          = sdio_rx_delay_ms;
    g_sdio_cfg.io_ready_poll_count = 100000UL;

    return (SDIO_SUCCESS == R_SDIO_Open(&g_sdio_ctrl, &g_sdio_cfg));
}

bool sdio_host_cmd52_read(uint8_t function, uint32_t address, uint8_t * p_data)
{
    uint32_t r5 = 0U;
    return (SDIO_SUCCESS == R_SDIO_Cmd52Read(&g_sdio_ctrl, function, address, p_data, &r5));
}

bool sdio_host_enable_function(uint8_t function, uint8_t * p_ready)
{
    uint32_t r5 = 0U;
    return (SDIO_SUCCESS == R_SDIO_EnableFunction(&g_sdio_ctrl, function, p_ready, &r5));
}

bool sdio_host_cmd52_write(uint8_t function, uint32_t address, uint8_t data, uint8_t * p_readback)
{
    uint32_t r5 = 0U;
    return (SDIO_SUCCESS == R_SDIO_Cmd52Write(&g_sdio_ctrl, function, address, data, true, p_readback, &r5));
}

/*
 * Enable SDIO high speed if the card supports it (CCCR 0x13: SHS = support,
 * EHS = enable). Part of the perf project's proven pre-CMD53 sequence.
 */
bool sdio_host_set_high_speed(void)
{
    uint8_t speed = 0U;
    uint8_t readback = 0U;

    if (!sdio_host_cmd52_read(0U, 0x13U, &speed))
    {
        return false;
    }
    if (0U != (speed & 0x01U))   /* SHS: card supports high speed */
    {
        if (!sdio_host_cmd52_write(0U, 0x13U, (uint8_t)(speed | 0x02U), &readback))  /* EHS */
        {
            return false;
        }
    }
    return true;
}

static bool sdio_host_set_one_block_size(uint8_t function, uint16_t block_size)
{
    uint32_t base = (uint32_t)function << 8;
    uint8_t readback = 0U;

    if (!sdio_host_cmd52_write(0U, base + SDIO_FBR_BLKSIZ0, (uint8_t)block_size, &readback))
    {
        return false;
    }
    if (!sdio_host_cmd52_write(0U, base + SDIO_FBR_BLKSIZ1, (uint8_t)(block_size >> 8), &readback))
    {
        return false;
    }

    if (function <= SDIO_MAX_FUNCTION)
    {
        g_sdio_block_size[function] = block_size;
    }
    return true;
}

/*
 * Set the F0 and F1 SDIO block sizes (CYW43439 uses 64). Part of the perf
 * project's proven pre-CMD53 sequence.
 */
bool sdio_host_set_block_size(void)
{
    return sdio_host_set_one_block_size(0U, 64U) && sdio_host_set_one_block_size(1U, 64U);
}

/*
 * Mirror a CMD52 write into g_sdio_block_size when it targets a function's
 * block-size register, so block-mode CMD53 on that function uses the size the
 * upper layer actually programmed. The block-size registers live in the
 * function-0 (CIA) address space: F0 at CCCR 0x10/0x11 and Fn at FBRn + 0x10/
 * 0x11 = (n << 8) + 0x10/0x11, the LSB at 0x10 and the MSB at 0x11. WHD programs
 * F0/F1/F2 here directly (BUS_FUNCTION = 0) rather than through
 * sdio_host_set_block_size, which seeds only F0/F1; without this, g_sdio_block_size[2]
 * stays 0 and sdio_cmd53_transfer_blocks rejects the F2/WLAN block transfers.
 */
void sdio_host_note_cmd52_write(uint8_t function, uint32_t address, uint8_t value)
{
    uint8_t target;
    uint8_t reg;

    /* FBR/CCCR (block-size) registers are addressed through function 0. */
    if (0U != function)
    {
        return;
    }

    target = (uint8_t)((address >> 8) & 0x07U);
    reg = (uint8_t)(address & 0xFFU);
    if (SDIO_FBR_BLKSIZ0 == reg)
    {
        g_sdio_block_size[target] = (uint16_t)((g_sdio_block_size[target] & 0xFF00U) | value);
    }
    else if (SDIO_FBR_BLKSIZ1 == reg)
    {
        g_sdio_block_size[target] = (uint16_t)((g_sdio_block_size[target] & 0x00FFU) | ((uint16_t)value << 8));
    }
    else
    {
        /* Not a block-size register; nothing to mirror. */
    }
}

/*
 * Switch the SDIO bus to 4-bit before any CMD53 data transfer. The card
 * enumerates and answers CMD52 in its 1-bit default; the perf project's proven
 * data path runs 4-bit (CCCR bus interface control: clear the width field, set
 * 4-bit, disable the DAT3 card-detect pull-up so DAT3 is a data line), then
 * switches the SDHI to 4-bit and re-applies the transfer pins.
 */
bool sdio_host_set_bus_4bit(void)
{
    uint8_t bus_if = 0U;
    uint8_t new_bus_if;
    uint8_t readback = 0U;

    if (!sdio_host_cmd52_read(0U, SDIO_CCCR_BUS_IF_CONTROL, &bus_if))
    {
        return false;
    }

    new_bus_if = (uint8_t)((bus_if & (uint8_t)(~SDIO_BUS_WIDTH_MASK)) |
                           SDIO_BUS_WIDTH_4BIT | SDIO_BUS_CD_DISABLE);
    if (!sdio_host_cmd52_write(0U, SDIO_CCCR_BUS_IF_CONTROL, new_bus_if, &readback))
    {
        return false;
    }

    if (SDHI_SUCCESS != R_SDHI_SetBus(SDHI_CH0, SDHI_PORT_4BIT))
    {
        return false;
    }
    R_SDHI_PinSetTransfer();
    return true;
}

/*
 * Raise the SDHI clock from the ~400 kHz identification divider (DIV_256) used
 * for enumerate to a run divider (DIV_4) before any CMD53 data transfer.
 */
bool sdio_host_set_run_clock(void)
{
    return (SDHI_SUCCESS == R_SDHI_SetClock(SDHI_CH0, SDHI_DIV_8, SDHI_CLOCK_ENABLE));
}

/*
 * Request the ALP backplane clock (F1 CHIPCLKCSR), poll for ALP_AVAIL. This
 * sets the ALP_AVAIL status bit but is NOT sufficient on its own to clock the
 * backplane data phase - sdio_host_brcm_force_clocks() must follow. Writes the
 * final CSR byte.
 */
bool sdio_host_request_alp(uint8_t * p_csr)
{
    uint8_t readback = 0U;
    uint8_t csr = 0U;
    uint32_t poll;

    if (!sdio_host_cmd52_write(1U, SDIO_BRCM_FUNC1_CHIPCLKCSR, SDIO_BRCM_CLK_ALP_REQ, &readback))
    {
        return false;
    }

    for (poll = 0UL; poll < 100000UL; poll++)
    {
        if (!sdio_host_cmd52_read(1U, SDIO_BRCM_FUNC1_CHIPCLKCSR, &csr))
        {
            return false;
        }
        if (0U != (csr & SDIO_BRCM_ALP_AVAIL))
        {
            if (NULL != p_csr)
            {
                *p_csr = csr;
            }
            return true;
        }
        R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);
    }

    if (NULL != p_csr)
    {
        *p_csr = csr;
    }
    return false;
}

/*
 * Force the backplane clocks exactly as perf does before its first CMD53
 * backplane read (verified byte-for-byte against a known-good perf run on this
 * bench):
 *   1. FORCE_ALP  - force ALP on, not just request it
 *   2. WAKEUPCTRL - set WAKE_TILL_HT so the WLAN core stays awake until HT
 *   3. FORCE_HT   - force HT, and do NOT wait for HT_AVAIL (it does not come up
 *                   pre-firmware; perf proceeds at CHIPCLKCSR=0x42)
 * Requesting ALP alone (ALP_AVAIL status set) does NOT clock the backplane data
 * phase - this was the missing precondition behind the CMD53 stall (the card
 * ACKs CMD53 but never clocks data, SDSTS2 stuck CBSY / RE never asserts).
 * Writes the final CHIPCLKCSR byte. Call after sdio_host_request_alp().
 */
bool sdio_host_brcm_force_clocks(uint8_t * p_csr)
{
    uint8_t readback = 0U;
    uint8_t wctrl = 0U;

    if (!sdio_host_cmd52_write(1U, SDIO_BRCM_FUNC1_CHIPCLKCSR, SDIO_BRCM_CLK_FORCE_ALP, &readback))
    {
        return false;
    }

    if (!sdio_host_cmd52_read(1U, SDIO_BRCM_FUNC1_WAKEUPCTRL, &wctrl))
    {
        return false;
    }
    if (!sdio_host_cmd52_write(1U, SDIO_BRCM_FUNC1_WAKEUPCTRL,
                               (uint8_t)(wctrl | SDIO_BRCM_WCTRL_WAKE_TILL_HT), &readback))
    {
        return false;
    }

    if (!sdio_host_cmd52_write(1U, SDIO_BRCM_FUNC1_CHIPCLKCSR, SDIO_BRCM_FORCE_HT, &readback))
    {
        return false;
    }

    if (NULL != p_csr)
    {
        *p_csr = readback;
    }
    return true;
}

/*
 * Keep the WLAN SDIO core on (KSO). Write SLEEPCSR (F1 0x1001f) with KEEP_WL_KSO
 * twice (the second write sticks once the core is up), then poll until KEEP_WL_
 * KSO reads back. perf does this before backplane reads. Writes the final
 * SLEEPCSR byte.
 */
bool sdio_host_request_kso(uint8_t * p_slp)
{
    uint8_t readback = 0U;
    uint8_t slp = 0U;
    uint32_t poll;

    (void)sdio_host_cmd52_write(1U, SDIO_BRCM_FUNC1_SLEEPCSR, SDIO_BRCM_SLPCSR_KEEP_WL_KSO, &readback);
    (void)sdio_host_cmd52_write(1U, SDIO_BRCM_FUNC1_SLEEPCSR, SDIO_BRCM_SLPCSR_KEEP_WL_KSO, &readback);

    for (poll = 0UL; poll < 2000UL; poll++)
    {
        if (!sdio_host_cmd52_read(1U, SDIO_BRCM_FUNC1_SLEEPCSR, &slp))
        {
            return false;
        }
        if (0U != (slp & SDIO_BRCM_SLPCSR_KEEP_WL_KSO))
        {
            if (NULL != p_slp)
            {
                *p_slp = slp;
            }
            return true;
        }
        R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);
    }

    if (NULL != p_slp)
    {
        *p_slp = slp;
    }
    return false;
}

/*
 * Read a 32-bit little-endian word from the Broadcom backplane (sets the SB
 * window via CMD52, then a 4-byte CMD53 byte read through r_sdio_rx). This is
 * the first user of the CMD53 data path: a backplane read of the chipcommon
 * base returns the chip ID, proving the host data phase end to end.
 */
bool sdio_host_backplane_read32(uint32_t address, uint32_t * p_value)
{
    uint32_t r5 = 0U;
    uint8_t data[4] = {0U, 0U, 0U, 0U};

    if (NULL == p_value)
    {
        return false;
    }

    if (SDIO_SUCCESS != R_SDIO_BrcmBackplaneRead(&g_sdio_ctrl, address, true, data, 4U, &r5))
    {
        return false;
    }

    *p_value = ((uint32_t)data[0]) | ((uint32_t)data[1] << 8) |
               ((uint32_t)data[2] << 16) | ((uint32_t)data[3] << 24);
    return true;
}

bool sdio_host_backplane_read(uint32_t address, uint8_t * p_data, uint32_t length)
{
    uint32_t r5 = 0U;

    if ((NULL == p_data) || (0U == length))
    {
        return false;
    }

    return (SDIO_SUCCESS == R_SDIO_BrcmBackplaneRead(&g_sdio_ctrl, address, true, p_data, length, &r5));
}

/*
 * Read block_count blocks (of the F1 block size) from the Broadcom backplane via
 * the CMD53 block-mode path: set the SB window, then R_SDIO_Cmd53ReadBlocks on
 * F1. Exercises the block transfer that the firmware download will use.
 */
bool sdio_host_backplane_read_block(uint32_t address, uint8_t * p_data, uint32_t block_count)
{
    uint32_t r5 = 0U;
    uint32_t f1_address;
    uint32_t length = (uint32_t)g_sdio_block_size[1] * block_count;

    if ((NULL == p_data) || (0U == block_count))
    {
        return false;
    }

    if (SDIO_SUCCESS != R_SDIO_BrcmSetBackplaneWindow(&g_sdio_ctrl, address, NULL, &r5))
    {
        return false;
    }
    f1_address = R_SDIO_BrcmBackplaneFunctionAddress(address, length);
    return (SDIO_SUCCESS == R_SDIO_Cmd53ReadBlocks(&g_sdio_ctrl, 1U, f1_address, true,
                                                   p_data, block_count, &r5));
}

bool sdio_host_backplane_write(uint32_t address, uint8_t * p_data, uint32_t length)
{
    uint32_t r5 = 0U;

    if ((NULL == p_data) || (0U == length))
    {
        return false;
    }
    return (SDIO_SUCCESS == R_SDIO_BrcmBackplaneWrite(&g_sdio_ctrl, address, true, p_data, length, &r5));
}

bool sdio_host_backplane_write_block(uint32_t address, uint8_t * p_data, uint32_t block_count)
{
    uint32_t r5 = 0U;
    uint32_t f1_address;
    uint32_t length = (uint32_t)g_sdio_block_size[1] * block_count;

    if ((NULL == p_data) || (0U == block_count))
    {
        return false;
    }
    if (SDIO_SUCCESS != R_SDIO_BrcmSetBackplaneWindow(&g_sdio_ctrl, address, NULL, &r5))
    {
        return false;
    }
    f1_address = R_SDIO_BrcmBackplaneFunctionAddress(address, length);
    return (SDIO_SUCCESS == R_SDIO_Cmd53WriteBlocks(&g_sdio_ctrl, 1U, f1_address, true,
                                                    p_data, block_count, &r5));
}

/* Raw CMD53 (no backplane windowing) for the WHD SDIO bus backend. The WHD bus
 * driver owns the Broadcom backplane window (it programs SBADDR* via CMD52), so
 * this issues the CMD53 to the function/address exactly as asked. count is bytes
 * in byte mode, blocks in block mode. Writes the R5 response (p_r5 may be NULL).
 * This is the primitive cyhal_sdio_bulk_transfer maps onto. */
bool sdio_host_cmd53(bool write, uint8_t function, uint32_t address, bool increment,
                     bool block_mode, uint8_t * p_data, uint32_t count, uint32_t * p_r5)
{
    uint32_t r5 = 0U;
    sdio_err_t err;

    if ((NULL == p_data) || (0U == count))
    {
        if (NULL != p_r5)
        {
            *p_r5 = 0U;
        }
        return false;
    }

    if (block_mode)
    {
        err = write
            ? R_SDIO_Cmd53WriteBlocks(&g_sdio_ctrl, function, address, increment, p_data, count, &r5)
            : R_SDIO_Cmd53ReadBlocks(&g_sdio_ctrl, function, address, increment, p_data, count, &r5);
    }
    else
    {
        err = write
            ? R_SDIO_Cmd53WriteBytes(&g_sdio_ctrl, function, address, increment, p_data, count, &r5)
            : R_SDIO_Cmd53ReadBytes(&g_sdio_ctrl, function, address, increment, p_data, count, &r5);
    }

    if (NULL != p_r5)
    {
        *p_r5 = r5;
    }
    return (SDIO_SUCCESS == err);
}

/* ---- Broadcom core control (firmware-download bring-up) --------------------
 *
 * The CYW43439 ARM (WLAN CPU) and SOCRAM cores are reset/clocked through their
 * AI wrapper registers (IOCTRL / RESETCTRL), accessed over the backplane. The
 * firmware download halts the ARM, resets SOCRAM, loads the blob into RAM, then
 * releases the ARM to boot. */
static bool brcm_bp_write8(uint32_t address, uint8_t value)
{
    uint32_t r5 = 0U;
    return (SDIO_SUCCESS == R_SDIO_BrcmBackplaneWrite(&g_sdio_ctrl, address, true, &value, 1U, &r5));
}

static bool brcm_bp_read8(uint32_t address, uint8_t * p_value)
{
    uint32_t r5 = 0U;
    return (SDIO_SUCCESS == R_SDIO_BrcmBackplaneRead(&g_sdio_ctrl, address, true, p_value, 1U, &r5));
}

static bool brcm_bp_write32(uint32_t address, uint32_t value)
{
    uint32_t r5 = 0U;
    uint8_t data[4];

    data[0] = (uint8_t)value;
    data[1] = (uint8_t)(value >> 8);
    data[2] = (uint8_t)(value >> 16);
    data[3] = (uint8_t)(value >> 24);
    return (SDIO_SUCCESS == R_SDIO_BrcmBackplaneWrite(&g_sdio_ctrl, address, true, data, 4U, &r5));
}

/* Put a core into reset (IOCTRL=0, then RESETCTRL=AIRC_RESET). No-op if it is
 * already in reset. */
static bool brcm_core_disable(uint32_t wrap_base)
{
    uint8_t readback = 0U;

    if (!brcm_bp_read8(wrap_base + BRCM_AI_RESETCTRL_OFFSET, &readback))
    {
        return false;
    }
    if (0U != (readback & BRCM_AIRC_RESET))
    {
        return true;
    }

    if (!brcm_bp_write8(wrap_base + BRCM_AI_IOCTRL_OFFSET, 0U))
    {
        return false;
    }
    (void)brcm_bp_read8(wrap_base + BRCM_AI_IOCTRL_OFFSET, &readback);
    R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);

    if (!brcm_bp_write8(wrap_base + BRCM_AI_RESETCTRL_OFFSET, BRCM_AIRC_RESET))
    {
        return false;
    }
    R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);
    return true;
}

/* Reset a core and bring it back out of reset with clocks running. */
static bool brcm_core_reset(uint32_t wrap_base)
{
    uint8_t readback = 0U;

    if (!brcm_core_disable(wrap_base))
    {
        return false;
    }

    if (!brcm_bp_write8(wrap_base + BRCM_AI_IOCTRL_OFFSET, (uint8_t)(BRCM_SICF_FGC | BRCM_SICF_CLOCK_EN)))
    {
        return false;
    }
    (void)brcm_bp_read8(wrap_base + BRCM_AI_IOCTRL_OFFSET, &readback);

    if (!brcm_bp_write8(wrap_base + BRCM_AI_RESETCTRL_OFFSET, 0U))
    {
        return false;
    }
    R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);

    if (!brcm_bp_write8(wrap_base + BRCM_AI_IOCTRL_OFFSET, BRCM_SICF_CLOCK_EN))
    {
        return false;
    }
    (void)brcm_bp_read8(wrap_base + BRCM_AI_IOCTRL_OFFSET, &readback);
    R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);
    return true;
}

/*
 * Prepare SOCRAM for the firmware download: halt the WLAN ARM core, reset the
 * SOCRAM core, power up bank 3, then prove the SOCRAM data path with a 1-byte
 * and a 64-byte byte-mode write/read-back. Mirrors perf's socram_write_init.
 * Returns true once the round-trip matches.
 */
bool sdio_host_socram_init(void)
{
    uint8_t byte_value = 0U;
    uint8_t pattern[64];
    uint8_t verify[64];
    uint32_t i;
    uint32_t r5 = 0U;

    if (!brcm_core_disable(BRCM_ARM_WRAP_BASE))
    {
        return false;
    }
    if (!brcm_core_reset(BRCM_SOCRAM_WRAP_BASE))
    {
        return false;
    }
    if (!brcm_bp_write32(BRCM_SOCSRAM_BANKX_INDEX, 0x3UL) ||
        !brcm_bp_write32(BRCM_SOCSRAM_BANKX_PDA, 0UL))
    {
        return false;
    }

    if (!brcm_bp_write8(BRCM_RAM_BASE, 0xA5U) ||
        !brcm_bp_read8(BRCM_RAM_BASE, &byte_value) || (0xA5U != byte_value))
    {
        return false;
    }

    for (i = 0U; i < 64U; i++)
    {
        pattern[i] = (uint8_t)(i ^ (i >> 8));
    }
    if (SDIO_SUCCESS != R_SDIO_BrcmBackplaneWrite(&g_sdio_ctrl, BRCM_RAM_BASE, true, pattern, 64U, &r5))
    {
        return false;
    }
    if (SDIO_SUCCESS != R_SDIO_BrcmBackplaneRead(&g_sdio_ctrl, BRCM_RAM_BASE, true, verify, 64U, &r5))
    {
        return false;
    }
    for (i = 0U; i < 64U; i++)
    {
        if (pattern[i] != verify[i])
        {
            return false;
        }
    }

    return true;
}

/* Read-back scratch for the firmware verify (max chunk = 1024 bytes). */
static uint8_t g_fw_verify[1024];

/*
 * Stream a flash-resident image into card backplane RAM. Chunks are capped at
 * 1024 bytes, floored to 64-byte block-mode units, and never cross a 32 KB
 * backplane window; a sub-64-byte tail goes out in byte mode.
 */
static bool sdio_fw_write_region(uint32_t bp_addr, const uint8_t * p_src, uint32_t length)
{
    uint32_t offset = 0U;
    uint32_t r5 = 0U;

    while (offset < length)
    {
        uint32_t addr = bp_addr + offset;
        uint32_t window_left = 0x8000UL - (addr & 0x7FFFUL);
        uint32_t chunk = length - offset;
        uint32_t f1_address;

        if (chunk > 1024UL)
        {
            chunk = 1024UL;
        }
        if (chunk > window_left)
        {
            chunk = window_left;
        }
        if (chunk >= SDIO_FW_BLOCK_SIZE)
        {
            chunk &= ~(SDIO_FW_BLOCK_SIZE - 1UL);
        }

        if (SDIO_SUCCESS != R_SDIO_BrcmSetBackplaneWindow(&g_sdio_ctrl, addr, NULL, &r5))
        {
            return false;
        }
        f1_address = R_SDIO_BrcmBackplaneFunctionAddress(addr, chunk);

        if (chunk >= SDIO_FW_BLOCK_SIZE)
        {
            if (SDIO_SUCCESS != R_SDIO_Cmd53WriteBlocks(&g_sdio_ctrl, 1U, f1_address, true,
                                                        (uint8_t *)p_src + offset,
                                                        chunk / SDIO_FW_BLOCK_SIZE, &r5))
            {
                return false;
            }
        }
        else
        {
            if (SDIO_SUCCESS != R_SDIO_Cmd53WriteBytes(&g_sdio_ctrl, 1U, f1_address, true,
                                                       (uint8_t *)p_src + offset, chunk, &r5))
            {
                return false;
            }
        }
        offset += chunk;
    }

    return true;
}

/* Read a region back from backplane RAM and compare with the flash source. */
static bool sdio_fw_verify_region(uint32_t bp_addr, const uint8_t * p_src, uint32_t length)
{
    uint32_t offset = 0U;
    uint32_t r5 = 0U;

    while (offset < length)
    {
        uint32_t addr = bp_addr + offset;
        uint32_t window_left = 0x8000UL - (addr & 0x7FFFUL);
        uint32_t chunk = length - offset;
        uint32_t f1_address;
        uint32_t i;

        if (chunk > 1024UL)
        {
            chunk = 1024UL;
        }
        if (chunk > window_left)
        {
            chunk = window_left;
        }
        if (chunk >= SDIO_FW_BLOCK_SIZE)
        {
            chunk &= ~(SDIO_FW_BLOCK_SIZE - 1UL);
        }

        if (SDIO_SUCCESS != R_SDIO_BrcmSetBackplaneWindow(&g_sdio_ctrl, addr, NULL, &r5))
        {
            return false;
        }
        f1_address = R_SDIO_BrcmBackplaneFunctionAddress(addr, chunk);

        if (chunk >= SDIO_FW_BLOCK_SIZE)
        {
            if (SDIO_SUCCESS != R_SDIO_Cmd53ReadBlocks(&g_sdio_ctrl, 1U, f1_address, true,
                                                       g_fw_verify, chunk / SDIO_FW_BLOCK_SIZE, &r5))
            {
                return false;
            }
        }
        else
        {
            if (SDIO_SUCCESS != R_SDIO_Cmd53ReadBytes(&g_sdio_ctrl, 1U, f1_address, true,
                                                      g_fw_verify, chunk, &r5))
            {
                return false;
            }
        }
        for (i = 0U; i < chunk; i++)
        {
            if (p_src[offset + i] != g_fw_verify[i])
            {
                return false;
            }
        }
        offset += chunk;
    }

    return true;
}

/*
 * Firmware download + boot (the de-risk gate). Stream the firmware blob into
 * SOCRAM at address 0, the NVRAM image near the top with its TOC trailer, clear
 * CHIPCLKCSR, then release the WLAN ARM core. Success = the chip comes alive:
 * HT_AVAIL (firmware brought the PLL up) and function 2 (IO_READY bit 2) ready.
 * Mirrors perf's fw_download_and_boot. Writes the HT/IOR settle times (ms).
 * The blobs must already be in flash (loaded via J-Link).
 */
bool sdio_host_fw_download_and_boot(uint32_t * p_ht_ms, uint32_t * p_ior_ms)
{
    const uint8_t * p_fw = (const uint8_t *)SDIO_FW_BLOB_ADDR;
    const uint8_t * p_nv = (const uint8_t *)SDIO_NVRAM_IMAGE_ADDR;
    const uint32_t nvram_base = 0x0007FFFCUL - SDIO_NVRAM_IMAGE_SIZE;
    const uint32_t toc = (((~(SDIO_NVRAM_IMAGE_SIZE / 4UL)) & 0xFFFFUL) << 16) |
                         ((SDIO_NVRAM_IMAGE_SIZE / 4UL) & 0xFFFFUL);
    uint32_t fw_tail = (SDIO_FW_BLOB_SIZE > 1024UL) ? (SDIO_FW_BLOB_SIZE - 1024UL) : 0UL;
    uint32_t i;
    uint8_t val = 0U;
    uint8_t readback = 0U;

    if (NULL != p_ht_ms)
    {
        *p_ht_ms = 0U;
    }
    if (NULL != p_ior_ms)
    {
        *p_ior_ms = 0U;
    }

    /* The blobs must be present in flash (0xFF == erased). */
    if ((0xFFU == p_fw[0]) || (0xFFU == p_nv[0]))
    {
        return false;
    }

    /* Terminate any in-flight F2 frame a previous run may have left (issue #25:
     * an aborted F2 write wedges every later multi-block CMD53). */
    (void)sdio_host_cmd52_write(0U, SDIO_CCCR_IO_ABORT, 2U, &readback);
    (void)sdio_host_cmd52_write(1U, SDIO_BRCM_FUNC1_FRAMECTRL, 0x03U, &readback);

    /* Enable function 2. */
    if (!sdio_host_cmd52_read(0U, SDIO_CCCR_IO_ENABLE, &val) ||
        !sdio_host_cmd52_write(0U, SDIO_CCCR_IO_ENABLE, (uint8_t)(val | SDIO_CCCR_IO_ENABLE_FN2), &readback))
    {
        return false;
    }

    if (!sdio_host_socram_init())
    {
        return false;
    }

    /* Firmware -> SOCRAM 0, verify head + tail. */
    if (!sdio_fw_write_region(0UL, p_fw, SDIO_FW_BLOB_SIZE))
    {
        return false;
    }
    if (!sdio_fw_verify_region(0UL, p_fw, 1024UL) ||
        !sdio_fw_verify_region(fw_tail, p_fw + fw_tail, SDIO_FW_BLOB_SIZE - fw_tail))
    {
        return false;
    }

    /* NVRAM near the top of SOCRAM + verify, then the TOC trailer. */
    if (!sdio_fw_write_region(nvram_base, p_nv, SDIO_NVRAM_IMAGE_SIZE) ||
        !sdio_fw_verify_region(nvram_base, p_nv, SDIO_NVRAM_IMAGE_SIZE))
    {
        return false;
    }
    if (!brcm_bp_write32(0x0007FFFCUL, toc) ||
        !sdio_host_cmd52_write(1U, SDIO_BRCM_FUNC1_CHIPCLKCSR, 0x00U, &readback))
    {
        return false;
    }

    /* Release the WLAN ARM core - it starts running the firmware. */
    if (!brcm_core_reset(BRCM_ARM_WRAP_BASE))
    {
        return false;
    }
    if (!brcm_bp_read8(BRCM_ARM_WRAP_BASE + BRCM_AI_IOCTRL_OFFSET, &val) ||
        (BRCM_SICF_CLOCK_EN != (val & (BRCM_SICF_FGC | BRCM_SICF_CLOCK_EN))) ||
        !brcm_bp_read8(BRCM_ARM_WRAP_BASE + BRCM_AI_RESETCTRL_OFFSET, &val) ||
        (0U != (val & BRCM_AIRC_RESET)))
    {
        return false;
    }

    /* Wait for HT (the running firmware brings the PLL up). */
    for (i = 0U; i < 2500U; i++)
    {
        if (sdio_host_cmd52_read(1U, SDIO_BRCM_FUNC1_CHIPCLKCSR, &val) &&
            (0U != (val & SDIO_BRCM_HT_AVAIL)))
        {
            break;
        }
        R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);
    }
    if (i >= 2500U)
    {
        return false;
    }
    if (NULL != p_ht_ms)
    {
        *p_ht_ms = i;
    }

    /* Wait for function 2 (the SDPCM data function) to be ready. */
    for (i = 0U; i < 1000U; i++)
    {
        if (sdio_host_cmd52_read(0U, SDIO_CCCR_IO_READY, &val) &&
            (0U != (val & SDIO_CCCR_IO_READY_FN2)))
        {
            break;
        }
        R_BSP_SoftwareDelay(1U, BSP_DELAY_MILLISECS);
    }
    if (i >= 1000U)
    {
        return false;
    }
    if (NULL != p_ior_ms)
    {
        *p_ior_ms = i;
    }

    return true;
}

void sdio_host_cmd53_diag(uint8_t * p_stage, uint32_t * p_s1, uint32_t * p_s2, uint32_t * p_r5)
{
    if (NULL != p_stage)
    {
        *p_stage = g_cmd53_diag_stage;
    }
    if (NULL != p_s1)
    {
        *p_s1 = g_cmd53_diag_s1;
    }
    if (NULL != p_s2)
    {
        *p_s2 = g_cmd53_diag_s2;
    }
    if (NULL != p_r5)
    {
        *p_r5 = g_cmd53_diag_r5;
    }
}

void sdio_host_cmd53_diag_ext(uint8_t * p_stage, uint32_t * p_s1, uint32_t * p_s2,
                              uint32_t * p_er1, uint32_t * p_er2,
                              uint32_t * p_r5, uint32_t * p_data0)
{
    sdio_host_cmd53_diag(p_stage, p_s1, p_s2, p_r5);
    if (NULL != p_er1)
    {
        *p_er1 = g_cmd53_diag_er1;
    }
    if (NULL != p_er2)
    {
        *p_er2 = g_cmd53_diag_er2;
    }
    if (NULL != p_data0)
    {
        *p_data0 = g_cmd53_diag_data0;
    }
}
