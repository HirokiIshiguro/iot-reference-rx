"""Check package wiring and execute its script with public-file-only tool stubs."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools import normal_boot


ROOT = Path(__file__).resolve().parents[3]
TEXT = (ROOT / "tools/ci/normal_boot_jobs.yml").read_text(encoding="utf-8")
PWSH = shutil.which("pwsh")
TARGETS = {"rx72n": ("rx72n-ethernet", "build_rx72n_ether"),
           "rx65n": ("rx65n-bg96", "build_rx65n_bg96"),
           "rx671": ("rx671-wifi", "build_rx671_wifi"),
           "rx72n_fleet": ("rx72n-ethernet", "build_rx72n_ether_fleet"),
           "rx65n_fleet": ("rx65n-bg96", "build_rx65n_bg96_fleet")}


def block(name):
    start = TEXT.index(name + ":\n")
    following = re.search(r"(?m)^[\w.-]+:\s*$", TEXT[start + len(name) + 2:])
    return TEXT[start:start + len(name) + 2 + following.start()] if following else TEXT[start:]


def variables(name):
    return dict(re.findall(r"(?m)^    (NORMAL_BOOT_\w+): (.+)$", block(name)))


def script():
    text = block(".normal_boot_package").split("    - |\n", 1)[1].split("  artifacts:\n", 1)[0]
    return "\n".join(line[6:] for line in text.splitlines())


class NormalBootJobsTests(unittest.TestCase):
    def test_same_stage_needs_and_rules_reference_each_normal_build(self):
        common = block(".normal_boot_package")
        self.assertIn("extends: .rx_windows_canonical_checkout", common)
        self.assertIn("stage: build", common)
        self.assertIn("resource_group: $WINDOWS_CCRX_BUILD_RESOURCE_GROUP", common)
        self.assertIn("python -m pip install --user cryptography", common)
        for suffix, (target, build) in TARGETS.items():
            with self.subTest(target=target):
                body = block("package_normal_boot_" + suffix)
                rule_source = ".rx65n_bg96_fleet_rules" if suffix == "rx65n_fleet" else build
                self.assertIn("rules: !reference [" + rule_source + ", rules]", body)
                self.assertIn("- job: " + build + "\n      artifacts: true", body)
                self.assertEqual(variables("package_normal_boot_" + suffix)["NORMAL_BOOT_TARGET"], target)
                self.assertNotIn("RUN_", body)
                board = suffix.split("_", 1)[0]
                runner = {"rx72n": "RX72N_BUILD_RUNNER_TAG", "rx65n": "RX65N_BG96_BUILD_RUNNER_TAG", "rx671": "RX671_WIFI_BUILD_RUNNER_TAG"}[board]
                self.assertIn("tags: [exec-shell, os-windows, ccrx, $" + runner + "]", body)
                self.assertNotIn("NORMAL_BOOT_RUNNER_TAG", body)

    def test_publication_is_exact_api_output_allowlist_without_private_logs(self):
        body = script()
        names = set(re.findall(r"'([^']+)'", body.split("$publicFiles = @(", 1)[1].split(")", 1)[0]))
        self.assertEqual(names, normal_boot.FILES | {"normal_install_manifest.json"})
        self.assertIn("C:/ai/codex/tmp/normal-boot-", body)
        self.assertIn("C:/ai/codex/ws/normal-boot-", body)
        self.assertIn("--signing-key", body)
        self.assertNotIn("--allow-dirty", body)
        self.assertNotIn("Remove-Item", body)

    def test_downloaded_and_generated_artifacts_are_ignored_by_real_git_rules(self):
        paths = {"rx72n_codesign_cert.pem", "rx72n_e2studio_build.log", "rx65n_bg96_e2studio_build.log",
                 "rx671_wifi_e2studio_build.log", "artifacts/build_rx671_wifi/aws_wifi_rx671_ek.mot",
                 "Projects/boot_loader_rx671_ek/e2studio_ccrx/HardwareDebug/boot_loader_rx671_ek.mot"}
        for suffix in TARGETS:
            settings = variables("package_normal_boot_"+suffix)
            paths.update(settings[name] for name in ("NORMAL_BOOT_RSU", "NORMAL_BOOT_BOOT0", "NORMAL_BOOT_BOOT1", "NORMAL_BOOT_APP_MOT") if name in settings)
        result = subprocess.run(["git", "check-ignore", "-z", "--stdin"], cwd=ROOT,
                                input=("\0".join(sorted(paths))+"\0").encode("utf-8"),
                                capture_output=True, timeout=10)
        self.assertEqual(0,result.returncode,result.stderr)
        self.assertEqual(paths,set(result.stdout.decode("utf-8").rstrip("\0").split("\0")))
        self.assertLess(script().index("_source_state"),script().index("$privateRoot ="))

    @unittest.skipUnless(PWSH, "PowerShell is required for the package script fixture")
    def test_product_inputs_survive_producer_rebuild_for_all_profiles(self):
        profiles = [("rx72n", "software"), ("rx72n", "tsip"),
                    ("rx65n", "software"), ("rx65n", "tsip"), ("rx671", "software"),
                    ("rx72n_fleet", "software"), ("rx72n_fleet", "tsip"),
                    ("rx65n_fleet", "software"), ("rx65n_fleet", "tsip")]
        for suffix, backend in profiles:
            with self.subTest(target=suffix, backend=backend), \
                    tempfile.TemporaryDirectory(prefix="normal-package-", dir=ROOT.parent) as temporary:
                folder = Path(temporary).resolve()
                self.assertTrue(folder.is_relative_to(ROOT.parent.resolve()))
                source = folder / "source"
                source.mkdir()
                settings = variables("package_normal_boot_" + suffix)
                for name in ("NORMAL_BOOT_RSU", "NORMAL_BOOT_BOOT0", "NORMAL_BOOT_BOOT1", "NORMAL_BOOT_APP_MOT"):
                    if name in settings:
                        path = source / settings[name]
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text("NORMAL_INPUT", encoding="utf-8")
                descriptor = source / "tools/idt/targets.json"
                descriptor.parent.mkdir(parents=True)
                descriptor.write_text(json.dumps({"targets": {"rx671-wifi": {"signing_key": "fixture-key.pem"}}}))
                boot = source / "tools/build_headless_rx671_bootloader.ps1"
                boot.write_text("""param($ProjectRoot,$E2Studio,$Workspace,$LogFile,$Python)
$path=Join-Path $ProjectRoot 'Projects/boot_loader_rx671_ek/e2studio_ccrx/HardwareDebug/boot_loader_rx671_ek.mot'
New-Item -ItemType Directory -Path (Split-Path -Parent $path) -Force | Out-Null
[IO.File]::WriteAllText($path,'NORMAL_INPUT')
$global:LASTEXITCODE=0
""", encoding="utf-8")
                body = script().replace("C:/ai/codex/tmp", (folder / "private").as_posix())
                body = body.replace("C:/ai/codex/ws", (folder / "workspace").as_posix())
                harness = folder / "fixture.ps1"
                harness.write_text("""$ErrorActionPreference='Stop'
function python {
  $call=@($args)
  function value($name) { return $call[[Array]::IndexOf($call,$name)+1] }
  if($call[0] -in @('-m','-c')) { $global:LASTEXITCODE=0; return }
  $tool=[IO.Path]::GetFileName($call[0])
  $output=value '--output'
  if($tool -eq 'prepare_public_signer.py') {
    foreach($name in @('NORMAL_BOOT_RSU','NORMAL_BOOT_BOOT0','NORMAL_BOOT_BOOT1')) {
      $relative=[Environment]::GetEnvironmentVariable($name)
      if($relative) { [IO.File]::WriteAllText((Join-Path $env:CI_PROJECT_DIR $relative),'OVERWRITTEN') }
    }
    New-Item -ItemType Directory -Path $output -Force | Out-Null
    foreach($name in @('public_signer_provisioner.mot','public_signer_provisioner_manifest.json','signer.crt.pem','signer.pub.pem')) {
      [IO.File]::WriteAllText((Join-Path $output $name),'PUBLIC_INPUT')
    }
  } elseif($tool -eq 'shift_srec_addresses.py') {
    if((value '--range-start') -ne '0xFFFC0000' -or '--shift=-0x100000' -notin $call -or '--drop-out-of-range' -notin $call) { throw 'wrong mirror policy' }
    [IO.File]::WriteAllText($output,'NORMAL_INPUT')
  } elseif($tool -eq 'build_rx671_fwup_v2_rsu.py') {
    if([IO.File]::ReadAllText((value '--mot')) -ne 'NORMAL_INPUT') { throw 'normal RX671 MOT lost' }
    [IO.File]::WriteAllText($output,'NORMAL_INPUT')
  } elseif($tool -eq 'prepare_normal_boot.py') {
    foreach($name in @('--rsu','--bootloader','--bootloader-bank1')) {
      $inputPath=value $name
      if($inputPath.StartsWith($env:CI_PROJECT_DIR) -or [IO.File]::ReadAllText($inputPath) -ne 'NORMAL_INPUT') { throw 'normal input overwritten or inside checkout' }
    }
    if((value '--tls-backend') -ne $env:EXPECTED_BACKEND) { throw 'wrong TLS backend' }
    New-Item -ItemType Directory -Path $output -Force | Out-Null
    foreach($name in @('normal_app.rsu','bootloader.mot','bootloader_bank1.mot','public_signer_provisioner.mot','public_signer_provisioner_manifest.json','signer.crt.pem','signer.pub.pem','public_signer_bootloader_config.h','public_signer_target.h','normal_install_manifest.json','private-build.log')) {
      [IO.File]::WriteAllText((Join-Path $output $name),'PUBLIC_BUNDLE')
    }
  } else { throw ('unexpected tool '+$tool) }
  $global:LASTEXITCODE=0
}
""" + body, encoding="utf-8")
                environment = {k: v for k, v in os.environ.items() if not k.startswith("NORMAL_BOOT_")}
                environment.update(settings)
                environment.update(CI_PROJECT_DIR=str(source), CI_PIPELINE_ID="fixture", CI_JOB_ID="1",
                                   RX72N_SIGNING_KEY="fixture-key.pem", RX65N_BG96_SIGNING_KEY="fixture-key.pem",
                                   RX72N_TLS_BACKEND=backend, RX65N_BG96_TLS_BACKEND=backend,
                                   EXPECTED_BACKEND=backend, E2STUDIO_CLI="fixture-e2studio-cli.exe")
                result = subprocess.run([PWSH, "-NoProfile", "-File", str(harness)], cwd=source,
                                        env=environment, capture_output=True, text=True, timeout=20)
                self.assertEqual(result.returncode, 0, result.stderr)
                artifact = source / settings["NORMAL_BOOT_ARTIFACT_DIR"]
                self.assertEqual({p.name for p in artifact.iterdir()},
                                 normal_boot.FILES | {"normal_install_manifest.json"})


if __name__ == "__main__":
    unittest.main()
