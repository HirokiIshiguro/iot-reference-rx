import unittest
from pathlib import Path
from unittest import mock

from tools.ci import verify_ci_runner_mr_scope as scope


class RunnerMrScopeTests(unittest.TestCase):
    def test_only_allowed_paths_and_ci_regions_pass(self):
        base = "workflow:\n  rules:\n    - when: always\n\ncleanup_rx72n_ether_ota_jobs:\n  script: old\n\nother:\n  script: keep\n"
        head = base.replace("    - when: always\n", scope.START + "    - when: never\n" + scope.END + "    - when: always\n").replace("script: old", "script: new")
        with mock.patch.object(scope, "changed_paths", return_value={".gitlab-ci.yml"}), mock.patch.object(scope, "read_blob", side_effect=[base, head]):
            scope.verify("base", "head")

    def test_mixed_file_fails(self):
        with mock.patch.object(scope, "changed_paths", return_value={"tools/cleanup_iot_jobs.py", "Projects/board.c"}):
            with self.assertRaises(RuntimeError):
                scope.verify("base", "head")

    def test_unrelated_ci_change_fails(self):
        with mock.patch.object(scope, "changed_paths", return_value={".gitlab-ci.yml"}), mock.patch.object(scope, "read_blob", side_effect=["other:\n  script: old\n", "other:\n  script: new\n"]):
            with self.assertRaises(RuntimeError):
                scope.verify("base", "head")

    def test_missing_workflow_end_fails(self):
        with self.assertRaises(RuntimeError):
            scope.strip_ci_regions(scope.START)

    def test_real_ci_boundaries_and_profile(self):
        ci = (Path(__file__).resolve().parents[3] / ".gitlab-ci.yml").read_text(encoding="utf-8")
        self.assertEqual(ci.count(scope.START), 1)
        self.assertEqual(ci.count(scope.END), 1)
        profile = ci.split(scope.START, 1)[1].split(scope.END, 1)[0]
        for value in ('RX65N_BG96_SKIP_HW_TESTS: "true"', 'RX72N_SKIP_HW_TESTS: "true"', 'RX671_WIFI_SKIP_HW_TESTS: "true"', 'RUN_RX72N_BUILD: "false"'):
            self.assertIn(value, profile)
        self.assertNotIn(scope.START, scope.strip_ci_regions(ci))


if __name__ == "__main__":
    unittest.main()
