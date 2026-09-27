"""Latch failed flash callbacks even when native IDT ignores their exit code."""
import json
import os
from pathlib import Path

MARKER = "flash-callback-failure.json"


def record_flash_failure(runtime, error):
    path = Path(runtime).resolve(strict=True) / MARKER
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_NOFOLLOW", 0), 0o600)
    except FileExistsError:
        return  # The first failure remains latched for the entire run.
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        # Exception messages and command arguments can contain credentials.
        json.dump({"schema_version": 1, "error_type": type(error).__name__}, stream)
        stream.write("\n")


def raise_if_flash_failed(runtime):
    directory = Path(runtime).resolve(strict=True)
    try:
        (directory / MARKER).lstat()
    except FileNotFoundError:
        return
    # Presence is enough: malformed/partial content is never a success signal.
    raise RuntimeError("Firmware flash callback failed; remaining native results are invalid")
