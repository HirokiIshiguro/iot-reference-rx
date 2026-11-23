"""Check the committed SBOM in the existing RXCI check job."""

import copy
import json
import unittest

import generate_sbom as sbom


class SbomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.links = sbom.gitlinks(sbom.ROOT, "HEAD", sbom.REPOSITORY)
        cls.manifest = sbom.git(sbom.ROOT, "show", "HEAD:manifest.yml")
        cls.snapshot = json.loads(sbom.EVIDENCE.read_text(encoding="utf-8"))

    def test_committed_sbom_matches_manifest_and_pins(self):
        self.assertEqual(sbom.OUTPUT.read_text(encoding="utf-8"),
                         sbom.document(self.links, self.manifest, self.snapshot),
                         "Run python tools/ci/generate_sbom.py to update sbom.spdx")

    def test_manifest_version_must_match_the_pinned_commit(self):
        url, pin = "https://github.com/example/mqtt.git", "a" * 40
        manifest = (
            'version: "base"\ndependencies:\n  - name: "mqtt"\n'
            '    version: "v2.3.1"\n    repository:\n      type: "git"\n'
            f'      url: "{url}"\n      path: "/mqtt"\n'
        )
        evidence = {sbom.dependency_key(url, pin): {"tags": ["v5.0.2"], "children": {}}}
        with self.assertRaisesRegex(ValueError, "version v2.3.1 does not match mqtt"):
            sbom.manifest_versions(manifest, {"mqtt": [url, pin]}, evidence)

    def test_unrecorded_gitlink_fails_closed(self):
        links = self.links | {"external/new": ["https://github.com/example/new.git", "a" * 40]}
        with self.assertRaisesRegex(ValueError, "Missing pinned Git evidence for external/new"):
            sbom.document(links, self.manifest, self.snapshot)

    def test_nested_gitlink_remains_under_its_parent(self):
        links = {"agent": ["https://github.com/example/agent.git", "a" * 40],
                 "mqtt": ["https://github.com/example/mqtt.git", "b" * 40]}
        agent, mqtt = (sbom.dependency_key(*entry) for entry in links.values())
        snapshot = {
            "created": self.snapshot["created"],
            "repositories": {
                agent: {"tags": ["v1.0"], "children": {"source/dependency/mqtt": links["mqtt"]}},
                mqtt: {"tags": ["v5.0"], "children": {}},
            },
        }
        manifest = (
            'version: "base"\ndependencies:\n  - name: "mqtt"\n'
            '    version: "v5.0"\n    repository:\n      type: "git"\n'
            '      url: "https://github.com/example/mqtt.git"\n      path: "/mqtt"\n'
        )
        generated = sbom.document(links, manifest, snapshot)
        package_id = generated.split("PackageName: mqtt\nSPDXID: ", 1)[1].splitlines()[0]
        agent_id = generated.split("PackageName: agent\nSPDXID: ", 1)[1].splitlines()[0]
        self.assertEqual(generated.count("PackageName: mqtt\n"), 1)
        self.assertIn(f"{sbom.ROOT_ID} CONTAINS {package_id}\n", generated)
        self.assertIn(f"{agent_id} CONTAINS {package_id}\n"
                      "RelationshipComment: <text>source/dependency/mqtt</text>", generated)

    def test_unused_commit_is_rejected(self):
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["repositories"]["github.com/example/unused@" + "c" * 40] = {
            "tags": [], "children": {},
        }
        with self.assertRaisesRegex(ValueError, "Unused commits"):
            sbom.document(self.links, self.manifest, snapshot)
