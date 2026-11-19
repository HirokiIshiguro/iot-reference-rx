import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import rx671_heap_watermark as heap  # noqa: E402


def line(at, free, minimum, total=229376, tasks=12, largest=None, blocks=3):
    largest = free // 2 if largest is None else largest
    return (f"RX671 heap: at={at} free={free} min={minimum} largest={largest} blocks={blocks} "
            f"total={total} tasks={tasks}\r\n")


def bsp(ustack, istack, cheap):
    return f"RX671 bsp: ustack={ustack}/4096 istack={istack}/1024 cheap={cheap}/8192\r\n"


class HeapWatermarkTests(unittest.TestCase):
    def test_smallest_min_of_several_lines(self):
        text = line("tick0", 200000, 200000) + "noise\r\n" + line("tick10", 90000, 60000) + line("tick20", 80000, 60000)
        summary = heap.summarize(text)
        self.assertEqual(3, summary["lines"])
        self.assertEqual(60000, summary["min_free_bytes"])
        self.assertEqual("tick10", summary["at"])
        self.assertEqual(229376, summary["total_bytes"])
        self.assertEqual(26.2, summary["percent"])

    def test_no_line_is_not_an_error(self):
        summary = heap.summarize("alive tick=1\r\nRX671 Fleet heap: free=1 min=1 tasks=1\r\n")
        self.assertEqual(0, summary["lines"])
        self.assertEqual("heap watermark: no line", heap.format_line(summary))
        self.assertEqual([], heap.format_extra_lines(summary))

    def test_minimum_across_a_reset_and_per_boot_values(self):
        # The baseline downloads (low), resets, and the new image starts with a higher watermark.
        text = (line("tick0", 220000, 220000) + line("tick10", 40000, 30000) + line("tick20", 60000, 30000)
                + line("tick0", 220000, 220000) + line("tick10", 100000, 90000))
        summary = heap.summarize(text)
        self.assertEqual(30000, summary["min_free_bytes"])
        self.assertEqual("tick10", summary["at"])
        self.assertEqual([(0, 30000, 3), (1, 90000, 2)],
                         [(b["boot"], b["min_free_bytes"], b["lines"]) for b in summary["per_boot"]])

    def test_lines_of_the_raw_log_with_timestamps(self):
        text = "[2026-11-19T00:00:00+00:00][+000001.000s] " + line("tick30", 5, 4, 100, 3)
        summary = heap.summarize(text)
        self.assertEqual(4, summary["min_free_bytes"])
        self.assertEqual("heap watermark: min free 4 B of 100 B (4.0%) at tick30", heap.format_line(summary))

    def test_smallest_largest_free_block_and_its_place(self):
        text = (line("tick0", 200000, 200000, largest=190000) + line("tick10", 90000, 60000, largest=7000, blocks=9)
                + line("tick20", 80000, 60000, largest=30000))
        summary = heap.summarize(text)
        self.assertEqual(7000, summary["min_largest_free_block_bytes"])
        self.assertEqual("tick10", summary["min_largest_free_block_at"])
        self.assertEqual(9, summary["max_free_blocks"])

    def test_lines_without_largest_still_parse(self):
        summary = heap.summarize("RX671 heap: at=tick0 free=5 min=4 total=100 tasks=2\r\n")
        self.assertEqual(4, summary["min_free_bytes"])
        self.assertNotIn("min_largest_free_block_bytes", summary)

    def test_bsp_high_water_marks_across_a_reset(self):
        text = bsp(100, 300, 1000) + bsp(2000, 500, 4000) + bsp(100, 300, 1000)
        summary = heap.summarize(text)["bsp"]
        self.assertEqual((2000, 500, 4000),
                         (summary["ustack_used_max"], summary["istack_used_max"], summary["cheap_used_max"]))
        self.assertEqual((4096, 1024, 8192), (summary["ustack_size"], summary["istack_size"], summary["cheap_size"]))

    def test_extra_lines_are_printed_after_the_main_line(self):
        buffer = StringIO()
        with redirect_stdout(buffer):
            heap.report(line("tick10", 9, 8, 100, 2, largest=4) + bsp(10, 20, 30))
        out = buffer.getvalue().splitlines()
        self.assertEqual("heap watermark: min free 8 B of 100 B (8.0%) at tick10", out[0])
        self.assertEqual(["heap largest free block: min 4 B at tick10 (up to 3 free blocks)",
                          "bsp watermark: ustack 10/4096 B, istack 20/1024 B, C library heap 30/8192 B"], out[1:])

    def test_report_prints_and_writes_json(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "out" / "heap_watermark.json"
            buffer = StringIO()
            with redirect_stdout(buffer):
                heap.report(line("tick10", 9, 8, 100, 2), path)
                heap.print_from_json(path)
            self.assertEqual(2, buffer.getvalue().count("heap watermark: min free 8 B of 100 B (8.0%) at tick10"))
            self.assertEqual(8, json.loads(path.read_text(encoding="utf-8"))["min_free_bytes"])

    def test_print_from_summary_with_a_heap_watermark_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "summary.json"
            path.write_text(json.dumps({"success": True, "heap_watermark": heap.summarize(line("tick0", 7, 7, 70, 1))}),
                            encoding="utf-8")
            buffer = StringIO()
            with redirect_stdout(buffer):
                heap.print_from_json(path)
                heap.print_from_json(Path(temporary) / "missing.json")
            lines = buffer.getvalue().splitlines()
            self.assertEqual("heap watermark: min free 7 B of 70 B (10.0%) at tick0", lines[0])
            self.assertEqual("heap watermark: no line", lines[-1])


class BspConfigurationTests(unittest.TestCase):
    """The warm start callbacks are set in the .scfg and in r_bsp_config.h (Smart Configurator rewrites the header)."""

    def test_callbacks_agree_in_scfg_and_header(self):
        import re
        for project in ("aws_wifi_rx671_ek", "aws_wifi_rx671_ek_tsip"):
            with self.subTest(project=project):
                base = ROOT / "Projects" / project / "e2studio_ccrx"
                header = (base / "src/smc_gen/r_config/r_bsp_config.h").read_text(encoding="utf-8", errors="replace")
                scfg = (base / f"{project}.scfg").read_text(encoding="utf-8")
                for key, name in (("PRE_INITC", "rx671_bsp_prec"), ("POST_INITC", "rx671_bsp_postc")):
                    self.assertRegex(header, rf"BSP_CFG_USER_WARM_START_CALLBACK_{key}_ENABLED\s+\(1\)")
                    self.assertIn(f'id="BSP_CFG_USER_WARM_START_CALLBACK_{key}_ENABLED" selectedIndex="1"', scfg)
                    function = "PRE_C" if key == "PRE_INITC" else "POST_C"
                    self.assertRegex(header, rf"BSP_CFG_USER_WARM_START_{function}_FUNCTION\s+{name}")
                    self.assertIn(f'id="BSP_CFG_USER_WARM_START_{function}_FUNCTION" selectedIndex="{name}"', scfg)
                for key in ("USTACK_BYTES", "ISTACK_BYTES", "HEAP_BYTES"):
                    value = re.search(rf"#define BSP_CFG_{key}\s+\((0x[0-9A-Fa-f]+)\)", header).group(1)
                    self.assertIn(f'id="BSP_CFG_{key}" selectedIndex="{value}"', scfg)
                self.assertTrue((base / "src/bsp_usage_probe.c").is_file())


if __name__ == "__main__":
    unittest.main()
