"""Replay the RX72N PEM send when the board stays silent, with a fake serial port (no UART, no MCU)."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


serial_stub = types.ModuleType("serial")
serial_stub.SerialException = OSError
# tools/provisioning is a submodule that CI does not always check out; stub the masker.
provisioning_stub = types.ModuleType("provisioning")
provisioning_stub.__path__ = []
security_stub = types.ModuleType("provisioning.security")
security_stub.mask_sensitive_output = lambda text: text
provisioning_stub.security = security_stub
spec = importlib.util.spec_from_file_location(
    "provision_rx72n_retry_subject", Path(__file__).resolve().parents[2] / "provision_rx72n.py")
subject = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"serial": serial_stub, "provisioning": provisioning_stub,
                              "provisioning.security": security_stub}):
    spec.loader.exec_module(subject)


class BoardSerial:
    """Echoes every byte like the CLI does; each line terminator takes the next scripted reply.

    A reply of None is a board that stays silent. `echo_drop` loses the echo of every n-th byte.
    """

    def __init__(self, replies, echo_drop=0):
        self.replies = list(replies)
        self.echo_drop = echo_drop
        self.pending = b""
        self.written = 0
        self.terminators = 0

    def reset_input_buffer(self):
        self.pending = b""

    def write(self, data):
        if data == b"\r\n":
            self.terminators += 1
            reply = self.replies.pop(0) if self.replies else None
            if reply:
                self.pending += reply
            return len(data)
        for _ in data:
            self.written += 1
            if not (self.echo_drop and self.written % self.echo_drop == 0):
                self.pending += b"x"
        return len(data)

    @property
    def in_waiting(self):
        return len(self.pending)

    def read(self, size=1):
        data, self.pending = self.pending[:size], self.pending[size:]
        return data


PEM = "-----BEGIN PRIVATE KEY-----\nAAAA\n-----END PRIVATE KEY-----"
PROMPT = b"\r\n>"
OK = b"OK.\r\n>"


def run_pem(ser, **kwargs):
    subject.reset_run_stats()
    out = io.StringIO()
    kwargs.setdefault("response_timeout", 0.2)
    kwargs.setdefault("prompt_timeout", 0.2)
    with contextlib.redirect_stdout(out):
        ok = subject.send_pem_content_command(ser, "key", PEM, "label", 0, 0.5, **kwargs)
    return ok, out.getvalue()


class PemRetryTests(unittest.TestCase):
    def test_silent_first_try_then_ok_is_retried_once(self):
        # (a) first send gets no reply, the abort line brings the prompt, the second send is answered.
        ser = BoardSerial([None, PROMPT, OK])
        ok, text = run_pem(ser)
        self.assertTrue(ok)
        self.assertEqual(subject.RUN_STATS["pem_retries"], 1)
        self.assertEqual(subject.RUN_STATS["pem_retried_keys"], ["key"])
        self.assertIn("RETRY 1/2", text)
        self.assertEqual(text.count("Echo count:"), 2)
        self.assertEqual(ser.terminators, 3)

    def test_no_prompt_after_abort_line_fails_without_resending(self):
        # (b) the board does not even return the prompt: fail as before, do not send again.
        ser = BoardSerial([None, None, OK])
        ok, text = run_pem(ser)
        self.assertFalse(ok)
        self.assertEqual(subject.RUN_STATS["pem_retries"], 0)
        self.assertEqual(text.count("Echo count:"), 1)
        self.assertEqual(len([line for line in text.splitlines() if "ERROR" in line]), 1)
        self.assertIn("No CLI prompt", text)
        self.assertEqual(ser.terminators, 2)

    def test_retries_stop_at_the_limit(self):
        ser = BoardSerial([None, PROMPT, None, PROMPT, None, PROMPT, OK])
        ok, text = run_pem(ser)
        self.assertFalse(ok)
        self.assertEqual(subject.RUN_STATS["pem_retries"], 2)
        self.assertIn("retries used: 2/2", text)

    def test_retries_can_be_turned_off(self):
        ser = BoardSerial([None, PROMPT, OK])
        ok, _ = run_pem(ser, retries=0)
        self.assertFalse(ok)
        self.assertEqual(ser.terminators, 1)

    def test_error_reply_is_not_retried(self):
        ser = BoardSerial([b"Error.\r\n>", OK])
        ok, _ = run_pem(ser)
        self.assertFalse(ok)
        self.assertEqual(subject.RUN_STATS["pem_retries"], 0)

    def test_echo_count_matches(self):
        ser = BoardSerial([OK])
        ok, text = run_pem(ser)
        total = len("conf set key ") + len(PEM)
        self.assertTrue(ok)
        self.assertIn(f"Echo count: sent={total} echoed={total}", text)
        self.assertNotIn("MISMATCH", text)

    def test_echo_count_shows_lost_characters(self):
        # (c) every 10th byte is not echoed: the numbers show it, and only numbers are printed.
        ser = BoardSerial([OK], echo_drop=10)
        ok, text = run_pem(ser)
        total = len("conf set key ") + len(PEM)
        self.assertTrue(ok)
        self.assertIn(f"Echo count: sent={total} echoed={total - total // 10} (MISMATCH)", text)
        self.assertEqual(subject.RUN_STATS["pem_echo_mismatches"], 1)
        self.assertNotIn("AAAA", text)

    def test_summary_json_counts_retries(self):
        ser = BoardSerial([None, PROMPT, OK])
        run_pem(ser)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "provision_summary.json"
            subject.write_summary(path)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["pem_retries"], 1)
        self.assertEqual(data["pem_commands"], 1)


if __name__ == "__main__":
    unittest.main()
