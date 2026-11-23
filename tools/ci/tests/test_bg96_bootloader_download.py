"""Exercise the CF-only UART protocol without opening a device."""
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from tools import bg96_bootloader_integration as boot

INTEGRITY_OK = b"bank1(temporary area) on code flash integrity check...OK"
SWAP = b"swap bank"
STARTUP = boot.APP_START_MARKERS[0].encode("ascii") + b"\r\n"


def cf_image():
    image = bytearray(b"\xff" * boot.CODE_FLASH_SIZE)
    image[:8] = b"Renesas\xfe"
    struct.pack_into("<III", image, 0x12C, 0, 0xFFFFFFFF, 0xFFFFFFFF)
    return bytes(image)


class Clock:
    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def sleep(self, _seconds):
        self.now += 1.0


class FakeSerial:
    """Boot progress replies appear only after each complete CF block."""
    def __init__(self, final=INTEGRITY_OK+b"\r\n"+SWAP+b"...\r\n"+STARTUP):
        self.received = bytearray()
        self.pending = bytearray(boot.READY.encode("ascii"))
        self.final = final
        self.reads = []
        self.flushes = 0

    @property
    def in_waiting(self):
        return len(self.pending)

    def read(self, size):
        self.reads.append((len(self.received), size))
        chunk = bytes(self.pending[:size])
        del self.pending[:size]
        return chunk

    def write(self, data):
        self.received.extend(data)
        if len(self.received) % boot.CODE_FLASH_BLOCK_SIZE == 0:
            blocks = len(self.received) // boot.CODE_FLASH_BLOCK_SIZE
            if blocks < boot.CODE_FLASH_BLOCKS:
                self.pending.extend(f"({blocks*32}/{boot.CODE_FLASH_SIZE_KB}KB)".encode("ascii"))
            elif blocks == boot.CODE_FLASH_BLOCKS:
                # Integrity, swap and app startup are coalesced in one UART queue.
                self.pending.extend(self.final)
        return len(data)

    def flush(self):
        self.flushes += 1


class Bg96BootloaderDownloadTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name)/"userprog.rsu"
        self.image = cf_image()
        self.path.write_bytes(self.image)
        self.clock = Clock()
        for name, replacement in (("time",self.clock.time),("sleep",self.clock.sleep)):
            patcher = mock.patch.object(boot.time,name,replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        quiet = mock.patch.object(boot,"write_serial_text")
        quiet.start()
        self.addCleanup(quiet.stop)

    def test_sends_only_cf_and_preserves_coalesced_app_startup_for_next_verifier(self):
        port = FakeSerial()
        boot.download_rsu(port,self.path)
        self.assertEqual(bytes(port.received),self.image)
        self.assertEqual(port.flushes,boot.CODE_FLASH_BLOCKS)
        final_reads=[size for written,size in port.reads if written==boot.CODE_FLASH_SIZE]
        self.assertTrue(final_reads)
        self.assertEqual(set(final_reads),{1})
        self.assertEqual(bytes(port.pending),b"...\r\n"+STARTUP)
        self.assertEqual(boot.wait_for_any(port,boot.APP_START_MARKERS,10),boot.APP_START_MARKERS[0])

    def test_already_observed_ready_still_requires_integrity_and_swap(self):
        port=FakeSerial()
        port.pending.clear()
        boot.download_rsu(port,self.path,ready_observed=True)
        self.assertEqual(bytes(port.received),self.image)
        self.assertIn(STARTUP,bytes(port.pending))

    def test_malformed_size_magic_and_df_declarations_fail_before_any_serial_io(self):
        cases={"short":self.image[:-1],"long":self.image+b"\xff","bad-magic":b"Invalid"+self.image[7:]}
        for name,fields in (("df-flag",(1,0xFFFFFFFF,0xFFFFFFFF)),
                            ("df-start",(0,0x00100000,0xFFFFFFFF)),("df-end",(0,0xFFFFFFFF,0x00107FFF))):
            image=bytearray(self.image)
            struct.pack_into("<III",image,0x12C,*fields)
            cases[name]=bytes(image)
        for name,data in cases.items():
            with self.subTest(case=name):
                self.path.write_bytes(data)
                port=mock.Mock()
                with self.assertRaises(RuntimeError):
                    boot.download_rsu(port,self.path)
                self.assertEqual(port.mock_calls,[])

    def test_integrity_failure_does_not_accept_swap_or_app_startup(self):
        port=FakeSerial(final=INTEGRITY_OK[:-2]+b"NG\r\n"+SWAP+b"...\r\n"+STARTUP)
        with self.assertRaisesRegex(RuntimeError,"integrity check"):
            boot.download_rsu(port,self.path)
        self.assertEqual(bytes(port.received),self.image)
        self.assertEqual(self.clock.now,180)

    def test_no_bank_swap_fails_within_original_timeout(self):
        port=FakeSerial(final=INTEGRITY_OK+b"\r\nsoftware reset...\r\n"+STARTUP)
        with self.assertRaisesRegex(RuntimeError,"bank swap"):
            boot.download_rsu(port,self.path)
        self.assertEqual(bytes(port.received),self.image)
        self.assertEqual(self.clock.now,180)

    def test_actions_validate_input_before_opening_uart_or_running_rfp(self):
        self.path.write_bytes(b"malformed")
        mot=Path(self.temporary.name)/"boot.mot"
        mot.touch()
        args=SimpleNamespace(userprog_rsu=self.path,bootloader_mot=mot)
        for action in (boot.download_rsu_via_bootloader,boot.full_integration):
            with self.subTest(action=action.__name__), mock.patch.object(boot,"open_serial_candidates") as uart, \
                 mock.patch.object(boot,"run_rfp") as rfp:
                with self.assertRaisesRegex(RuntimeError,"RSU size"):
                    action(args)
                uart.assert_not_called()
                rfp.assert_not_called()


if __name__ == "__main__":
    unittest.main()
