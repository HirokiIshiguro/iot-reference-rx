/*
 * WHD core bring-up for EK-RX671 + Murata Type 1YN.
 */
#include <stdint.h>
#include <string.h>

#include "FreeRTOS.h"
#include "task.h"

#include "cyhal_hw_types.h"
#include "cyhal_gpio.h"
#include "cyhal_sdio.h"
#include "cyabs_rtos.h"
#include "whd.h"
#include "whd_wifi_api.h"
#include "whd_types.h"

#include "debug_uart.h"
#include "whd_join_config.h"
#include "whd_port.h"
#include "whd_bringup.h"

#define WHD_THREAD_STACK_BYTES          (8192UL)

static uint32_t g_whd_thread_stack[WHD_THREAD_STACK_BYTES / sizeof(uint32_t)];
#if WHD_SCAN_ENABLE
static whd_sync_scan_result_t g_scan_results[WHD_SCAN_RESULT_LIMIT];
static whd_scan_result_t g_target_ap;
#endif
static whd_driver_t g_whd_driver;
static whd_interface_t g_whd_ifp;
static cyhal_sdio_t g_sdio_obj;

volatile uint32_t g_whd_bringup_stage;
volatile uint32_t g_whd_bringup_last_result;
volatile uint32_t g_whd_bringup_scan_count;
volatile uint32_t g_whd_bringup_join_result;
volatile uint32_t g_whd_bringup_ready_result;
volatile int32_t  g_whd_bringup_rssi;
volatile uint32_t g_whd_bringup_channel;
volatile uint8_t  g_whd_bringup_sta_mac[6];
volatile uint8_t  g_whd_bringup_ap_bssid[6];
volatile uint32_t g_whd_bringup_target_seen_count;
volatile uint32_t g_whd_bringup_target_best_index;
volatile int32_t  g_whd_bringup_target_best_rssi;
volatile uint32_t g_whd_bringup_target_security;
volatile uint32_t g_whd_bringup_target_channel;
volatile uint8_t  g_whd_bringup_target_bssid[6];
volatile uint32_t g_whd_bringup_join_mode;

extern volatile uint32_t g_whd_sdio_sdhi_irq_count;
extern volatile uint32_t g_whd_sdio_sdhi_irq_notify_count;
extern volatile uint32_t g_whd_sdio_sdhi_irq_task_count;
extern volatile uint32_t g_whd_sdio_sdhi_irq_enable_count;
extern volatile uint32_t g_whd_sdio_sdhi_irq_deferred_enable_count;
extern volatile uint32_t g_whd_sdio_cmd53_f2_byte_read_retry_count;
extern volatile uint32_t g_whd_sdio_cmd53_f2_byte_read_recovered_count;
extern volatile uint32_t g_whd_sdio_cmd53_f2_byte_read_retry_fail_count;
extern volatile uint32_t g_whd_sdio_cmd53_f2_byte_read_retry_abort_count;
extern volatile uint32_t g_sdio_host_run_clock_div;
extern volatile uint32_t g_sdio_host_run_clock_status;
extern volatile uint32_t g_sdio_host_cmd53_xfer_engine;
extern volatile uint32_t g_sdio_host_portd_dscr;
extern volatile uint32_t g_sdio_host_portd_dscr2;

static void whd_record_stage(uint32_t stage, uint32_t result)
{
    g_whd_bringup_stage = stage;
    g_whd_bringup_last_result = result;
}

static void whd_record_mac(volatile uint8_t * p_dst, const whd_mac_t * p_src)
{
    uint32_t i;

    for (i = 0U; i < sizeof(p_src->octet); i++)
    {
        p_dst[i] = p_src->octet[i];
    }
}

static char * append_int32(char * p, int32_t value)
{
    uint32_t magnitude;

    if (value < 0)
    {
        *p = '-';
        p++;
        magnitude = (uint32_t)(-value);
    }
    else
    {
        magnitude = (uint32_t)value;
    }

    return append_dec32(p, magnitude);
}

static void whd_log_result(const char * label, uint32_t result)
{
    char line[96];
    char * p = line;

    p = append_text(p, label);
    p = append_text(p, "=");
    p = append_hex32(p, result);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void whd_log_powersave_mode(const char * label, uint32_t result, uint32_t mode)
{
    char line[96];
    char * p = line;

    p = append_text(p, label);
    p = append_text(p, "=");
    p = append_hex32(p, result);
    p = append_text(p, " mode=");
    p = append_dec32(p, mode);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void whd_log_sdio_diag(const char * label)
{
    char line[240];
    char * p = line;

    p = append_text(p, label);
    p = append_text(p, " clkdiv=");
    p = append_hex32(p, g_sdio_host_run_clock_div);
    p = append_text(p, " clkst=");
    p = append_hex32(p, g_sdio_host_run_clock_status);
    p = append_text(p, " xfer=");
    p = append_dec32(p, g_sdio_host_cmd53_xfer_engine);
    p = append_text(p, " dscr=");
    p = append_hex32(p, g_sdio_host_portd_dscr);
    p = append_text(p, " dscr2=");
    p = append_hex32(p, g_sdio_host_portd_dscr2);
    p = append_text(p, " irq_en=");
    p = append_dec32(p, g_whd_sdio_sdhi_irq_enable_count);
    p = append_text(p, " defer=");
    p = append_dec32(p, g_whd_sdio_sdhi_irq_deferred_enable_count);
    p = append_text(p, " irq=");
    p = append_dec32(p, g_whd_sdio_sdhi_irq_count);
    p = append_text(p, " notify=");
    p = append_dec32(p, g_whd_sdio_sdhi_irq_notify_count);
    p = append_text(p, " task=");
    p = append_dec32(p, g_whd_sdio_sdhi_irq_task_count);
    p = append_text(p, " f2retry=");
    p = append_dec32(p, g_whd_sdio_cmd53_f2_byte_read_retry_count);
    p = append_text(p, " f2rec=");
    p = append_dec32(p, g_whd_sdio_cmd53_f2_byte_read_recovered_count);
    p = append_text(p, " f2fail=");
    p = append_dec32(p, g_whd_sdio_cmd53_f2_byte_read_retry_fail_count);
    p = append_text(p, " f2abort=");
    p = append_dec32(p, g_whd_sdio_cmd53_f2_byte_read_retry_abort_count);
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

static void whd_log_mac(const char * label, const whd_mac_t * p_mac)
{
    char line[96];
    char * p = line;
    uint32_t i;

    p = append_text(p, label);
    p = append_text(p, "=");
    for (i = 0U; i < sizeof(p_mac->octet); i++)
    {
        if (0U != i)
        {
            p = append_text(p, ":");
        }
        p = append_hex8(p, p_mac->octet[i]);
    }
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}

#if WHD_SCAN_ENABLE
static uint32_t whd_ssid_matches_join_target(const whd_ssid_t * p_ssid)
{
    const char join_ssid[] = WHD_JOIN_SSID;
    uint32_t target_len = (uint32_t)(sizeof(join_ssid) - 1U);

    if (p_ssid->length != target_len)
    {
        return 0U;
    }

    if (0 != memcmp(p_ssid->value, join_ssid, target_len))
    {
        return 0U;
    }

    return 1U;
}

static void whd_record_scan_candidate(uint32_t index, const whd_sync_scan_result_t * p_result)
{
    if (0U == whd_ssid_matches_join_target(&p_result->SSID))
    {
        return;
    }

    g_whd_bringup_target_seen_count++;

    if ((1U == g_whd_bringup_target_seen_count) ||
        ((int32_t)p_result->signal_strength > g_whd_bringup_target_best_rssi))
    {
        memset(&g_target_ap, 0, sizeof(g_target_ap));
        g_target_ap.SSID = p_result->SSID;
        g_target_ap.BSSID = p_result->BSSID;
        g_target_ap.signal_strength = p_result->signal_strength;
        g_target_ap.bss_type = WHD_BSS_TYPE_INFRASTRUCTURE;
        g_target_ap.security = p_result->security;
        g_target_ap.channel = p_result->channel;

        g_whd_bringup_target_best_index = index;
        g_whd_bringup_target_best_rssi = (int32_t)p_result->signal_strength;
        g_whd_bringup_target_security = (uint32_t)p_result->security;
        g_whd_bringup_target_channel = (uint32_t)p_result->channel;
        whd_record_mac(g_whd_bringup_target_bssid, &p_result->BSSID);
    }
}

static char * append_ssid(char * p, const whd_ssid_t * p_ssid)
{
    uint32_t i;

    *p = '"';
    p++;
    for (i = 0U; (i < p_ssid->length) && (i < sizeof(p_ssid->value)); i++)
    {
        uint8_t ch = p_ssid->value[i];

        *p = ((ch >= 0x20U) && (ch <= 0x7eU)) ? (char)ch : '.';
        p++;
    }
    *p = '"';
    p++;

    return p;
}

static void whd_log_scan_result(uint32_t index, const whd_sync_scan_result_t * p_result)
{
    char line[192];
    char * p = line;
    uint32_t i;

    p = append_text(p, "scan[");
    p = append_dec32(p, index);
    p = append_text(p, "] ssid=");
    p = append_ssid(p, &p_result->SSID);
    p = append_text(p, " ch=");
    p = append_dec32(p, p_result->channel);
    p = append_text(p, " rssi=");
    p = append_int32(p, (int32_t)p_result->signal_strength);
    p = append_text(p, " sec=");
    p = append_hex32(p, (uint32_t)p_result->security);
    p = append_text(p, " bssid=");
    for (i = 0U; i < sizeof(p_result->BSSID.octet); i++)
    {
        if (0U != i)
        {
            p = append_text(p, ":");
        }
        p = append_hex8(p, p_result->BSSID.octet[i]);
    }
    p = append_text(p, "\r\n");
    *p = '\0';
    debug_puts(line);
}
#endif

bool whd_bringup_run(void)
{
    whd_init_config_t init_config;
    whd_sdio_config_t sdio_config;
    cyhal_sdio_cfg_t hal_sdio_config;
    uint32_t result;

    g_whd_bringup_stage = 1U;
    g_whd_bringup_last_result = 0U;
    g_whd_bringup_scan_count = 0U;
    g_whd_bringup_join_result = 0xffffffffUL;
    g_whd_bringup_ready_result = 0xffffffffUL;
    g_whd_bringup_rssi = 0;
    g_whd_bringup_channel = 0U;
    g_whd_bringup_target_seen_count = 0U;
    g_whd_bringup_target_best_index = 0xffffffffUL;
    g_whd_bringup_target_best_rssi = -128;
    g_whd_bringup_target_security = 0U;
    g_whd_bringup_target_channel = 0U;
    g_whd_bringup_join_mode = 0U;

    debug_puts("WHD bring-up start\r\n");
    debug_puts("WHD resources linked: fw=TYPE1YN_FW_BLOB nvram=TYPE1YN_NVRAM_BLOB clm=TYPE1YN_CLM_BLOB\r\n");

    memset(&init_config, 0, sizeof(init_config));
    init_config.thread_stack_start = g_whd_thread_stack;
    init_config.thread_stack_size  = sizeof(g_whd_thread_stack);
    init_config.thread_priority    = CY_RTOS_PRIORITY_ABOVENORMAL;
    init_config.country            = WHD_COUNTRY_JAPAN;

    memset(&sdio_config, 0, sizeof(sdio_config));
    sdio_config.sdio_1bit_mode        = WHD_FALSE;
    sdio_config.high_speed_sdio_clock = WHD_TRUE;
    sdio_config.oob_config.host_oob_pin = CYHAL_NC_PIN_VALUE;

    result = cyhal_sdio_init(&g_sdio_obj, CYHAL_NC_PIN_VALUE, CYHAL_NC_PIN_VALUE,
                             CYHAL_NC_PIN_VALUE, CYHAL_NC_PIN_VALUE,
                             CYHAL_NC_PIN_VALUE, CYHAL_NC_PIN_VALUE);
    whd_record_stage(10U, result);
    whd_log_result("cyhal_sdio_init", result);
    if (CY_RSLT_SUCCESS != result)
    {
        return false;
    }

    memset(&hal_sdio_config, 0, sizeof(hal_sdio_config));
    hal_sdio_config.frequencyhal_hz = 50000000UL;
    hal_sdio_config.block_size = 64U;
    result = cyhal_sdio_configure(&g_sdio_obj, &hal_sdio_config);
    whd_record_stage(20U, result);
    whd_log_result("cyhal_sdio_configure", result);
    if (CY_RSLT_SUCCESS != result)
    {
        return false;
    }

    result = whd_init(&g_whd_driver, &init_config,
                      &g_whd_port_resource_source,
                      &g_whd_port_buffer_funcs,
                      &g_whd_port_netif_funcs);
    whd_record_stage(30U, result);
    whd_log_result("whd_init", result);
    if (WHD_SUCCESS != result)
    {
        return false;
    }

    result = whd_bus_sdio_attach(g_whd_driver, &sdio_config, &g_sdio_obj);
    whd_record_stage(40U, result);
    whd_log_result("whd_bus_sdio_attach", result);
    if (WHD_SUCCESS != result)
    {
        return false;
    }

    result = whd_wifi_on(g_whd_driver, &g_whd_ifp);
    whd_record_stage(50U, result);
    whd_log_result("whd_wifi_on", result);
    if (WHD_SUCCESS != result)
    {
        whd_log_sdio_diag("whd_wifi_on diag");
        return false;
    }
    whd_log_sdio_diag("whd_wifi_on ok");

    {
        whd_mac_t mac;

        memset(&mac, 0, sizeof(mac));
        result = whd_wifi_get_mac_address(g_whd_ifp, &mac);
        whd_record_stage(60U, result);
        whd_log_result("whd_wifi_get_mac_address", result);
        if (WHD_SUCCESS == result)
        {
            whd_record_mac(g_whd_bringup_sta_mac, &mac);
            whd_log_mac("sta_mac", &mac);
        }
    }

#if WHD_SCAN_ENABLE
    memset(g_scan_results, 0, sizeof(g_scan_results));
    whd_record_stage(70U, 0U);
    debug_puts("WHD scan start\r\n");
    result = whd_wifi_scan_synch(g_whd_ifp, g_scan_results, WHD_SCAN_RESULT_LIMIT);
    g_whd_bringup_scan_count = result;
    whd_record_stage(71U, result);
    whd_log_result("whd_wifi_scan_synch", result);
    if (result <= WHD_SCAN_RESULT_LIMIT)
    {
        uint32_t i;

        for (i = 0U; i < result; i++)
        {
            whd_log_scan_result(i, &g_scan_results[i]);
            whd_record_scan_candidate(i, &g_scan_results[i]);
        }
    }
#else
    debug_puts("WHD scan skipped (WHD_SCAN_ENABLE=0)\r\n");
#endif

#if WHD_JOIN_ENABLE
    {
        whd_ssid_t ssid;
        const uint8_t passphrase[] = WHD_JOIN_PASSPHRASE;

        memset(&ssid, 0, sizeof(ssid));
        ssid.length = (uint8_t)(sizeof(WHD_JOIN_SSID) - 1U);
        memcpy(ssid.value, WHD_JOIN_SSID, ssid.length);

        whd_record_stage(80U, 0U);
        debug_puts("WHD join start\r\n");
#if WHD_SCAN_ENABLE && WHD_JOIN_USE_SCAN_RESULT
        if (0U != g_whd_bringup_target_seen_count)
        {
            g_whd_bringup_join_mode = 2U;
            result = whd_wifi_join_specific(g_whd_ifp, &g_target_ap,
                                            passphrase, (uint8_t)(sizeof(passphrase) - 1U));
        }
        else
#endif
        {
            g_whd_bringup_join_mode = 1U;
            result = whd_wifi_join(g_whd_ifp, &ssid, WHD_JOIN_SECURITY,
                                   passphrase, (uint8_t)(sizeof(passphrase) - 1U));
        }
        g_whd_bringup_join_result = result;
        whd_record_stage(81U, result);
        whd_log_result("whd_wifi_join", result);
        whd_log_sdio_diag("whd_wifi_join diag");
        if (WHD_SUCCESS == result)
        {
            whd_mac_t bssid;

            memset(&bssid, 0, sizeof(bssid));
            result = whd_wifi_get_bssid(g_whd_ifp, &bssid);
            whd_record_stage(82U, result);
            whd_log_result("whd_wifi_get_bssid", result);
            if (WHD_SUCCESS == result)
            {
                whd_record_mac(g_whd_bringup_ap_bssid, &bssid);
                whd_log_mac("ap_bssid", &bssid);
            }

            result = whd_wifi_is_ready_to_transceive(g_whd_ifp);
            g_whd_bringup_ready_result = result;
            whd_record_stage(83U, result);
            whd_log_result("whd_wifi_is_ready_to_transceive", result);

            if (WHD_SUCCESS == result)
            {
                int32_t rssi = 0;
                uint32_t channel = 0U;
                uint32_t powersave_mode = 0xffffffffUL;

#if WHD_JOIN_DISABLE_POWERSAVE
                result = whd_wifi_get_powersave_mode(g_whd_ifp, &powersave_mode);
                whd_record_stage(831U, result);
                whd_log_powersave_mode("whd_wifi_get_powersave_mode(before)", result, powersave_mode);

                result = whd_wifi_disable_powersave(g_whd_ifp);
                whd_record_stage(832U, result);
                whd_log_result("whd_wifi_disable_powersave", result);

                powersave_mode = 0xffffffffUL;
                result = whd_wifi_get_powersave_mode(g_whd_ifp, &powersave_mode);
                whd_record_stage(833U, result);
                whd_log_powersave_mode("whd_wifi_get_powersave_mode(after)", result, powersave_mode);
#else
                result = whd_wifi_get_powersave_mode(g_whd_ifp, &powersave_mode);
                whd_record_stage(831U, result);
                whd_log_powersave_mode("whd_wifi_get_powersave_mode", result, powersave_mode);
#endif

                result = whd_wifi_get_rssi(g_whd_ifp, &rssi);
                whd_record_stage(84U, result);
                whd_log_result("whd_wifi_get_rssi", result);
                if (WHD_SUCCESS == result)
                {
                    g_whd_bringup_rssi = rssi;
                }

                result = whd_wifi_get_channel(g_whd_ifp, &channel);
                whd_record_stage(85U, result);
                whd_log_result("whd_wifi_get_channel", result);
                if (WHD_SUCCESS == result)
                {
                    g_whd_bringup_channel = channel;
                }
            }
        }
    }
#else
    debug_puts("WHD join skipped (WHD_JOIN_ENABLE=0)\r\n");
#endif

#if WHD_JOIN_ENABLE
    if ((WHD_SUCCESS != g_whd_bringup_join_result) ||
        (WHD_SUCCESS != g_whd_bringup_ready_result))
    {
        debug_puts("WHD bring-up failed before network start\r\n");
        return false;
    }
#endif

    whd_record_stage(90U, 0U);
    debug_puts("WHD bring-up done\r\n");
    return true;
}

whd_interface_t whd_bringup_get_interface(void)
{
    return g_whd_ifp;
}

void whd_bringup_get_sta_mac(uint8_t mac[6])
{
    uint32_t i;

    if (NULL == mac)
    {
        return;
    }

    for (i = 0U; i < 6U; i++)
    {
        mac[i] = (uint8_t)g_whd_bringup_sta_mac[i];
    }
}
