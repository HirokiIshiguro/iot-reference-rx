#!/usr/bin/env python3
"""Check SC regeneration cannot replace the shared FreeRTOS V11.3.0 input."""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import urllib.parse
import xml.etree.ElementTree as ET

PROJECTS = (
    'aws_ether_rx72n_envision_kit', 'aws_ether_rx72n_envision_kit_tsip',
    'aws_bg96_ck_rx65n', 'aws_bg96_ck_rx65n_tsip', 'aws_wifi_rx671_ek',
)
KERNEL_VERSION = '11.3.0'
SELECTOR = 'com.renesas.smc.toolchain.option.rtos.freertoslts'
CONFIG_PATHS = {'src/frtos_config/FreeRTOSConfig.h', 'src/frtos_config/FreeRTOSIPConfig.h',
                'src/frtos_config/rm_littlefs_flash_config.h'}
CONFIG_TAGS = {'refinfo', 'package', 'type', 'name', 'version', 'component', 'display', 'detail',
               'configgenpath', 'path', 'category', 'application', 'desc', 'details'}

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def validate(repo: Path) -> dict:
    header = repo / 'Middleware/FreeRTOS/FreeRTOS-Kernel/include/task.h'
    versions = re.findall(r'^#define\s+tskKERNEL_VERSION_NUMBER\s+"V([^" ]+)"',
                          header.read_text(encoding='utf-8'), re.M)
    require(versions == [KERNEL_VERSION], 'Shared Kernel source must remain V11.3.0')
    canonical = repo / 'Configuration/sc_freertos_lts.xml'
    lts = ET.parse(canonical).getroot()
    version = lts.findtext('package/version')
    require(bool(version) and '-saffti-' in version, 'SC descriptor must identify the product configuration version')
    require(lts.findtext('package/name') == 'FreeRTOSLTS', 'SC descriptor name differs from FreeRTOSLTS')
    require(all(item.tag in CONFIG_TAGS for item in lts.iter()), 'SC descriptor may generate configuration headers only')
    require({item.text for item in lts.findall('.//configgenpath/path')} == CONFIG_PATHS,
            'SC descriptor configuration output paths changed')
    require(len(lts.findall('.//configgenpath/path')) == len(CONFIG_PATHS), 'SC descriptor repeats output paths')
    kernel = repo / 'Configuration/sc_freertos_kernel.xml'
    kxml = ET.parse(kernel).getroot()
    require(kxml.findtext('package/name') == 'FreeRTOS_Kernel' and
            kxml.findtext('package/version') == KERNEL_VERSION and
            kxml.findtext('package/application') == 'FreeRTOSLTSLibrary', 'SC Kernel descriptor must remain 11.3.0')
    require(all(item.tag in CONFIG_TAGS for item in kxml.iter()), 'SC Kernel descriptor cannot copy sources')
    for name in PROJECTS:
        project = repo / 'Projects' / name / 'e2studio_ccrx'
        settings = project / '.settings/smartconfigurator/rtos'
        require((settings/'nopg_freertos.xml').read_bytes() == canonical.read_bytes(), name + ': local LTS descriptor drifted')
        require((settings/'FreeRTOS_Kernel.xml').read_bytes() == kernel.read_bytes(), name + ': local Kernel descriptor drifted')
        scfg = ET.parse(project / (name + '.scfg')).getroot()
        selectors = scfg.findall('.//option[@id="com.renesas.smc.toolchain.option.rtos"]')
        require(len(selectors) == 1 and selectors[0].get('key') == SELECTOR and
                selectors[0].find('item').get('id') == SELECTOR and
                selectors[0].find('item').get('value') == version, name + ': SC RTOS selection reverted')
        components = scfg.findall('.//configuration[@name="FreeRTOS_Kernel"]/component')
        require(len(components) == 1 and components[0].get('version') == KERNEL_VERSION,
                name + ': SC Kernel version reverted')
        description = ET.parse(project/'.project').getroot()
        middleware = [link for link in description.findall('linkedResources/link') if link.findtext('name') == 'Middleware']
        require(len(middleware) == 1 and middleware[0].findtext('locationURI') == 'AWS_IOT_MCU_ROOT/Middleware',
                name + ': Middleware no longer uses the shared source root')
        variables = [var for var in description.findall('variableList/variable') if var.findtext('name') == 'AWS_IOT_MCU_ROOT']
        require(len(variables) == 1 and urllib.parse.unquote(variables[0].findtext('value', '')) == '${PARENT-3-PROJECT_LOC}',
                name + ': shared source root location changed')
        for filename in ('task.h', 'tasks.c', 'FreeRTOS.h'):
            for candidate in project.rglob(filename):
                # This product wrapper installs the public Trace hooks after
                # the original Kernel types exist; it contains no Kernel body.
                if candidate.relative_to(project).as_posix() == 'src/tracealyzer_freertos_wrap/FreeRTOS.h':
                    body = candidate.read_text(encoding='utf-8')
                    includes = re.findall(r'^#include\s+["<]([^">]+)[">]', body, re.M)
                    require(includes == ['../../../../../Middleware/FreeRTOS/FreeRTOS-Kernel/include/FreeRTOS.h', 'trcRecorder.h'] and
                            'INC_FREERTOS_H' not in body, name + ': product trace wrapper changed Kernel input')
                    continue
                require(False, name + ': SC created a local Kernel body copy: ' + filename)
    return {'kernel_version': 'V'+KERNEL_VERSION, 'project_count': len(PROJECTS),
            'sc_product_config_version': version, 'source_copy_enabled': False,
            'gui_generation_observed': False}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    result = validate(args.repo_root.resolve())
    print('Common Kernel V11.3.0 and SC configuration verified for', result['project_count'], 'projects')
