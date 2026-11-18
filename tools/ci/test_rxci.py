"""Tests for the planning logic of tools/ci/rxci.py."""
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


if __name__ == "__main__":
    unittest.main()
