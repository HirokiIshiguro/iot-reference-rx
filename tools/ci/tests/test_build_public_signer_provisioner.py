"""Standalone public signer profiles never change normal app/vendor inputs."""
from pathlib import Path
import json
import os
import time
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import patch

from tools import build_public_signer_provisioner as builder

ROOT = Path(__file__).resolve().parents[3]
SOURCE_SHA = 'a' * 40

def srecord(address, data):
    body = bytes([len(data)+5]) + address.to_bytes(4, 'big') + data
    return 'S3' + (body+bytes([(~sum(body))&255])).hex().upper()+'\n'

def image(target_id, source_sha=SOURCE_SHA, *, mde=b'\x8f\xff\xff\xff', bank=b'\xff'*4, extra=None):
    start = builder.CODE_FLASH_START[target_id]+0x300
    marker = b'PUBLIC_SIGNER_PROVISIONER source_sha='+source_sha.encode('ascii')+b'\r\n'
    records = [srecord(start,b'\x01\x02\x03\x04'), srecord(0xFFFFFFFC,start.to_bytes(4,'little')),
               srecord(0xFE7F5D00,mde), srecord(0xFE7F5D20,bank),srecord(start+0x1000,marker)]
    if extra is not None:
        records.append(srecord(*extra))
    return ''.join(records)

class PublicSignerProfileTests(unittest.TestCase):
    def test_three_dual_profiles_keep_payload_layout_and_move_only_vectors(self):
        for target_id in builder.BUILD_HELPERS:
            with self.subTest(target=target_id):
                path = ROOT / builder.get_target(target_id)['application_project'] / '.cproject'
                original = path.read_text(encoding='utf-8')
                changed = builder.make_profile(original)
                old = ET.fromstring(original)
                new = ET.fromstring(changed)
                def section(root):
                    return [item.get('value') for item in root.iter('option')
                            if item.get('superClass', '').endswith('.linker.option.linkerSection')][0]
                self.assertEqual(section(old).split(',EXCEPTVECT/')[0], section(new).split(',EXCEPTVECT/')[0])
                self.assertIn('EXCEPTVECT/0FFFFFF80', section(new).split(','))
                self.assertIn('RESETVECT/0FFFFFFFC', section(new).split(','))
                self.assertEqual([part for part in section(old).split(',') if not part.startswith(('EXCEPTVECT/', 'RESETVECT/'))],
                                 [part for part in section(new).split(',') if not part.startswith(('EXCEPTVECT/', 'RESETVECT/'))])
                self.assertIn('modes="bank.dual"', changed)
                self.assertIn('-define=PUBLIC_SIGNER_PROVISIONER_ENABLE=1', changed)
                self.assertIn('PFRAM2=RPFRAM2', changed)
                self.assertNotIn('PUBLIC_SIGNER_PROVISIONER_ENABLE', original)

    def test_linear_input_and_duplicate_vector_options_fail_before_edit(self):
        target = builder.get_target('rx671-wifi')
        source = (ROOT / target['application_project'] / '.cproject').read_text(encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'canonical dual-bank'):
            builder.make_profile(source.replace('modes="bank.dual"', 'modes="bank.single"'))
        tree = ET.fromstring(source)
        option = next(item for item in tree.iter('option') if 'EXCEPTVECT/' in item.get('value', ''))
        tree.append(ET.fromstring(ET.tostring(option)))
        with self.assertRaisesRegex(ValueError, 'one application vector'):
            builder.make_profile(ET.tostring(tree, encoding='unicode'))

    def test_failed_build_restores_project_bytes(self):
        target = builder.get_target('rx671-wifi')
        raw = (ROOT / target['application_project'] / '.cproject').read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            path = project / '.cproject'
            path.write_bytes(raw)
            with self.assertRaisesRegex(RuntimeError, 'synthetic build failure'):
                with builder.temporary_profile(project):
                    self.assertNotEqual(raw, path.read_bytes())
                    raise RuntimeError('synthetic build failure')
            self.assertEqual(raw, path.read_bytes())

    def test_environment_removes_injection_and_keeps_tool_license_and_ca_paths(self):
        original={'PATH':'TOOLS','BIN_RX':'COMPILER','SSL_CERT_FILE':'CA',
                  'GITLAB_API_TOKEN_FOR_CODEX':'dummy-tool-auth','AWS_IOT_PRIVATE_KEY_FILE':'dummy-key',
                  'RX671_EK_WIFI_SSID':'dummy-wifi','IDT_PRIVATE_KEY':'dummy-key','CPATH':'overlay',
                  'RX65N_BG96_TLS_BACKEND':'tsip','AWS_SECRET_ACCESS_KEY':'dummy-cloud'}
        isolated=builder.isolated_environment(original)
        self.assertEqual(set(isolated), {'PATH','BIN_RX','SSL_CERT_FILE','GITLAB_API_TOKEN_FOR_CODEX'})
        self.assertIn('IDT_PRIVATE_KEY',original)

    def test_failure_restores_private_header_bytes_and_absent_local_paths(self):
        with tempfile.TemporaryDirectory() as temporary:
            repo=Path(temporary);project=repo/'project';project.mkdir()
            header=repo/'Demos/include/aws_clientcredential_keys.h';header.parent.mkdir(parents=True)
            original=b'/* SYNTHETIC PRIVATE USER DATA, not a real credential. */'
            header.write_bytes(original)
            local=project/builder.LOCAL_HEADERS[0];local.parent.mkdir(parents=True)
            local.write_bytes(b'dummy local input')
            with self.assertRaisesRegex(RuntimeError,'synthetic error'):
                with builder.CredentialIsolation(repo,project) as scope:
                    scope.validate()
                    self.assertNotEqual(header.read_bytes(),original)
                    self.assertFalse(local.exists())
                    raise RuntimeError('synthetic error')
            self.assertEqual(header.read_bytes(),original)
            self.assertEqual(local.read_bytes(),b'dummy local input')
            self.assertFalse((repo/'Demos/include/aws_clientcredential.h').exists())

    def test_binary_validation_rejects_wrong_bank_source_private_data_and_data_flash(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'provisioner.mot'
            for target in builder.BUILD_HELPERS:
                path.write_text(image(target),encoding='ascii')
                self.assertTrue(builder.validate_image(path,target,SOURCE_SHA)['compiled_source_identity_verified'])
                for malformed in (
                    image(target,mde=b'\xff'*4),image(target,bank=b'\xf8\xff\xff\xff'),
                    image(target,source_sha='b'*40),image(target,extra=(0x00100000,b'DF')),
                    image(target,extra=(builder.CODE_FLASH_START[target]+0x2000,b'-----BEGIN EC PRIVATE KEY-----')),
                ):
                    path.write_text(malformed,encoding='ascii')
                    with self.assertRaises(RuntimeError):builder.validate_image(path,target,SOURCE_SHA)

    def test_effective_commands_require_actual_defines_layout_and_ram_mapping(self):
        with tempfile.TemporaryDirectory() as temporary:
            project=Path(temporary);directory=project/'HardwareDebug';directory.mkdir()
            log=project/'private.log';log.write_text('',encoding='utf-8')
            response=directory/'Linker.tmp'
            valid='-define=PUBLIC_SIGNER_PROVISIONER_ENABLE=1,PUBLIC_SIGNER_SOURCE_SHA='+SOURCE_SHA+'\n-start=P/FFF00300,EXCEPTVECT/0FFFFFF80,RESETVECT/0FFFFFFFC\n-rom=PFRAM2=RPFRAM2\n'
            response.write_text(valid,encoding='utf-8')
            self.assertTrue(builder.validate_effective_commands(project,SOURCE_SHA,log)['standalone_vectors_verified'])
            for invalid in (valid.replace(SOURCE_SHA,'b'*40),valid.replace('PFRAM2=RPFRAM2','P=RP'),valid.replace('FFFFFFFC','FFFBFFFC'),valid+'-define=AWS_IOT_USE_LOCAL_CONFIG\n'):
                response.write_text(invalid,encoding='utf-8')
                with self.assertRaises(RuntimeError):builder.validate_effective_commands(project,SOURCE_SHA,log)

    def test_build_proves_input_isolation_source_bound_mot_and_restores_on_failure(self):
        for target_id in builder.BUILD_HELPERS:
            for failure in (False,True,'stale'):
                with self.subTest(target=target_id,failure=failure), tempfile.TemporaryDirectory() as temporary:
                    base=Path(temporary);repo=base/'repo';repo.mkdir()
                    project=repo/builder.get_target(target_id)['application_project'];project.mkdir(parents=True)
                    reference=ROOT/builder.get_target(target_id)['application_project']
                    project.joinpath('.cproject').write_bytes(reference.joinpath('.cproject').read_bytes())
                    project.joinpath('.project').write_bytes(reference.joinpath('.project').read_bytes())
                    before=project.joinpath('.cproject').read_bytes()
                    header=repo/'Demos/include/aws_clientcredential_keys.h';header.parent.mkdir(parents=True)
                    header.write_bytes(b'dummy saved caller input')
                    name=ET.parse(project/'.project').getroot().findtext('name')
                    def runner(command,**kwargs):
                        self.assertNotIn('AWS_IOT_PRIVATE_KEY_PEM',kwargs['env'])
                        self.assertEqual(header.read_text(encoding='utf-8'),builder.BLANK_HEADERS[header.name])
                        self.assertIn('PUBLIC_SIGNER_SOURCE_SHA='+SOURCE_SHA,project.joinpath('.cproject').read_text(encoding='utf-8'))
                        if failure is True:return subprocess.CompletedProcess(command,1,b'',b'')
                        generated=project/'HardwareDebug';generated.mkdir()
                        (generated/'Linker.tmp').write_text('-define=PUBLIC_SIGNER_PROVISIONER_ENABLE=1,PUBLIC_SIGNER_SOURCE_SHA='+SOURCE_SHA+'\n-start=P/FFF00300,EXCEPTVECT/0FFFFFF80,RESETVECT/0FFFFFFFC\n-rom=PFRAM2=RPFRAM2\n',encoding='utf-8')
                        (generated/(name+'.mot')).write_text(image(target_id),encoding='ascii')
                        for suffix in ('map','abs'):(generated/(name+'.'+suffix)).write_bytes(b'dummy fixture')
                        # A mocked compile finishes within one filesystem clock
                        # tick. Mark its synthetic outputs explicitly fresh;
                        # production's stale-artifact check remains unchanged.
                        fresh=0 if failure=='stale' else time.time_ns()+1_000_000_000
                        for suffix in ('mot','map','abs'):
                            os.utime(generated/(name+'.'+suffix),ns=(fresh,fresh))
                        return subprocess.CompletedProcess(command,0,b'',b'')
                    def git(command,**_):return SOURCE_SHA+'\n' if 'rev-parse' in command else ''
                    with patch.object(builder.subprocess,'run',side_effect=runner), patch.object(builder.subprocess,'check_output',side_effect=git), patch.dict(os.environ,{'AWS_IOT_PRIVATE_KEY_PEM':'dummy caller secret'}):
                        if failure=='stale':
                            with self.assertRaisesRegex(RuntimeError,'stale artifact'):builder.build(repo,target_id,base/'output',base/'workspace','python')
                        elif failure:
                            with self.assertRaisesRegex(RuntimeError,'build failed'):builder.build(repo,target_id,base/'output',base/'workspace','python')
                        else:
                            result=builder.build(repo,target_id,base/'output',base/'workspace','python')
                            self.assertIs(result['credentials_embedded'],False)
                            self.assertTrue(result['image_validation']['compiled_source_identity_verified'])
                            self.assertTrue(result['formal'])
                            self.assertEqual(json.loads((base/'output/provisioner-manifest.json').read_text())['source_sha'],SOURCE_SHA)
                    self.assertEqual(header.read_bytes(),b'dummy saved caller input')
                    self.assertEqual(project.joinpath('.cproject').read_bytes(),before)

if __name__ == '__main__':
    unittest.main()
