"""Keep fixed-RAM products on their original initialized-data layout."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
COMPILER = Path(os.environ.get('CCRX_BIN', 'C:/Program Files (x86)/Renesas/RX/3_7_0/bin')) / 'ccrx.exe'


class OtaZeroStoragePolicyTests(unittest.TestCase):
    def test_only_rx671_product_configuration_enables_the_storage_policy(self):
        enabled = []
        for header in ROOT.glob('Projects/*/e2studio_ccrx/src/frtos_config/demo_config.h'):
            if re.search(r'(?m)^#define OTA_STATIC_BUFFERS_IN_BSS\s+1\b', header.read_text(encoding='utf-8')):
                enabled.append(header.relative_to(ROOT).as_posix())
        self.assertEqual(['Projects/aws_wifi_rx671_ek/e2studio_ccrx/src/frtos_config/demo_config.h'], enabled)

    @unittest.skipUnless(COMPILER.is_file(), 'CC-RX preprocessing fixture unavailable')
    def test_default_and_disabled_policy_keep_the_real_declaration_initializer(self):
        body = (ROOT / 'Demos/OtaOverMqtt/OtaOverMqttDemo.c').read_text(encoding='utf-8')
        policy = re.search(r'#if defined\(OTA_STATIC_BUFFERS_IN_BSS\).*?#endif', body, re.S).group(0)
        declaration = re.search(r'(?m)^\s*static uint8_t decodedData\[[^\]]+\][^;]+;', body).group(0)
        folder = ROOT / 'artifacts/host-test-tmp'; folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='ota-storage-', dir=folder) as temporary:
            work = Path(temporary).resolve(); self.assertTrue(work.is_relative_to(folder.resolve()))
            source = work / 'policy.c'
            source.write_text('#include <stdint.h>\n#define mqttFileDownloader_CONFIG_BLOCK_SIZE 4096\n' + policy + '\n' + declaration + '\n', encoding='utf-8')
            for state in (None, 0, 1):
                output = work / (str(state) + '.p')
                command = [str(COMPILER), '-nologo', '-isa=rxv3', '-output=prep=' + str(output)]
                if state is not None: command.append('-define=OTA_STATIC_BUFFERS_IN_BSS=' + str(state))
                result = subprocess.run(command + [str(source)], capture_output=True, text=True, timeout=20)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                expanded = re.search(r'decodedData\s*\[[^\]]+\]\s*([^;]*);', output.read_text()).group(1)
                self.assertEqual(state != 1, '=' in expanded)
