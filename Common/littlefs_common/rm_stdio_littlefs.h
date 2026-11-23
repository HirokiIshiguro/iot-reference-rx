/*
* Copyright (c) 2023-2025 Renesas Electronics Corporation and/or its affiliates
*
* SPDX-License-Identifier: BSD-3-Clause
*/

/***********************************************************************************************************************
 * File Name    : rm_stdio_littlefs.h
 * Description  : Header file providing stdio-like API wrappers for LittleFS integration.
 **********************************************************************************************************************/

#ifndef RM_STDIO_LITTLEFS_H
#define RM_STDIO_LITTLEFS_H

/**********************************************************************************************************************
 Includes   <System Includes> , "Project Includes"
 *********************************************************************************************************************/
#include <stdio.h>
#include <stdlib.h>
#include "lfs_common_data.h"
#include "lfs.h"
#include "lfs_util.h"

/** Common macro for FSP header files. There is also a corresponding  macro at the end of this file. */


/**********************************************************************************************************************
 * Macro definitions
 **********************************************************************************************************************/

/* By default IAR does not define FILE unless DLIB is used. */
#if defined(__ICCARM__)
    #if !_DLIB_FILE_DESCRIPTOR
typedef void FILE;
    #endif
#endif

#define MBEDTLS_CONFIG_LFS    (LfsCommon_GetLfs())



/**********************************************************************************************************************
 * Function Name: rm_littlefs_fopen
 * Description  : .
 * Arguments    : path
 *              : mode
 * Return Value : .
 *********************************************************************************************************************/
static FILE * rm_littlefs_fopen(const char * path, const char * mode)
{
    /* Allocate a LittleFS file instance. */
    lfs_file_t * file = malloc(sizeof(lfs_file_t));
    int          lfs_status;

    if (NULL != file)
    {
        /* Check if the file is being opened for read or write and set the LittleFS flags. */
        int flags = ('r' == mode[0]) ? LFS_O_RDONLY : LFS_O_WRONLY | LFS_O_CREAT;

        lfs_status = LfsCommon_FileOpen(MBEDTLS_CONFIG_LFS, file, path, flags);

        /* If the file failed to open free the memory and return NULL. */
        if (lfs_status != LFS_ERR_OK)
        {
            free(file);
            file = NULL;
        }
    }

    return (FILE *) file;
}
/*****************************************************************************************
End of function rm_littlefs_fopen
****************************************************************************************/

/* Use the above inline function to replace fopen. */
#define fopen    (rm_littlefs_fopen)

/* fwrite macro defenition */
#define fwrite(data, n, len, stream)    (LfsCommon_FileWrite(MBEDTLS_CONFIG_LFS, (lfs_file_t *) stream, data, n * len))

/* fread macro defenition */
#define fread(data, n, len, stream)     (LfsCommon_FileRead(MBEDTLS_CONFIG_LFS, (lfs_file_t *) stream, data, n * len))

/* fseek macro defenition */
#define fseek(stream, offset,                                                                              \
                seek)                     ((LfsCommon_FileSeek(MBEDTLS_CONFIG_LFS, (lfs_file_t *) stream, offset, \
                                                        seek) >= 0) ? 0 : -1)

/* remove macro defenition */
#define remove(file)                    (LfsCommon_Remove(MBEDTLS_CONFIG_LFS, file))

/* Free the memory associated with this file after it is closed. */
static int rm_littlefs_fclose(FILE *stream)
{
    int result = LfsCommon_FileClose(MBEDTLS_CONFIG_LFS, (lfs_file_t *) stream);
    free(stream);
    return result;
}
#define fclose(stream)                  rm_littlefs_fclose(stream)

/* rename macro defenition */
#define rename(oldpath, newpath)        (LfsCommon_Rename(MBEDTLS_CONFIG_LFS, oldpath, newpath))


/**********************************************************************************************************************
 * Typedef definitions
 **********************************************************************************************************************/

/** Common macro for FSP header files. There is also a corresponding  macro at the top of this file. */


#endif
