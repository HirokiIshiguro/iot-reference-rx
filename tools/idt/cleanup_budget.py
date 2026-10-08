"""Bounds shared by callbacks, the bench bridge and the Windows supervisor.

The transaction deadline starts before acquiring the global RFP lock. RX671
also prepares the signer using the production linear provisioning firmware.
An interrupted/failed transaction may reset for another 90 seconds while
holding RFP. Since all boards share that lock, bridge shutdown allows the
longest supported transaction regardless of its own selected target.
"""

FLASH_LOCK_WAIT_SECONDS = 60
FLASH_CONTROL_SECONDS = 15
FLASH_RFP_COMMAND_SECONDS = 90
FLASH_DOWNLOAD_SECONDS = 540
RX671_SIGNER_PROVISION_SECONDS = 200
FLASH_TRANSACTION_PHASES = {
    "rx72n-ethernet": {
        "rfp_lock": FLASH_LOCK_WAIT_SECONDS,
        "uart_control": 3 * FLASH_CONTROL_SECONDS,
        "erase_and_bootloader_writes": 3 * FLASH_RFP_COMMAND_SECONDS,
        "uart_download": FLASH_DOWNLOAD_SECONDS,
        "final_reset_and_run": 2 * FLASH_RFP_COMMAND_SECONDS,
    },
    "rx65n-bg96": {
        "rfp_lock": FLASH_LOCK_WAIT_SECONDS,
        "uart_control": 3 * FLASH_CONTROL_SECONDS,
        "erase_and_bootloader_writes": 3 * FLASH_RFP_COMMAND_SECONDS,
        "uart_download": FLASH_DOWNLOAD_SECONDS,
        "final_reset_and_run": 2 * FLASH_RFP_COMMAND_SECONDS,
    },
    "rx671-wifi": {
        "rfp_lock": FLASH_LOCK_WAIT_SECONDS,
        "uart_control": 3 * FLASH_CONTROL_SECONDS,
        "initial_chip_erase": FLASH_RFP_COMMAND_SECONDS,
        "linear_provisioning_and_bootloader": 4 * FLASH_RFP_COMMAND_SECONDS,
        "signer_provisioning_cli": RX671_SIGNER_PROVISION_SECONDS,
        "bank1_bootloader_write": FLASH_RFP_COMMAND_SECONDS,
        "uart_download": FLASH_DOWNLOAD_SECONDS,
        "final_reset_and_run": 2 * FLASH_RFP_COMMAND_SECONDS,
    },
}
FLASH_TRANSACTION_SECONDS = {target: sum(phases.values()) for target, phases in FLASH_TRANSACTION_PHASES.items()}
FLASH_ABORT_RESET_SECONDS = 90
REMOTE_EXIT_MARGIN_SECONDS = 30
RFP_LOCK_WAIT_SECONDS = max(FLASH_TRANSACTION_SECONDS.values()) + FLASH_ABORT_RESET_SECONDS
END_STATE_RESET_SECONDS = 60
END_STATE_QUIET_SECONDS = 1
BRIDGE_SHUTDOWN_SECONDS = (RFP_LOCK_WAIT_SECONDS + END_STATE_RESET_SECONDS +
                           END_STATE_QUIET_SECONDS + REMOTE_EXIT_MARGIN_SECONDS)

NATIVE_CLEANUP_SECONDS = 120
NATIVE_TERMINATE_SECONDS = 10
NATIVE_KILL_SECONDS = 5
REMOTE_TERMINATE_SECONDS = 5
REMOTE_KILL_SECONDS = 5
CAPTURE_DRAIN_SECONDS = 5
BRIDGE_THREAD_JOIN_SECONDS = 1
SUPERVISOR_EXIT_MARGIN_SECONDS = 30


def flash_transaction_seconds(target_id):
    try:
        return FLASH_TRANSACTION_SECONDS[target_id]
    except (KeyError, TypeError):
        raise ValueError("Unknown IDT target for flash time budget") from None


def flash_remote_seconds(target_id):
    return (flash_transaction_seconds(target_id) + FLASH_ABORT_RESET_SECONDS +
            REMOTE_EXIT_MARGIN_SECONDS)


def owned_runtime_cleanup_seconds(native_cleanup_seconds=NATIVE_CLEANUP_SECONDS):
    if (not isinstance(native_cleanup_seconds, (int, float)) or
            isinstance(native_cleanup_seconds, bool) or native_cleanup_seconds <= 0):
        raise ValueError("Native cleanup time budget must be positive")
    return (native_cleanup_seconds + NATIVE_TERMINATE_SECONDS + NATIVE_KILL_SECONDS +
            BRIDGE_SHUTDOWN_SECONDS + REMOTE_TERMINATE_SECONDS + REMOTE_KILL_SECONDS +
            CAPTURE_DRAIN_SECONDS + 3 * BRIDGE_THREAD_JOIN_SECONDS + SUPERVISOR_EXIT_MARGIN_SECONDS)
