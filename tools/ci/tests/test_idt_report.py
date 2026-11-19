from __future__ import annotations

import contextlib
import io
import json
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

from tools.idt.check_idt_report import check_report, main
from tools.idt.run_idt import combined_summary
from tools.idt.run_idt import export_report
from tools.idt.run_idt import public_warnings
from tools.idt import run_idt


ROOT = Path(__file__).resolve().parents[3]
OPT_IN = (
    '($CI_PIPELINE_SOURCE == "web" || $CI_PIPELINE_SOURCE == "api") '
    '&& ($RUN_RX_IDT == "true" || $RUN_RX72N_IDT == "true")'
)


def report(group: str = "FreeRTOSVersion", status: str = "") -> str:
    counters = {"failure": 0, "error": 0, "skipped": 0}
    if status:
        counters[status] = 1
    attributes = (
        f'tests="1" failures="{counters["failure"]}" '
        f'errors="{counters["error"]}" skipped="{counters["skipped"]}"'
    )
    child = f"<{status}>sensitive diagnostic</{status}>" if status else ""
    return (
        f"<testsuites {attributes}><testsuite name=\"{group}\" {attributes}>"
        f'<testcase classname="FRQ {group}" name="test">{child}</testcase>'
        "</testsuite></testsuites>"
    )


class IdtReportTests(unittest.TestCase):
    def test_cipher_warning_is_preserved_without_raw_diagnostics(self) -> None:
        diagnostics = json.dumps([{"message": "FOUND_UNSUPPORTED_CIPHER_SUITE",
                                   "description": "secret-value must stay private; [0xc02f, 0xff]"},
                                  {"message": "NO_RECOMMENDED_CIPHER_SUITE", "description": "secret-value"}])
        result = public_warnings("-- Finished: TLS_Ciphers with status PASS_WITH_WARNINGS and message " + diagnostics + " --")
        self.assertEqual(["0xc02f", "0xff"], result[0]["cipher_ids"])
        self.assertEqual(2, len(result[0]["codes"]))
        self.assertNotIn("secret-value", json.dumps(result))

    def test_unparsed_warning_cannot_silently_look_like_clean_pass(self) -> None:
        result = public_warnings("-- Finished: Example with status PASS_WITH_WARNINGS and message secret-value --")
        self.assertEqual(["UNCLASSIFIED_WARNING"], result[0]["codes"])
        self.assertNotIn("secret-value", json.dumps(result))

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "FRQ_Report.xml"

    def check(self, xml: str, groups: tuple[str, ...] = ("FreeRTOSVersion",)) -> dict:
        self.path.write_text(xml, encoding="utf-8")
        return check_report(self.path, groups)

    def test_runtime_cleanup_failure_overrules_passing_junit(self) -> None:
        junit = self.check(report())
        merged = combined_summary(junit, 1)
        self.assertFalse(merged["passed"])
        self.assertTrue(junit["passed"])
        self.assertEqual([], junit["problems"])
        self.assertEqual(1, merged["runner_exit_code"])

    def test_zero_process_exit_does_not_override_junit_failure(self) -> None:
        merged = combined_summary(self.check(report(status="error")), 0)
        self.assertFalse(merged["passed"])
        self.assertEqual(1, merged["errors"])

    def test_complete_selected_group_passes_without_claiming_qualification(self) -> None:
        result = self.check(report())
        self.assertTrue(result["passed"])
        self.assertEqual(1, result["tests"])
        self.assertEqual("selected_groups_only", result["result_scope"])

    def test_each_nonpassing_testcase_is_rejected(self) -> None:
        for status in ("failure", "error", "skipped"):
            with self.subTest(status=status):
                result = self.check(report(status=status))
                self.assertFalse(result["passed"])
                self.assertNotIn("sensitive diagnostic", json.dumps(result))

    def test_declared_failure_cannot_hide_behind_passing_testcases(self) -> None:
        self.assertFalse(self.check(report().replace('failures="0"', 'failures="1"'))["passed"])

    def test_testcase_failure_cannot_hide_behind_zero_declared_totals(self) -> None:
        self.assertFalse(self.check(report(status="error").replace('errors="1"', 'errors="0"'))["passed"])

    def test_missing_or_empty_required_group_is_rejected(self) -> None:
        self.assertFalse(self.check(report("FullTransportInterfaceTLS"))["passed"])
        empty = '<testsuite name="FreeRTOSVersion" tests="0"/>'
        self.assertFalse(self.check(empty)["passed"])
        with_empty_group = report("FullTransportInterfaceTLS").replace("</testsuites>", empty + "</testsuites>")
        self.assertFalse(self.check(with_empty_group)["passed"])

    def test_required_groups_must_all_be_present(self) -> None:
        result = self.check(report(), ("FreeRTOSVersion", "FullTransportInterfaceTLS"))
        self.assertFalse(result["passed"])
        self.assertTrue(any("FullTransportInterfaceTLS" in p for p in result["problems"]))
        self.assertFalse(self.check(report(), ())["passed"])

    def test_malformed_missing_and_invalid_count_reports_fail_closed(self) -> None:
        self.assertFalse(check_report(self.path, ["FreeRTOSVersion"])["passed"])
        for xml in (
            "<unclosed>",
            "<notJUnit/>",
            report().replace('tests="1"', 'tests="2"'),
            report().replace('tests="1"', 'tests="-1"'),
            report().replace('tests="1"', ''),
            report().replace('tests="1"', 'tests="one"'),
            report().replace('tests="1"', 'tests="1" disabled="1"'),
        ):
            with self.subTest(xml=xml):
                self.assertFalse(self.check(xml)["passed"])

    def test_single_testsuite_and_namespaced_junit_are_supported(self) -> None:
        xml = report().split(">", 1)[1].removesuffix("</testsuites>")
        self.assertTrue(self.check(xml)["passed"])
        xml = report().replace("<testsuites ", '<testsuites xmlns="urn:junit" ')
        self.assertTrue(self.check(xml)["passed"])

    def test_cli_outputs_one_json_and_nonzero_for_idt_failure(self) -> None:
        for status, exit_code in (("", 0), ("error", 1)):
            self.path.write_text(report(status=status), encoding="utf-8")
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                result = main([str(self.path), "--required-group", "FreeRTOSVersion"])
            self.assertEqual(exit_code, result)
            self.assertEqual(exit_code == 0, json.loads(stdout.getvalue())["passed"])


class IdtScopeContractTests(unittest.TestCase):
    def test_scopes_select_native_idt_groups_and_are_exposed_by_cli(self):
        expected = {
            "preflight": "FreeRTOSVersion", "transport": "FullTransportInterfaceTLS",
            "mqtt": "FullCloudIoT", "ota-mqtt": "OTADataplaneMQTT",
            "pkcs11": "FullPKCS11_Core", "ota-pal": "OTACore",
        }
        self.assertEqual(expected, {scope: run_idt.SCOPE_GROUPS[scope] for scope in expected})
        stdout = io.StringIO()
        from unittest.mock import patch
        with patch("sys.argv", ["run_idt.py", "--help"]), contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as result:
                run_idt.main()
        self.assertEqual(0, result.exception.code)
        for scope in run_idt.SCOPE_GROUPS:
            self.assertIn(scope, stdout.getvalue())

    def test_single_ota_case_cannot_be_used_for_a_non_ota_scope(self):
        from unittest.mock import patch
        from contextlib import redirect_stderr
        for scope in ("preflight", "transport", "mqtt", "pkcs11", "ota-pal"):
            with self.subTest(scope=scope), patch("sys.argv", [
                "run_idt.py", "--scope", scope, "--test-id", "OTAE2EGreaterVersion", "--output", "unused",
            ]), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    run_idt.main()
                self.assertEqual(2, result.exception.code)


class IdtReportExportTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.source = Path(temp.name) / "raw.xml"
        self.target = Path(temp.name) / "exported.xml"
        self.credentials = SimpleNamespace(
            access_key="fake-sensitive-access-key",
            secret_key="fake-sensitive-secret-key",
            token="fake-sensitive-session-token",
        )

    def export(self, xml: str) -> ET.Element:
        self.source.write_text(xml, encoding="utf-8")
        export_report(self.source, self.target, self.credentials)
        return ET.parse(self.target).getroot()

    def test_export_discards_diagnostics_properties_and_system_output(self) -> None:
        xml = '''<testsuites tests="3" failures="1" errors="1" skipped="1">
          <testsuite name="FullTransportInterfaceTLS" tests="3" failures="1" errors="1" skipped="1">
            root-sensitive-text
            <properties><property name="private-key" value="property-sensitive-value"/></properties>
            <testcase name="failed" classname="FRQ FullTransportInterfaceTLS">
              <failure message="attribute-sensitive-value" type="secret-type">failure-sensitive-text</failure>
              <system-out>stdout-sensitive-text</system-out>
              <system-err>stderr-sensitive-text</system-err>
            </testcase>
            tail-sensitive-text
            <testcase name="errored"><error>error-sensitive-text</error></testcase>
            <testcase name="skipped"><skipped>skipped-sensitive-text</skipped></testcase>
          </testsuite>
        </testsuites>'''
        root = self.export(xml)
        exported = self.target.read_text(encoding="utf-8")
        self.assertNotIn("sensitive", exported)
        self.assertNotIn("secret-type", exported)
        for tag in ("properties", "property", "system-out", "system-err"):
            self.assertEqual([], list(root.iter(tag)))
        for status in ("failure", "error", "skipped"):
            self.assertEqual(1, len(list(root.iter(status))))
        result = check_report(self.target, ["FullTransportInterfaceTLS"])
        self.assertFalse(result["passed"])
        self.assertEqual((3, 1, 1, 1), tuple(result[key] for key in ("tests", "failures", "errors", "skipped")))

    def test_export_preserves_failure_of_observed_freertos_version_report(self) -> None:
        # Structure/counts from the IDT 4.9.0 preflight run: process exit 0,
        # but unsupported FreeRTOS and library versions fail two test cases.
        xml = '''<testsuites name="FRQ results" time="26" tests="2" failures="1" skipped="0" errors="1" disabled="0">
          <testsuite name="FreeRTOSVersion" package="" tests="2" failures="1" time="26" disabled="0" errors="1" skipped="0">
            <testcase classname="FRQ FreeRTOSVersion" name="FreeRTOS_Version">
              <error>The provided version, 202604.00-LTS, is not supported by IDT version 4.9.0.</error>
            </testcase>
            <testcase classname="FRQ FreeRTOSVersion" name="Library_Version">
              <failure type="Example Failure Type">FreeRTOS-Libraries-Integration-Tests version 202406.00 is NOT compatible.</failure>
            </testcase>
          </testsuite>
        </testsuites>'''
        root = self.export(xml)
        before = check_report(self.source, ["FreeRTOSVersion"])
        after = check_report(self.target, ["FreeRTOSVersion"])
        self.assertEqual(before, after)
        self.assertFalse(after["passed"])
        self.assertEqual(["FreeRTOS_Version", "Library_Version"], [case.get("name") for case in root.iter("testcase")])
        self.assertEqual("26", root.get("time"))
        self.assertNotIn("202604.00-LTS", self.target.read_text(encoding="utf-8"))

    def test_export_preserves_case_status_and_redacts_attribute_credentials(self) -> None:
        xml = report("FullTransportInterfaceTLS").replace(
            'name="test"',
            'name="test ' + " ".join(vars(self.credentials).values()) + '"',
        ).replace("<testsuites ", '<testsuites xmlns="urn:junit" ')
        root = self.export(xml)
        exported = self.target.read_text(encoding="utf-8")
        for value in vars(self.credentials).values():
            self.assertNotIn(value, exported)
        self.assertEqual("test [REDACTED] [REDACTED] [REDACTED]", next(root.iter("testcase")).get("name"))
        result = check_report(self.target, ["FullTransportInterfaceTLS"])
        self.assertFalse(result["passed"])
        self.assertEqual(["Required IDT group is incomplete: FullTransportInterfaceTLS "
                          "(14 mandatory cases missing)"], result["problems"])
        self.assertEqual(1, result["tests"])
        self.assertEqual("selected_groups_only", result["result_scope"])
        self.assertEqual({"tests": 1, "failures": 0, "errors": 0, "skipped": 0}, result["groups"]["FullTransportInterfaceTLS"])


class TransportCoverageTests(unittest.TestCase):
    def test_native_rx671_partial_pass_is_incomplete_without_rewriting_counts(self):
        result = check_report((ROOT / 'tools/ci/tests/fixtures/idt') / 'rx671-transport-truncated-70882.xml', ['FullTransportInterfaceTLS'])
        self.assertFalse(result['passed'])
        self.assertEqual((9, 0, 0, 0), tuple(result[k] for k in
                         ('tests', 'failures', 'errors', 'skipped')))
        missing = result['coverage']['FullTransportInterfaceTLS']['missing_cases']
        self.assertEqual(5, len(missing))
        self.assertIn('Transport_SendRecvCompareMultithreaded', missing)

    def test_real_rx72n_complete_pass_stays_pass(self):
        result = check_report((ROOT / 'tools/ci/tests/fixtures/idt') / 'rx72n-transport-complete-pass-70574.xml', ['FullTransportInterfaceTLS'])
        self.assertTrue(result['passed'])
        self.assertEqual(14, result['tests'])
        self.assertTrue(result['coverage']['FullTransportInterfaceTLS']['complete'])

    def test_real_rx65n_complete_failure_stays_failure(self):
        result = check_report((ROOT / 'tools/ci/tests/fixtures/idt') / 'rx65n-transport-complete-fail-70856.xml', ['FullTransportInterfaceTLS'])
        self.assertFalse(result['passed'])
        self.assertEqual((14, 1), (result['tests'], result['failures']))
        self.assertTrue(result['coverage']['FullTransportInterfaceTLS']['complete'])

    def test_duplicate_case_cannot_fill_missing_coverage(self):
        root = ET.parse((ROOT / 'tools/ci/tests/fixtures/idt') / 'rx72n-transport-complete-pass-70574.xml').getroot()
        cases = root.findall('.//testcase')
        cases[-1].set('name', cases[0].get('name'))
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / 'duplicate.xml'
            ET.ElementTree(root).write(report)
            result = check_report(report, ['FullTransportInterfaceTLS'])
        self.assertFalse(result['passed'])
        self.assertEqual(14, result['tests'])
        self.assertEqual(['TransportRecv_ReturnZeroRetry'],
                         result['coverage']['FullTransportInterfaceTLS']['missing_cases'])





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
