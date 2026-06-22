/*
 * WHD firmware/NVRAM/CLM resources linked into RX671 code flash.
 *
 * The binary blobs are pinned as project-local submodules, staged by
 * external/type1yn-blobs/stage_type1yn_blobs.ps1, and linked by CC-RX
 * -binary options into the TYPE1YN_*_BLOB sections.
 */
#include <stdint.h>
#include <stddef.h>

#include "whd.h"
#include "whd_resource_api.h"
#include "whd_port.h"

#define WHD_RESOURCE_BLOCK_BYTES        (1024UL)

#define TYPE1YN_FW_BLOB_SIZE            (249066UL)
#define TYPE1YN_NVRAM_BLOB_SIZE         (816UL)
#define TYPE1YN_CLM_BLOB_SIZE           (4752UL)

extern const uint8_t g_type1yn_firmware_bin[];
extern const uint8_t g_type1yn_nvram_bin[];
extern const uint8_t g_type1yn_clm_blob[];

typedef struct st_whd_resource_entry
{
    const uint8_t * p_data;
    uint32_t        size;
} whd_resource_entry_t;

static whd_result_t whd_resource_lookup(whd_resource_type_t type, whd_resource_entry_t * p_entry)
{
    if (NULL == p_entry)
    {
        return WHD_BADARG;
    }

    switch (type)
    {
        case WHD_RESOURCE_WLAN_FIRMWARE:
            p_entry->p_data = g_type1yn_firmware_bin;
            p_entry->size   = TYPE1YN_FW_BLOB_SIZE;
            break;
        case WHD_RESOURCE_WLAN_NVRAM:
            p_entry->p_data = g_type1yn_nvram_bin;
            p_entry->size   = TYPE1YN_NVRAM_BLOB_SIZE;
            break;
        case WHD_RESOURCE_WLAN_CLM:
            p_entry->p_data = g_type1yn_clm_blob;
            p_entry->size   = TYPE1YN_CLM_BLOB_SIZE;
            break;
        default:
            return WHD_WLAN_NOTFOUND;
    }

    return WHD_SUCCESS;
}

static uint32_t whd_port_resource_size(whd_driver_t whd_drv, whd_resource_type_t resource, uint32_t * size_out)
{
    whd_resource_entry_t entry;
    whd_result_t result;

    (void)whd_drv;

    if (NULL == size_out)
    {
        return WHD_BADARG;
    }

    result = whd_resource_lookup(resource, &entry);
    if (WHD_SUCCESS != result)
    {
        return result;
    }

    *size_out = entry.size;
    return WHD_SUCCESS;
}

static uint32_t whd_port_get_resource_block(whd_driver_t whd_drv, whd_resource_type_t type,
                                            uint32_t blockno, const uint8_t ** data, uint32_t * size_out)
{
    whd_resource_entry_t entry;
    uint32_t offset;
    whd_result_t result;

    (void)whd_drv;

    if ((NULL == data) || (NULL == size_out))
    {
        return WHD_BADARG;
    }

    result = whd_resource_lookup(type, &entry);
    if (WHD_SUCCESS != result)
    {
        return result;
    }

    offset = blockno * WHD_RESOURCE_BLOCK_BYTES;
    if (offset >= entry.size)
    {
        return WHD_WLAN_BADARG;
    }

    *data = &entry.p_data[offset];
    *size_out = entry.size - offset;
    if (*size_out > WHD_RESOURCE_BLOCK_BYTES)
    {
        *size_out = WHD_RESOURCE_BLOCK_BYTES;
    }

    return WHD_SUCCESS;
}

static uint32_t whd_port_get_resource_no_of_blocks(whd_driver_t whd_drv, whd_resource_type_t type,
                                                   uint32_t * block_count)
{
    whd_resource_entry_t entry;
    whd_result_t result;

    (void)whd_drv;

    if (NULL == block_count)
    {
        return WHD_BADARG;
    }

    result = whd_resource_lookup(type, &entry);
    if (WHD_SUCCESS != result)
    {
        return result;
    }

    *block_count = (entry.size + WHD_RESOURCE_BLOCK_BYTES - 1UL) / WHD_RESOURCE_BLOCK_BYTES;
    return WHD_SUCCESS;
}

static uint32_t whd_port_get_resource_block_size(whd_driver_t whd_drv, whd_resource_type_t type, uint32_t * size_out)
{
    whd_resource_entry_t entry;
    whd_result_t result;

    (void)whd_drv;

    if (NULL == size_out)
    {
        return WHD_BADARG;
    }

    result = whd_resource_lookup(type, &entry);
    if (WHD_SUCCESS != result)
    {
        return result;
    }

    *size_out = WHD_RESOURCE_BLOCK_BYTES;
    return WHD_SUCCESS;
}

whd_resource_source_t g_whd_port_resource_source =
{
    whd_port_resource_size,
    whd_port_get_resource_block,
    whd_port_get_resource_no_of_blocks,
    whd_port_get_resource_block_size,
};
