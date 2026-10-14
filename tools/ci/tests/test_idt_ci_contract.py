"""Exercise the real shared CI bootstrap block without compilers, cloud or boards."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tools.idt.public_signer_provision import ENVIRONMENT_INPUTS

ROOT=Path(__file__).resolve().parents[3]
PWSH=shutil.which("pwsh")


def bootstrap_block():
    yaml=(ROOT/".gitlab-ci.yml").read_text(encoding="utf-8")
    start=yaml.index("      if ($idtScope -ne 'preflight') {")
    end=yaml.index('      & "$env:RX72N_IDT_PYTHON" tools/idt/run_idt.py',start)
    return "\n".join(line[6:] for line in yaml[start:end].splitlines())


class IdtCiContractTests(unittest.TestCase):
    def test_shared_native_bootstrap_uses_only_generic_inputs_and_sanitized_artifacts(self):
        block=bootstrap_block()
        self.assertIn("tools/idt/prepare_public_signer.py",block)
        self.assertIn('--target "$idtTarget"',block)
        self.assertIn("C:/ai/codex/tmp/rx-idt-public-signer-",block)
        self.assertIn("CI_JOB_ID",block)
        self.assertIn("ConvertFrom-Json",block)
        self.assertIn("PSObject.Properties).Count -ne $bootstrapNames.Count",block)
        self.assertIn("$bootstrapPresent.Count -ne $bootstrapNames.Count",block)
        self.assertNotIn("IDT_RX671",block)
        self.assertNotIn("$idtTarget -eq",block)
        self.assertEqual(set(ENVIRONMENT_INPUTS.values()),set(re.findall(r"'((?:IDT_PUBLIC_SIGNER_)[A-Z_]+)'",block)))
        yaml=(ROOT/".gitlab-ci.yml").read_text(encoding="utf-8")
        native=yaml[yaml.index(".rx_idt_job:"):yaml.index("test_rx72n_idt:")]
        artifacts=native[native.index("  artifacts:"):]
        for private in ("signer.crt.pem","signer.pub.pem","producer-private.log","build-private.log",".mot",".abs"):
            self.assertNotIn(private,artifacts)

    @unittest.skipUnless(PWSH,"PowerShell is required to execute CI control flow")
    def test_all_three_targets_generate_skip_complete_overrides_and_reject_bad_input_sets(self):
        variables=tuple(ENVIRONMENT_INPUTS.values())
        for target in ("rx72n-ethernet","rx65n-bg96","rx671-wifi"):
            for scenario in ("generate","complete","partial","preflight","bad-json","extra-json","missing-path","helper-failure"):
                with self.subTest(target=target,scenario=scenario),tempfile.TemporaryDirectory() as temporary:
                    folder=Path(temporary);paths={name:str(folder/(str(index)+".input")) for index,name in enumerate(variables)}
                    for path in paths.values():Path(path).write_text("public fixture")
                    payload=json.dumps(paths)
                    # All tool execution is replaced by one PowerShell function.
                    # The production branching/count/path checks are left intact.
                    script="""$ErrorActionPreference='Stop'
$script:helperCalls=0
$script:helperArgs=@()
function fake-idt-python {
  $script:helperCalls++
  $script:helperArgs=@($args)
  $global:LASTEXITCODE=0
  if ($env:CONTRACT_SCENARIO -eq 'helper-failure') { $global:LASTEXITCODE=42; return }
  if ($env:CONTRACT_SCENARIO -eq 'bad-json') { return 'not-json' }
  $result=$env:CONTRACT_PATHS | ConvertFrom-Json -AsHashtable
  if ($env:CONTRACT_SCENARIO -eq 'extra-json') { $result['unexpected']='extra' }
  if ($env:CONTRACT_SCENARIO -eq 'missing-path') { $result[($result.Keys | Select-Object -First 1)]='absent-input' }
  return ($result | ConvertTo-Json -Compress)
}
$env:RX72N_IDT_PYTHON='fake-idt-python'
$idtTarget=$env:CONTRACT_TARGET
$idtScope=if ($env:CONTRACT_SCENARIO -eq 'preflight') {'preflight'} else {'pkcs11'}
"""+bootstrap_block()+"""
$values=@{}
foreach ($name in ($env:CONTRACT_PATHS | ConvertFrom-Json -AsHashtable).Keys) {
  $values[$name]=[Environment]::GetEnvironmentVariable($name,'Process')
}
@{calls=$script:helperCalls;args=$script:helperArgs;values=$values} | ConvertTo-Json -Compress -Depth 4
"""
                    path=folder/"ci-bootstrap.ps1";path.write_text(script,encoding="utf-8")
                    environment={name:value for name,value in os.environ.items() if name not in variables}
                    environment.update(CONTRACT_TARGET=target,CONTRACT_SCENARIO=scenario,CONTRACT_PATHS=payload,
                                       CI_PROJECT_DIR=str(ROOT),CI_PIPELINE_ID="unit",CI_JOB_ID="case")
                    if scenario=="complete":environment.update(paths)
                    elif scenario=="partial":environment[variables[0]]=paths[variables[0]]
                    result=subprocess.run([PWSH,"-NoProfile","-File",str(path)],capture_output=True,text=True,
                                          encoding="utf-8",errors="replace",env=environment,timeout=15)
                    if scenario in ("generate","complete","preflight"):
                        self.assertEqual(0,result.returncode,result.stderr)
                        observed=json.loads(result.stdout)
                        self.assertEqual(1 if scenario=="generate" else 0,observed["calls"])
                        if scenario!="preflight":self.assertEqual(paths,observed["values"])
                        if scenario=="generate":
                            args=observed["args"]
                            self.assertEqual(target,args[args.index("--target")+1])
                            self.assertEqual("tools/idt/prepare_public_signer.py",args[0])
                            self.assertTrue(args[args.index("--output")+1].startswith("C:/ai/codex/tmp/"))
                    else:
                        self.assertNotEqual(0,result.returncode)
                        self.assertFalse(result.stdout.strip())


if __name__=="__main__":unittest.main()
