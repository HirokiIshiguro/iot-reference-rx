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


def line(at, free, minimum, total=229376, tasks=12):
    return f"RX671 heap: at={at} free={free} min={minimum} total={total} tasks={tasks}\r\n"


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
        self.assertEqual({"lines": 0}, summary)
        self.assertEqual("heap watermark: no line", heap.format_line(summary))

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
            self.assertEqual(["heap watermark: min free 7 B of 70 B (10.0%) at tick0", "heap watermark: no line"],
                             buffer.getvalue().splitlines())


if __name__ == "__main__":
    unittest.main()
