/* Copyright (c) 2026 SAFFTI and contributors. SPDX-License-Identifier: BSD-3-Clause */
#include "lfs_common_data.h"
#include "platform.h"
#include "rm_littlefs_flash_config.h"
#include "FreeRTOS.h"
#include "task.h"
#include "semphr.h"
#include "r_common_api_flash.h"
#include "rm_rtos_abstraction_rx_if.h"

#ifdef LFS_THREADSAFE
#error "rm_littlefs_rx uses product-level locking; do not enable LFS_THREADSAFE."
#endif

static rm_littlefs_ctrl_t s_littlefs;
static StaticSemaphore_t s_mutex_buffer;
static SemaphoreHandle_t s_mutex;
/* Kept for the PKCS11 diagnostic trace switch. No borrowed callbacks are patched. */
volatile uint32_t g_littlefs_flash_trace_enabled = 0U;

static const rm_littlefs_cfg_t s_config =
{
    .base_address = RM_LITTLEFS_FLASH_DATA_START,
    .region_size = LFS_FLASH_BLOCK_SIZE * LFS_FLASH_BLOCK_COUNT,
    .read_size = LFS_FLASH_READ_SIZE,
    .prog_size = LFS_FLASH_PROGRAM_SIZE,
    .block_size = LFS_FLASH_BLOCK_SIZE,
    .cache_size = RM_LITTLEFS_CFG_CACHE_SIZE,
    .lookahead_size = RM_LITTLEFS_CFG_LOOKAHEAD_SIZE,
    .block_cycles = RM_LITTLEFS_CFG_BLOCK_CYCLES,
    .format_if_mount_failed = 1U
};

static int32_t prvMapError(rm_littlefs_err_t error)
{
    switch (error)
    {
        case RM_LITTLEFS_SUCCESS: return LFS_ERR_OK;
        case RM_LITTLEFS_ERR_INVALID_ARGUMENT: return LFS_ERR_INVAL;
        case RM_LITTLEFS_ERR_MOUNT: return LFS_ERR_CORRUPT;
        case RM_LITTLEFS_ERR_NOT_OPEN: return LFS_ERR_BADF;
        default: return LFS_ERR_IO;
    }
}

static void prvSleepTask(rm_rtos_abstraction_task_id_t task_id)
{
    (void) task_id;
    if (taskSCHEDULER_RUNNING == xTaskGetSchedulerState())
    {
        vTaskDelay(1U);
    }
}

static int32_t prvOpen(void)
{
    if (NULL != RM_LITTLEFS_GetLfs(&s_littlefs))
    {
        return LFS_ERR_OK;
    }
    /* Retain the application-wide Flash BGO callback/priority used by OTA.
     * The RX adapter tolerates the already-open Flash driver. */
    if (COMMONAPI_SUCCESS != R_Demo_Common_API_Flash_Open())
    {
        return LFS_ERR_IO;
    }
    if (RM_RTOS_ABSTRACTION_SUCCESS != RM_RTOS_ABSTRACTION_SetSleepTask(prvSleepTask))
    {
        return LFS_ERR_IO;
    }
    return prvMapError(RM_LITTLEFS_Open(&s_littlefs, &s_config));
}

int32_t littlFs_init(void)
{
    int32_t result;
    if (NULL == s_mutex)
    {
        s_mutex = xSemaphoreCreateMutexStatic(&s_mutex_buffer);
    }
    if ((NULL == s_mutex) || (pdTRUE != xSemaphoreTake(s_mutex, portMAX_DELAY)))
    {
        return LFS_ERR_IO;
    }
    result = prvOpen();
    (void) xSemaphoreGive(s_mutex);
    return result;
}

int32_t littlFs_format(void)
{
    int32_t result;
    if (LFS_ERR_OK != (result = littlFs_init()))
    {
        return result;
    }
    if (pdTRUE != xSemaphoreTake(s_mutex, portMAX_DELAY))
    {
        return LFS_ERR_IO;
    }
    result = prvMapError(RM_LITTLEFS_Format(&s_littlefs));
    (void) xSemaphoreGive(s_mutex);
    return result;
}

lfs_t * LfsCommon_GetLfs(void)
{
    return RM_LITTLEFS_GetLfs(&s_littlefs);
}

static int prvLock(lfs_t * lfs)
{
    if ((NULL == s_mutex) || (pdTRUE != xSemaphoreTake(s_mutex, portMAX_DELAY)))
    {
        return LFS_ERR_IO;
    }
    if ((NULL == lfs) || (lfs != RM_LITTLEFS_GetLfs(&s_littlefs)))
    {
        (void) xSemaphoreGive(s_mutex);
        return LFS_ERR_BADF;
    }
    return LFS_ERR_OK;
}

int LfsCommon_Remove(lfs_t *lfs, const char *path)
{
    int result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_remove(lfs, path);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}

int LfsCommon_Rename(lfs_t *lfs, const char *oldpath, const char *newpath)
{
    int result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_rename(lfs, oldpath, newpath);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}

int LfsCommon_Stat(lfs_t *lfs, const char *path, struct lfs_info *info)
{
    int result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_stat(lfs, path, info);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}

int LfsCommon_FileOpen(lfs_t *lfs, lfs_file_t *file, const char *path, int flags)
{
    int result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_file_open(lfs, file, path, flags);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}

int LfsCommon_FileClose(lfs_t *lfs, lfs_file_t *file)
{
    int result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_file_close(lfs, file);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}

int LfsCommon_FileSync(lfs_t *lfs, lfs_file_t *file)
{
    int result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_file_sync(lfs, file);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}

lfs_ssize_t LfsCommon_FileRead(lfs_t *lfs, lfs_file_t *file, void *buffer, lfs_size_t size)
{
    lfs_ssize_t result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_file_read(lfs, file, buffer, size);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}

lfs_ssize_t LfsCommon_FileWrite(lfs_t *lfs, lfs_file_t *file, const void *buffer, lfs_size_t size)
{
    lfs_ssize_t result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_file_write(lfs, file, buffer, size);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}

lfs_soff_t LfsCommon_FileSeek(lfs_t *lfs, lfs_file_t *file, lfs_soff_t offset, int whence)
{
    lfs_soff_t result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_file_seek(lfs, file, offset, whence);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}

lfs_soff_t LfsCommon_FileSize(lfs_t *lfs, lfs_file_t *file)
{
    lfs_soff_t result = prvLock(lfs);
    if (LFS_ERR_OK == result)
    {
        result = lfs_file_size(lfs, file);
        (void) xSemaphoreGive(s_mutex);
    }
    return result;
}
