"""A native PASS cannot mask a failed flash callback."""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

IDT = Path(__file__).resolve().parents[2] / "idt"
sys.path.insert(0, str(IDT))
from flash_failure import MARKER, record_flash_failure, raise_if_flash_failed
import flash_transport


class FlashFailureTests(unittest.TestCase):
    def test_callback_failure_latches_without_command_or_secret(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"IDT_RUNTIME_DIR": directory}):
            error = subprocess.CalledProcessError(1, ["private-command", "SECRET-value"])
            with patch.object(flash_transport, "main", side_effect=error):
                with self.assertRaises(subprocess.CalledProcessError):
                    flash_transport.run_callback()
            text = (Path(directory) / MARKER).read_text()
            self.assertNotIn("SECRET", text)
            self.assertNotIn("private-command", text)
            self.assertEqual(json.loads(text)["error_type"], "CalledProcessError")
            with self.assertRaisesRegex(RuntimeError, "flash callback failed"):
                raise_if_flash_failed(directory)

    def test_success_does_not_clear_an_earlier_failure(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"IDT_RUNTIME_DIR": directory}):
            with patch.object(flash_transport, "main"):
                flash_transport.run_callback()
                raise_if_flash_failed(directory)
                record_flash_failure(directory, ValueError("private value"))
                flash_transport.run_callback()
            with self.assertRaises(RuntimeError):
                raise_if_flash_failed(directory)
            record_flash_failure(directory, OSError("later failure"))
            self.assertEqual(json.loads((Path(directory) / MARKER).read_text())["error_type"], "ValueError")

    def test_partial_marker_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / MARKER).write_text('{"partial')
            with self.assertRaises(RuntimeError):
                raise_if_flash_failed(directory)

    def test_missing_runtime_is_not_a_successful_check(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                raise_if_flash_failed(Path(directory) / "missing")

    @unittest.skipUnless(os.name == "posix", "Linux supervisor uses PTYs")
    def test_supervisor_rejects_native_zero_after_failed_callback(self):
        supervisor = importlib.import_module("run_transport")
        with tempfile.TemporaryDirectory() as directory:
            record_flash_failure(directory, RuntimeError("private value"))
            process = Mock()
            process.poll.return_value = 0
            with self.assertRaisesRegex(RuntimeError, "flash callback failed"):
                supervisor.wait_for_native(process, Mock(), directory, 100)

    @unittest.skipUnless(os.name == "posix", "Linux supervisor uses PTYs")
    def test_supervisor_stops_while_native_keeps_running(self):
        supervisor = importlib.import_module("run_transport")
        with tempfile.TemporaryDirectory() as directory:
            process = Mock()
            def callback_failed():
                record_flash_failure(directory, RuntimeError("private value"))
                return None
            process.poll.side_effect = callback_failed
            with self.assertRaisesRegex(RuntimeError, "flash callback failed"):
                supervisor.wait_for_native(process, Mock(), directory, 100)
            self.assertEqual(process.poll.call_count, 1)


if __name__ == "__main__":
    unittest.main()
