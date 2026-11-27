#define _DEFAULT_SOURCE
#include <assert.h>
#include <stdint.h>
#include <string.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <sys/mman.h>
#endif

#include "platform.h"
#include "rm_littlefs_flash_config.h"
#include "rm_littlefs_rx_if.h"
#include "r_flash_rx_if.h"
#include "rx_bootloader_config.h"

#define LEGACY_SIZE (16u * 1024u)
#define FLASH_SIZE BSP_DATA_FLASH_SIZE_BYTES

static uint8_t *flash;
static unsigned mutations;
static int flash_open;
static const char public_key[] = "DFL1 test data";

flash_err_t R_FLASH_Open(void)
{
    assert(!flash_open);
    flash_open = 1;
    return FLASH_SUCCESS;
}

flash_err_t R_FLASH_Close(void)
{
    assert(flash_open);
    flash_open = 0;
    return FLASH_SUCCESS;
}

flash_err_t R_FLASH_Write(uint32_t source, uint32_t destination, uint32_t size)
{
    uint8_t *target = (uint8_t *)(uintptr_t)destination;
    const uint8_t *data = (const uint8_t *)(uintptr_t)source;
    assert(flash_open && target >= flash && target + size <= flash + FLASH_SIZE);
    for (uint32_t i = 0; i < size; ++i)
    {
        assert((target[i] & data[i]) == data[i]);
        target[i] &= data[i];
    }
    ++mutations;
    return FLASH_SUCCESS;
}

flash_err_t R_FLASH_Erase(flash_block_address_t address, uint32_t blocks)
{
    uint8_t *target = (uint8_t *)(uintptr_t)address;
    uint32_t size = blocks * FLASH_DF_BLOCK_SIZE;
    assert(flash_open && target >= flash && target + size <= flash + FLASH_SIZE);
    memset(target, 0xff, size);
    ++mutations;
    return FLASH_SUCCESS;
}

flash_err_t R_FLASH_Control(int command, void *argument)
{
    assert(flash_open && command == FLASH_CMD_STATUS_GET && argument == NULL);
    return FLASH_SUCCESS;
}

static void check_public_key(rm_littlefs_ctrl_t *ctrl)
{
    char result[sizeof(public_key)] = {0};
    lfs_t *lfs = RM_LITTLEFS_GetLfs(ctrl);
    lfs_file_t file = {0};

    assert(lfs != NULL);
    assert(lfs_file_open(lfs, &file, RX_BOOTLOADER_LITTLEFS_PUBLIC_KEY_FILE, LFS_O_RDONLY) == 0);
    assert(lfs_file_read(lfs, &file, result, sizeof(result)) == sizeof(result));
    assert(memcmp(result, public_key, sizeof(result)) == 0);
    assert(lfs_file_close(lfs, &file) == 0);
}

int main(void)
{
    const size_t mapping_size = FLASH_SIZE + sizeof(rm_littlefs_ctrl_t);
    void *const low_address = (void *)(uintptr_t)0x10000000u;
#ifdef _WIN32
    flash = VirtualAlloc(low_address, mapping_size, MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE);
#else
    flash = mmap(low_address, mapping_size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0);
    assert(flash != MAP_FAILED);
#endif
    /* The RX adapter passes flash addresses and its program buffer as 32-bit values. */
    assert(flash != NULL && (uintptr_t)flash <= UINT32_MAX - mapping_size);
    rm_littlefs_ctrl_t *ctrl = (rm_littlefs_ctrl_t *)(flash + FLASH_SIZE);
    rm_littlefs_cfg_t cfg = {0};
    lfs_file_t file = {0};
    struct lfs_fsinfo info;
    unsigned seeded_mutations;
    uint32_t probe;

    assert(RM_LITTLEFS_CFG_FORMAT_IF_MOUNT_FAILED == 0);
    memset(flash, 0xff, FLASH_SIZE);
    cfg.base_address = (uint32_t)(uintptr_t)flash;
    cfg.region_size = LEGACY_SIZE;
    cfg.format_if_mount_failed = 1;
    assert(RM_LITTLEFS_Open(ctrl, &cfg) == RM_LITTLEFS_SUCCESS);
    lfs_t *lfs = RM_LITTLEFS_GetLfs(ctrl);
    assert(lfs_file_open(lfs, &file, RX_BOOTLOADER_LITTLEFS_PUBLIC_KEY_FILE,
                         LFS_O_CREAT | LFS_O_WRONLY) == 0);
    assert(lfs_file_write(lfs, &file, public_key, sizeof(public_key)) == sizeof(public_key));
    assert(lfs_file_close(lfs, &file) == 0);
    assert(RM_LITTLEFS_Close(ctrl) == RM_LITTLEFS_SUCCESS);
    seeded_mutations = mutations;

    cfg.region_size = LFS_FLASH_BLOCK_SIZE * LFS_FLASH_BLOCK_COUNT;
    assert(RM_LITTLEFS_Open(ctrl, &cfg) == RM_LITTLEFS_SUCCESS);
    check_public_key(ctrl);
    assert(lfs_fs_stat(RM_LITTLEFS_GetLfs(ctrl), &info) == 0 && info.block_count == 128);
    assert(RM_LITTLEFS_Close(ctrl) == RM_LITTLEFS_SUCCESS);
    assert(mutations == seeded_mutations);

    cfg.region_size = RX_BOOTLOADER_LITTLEFS_KEY_STORE_REGION_SIZE;
    cfg.format_if_mount_failed = 0;
    assert(RM_LITTLEFS_Open(ctrl, &cfg) == RM_LITTLEFS_SUCCESS);
    check_public_key(ctrl);
    assert(ctrl->lfs_cfg.read(&ctrl->lfs_cfg, 256, 0, &probe, sizeof(probe)) == LFS_ERR_IO);
    assert(RM_LITTLEFS_Close(ctrl) == RM_LITTLEFS_SUCCESS);
    assert(mutations == seeded_mutations);

    memset(flash, 0xff, FLASH_SIZE);
    assert(RM_LITTLEFS_Open(ctrl, &cfg) == RM_LITTLEFS_ERR_MOUNT);
    assert(mutations == seeded_mutations && !flash_open);
    cfg.format_if_mount_failed = 1;
    assert(RM_LITTLEFS_Open(ctrl, &cfg) == RM_LITTLEFS_SUCCESS);
    assert(lfs_fs_stat(RM_LITTLEFS_GetLfs(ctrl), &info) == 0 && info.block_count == 256);
    assert(RM_LITTLEFS_Close(ctrl) == RM_LITTLEFS_SUCCESS);

    seeded_mutations = mutations;
    cfg.region_size = LEGACY_SIZE;
    assert(RM_LITTLEFS_Open(ctrl, &cfg) == RM_LITTLEFS_ERR_MOUNT);
    assert(mutations == seeded_mutations && !flash_open);

#ifdef _WIN32
    assert(VirtualFree(flash, 0, MEM_RELEASE));
#else
    assert(munmap(flash, mapping_size) == 0);
#endif
    return 0;
}
