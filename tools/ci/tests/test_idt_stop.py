"""Ensure interruption targets only the requested supervisor/source/output."""
from pathlib import Path
import unittest

from tools.idt.stop_runtime import is_owned


class IdtStopTests(unittest.TestCase):
    def setUp(self):
        self.source = Path("/test/source").resolve()
        self.runtime = Path("/test/private-run/execution").resolve()
        self.args = ["python3", str(self.source / "tools/idt/run_transport.py"),
                     "--source-path", str(self.source), "--output", str(self.runtime)]

    def test_exact_supervisor_is_owned(self):
        self.assertTrue(is_owned(self.args, self.source, self.runtime))

    def test_other_run_is_not_owned(self):
        self.assertFalse(is_owned(self.args, self.source, self.runtime / "another"))

    def test_other_script_or_source_is_not_owned(self):
        self.assertFalse(is_owned(["python3", "unrelated.py", *self.args[2:]], self.source, self.runtime))
        self.assertFalse(is_owned(self.args, self.source / "another", self.runtime))

    def test_ambiguous_or_incomplete_arguments_are_rejected(self):
        self.assertFalse(is_owned(self.args + ["--output", str(self.runtime)], self.source, self.runtime))
        self.assertFalse(is_owned(self.args[:-1], self.source, self.runtime))


if __name__ == "__main__":
    unittest.main()
