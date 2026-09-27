"""Private, passive UART capture and independent OTA boot-image observations."""
import hashlib
import json
import os
from pathlib import Path
import re
import threading
import time
from datetime import datetime, timezone

BOOT = re.compile(rb"\[IDT_BOOT\] image=([a-f0-9]{32}) version=(\d+\.\d+\.\d+)")


def version_tuple(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d+\.\d+\.\d+", value):
        raise ValueError("Invalid application version")
    result = tuple(map(int, value.split(".")))
    if any(value > limit for value, limit in zip(result, (255, 255, 65535))):
        raise ValueError("Application version exceeds its fields")
    return result


class UartWitness:
    def __init__(self, private_dir, public_output=None, max_bytes=128 * 1024 * 1024):
        self.directory = Path(private_dir).resolve()
        if public_output is not None:
            public = Path(public_output).resolve()
            if self.directory == public or public in self.directory.parents:
                raise ValueError("Raw UART must remain outside public artifacts")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        self._lock = threading.Lock()
        self._raw = self._events_file = None
        self._hash, self._bytes = hashlib.sha256(), 0
        self._pending, self.events = b"", []
        self._error, self._finished = None, False
        self.max_bytes = max_bytes
        try:
            self._raw = self._open("uart.bin")
            self._events_file = self._open("events.jsonl")
        except OSError:
            if self._raw:
                self._raw.close()
            raise

    def _open(self, name):
        fd = os.open(self.directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     getattr(os, "O_BINARY", 0), 0o600)
        return os.fdopen(fd, "wb")

    def feed(self, data):
        with self._lock:
            if self._finished or self._error:
                raise RuntimeError("UART capture is not writable")
            try:
                if self._bytes + len(data) > self.max_bytes:
                    raise OSError("UART capture capacity exceeded")
                if self._raw.write(data) != len(data):
                    raise OSError("Incomplete UART capture write")
                self._hash.update(data)
                self._bytes += len(data)
                lines = (self._pending + data).split(b"\n")
                self._pending = lines.pop()
                if len(self._pending) > 65536 or any(len(line) > 65536 for line in lines):
                    raise OSError("UART line capacity exceeded")
                for line in lines:
                    line = line.rstrip(b"\r")
                    match = BOOT.fullmatch(line)
                    if not match:
                        if line.startswith(b"[IDT_BOOT]"):
                            raise OSError("Invalid boot witness frame")
                        continue
                    image_id, version = (part.decode("ascii") for part in match.groups())
                    version_tuple(version)
                    event = {"event": "boot", "image_id": image_id, "version": version,
                             "utc": datetime.now(timezone.utc).isoformat(),
                             "monotonic_ns": time.monotonic_ns()}
                    encoded = (json.dumps(event, sort_keys=True) + "\n").encode("utf-8")
                    if self._events_file.write(encoded) != len(encoded):
                        raise OSError("Incomplete boot witness write")
                    self._events_file.flush()
                    self.events.append(event)
            except (OSError, ValueError) as error:
                self._error = type(error).__name__  # Never expose UART content.
                raise

    def finish(self):
        with self._lock:
            if not self._finished:
                if self._pending.startswith(b"[IDT_BOOT"):
                    self._error = "truncated_boot_marker"
                for stream in (self._raw, self._events_file):
                    if stream:
                        try:
                            stream.flush()
                            os.fsync(stream.fileno())
                        except OSError:
                            self._error = "capture_close_error"
                        finally:
                            try:
                                stream.close()
                            except OSError:
                                self._error = "capture_close_error"
                self._finished = True
            return {"schema_version": 1, "complete": self._error is None,
                    "error": self._error, "raw_bytes": self._bytes,
                    "raw_sha256": self._hash.hexdigest(), "events": list(self.events)}


def analyze_ota_witness(events, build_ledger, selected_test_id=None, capture_complete=True,
                        initial_image_id=None, candidate_image_id=None):
    reasons, images, observed, pre_run = [], {}, [], []
    required = selected_test_id == "OTAE2EGreaterVersion"
    if not capture_complete:
        reasons.append("UART capture did not finish successfully")
    try:
        for build in build_ledger:
            image_id = build["image_id"]
            if not re.fullmatch(r"[a-f0-9]{32}", image_id) or image_id in images:
                raise ValueError("Duplicate or malformed build image ID")
            version_tuple(build["ota_version"])
            if not re.fullmatch(r"[a-f0-9]{64}", build["payload_sha256"]):
                raise ValueError("Malformed payload hash")
            if not re.fullmatch(r"[a-f0-9]{40}", build["source_sha"]):
                raise ValueError("Malformed source SHA")
            if not isinstance(build["source_tree_dirty"], bool):
                raise ValueError("Missing source provenance")
            images[image_id] = build
        if len({b["source_sha"] for b in images.values()}) > 1:
            raise ValueError("Builds refer to different source SHAs")
        for event in events:
            if event.get("event") != "boot":
                continue
            image_id = event["image_id"]
            if not isinstance(image_id, str) or not re.fullmatch(r"[a-f0-9]{32}", image_id):
                raise ValueError("Invalid observed image ID")
            if image_id not in images:
                if observed:
                    reasons.append("Unknown image booted after the test image")
                else:
                    pre_run.append(image_id)
                continue
            build = images[image_id]
            if version_tuple(event["version"]) != version_tuple(build["ota_version"]):
                reasons.append("Observed version differs from its compiled image")
            observed.append({"image_id": image_id, "version": event["version"],
                             "payload_sha256": build["payload_sha256"],
                             "source_sha": build["source_sha"],
                             "source_tree_dirty": build["source_tree_dirty"],
                             "utc": event.get("utc"), "monotonic_ns": event.get("monotonic_ns")})
        if required:
            if (initial_image_id not in images or candidate_image_id not in images or
                    initial_image_id == candidate_image_id):
                reasons.append("Initial and candidate image identities are not established")
            elif version_tuple(images[candidate_image_id]["ota_version"]) <= version_tuple(images[initial_image_id]["ota_version"]):
                reasons.append("Candidate version is not greater than the initial version")
            ids = [e["image_id"] for e in observed]
            if not ids or ids[0] != initial_image_id:
                reasons.append("Initial image boot was not observed first")
            if candidate_image_id not in ids or not ids or ids[-1] != candidate_image_id:
                reasons.append("Updated image boot was not observed as the final image")
    except (KeyError, TypeError, ValueError):
        reasons.append("Build ledger or boot observation is invalid")
    return {"required": required, "verified": required and not reasons,
            "verdict": "not_verified" if reasons else "verified" if required else "observed_only",
            "reasons": list(dict.fromkeys(reasons)), "observed_images": observed,
            "pre_run_image_ids": pre_run}
