"""Replay boot-loader failures without a UART, compiler or MCU."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


serial_stub = types.ModuleType("serial")
serial_stub.SerialException = OSError
spec = importlib.util.spec_from_file_location(
    "uart_download_error_subject", Path(__file__).resolve().parents[2] / "test_uart_download_rx72n.py")
subject = importlib.util.module_from_spec(spec)
with patch.dict(sys.modules, {"serial": serial_stub}):
    spec.loader.exec_module(subject)


class FakeSerial:
    def __init__(self, chunks, delay_until_monitor=False):
        self.chunks = list(chunks)
        self.is_open = True
        self.delay_until_monitor = delay_until_monitor

    @property
    def in_waiting(self):
        if self.delay_until_monitor:
            self.delay_until_monitor = False
            return 0
        return len(self.chunks[0]) if self.chunks else 0

    def read(self, size):
        return self.chunks.pop(0) if self.chunks else b""

    def write(self, data):
        return len(data)

    def close(self):
        self.is_open = False


class UartDownloadErrorTests(unittest.TestCase):
    def test_fatal_messages_and_normal_output(self):
        for text in ("system error.", "fatal error occurred.",
                     "R_FLASH_Write() returns error. 4.", "R_FLASH_Write() callback error. 4."):
            self.assertTrue(subject.bootloader_failed(text), text)
        for text in ("installing const data...25%(7/28KB).", "integrity check...OK", "0 errors"):
            self.assertFalse(subject.bootloader_failed(text), text)

    def test_mixed_cr_progress_and_crlf_error_preserve_error_code(self):
        downloader = subject.UartDownloader("unused", 921600, 10)
        downloader.ser = FakeSerial([
            b"installing const data...25%(7/28KB).\rR_FLASH_Write() callback error. 4.\r\nsystem error.\r\n"])
        self.assertEqual(downloader.read_uart(), ["installing const data...25%(7/28KB).",
                         "R_FLASH_Write() callback error. 4.", "system error."])
        self.assertIn("R_FLASH_Write() callback error. 4.", downloader.messages)

    def test_fragmented_crlf_does_not_duplicate_ack(self):
        downloader = subject.UartDownloader("unused", 921600, 10, ack_each_chunk=True)
        downloader.ser = FakeSerial([b" W 0x00000000 \r", b"\nR_FLASH_Wr", b"ite() returns error. 5.\r\n"])
        self.assertEqual(downloader.read_uart(), ["W 0x00000000"])
        self.assertEqual(downloader.read_uart(), [])
        self.assertEqual(downloader.read_uart(), ["R_FLASH_Write() returns error. 5."])
        self.assertEqual(downloader.write_ack_count, 1)

    def test_const_flash_failure_exits_even_without_strict_success(self):
        for strict in (False, True):
            with self.subTest(strict=strict), tempfile.TemporaryDirectory() as directory:
                image = Path(directory) / "fixture.rsu"
                image.write_bytes(b"fixture")
                downloader = subject.UartDownloader("unused", 921600, 10, strict_success=strict)
                port = FakeSerial([b"installing const data...25%(7/28KB).\r"
                                   b"R_FLASH_Write() callback error. 4.\r\nsystem error.\r\n"], True)
                downloader.open_port = lambda: setattr(downloader, "ser", port)
                downloader.trigger_reset = lambda: None
                output = io.StringIO()
                with patch.object(subject.time, "sleep"), contextlib.redirect_stdout(output):
                    self.assertEqual(downloader.download(image), 1)
                self.assertFalse(port.is_open)
                self.assertIn("callback error. 4.", output.getvalue())
                self.assertNotIn("TX only, no RX", output.getvalue())

    def test_strict_success_requires_fresh_install_and_integrity_markers(self):
        for installed, verified, expected in ((True, True, 0), (False, True, 1),
                                              (True, False, 1), (False, False, 1)):
            with self.subTest(installed=installed, verified=verified), tempfile.TemporaryDirectory() as directory:
                image = Path(directory) / "fixture.rsu"
                image.write_bytes(b"fixture")
                lines = []
                if installed:
                    lines.append(b"completed installing firmware.")
                if verified:
                    lines.append(b"bank1(temporary area) on code flash integrity check...OK")
                lines += [b"software reset...", b"jump to user program"]
                downloader = subject.UartDownloader("unused", 921600, 5, strict_success=True)
                port = FakeSerial([b"\r\n".join(lines) + b"\r\n"], True)
                downloader.open_port = lambda: setattr(downloader, "ser", port)
                downloader.trigger_reset = lambda: None
                output = io.StringIO()
                with patch.object(subject.time, "sleep"), contextlib.redirect_stdout(output):
                    self.assertEqual(expected, downloader.download(image))
                self.assertFalse(port.is_open)
                self.assertNotIn("Const data:        YES", output.getvalue())
                if expected:
                    self.assertIn("Missing firmware-install completion", output.getvalue())

    def _assert_acknowledged_transfer(self, target=None):
        class Receiver(FakeSerial):
            def __init__(self):
                super().__init__([])
                self.blocks = 0
                self.pending_ack = False

            def write(self, data):
                if self.pending_ack:
                    raise AssertionError('Sender wrote before receiving the previous flash-write ACK')
                if len(data) != 32768:
                    raise AssertionError('Receiver needs one complete 32 KiB block')
                self.blocks += 1
                self.pending_ack = True
                progress = f'installing firmware...({self.blocks * 32}/96KB).\r\n'
                if self.blocks == 3:
                    progress += ('completed installing firmware.\r\n'
                                 'bank1(temporary area) on code flash integrity check...OK\r\n'
                                 'completed installing const data.\r\n'
                                 'software reset...\r\n'
                                 'jump to user program\r\n')
                self.chunks.append(progress.encode())
                return len(data)

            def read(self, size):
                data = super().read(size)
                if data:
                    self.pending_ack = False
                return data

        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'normal_app.rsu'
            image.write_bytes(b'\xff' * (3 * 32768))
            if target is None:
                command = [sys.executable, 'test_uart_download_rx72n.py', '--rsu', str(image),
                           '--timeout', '5', '--strict-success', '--ack-each-chunk',
                           '--send-chunk-size', '32768', '--ack-prefix', 'installing firmware...',
                           '--success-message', 'jump to user program']
            else:
                from tools import install_normal_boot as installer
                from tools.idt.targets import get_target
                command = installer.download_command(Path(directory), get_target(target))
                # Bound a broken fixture while leaving production wait budgets unchanged.
                command[command.index('--timeout') + 1] = '5'
            port = Receiver()
            if target is not None:
                port.chunks.append(b'send "userprog.rsu" via UART.\r\n')
            original = subject.UartDownloader
            created = []
            def make_downloader(*args, **kwargs):
                instance = original(*args, **kwargs)
                instance.open_port = lambda: setattr(instance, 'ser', port)
                instance.trigger_reset = lambda: None
                created.append(instance)
                return instance
            with patch.object(subject, 'UartDownloader', side_effect=make_downloader), \
                 patch.object(sys, 'argv', command[1:]), \
                 patch.object(subject.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(0, subject.main())
            self.assertEqual(3, port.blocks)
            self.assertEqual(3, created[0].write_ack_count)
            self.assertFalse(port.is_open)

    def test_32k_progress_is_consumed_before_the_next_block_is_sent(self):
        self._assert_acknowledged_transfer()

    def test_normal_installers_drive_acknowledged_block_transfer(self):
        for target in ('rx72n-ethernet', 'rx65n-bg96', 'rx671-wifi'):
            with self.subTest(target=target):
                self._assert_acknowledged_transfer(target)


if __name__ == "__main__":
    unittest.main()
