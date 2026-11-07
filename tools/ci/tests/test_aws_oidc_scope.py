"""Safety boundary for the generic OIDC source-only workflow family."""
import unittest

from tools.ci.verify_aws_oidc_scope import legacy_ci, verify_scope


class OidcScopeTests(unittest.TestCase):
    BASE = 'include:\n  - local: /existing.yml\nvariables:\n  KEEP: "true"\nworkflow:\n  rules:\n    - when: always\n'
    HEAD = BASE.replace('variables:\n',
        '  # OIDC include begin\n  - local: /.gitlab/ci/aws-oidc-probe.yml\n  # OIDC include end\nvariables:\n')
    HEAD = HEAD.replace('  KEEP:', '  # OIDC inputs begin\n  RUN_RX_IOT_OIDC_PROBE: "false"\n  # OIDC inputs end\n  KEEP:')
    HEAD = HEAD.replace('    - when: always',
        '    # OIDC workflows begin\n    - if: $OIDC\n      when: never\n    # OIDC workflows end\n    - when: always')

    def test_only_oidc_paths_and_new_regions_pass(self):
        verify_scope({'.gitlab-ci.yml', 'tools/aws/oidc_probe.py'}, self.BASE, self.HEAD)
        self.assertEqual(self.BASE, legacy_ci(self.HEAD))

    def test_unrelated_firmware_file_fails(self):
        with self.assertRaises(RuntimeError):
            verify_scope({'Projects/board/main.c'}, self.BASE, self.HEAD)

    def test_existing_ci_change_fails(self):
        with self.assertRaises(RuntimeError):
            verify_scope({'.gitlab-ci.yml'}, self.BASE, self.HEAD.replace('KEEP: "true"', 'KEEP: "false"'))

    def test_missing_duplicate_and_reversed_markers_fail(self):
        begin, end = '  # OIDC inputs begin\n', '  # OIDC inputs end\n'
        for text in (self.HEAD.replace(end, ''), self.HEAD + begin, end + begin):
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                legacy_ci(text)

    def test_no_changes_on_current_main_are_valid(self):
        verify_scope(set(), self.HEAD, self.HEAD)


if __name__ == '__main__':
    unittest.main()
