/* Copyright (c) 2026 SAFFTI and contributors. SPDX-License-Identifier: BSD-3-Clause */
#ifndef LFS_COMMON_DATA_H
#define LFS_COMMON_DATA_H

#include <stdint.h>
#include "rm_littlefs_rx_if.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Application storage operations are serialized here. The pristine RX adapter
 * is built without LFS_THREADSAFE, whose lock hooks it does not implement.
 * Initialize storage during application startup before other users run. */
int32_t littlFs_init(void);
int32_t littlFs_format(void);
lfs_t * LfsCommon_GetLfs(void);
int LfsCommon_Remove(lfs_t *lfs, const char *path);
int LfsCommon_Rename(lfs_t *lfs, const char *oldpath, const char *newpath);
int LfsCommon_Stat(lfs_t *lfs, const char *path, struct lfs_info *info);
lfs_ssize_t LfsCommon_GetAttr(lfs_t *lfs, const char *path, uint8_t type, void *buffer, lfs_size_t size);
int LfsCommon_SetAttr(lfs_t *lfs, const char *path, uint8_t type, const void *buffer, lfs_size_t size);
int LfsCommon_RemoveAttr(lfs_t *lfs, const char *path, uint8_t type);
int LfsCommon_FileOpen(lfs_t *lfs, lfs_file_t *file, const char *path, int flags);
/* Opens a file with LittleFS custom attributes (lfs_file_opencfg). With a readable
 * mode, the attributes in config->attrs are read into their buffers on open. With a
 * writable mode, the attribute buffers are written on LfsCommon_FileSync and
 * LfsCommon_FileClose, together with the file contents. The caller must keep config,
 * the attrs array, every attribute buffer and config->buffer (if set) valid and
 * unchanged in place until LfsCommon_FileClose returns. */
int LfsCommon_FileOpenCfg(lfs_t *lfs, lfs_file_t *file, const char *path, int flags,
                          const struct lfs_file_config *config);
int LfsCommon_FileClose(lfs_t *lfs, lfs_file_t *file);
int LfsCommon_FileSync(lfs_t *lfs, lfs_file_t *file);
lfs_ssize_t LfsCommon_FileRead(lfs_t *lfs, lfs_file_t *file, void *buffer, lfs_size_t size);
lfs_ssize_t LfsCommon_FileWrite(lfs_t *lfs, lfs_file_t *file, const void *buffer, lfs_size_t size);
lfs_soff_t LfsCommon_FileSeek(lfs_t *lfs, lfs_file_t *file, lfs_soff_t offset, int whence);
lfs_soff_t LfsCommon_FileSize(lfs_t *lfs, lfs_file_t *file);

#ifdef __cplusplus
}
#endif
#endif /* LFS_COMMON_DATA_H */
