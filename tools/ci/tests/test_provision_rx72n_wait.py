"""Replay the RX72N provisioning CLI with a fake serial port (no UART, no MCU)."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
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
    "provision_rx72n_wait_subject", Path(__file__).resolve().parents[2] / "provision_rx72n.py")
subject = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"serial": serial_stub, "provisioning": provisioning_stub,
                              "provisioning.security": security_stub}):
    spec.loader.exec_module(subject)


class FakeSerial:
    """Answers the line terminator after `reply_delay` seconds (None = never)."""

    def __init__(self, reply_delay, reply=b"OK\r\n>"):
        self.reply_delay = reply_delay
        self.reply = reply
        self.sent_at = None
        self.pending = b""

    def reset_input_buffer(self):
        self.pending = b""

    def write(self, data):
        if data.endswith(b"\n"):
            self.sent_at = subject.time.monotonic()
        return len(data)

    @property
    def in_waiting(self):
        if (self.sent_at is not None and self.reply_delay is not None
                and subject.time.monotonic() - self.sent_at >= self.reply_delay):
            self.pending, self.reply = self.reply, b""
        return len(self.pending)

    def read(self, size=1):
        data, self.pending = self.pending[:size], self.pending[size:]
        return data


PEM = "-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----"


def run_pem(ser, timeout):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        ok = subject.send_pem_content_command(ser, "cert", PEM, "label", 0, 0.5, timeout)
    return ok, out.getvalue()


class ProvisionWaitTests(unittest.TestCase):
    def test_late_ok_is_accepted(self):
        ser = FakeSerial(reply_delay=1.5)
        ok, _ = run_pem(ser, timeout=5.0)
        self.assertTrue(ok)

    def test_ok_returns_without_extra_wait(self):
        ser = FakeSerial(reply_delay=0.0)
        start = subject.time.monotonic()
        ok, _ = run_pem(ser, timeout=5.0)
        self.assertTrue(ok)
        self.assertLess(subject.time.monotonic() - start, 0.4)

    def test_missing_ok_fails_at_the_upper_bound_with_one_line(self):
        ser = FakeSerial(reply_delay=None)
        ok, text = run_pem(ser, timeout=0.3)
        self.assertFalse(ok)
        self.assertEqual(len([line for line in text.splitlines() if "ERROR" in line]), 1)
        self.assertIn("within 0.3s", text)

    def test_error_reply_fails_at_once(self):
        ser = FakeSerial(reply_delay=0.0, reply=b"Error: bad\r\n>")
        ok, _ = run_pem(ser, timeout=5.0)
        self.assertFalse(ok)

    def test_send_command_waits_for_late_token(self):
        ser = FakeSerial(reply_delay=1.2)
        with contextlib.redirect_stdout(io.StringIO()):
            resp = subject.send_command(ser, "conf set endpoint x", 0, 0.5,
                                        required_tokens=("OK",), response_timeout=5.0)
        self.assertIn("OK", resp)


class RetryAfterFormatTests(unittest.TestCase):
    def _args(self, attempts):
        return types.SimpleNamespace(attempts=attempts)

    def _run_main(self, side_effect):
        calls = []

        def fake_provision(args, state):
            calls.append(1)
            return side_effect(state)

        argv = ["provision_rx72n.py", "--endpoint", "e", "--thing-name", "t",
                "--cert", __file__, "--key", __file__, "--attempts", "3"]
        out = io.StringIO()
        with patch.object(subject, "_provision", fake_provision), \
                patch.object(subject.time, "sleep"), patch.object(sys, "argv", argv), \
                contextlib.redirect_stdout(out):
            rc = subject.main()
        return rc, len(calls), out.getvalue()

    def test_no_retry_after_format(self):
        def fail_after_format(state):
            state["formatted"] = True
            return 1
        rc, calls, text = self._run_main(fail_after_format)
        self.assertEqual((rc, calls), (1, 1))
        self.assertIn("data flash was formatted", text)

    def test_retry_before_format_is_unchanged(self):
        rc, calls, _ = self._run_main(lambda state: 1)
        self.assertEqual((rc, calls), (1, 3))


if __name__ == "__main__":
    unittest.main()
