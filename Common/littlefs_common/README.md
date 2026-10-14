# Application LittleFS integration

`lfs_common_data.c` uses the public API of the pristine `rm_littlefs_rx` submodule.
The application and bootloader build the same upstream littlefs core. The selected
source revisions are recorded in the product dependency manifest and gitlinks.
The old RA/FSP-derived `RM_LITTLEFS_FLASH_*` adapter and shim headers are removed.

The application partition comes from each project's `rm_littlefs_flash_config.h`;
the RX adapter settings come from `rm_littlefs_rx_config.h`. The bootloader uses its
public `rx_bootloader_config.h`. The product tests compile those actual headers
and check that all five applications and three bootloaders agree on the partition
and read/program/block/cache geometry.

Initialize storage with `littlFs_init()` during startup before other storage users
run. Repeated successful initialization preserves the mounted filesystem. As in
the previous application integration, an initial mount failure requests formatting
through the adapter's public configuration. Changing the partition or persistent
format therefore requires a controlled provisioning procedure before hardware use.

All product CLI, KVS, PKCS11, TSIP and stdio calls use `LfsCommon_*` functions. A
single static FreeRTOS mutex serializes each complete public filesystem operation,
including the adapter's synchronous BGO completion wait. Explicit formatting uses
`RM_LITTLEFS_Format()` while holding the same mutex. Borrowed littlefs and the RX
adapter are built without `LFS_THREADSAFE`: the adapter does not install the lock
callbacks required by that option. No borrowed source or callback is replaced.

The existing application Flash service installs the BGO callback shared with OTA.
`RM_RTOS_ABSTRACTION_SetSleepTask()` binds the adapter's public busy-wait hook to
one FreeRTOS tick when the scheduler runs. The adapter remains responsible for the
Flash block callbacks and completion polling.

`tools/ci/tests/test_product_littlefs.py` exercises the actual application headers,
the pristine RX API, and a pristine littlefs filesystem backed by host RAM. It
checks storage errors, mutex release, retries, idempotent initialization, a public
signer file roundtrip and formatting. Host tests and object compilation do not
establish device execution or OTA compatibility.
