"""Fail a selected IDT scope on JUnit failures, even when IDT exits zero.

This checks the selected groups only. A passing preflight or transport group
does not establish complete FreeRTOS qualification or release eligibility.
Failure messages and system-out from IDT are intentionally never copied into
the summary; raw reports may contain credentials or retained-source paths.
"""

from __future__ import annotations

import argparse
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Sequence


def _tag(element: ET.Element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _counts(element: ET.Element) -> dict[str, int]:
    cases = [node for node in element.iter() if _tag(node) == "testcase"]
    return {
        "tests": len(cases),
        **{
            counter: sum(
                any(_tag(child) == status for child in case) for case in cases
            )
            for counter, status in (
                ("failures", "failure"),
                ("errors", "error"),
                ("skipped", "skipped"),
            )
        },
    }


def check_report(
    path: Path | str, required_groups: Sequence[str]
) -> dict[str, object]:
    """Return a value-only summary suitable for a sanitized JSON artifact."""
    summary: dict[str, object] = {
        "passed": False,
        "result_scope": "selected_groups_only",
        "tests": 0,
        "failures": 0,
        "errors": 0,
        "skipped": 0,
        "required_groups": list(dict.fromkeys(required_groups)),
        "groups": {},
        "problems": [],
    }
    problems: list[str] = []
    summary["problems"] = problems
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        problems.append("JUnit report is missing, unreadable or malformed")
        return summary
    if _tag(root) not in ("testsuites", "testsuite"):
        problems.append("JUnit root must be testsuites or testsuite")
        return summary

    counts = _counts(root)
    summary.update(counts)
    if counts["tests"] == 0:
        problems.append("JUnit report contains no test cases")
    if any(counts[key] for key in ("failures", "errors", "skipped")):
        problems.append("JUnit contains failed, errored or skipped test cases")

    # Check both declared totals and actual testcase children. IDT 4.9.0 can
    # return process exit 0 even with failures/errors in both these locations.
    suites = [node for node in root.iter() if _tag(node) == "testsuite"]
    containers = [node for node in root.iter() if _tag(node) in ("testsuites", "testsuite")]
    for index, container in enumerate(containers):
        observed = _counts(container)
        for counter in ("tests", "failures", "errors", "skipped", "disabled"):
            raw = container.get(counter, "" if counter == "tests" else "0")
            if re.fullmatch(r"[0-9]+", raw) is None:
                problems.append(f"JUnit container {index} has an invalid {counter} count")
                continue
            declared = int(raw)
            if counter != "tests" and declared != 0:
                problems.append(f"JUnit container {index} declares nonzero {counter}")
            if counter != "disabled" and declared != observed[counter]:
                problems.append(f"JUnit container {index} has inconsistent {counter} totals")

    if not required_groups:
        problems.append("At least one required IDT group must be selected")
    groups: dict[str, dict[str, int]] = {}
    for group in dict.fromkeys(required_groups):
        matches = [suite for suite in suites if suite.get("name") == group]
        if not matches:
            problems.append(f"Required IDT group is missing: {group}")
            continue
        group_counts = {
            key: sum(_counts(suite)[key] for suite in matches) for key in counts
        }
        groups[group] = group_counts
        if group_counts["tests"] == 0:
            problems.append(f"Required IDT group contains no test cases: {group}")
    summary["groups"] = groups
    summary["passed"] = not problems
    return summary


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--required-group", action="append", required=True)
    args = parser.parse_args(argv)
    summary = check_report(args.report, args.required_group)
    print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
