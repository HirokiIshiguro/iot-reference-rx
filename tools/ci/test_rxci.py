"""Tests for the planning logic of tools/ci/rxci.py."""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rxci  # noqa: E402


def registry(ready=()):
    data = rxci.load_registry()
    for test in data["tests"]:
        test["ready"] = test["name"] in ready
    return data


class RegistryTests(unittest.TestCase):
    def test_release_set_is_three_boards_times_twelve(self):
        tests = rxci.load_registry()["tests"]
        self.assertEqual(len(tests), 36)
        self.assertEqual(len({test["name"] for test in tests}), 36)
        self.assertEqual(len({test["id"] for test in tests}), 36)
        for board in ("rx72n", "rx65n", "rx671"):
            self.assertEqual(sum(test["board"] == board for test in tests), 12)

    def test_software_build_is_shared_between_tls_versions(self):
        data = rxci.load_registry()
        tests = {test["name"]: test for test in data["tests"]}
        self.assertEqual(rxci.build_variant(tests["rx72n:sw:tls12:mqtt"], data),
                         rxci.build_variant(tests["rx72n:sw:tls13:mqtt"], data))
        self.assertNotEqual(rxci.build_variant(tests["rx72n:tsip:tls12:mqtt"], data),
                            rxci.build_variant(tests["rx72n:tsip:tls13:mqtt"], data))

    def test_rx671_software_build_depends_on_the_tls_version(self):
        data = rxci.load_registry()
        tests = {test["name"]: test for test in data["tests"]}
        self.assertEqual(rxci.build_variant(tests["rx671:sw:tls12:mqtt"], data), "rx671/software-tls12/app")
        self.assertEqual(rxci.build_variant(tests["rx671:sw:tls13:mqtt"], data), "rx671/software-tls13/app")


class PlanTests(unittest.TestCase):

    def test_a_test_job_may_wait_for_its_board_without_losing_test_time(self):
        name = "rx65n:tsip:tls13:ota"
        jobs, _ = rxci.child_pipeline(registry([name]), "check", "^rx65n:tsip:tls13:ota$", 1)
        minutes = int(jobs[name]["timeout"].split()[0])
        self.assertEqual(jobs[name]["timeout"], f"{minutes} minutes")
        self.assertEqual(minutes * 60, rxci.LOCK_WAIT_SECONDS + rxci.TEST_SECONDS)
        self.assertGreaterEqual(rxci.TEST_SECONDS, 2400)

    def test_check_profile_has_no_build_and_no_test(self):
        jobs, summary = rxci.child_pipeline(registry(), "check", "", 1)
        self.assertEqual(summary["builds"], [])
        self.assertEqual(summary["tests"], [])
        self.assertIn("check", jobs)

    def test_one_test_pulls_only_its_build(self):
        name = "rx671:sw:tls12:mqtt"
        jobs, summary = rxci.child_pipeline(registry([name, "rx72n:sw:tls12:mqtt"]), "check", "^rx671:sw:tls12:mqtt$", 1)
        self.assertEqual(summary["tests"], [name])
        self.assertEqual(summary["builds"], ["rx671/common", "rx671/software-tls12/app"])
        self.assertEqual(jobs[name]["needs"], [{"job": "build rx671/common", "artifacts": True},
                                               {"job": "build rx671/software-tls12/app", "artifacts": True}])

    def test_repeat_makes_one_job_per_run_and_one_build(self):
        name = "rx72n:sw:tls12:mqtt"
        jobs, summary = rxci.child_pipeline(registry([name]), "check", "^rx72n:sw:tls12:mqtt$", 3)
        runs = [job for job in jobs if job.startswith(name)]
        self.assertEqual(runs, [f"{name} #1", f"{name} #2", f"{name} #3"])
        self.assertEqual(summary["builds"], ["rx72n/common", "rx72n/software/app"])

    def test_two_tls_versions_of_software_share_every_build(self):
        ready = ["rx72n:sw:tls12:mqtt", "rx72n:sw:tls13:mqtt"]
        _, summary = rxci.child_pipeline(registry(ready), "full", "", 1)
        self.assertEqual(summary["builds"], ["rx72n/common", "rx72n/software/app"])

    def test_tests_of_one_board_share_one_resource_group(self):
        ready = ["rx72n:sw:tls12:mqtt", "rx72n:sw:tls13:mqtt", "rx671:sw:tls12:mqtt"]
        jobs, _ = rxci.child_pipeline(registry(ready), "full", "", 1)
        self.assertEqual(jobs[ready[0]]["resource_group"], jobs[ready[1]]["resource_group"])
        self.assertNotEqual(jobs[ready[0]]["resource_group"], jobs[ready[2]]["resource_group"])

    def test_full_runs_ready_tests_and_reports_the_rest(self):
        ready = ["rx72n:sw:tls12:mqtt"]
        _, summary = rxci.child_pipeline(registry(ready), "full", "", 1)
        self.assertEqual(summary["tests"], ready)
        self.assertEqual(len(summary["not_implemented"]), 35)

    def test_selecting_only_unimplemented_tests_is_an_error(self):
        with self.assertRaises(SystemExit):
            rxci.child_pipeline(registry(), "check", "^rx65n:tsip:tls13:fleet$", 1)

    def test_doctor_profile_visits_every_runner_with_an_id_token(self):
        jobs, summary = rxci.child_pipeline(registry(), "doctor", "", 1)
        doctors = {name: job for name, job in jobs.items() if name.startswith("doctor: ")}
        self.assertEqual(len(doctors), 5)
        self.assertEqual(summary["tests"], [])
        for job in doctors.values():
            self.assertIn("GITLAB_OIDC_TOKEN", job["id_tokens"])
            self.assertNotIn("resource_group", job)

    def test_pipeline_with_tests_ends_with_a_sweep_that_always_runs(self):
        jobs, _ = rxci.child_pipeline(registry(["rx65n:sw:tls12:mqtt"]), "check", "^rx65n:sw:tls12:mqtt$", 1)
        self.assertEqual(jobs["sweep"]["when"], "always")
        self.assertEqual(jobs["sweep"]["stage"], jobs["stages"][-1])
        self.assertIn("GITLAB_OIDC_TOKEN", jobs["sweep"]["id_tokens"])
        without_tests, _ = rxci.child_pipeline(registry(), "check", "", 1)
        self.assertNotIn("sweep", without_tests)

    def test_hand_started_pipeline_is_not_cancelled_by_newer_commits(self):
        name = "rx72n:sw:tls12:mqtt"
        kept, _ = rxci.child_pipeline(registry([name]), "check", "^rx72n:sw:tls12:mqtt$", 1, keep=True)
        self.assertEqual(kept["workflow"]["auto_cancel"]["on_new_commit"], "none")
        self.assertFalse(kept["default"]["interruptible"])
        normal, _ = rxci.child_pipeline(registry([name]), "build", "", 1)
        self.assertEqual(normal["workflow"]["auto_cancel"]["on_new_commit"], "interruptible")
        self.assertTrue(normal["default"]["interruptible"])
        self.assertNotIn("interruptible", normal["build rx72n/software/app"])
        full, _ = rxci.child_pipeline(registry([name]), "full", "", 1)
        self.assertFalse(full[name]["interruptible"])
        self.assertFalse(full["sweep"]["interruptible"])

    def test_ota_needs_the_normal_application_and_the_candidate(self):
        name = "rx72n:sw:tls12:ota"
        jobs, summary = rxci.child_pipeline(registry([name]), "check", "^rx72n:sw:tls12:ota$", 1)
        self.assertEqual(summary["builds"], ["rx72n/common", "rx72n/software/app", "rx72n/software/ota"])
        self.assertEqual([need["job"] for need in jobs[name]["needs"]],
                         ["build rx72n/common", "build rx72n/software/app", "build rx72n/software/ota"])

    def test_rx671_ota_needs_only_its_bundle(self):
        name = "rx671:sw:tls13:ota"
        jobs, summary = rxci.child_pipeline(registry([name]), "check", "^rx671:sw:tls13:ota$", 1)
        self.assertEqual(summary["builds"], ["rx671/software-tls13/ota"])
        self.assertEqual([need["job"] for need in jobs[name]["needs"]], ["build rx671/software-tls13/ota"])

    def test_tsip_builds_are_per_tls_version(self):
        names = ["rx72n:tsip:tls12:ota", "rx72n:tsip:tls13:ota"]
        jobs, summary = rxci.child_pipeline(registry(names), "check", "^rx72n:tsip:", 1)
        self.assertEqual(summary["builds"], ["rx72n/common", "rx72n/tsip-tls12/app", "rx72n/tsip-tls12/ota",
                                             "rx72n/tsip-tls13/app", "rx72n/tsip-tls13/ota"])
        self.assertEqual([need["job"] for need in jobs[names[1]]["needs"]],
                         ["build rx72n/common", "build rx72n/tsip-tls13/app", "build rx72n/tsip-tls13/ota"])

    def test_build_job_leaves_dependencies_to_the_build_and_passes_rebuild(self):
        name = "rx72n:sw:tls12:mqtt"
        jobs, _ = rxci.child_pipeline(registry([name]), "check", "^rx72n:sw:tls12:mqtt$", 1)
        variables = jobs["build rx72n/software/app"]["variables"]
        self.assertEqual(variables["GIT_SUBMODULE_STRATEGY"], "none")
        self.assertEqual(variables["RXCI_REBUILD"], "0")
        jobs, _ = rxci.child_pipeline(registry([name]), "check", "^rx72n:sw:tls12:mqtt$", 1, rebuild=True)
        self.assertEqual(jobs["build rx72n/software/app"]["variables"]["RXCI_REBUILD"], "1")

    def test_build_inputs_ignore_pipeline_files_and_keep_no_credentials(self):
        import rxci_build

        full = rxci.load_registry()
        key = rxci_build.cache_key(full, "rx72n/software/app")
        self.assertEqual(len(key), 40)
        self.assertNotEqual(key, rxci_build.cache_key(full, "rx72n/software/ota"))
        self.assertEqual(rxci_build.cache_key(full, "rx671/software-tls12/app"), "")
        self.assertEqual(rxci_build.cache_key(full, "rx671/software-tls12/fleet"), "")
        self.assertNotEqual(rxci_build.cache_key(full, "rx671/software-tls12/ota"), "")

    def test_builds_are_spread_over_the_lanes(self):
        names = ["rx72n:sw:tls12:mqtt", "rx72n:sw:tls12:fleet", "rx72n:sw:tls12:ota"]
        jobs, summary = rxci.child_pipeline({**registry(names), "build_lanes": 3}, "check", "^rx72n:sw:tls12:", 1)
        groups = [jobs[f"build {variant}"]["resource_group"] for variant in summary["builds"]]
        self.assertEqual(len(groups), 4)
        self.assertEqual(sorted(set(groups)), ["windows-ccrx-build-1", "windows-ccrx-build-2", "windows-ccrx-build-3"])

    def test_unknown_pattern_is_an_error(self):
        with self.assertRaises(SystemExit):
            rxci.child_pipeline(registry(), "check", "^no-such-test$", 1)


class BoardInstallRangesTests(unittest.TestCase):
    def test_board_erase_ranges_preserve_each_bootloader(self):
        import importlib
        import types
        from unittest.mock import patch

        with patch.dict(sys.modules, {"fcntl": types.ModuleType("fcntl")}):
            board_module = importlib.import_module("rxci_board")
            data = rxci.load_registry()
            for name, expected in {
                "rx671": ((0xFFE00000, 0xFFEEFFFF), (0xFFF00000, 0xFFFEFFFF)),
                "rx65n": ((0xFFE00000, 0xFFEEFFFF), (0xFFF00000, 0xFFFEFFFF)),
                "rx72n": ((0xFFC00000, 0xFFDEFFFF), (0xFFE00000, 0xFFFEFFFF)),
            }.items():
                with self.subTest(board=name):
                    board = board_module.Board(data, name)
                    self.assertEqual(expected, board.rfp.install_ranges)
                    command = board.rfp.erase_ota_install_areas_command()
                    for start, end in expected:
                        self.assertIn(f"{start:08X},{end:08X}", command)


class BoardRestTests(unittest.TestCase):
    def test_only_the_board_with_a_display_keeps_running_after_a_test(self):
        import importlib
        import types
        from unittest.mock import patch

        with patch.dict(sys.modules, {"fcntl": types.ModuleType("fcntl")}):
            board_module = importlib.import_module("rxci_board")
            data = rxci.load_registry()
            for name, parked in {"rx72n": False, "rx65n": True, "rx671": True}.items():
                with self.subTest(board=name):
                    board = board_module.Board(data, name)
                    calls = []
                    board.park = lambda: calls.append("park")
                    board.rest()
                    self.assertEqual(["park"] if parked else [], calls)


class RetiredVariableTests(unittest.TestCase):
    """A run variable of the old CI stops the plan instead of being ignored."""

    def test_old_run_variables_are_recognised(self):
        environment = {"RX72N_TEST_SCOPE": "mqtt", "PIPELINE_PROFILE": "nightly_matrix", "RUN_RX_IDT": "true",
                       "IDT_SCOPE": "plan", "RX671_WIFI_REQUIRE_TLS_VERSION": "TLSv1.3", "RX72N_TLS_BACKEND": "tsip",
                       "NIGHTLY_RX72N_MULTI_TLS_TEST": "true", "RX65N_BG96_SKIP_HW_TESTS": "true"}
        self.assertEqual(rxci.retired_variables(environment), sorted(environment))

    def test_variables_of_this_ci_and_of_the_runner_are_not_retired(self):
        environment = {"PROFILE": "full", "BOARD": "rx671", "BACKEND": "sw", "TLS": "tls12", "FEATURE": "ota",
                       "REPEAT": "2", "REBUILD": "true", "TEST": "^rx72n:", "KEEP": "true", "CI_PIPELINE_SOURCE": "web",
                       "AWS_ROLE_ARN": "x", "AWS_IOT_ENDPOINT": "x", "RUNNER_TEMP": "x", "E2STUDIO_CLI": "x",
                       "RX671_EK_WIFI_SSID": "x", "RX671_TSIP_AWS_IOT_THING_NAME": "x", "GIT_SUBMODULE_STRATEGY": "none"}
        self.assertEqual(rxci.retired_variables(environment), [])

    def test_an_empty_old_variable_does_not_stop_the_plan(self):
        self.assertEqual(rxci.retired_variables({"RX72N_TEST_SCOPE": ""}), [])

    def test_the_plan_stops_and_names_the_variable(self):
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"RX72N_TEST_SCOPE": "mqtt"}):
            with self.assertRaises(SystemExit) as stopped:
                rxci.main(["plan", "--profile", "check"])
        self.assertIn("RX72N_TEST_SCOPE", str(stopped.exception))
        self.assertIn("PROFILE", str(stopped.exception))


class RunVariableTests(unittest.TestCase):
    """The variables of the "New pipeline" page: lists that select tests, and combinations that must stop."""

    def plan(self, *arguments):
        import contextlib
        import io
        import tempfile

        with tempfile.TemporaryDirectory() as folder:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rxci.main(["plan", *arguments, "--output", str(Path(folder) / "child.yml"),
                           "--summary", str(Path(folder) / "plan.json")])
            return json.loads((Path(folder) / "plan.json").read_text(encoding="utf-8"))

    def test_lists_select_the_tests_of_one_board(self):
        summary = self.plan("--profile", "full", "--board", "rx72n")
        self.assertTrue(summary["tests"])
        self.assertTrue(all(name.startswith("rx72n:") for name in summary["tests"]))
        self.assertTrue(all(variant.startswith("rx72n/") for variant in summary["builds"]))

    def test_four_lists_select_exactly_one_test(self):
        summary = self.plan("--profile", "full", "--board", "rx72n", "--backend", "sw", "--tls", "tls12",
                            "--feature", "mqtt", "--repeat", "3")
        self.assertEqual(["rx72n:sw:tls12:mqtt"], summary["tests"])
        self.assertEqual(3, summary["repeat"])

    def test_lists_at_all_leave_the_free_text_selection_alone(self):
        summary = self.plan("--profile", "full", "--test", "^rx65n:sw:tls12:mqtt$")
        self.assertEqual(["rx65n:sw:tls12:mqtt"], summary["tests"])

    def test_a_selection_without_profile_full_stops_with_the_reason(self):
        for profile in ("check", "build", "smoke", "doctor"):
            for selection in (["--board", "rx671"], ["--test", "^rx671:"]):
                with self.subTest(profile=profile, selection=selection):
                    with self.assertRaisesRegex(SystemExit, "only PROFILE=full runs a selection"):
                        self.plan("--profile", profile, *selection)

    def test_lists_and_free_text_together_stop(self):
        with self.assertRaisesRegex(SystemExit, "both select tests"):
            self.plan("--profile", "full", "--board", "rx671", "--test", "^rx72n:")

    def test_a_value_outside_a_list_stops(self):
        for name, value in (("--board", "rx99"), ("--backend", "software"), ("--tls", "tls14"), ("--feature", ""),
                            ("--board", "")):
            with self.subTest(name=name, value=value):
                with self.assertRaisesRegex(SystemExit, "must be one of all"):
                    self.plan("--profile", "full", name, value)

    def test_repeat_without_tests_stops(self):
        with self.assertRaisesRegex(SystemExit, "REPEAT repeats tests"):
            self.plan("--profile", "build", "--repeat", "3")

    def test_the_form_offers_exactly_the_values_the_tool_accepts(self):
        text = (Path(__file__).resolve().parents[2] / ".gitlab-ci.yml").read_text(encoding="utf-8")
        registry = rxci.load_registry()

        def options(name):
            block = text.split(f"\n  {name}:\n", 1)[1].split("\n    description:", 1)[0]
            return re.findall(r'^      - "([^"]*)"$', block, re.M)

        self.assertEqual(list(rxci.PROFILES), options("PROFILE"))
        for name, axis in (("BOARD", "board"), ("BACKEND", "backend"), ("TLS", "tls"), ("FEATURE", "feature")):
            self.assertEqual(["all", *registry["axes"][axis]], options(name))


class BuildCacheConcurrencyTests(unittest.TestCase):
    """Five build jobs share the cache folder; one of them once died on another job's temporary folder."""

    def store_while_another_job_is_busy(self, vanishing: str):
        import os
        import tempfile
        from unittest.mock import patch

        import rxci_build

        with tempfile.TemporaryDirectory() as folder:
            cache, out = Path(folder) / "cache", Path(folder) / "out"
            out.mkdir()
            (out / "app.mot").write_text("S0", encoding="utf-8")
            (cache / vanishing).mkdir(parents=True)     # listed, then gone before anyone looks at it
            (cache / "older").mkdir()
            real_stat = Path.stat

            def stat(path, *args, **kwargs):
                if path.name == vanishing:
                    raise FileNotFoundError(str(path))
                return real_stat(path, *args, **kwargs)

            with patch.object(Path, "stat", stat), patch.dict(os.environ, {"CI_JOB_ID": "1"}):
                rxci_build.store(cache / "mine", out)
            self.assertTrue((cache / "mine" / "app.mot").is_file())
            self.assertTrue((cache / "older").is_dir())

    def test_store_ignores_the_temporary_folder_of_another_job(self):
        self.store_while_another_job_is_busy("0123456789abcdef.90699.tmp")

    def test_store_survives_an_entry_that_another_job_removed(self):
        self.store_while_another_job_is_busy("fedcba9876543210")


class StsError(Exception):
    """Same shape as botocore's ClientError, which the check job cannot import."""

    def __init__(self, code, message):
        super().__init__(f"An error occurred ({code}): {message}")
        self.response = {"Error": {"Code": code, "Message": message}}


class FakeSts:

    def __init__(self, *failures):
        self.failures = list(failures)
        self.calls = 0

    def assume_role_with_web_identity(self, **request):
        self.calls += 1
        if self.failures:
            raise self.failures.pop(0)
        return {"Credentials": {"AccessKeyId": "id"}}


class AssumeRoleTests(unittest.TestCase):

    KEYS = "Couldn't retrieve verification key from your identity provider"

    def test_asks_again_while_sts_cannot_get_the_keys_from_gitlab(self):
        sts = FakeSts(StsError("InvalidIdentityToken", self.KEYS), StsError("IDPCommunicationError", "late"))
        waits = []
        self.assertEqual(rxci.assume_role(sts, sleep=waits.append), {"AccessKeyId": "id"})
        self.assertEqual(sts.calls, 3)
        self.assertEqual(waits, [rxci.STS_WAIT_SECONDS] * 2)

    def test_gives_up_after_the_last_attempt(self):
        sts = FakeSts(*[StsError("InvalidIdentityToken", self.KEYS)] * rxci.STS_ATTEMPTS)
        with self.assertRaises(StsError):
            rxci.assume_role(sts, sleep=lambda seconds: None)
        self.assertEqual(sts.calls, rxci.STS_ATTEMPTS)
        self.assertLessEqual((rxci.STS_ATTEMPTS - 1) * rxci.STS_WAIT_SECONDS, 150)

    def test_does_not_ask_again_when_the_token_or_the_role_is_wrong(self):
        for failure in (StsError("InvalidIdentityToken", "Incorrect token audience"),
                        StsError("AccessDenied", "Not authorized to perform sts:AssumeRoleWithWebIdentity"),
                        StsError("ExpiredTokenException", "Token is expired")):
            sts = FakeSts(failure)
            with self.assertRaises(StsError):
                rxci.assume_role(sts, sleep=lambda seconds: self.fail("must not wait"))
            self.assertEqual(sts.calls, 1)


if __name__ == "__main__":
    unittest.main()
