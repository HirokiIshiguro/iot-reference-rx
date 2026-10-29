from __future__ import annotations

import unittest
from unittest.mock import patch

from tools.idt import run_idt


class IdtSubmodulePinsTests(unittest.TestCase):
    def test_first_clean_pin_and_recursive_pin_are_retained(self) -> None:
        status = (
            " " + "1" * 40 + " Middleware/example (heads/main)\r\n"
            " " + "2" * 40 + " Middleware/example/nested (v1.0)\r\n"
        )
        with patch.object(run_idt.subprocess, "check_output", return_value=status):
            pins = run_idt.submodule_pins()
        self.assertEqual([
            {"path": "Middleware/example", "sha": "1" * 40, "state": " "},
            {"path": "Middleware/example/nested", "sha": "2" * 40, "state": " "},
        ], pins)

    def test_first_entry_keeps_its_git_state(self) -> None:
        for state in (" ", "+", "-", "U"):
            with self.subTest(state=state):
                status = state + "a" * 40 + " Test/example\n"
                with patch.object(run_idt.subprocess, "check_output", return_value=status):
                    pins = run_idt.submodule_pins()
                self.assertEqual([{"path": "Test/example", "sha": "a" * 40,
                                   "state": state}], pins)

    def test_sha_output_still_removes_line_terminators(self) -> None:
        with patch.object(run_idt.subprocess, "check_output", return_value="b" * 40 + "\r\n"):
            self.assertEqual("b" * 40, run_idt.git("rev-parse", "HEAD"))


if __name__ == "__main__":
    unittest.main()
