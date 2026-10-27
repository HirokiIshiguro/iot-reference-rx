#!/usr/bin/env python3
"""Check SC regeneration preserves the shared Kernel and reviewed Flash input."""
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
FLASH_PROJECTS = PROJECTS + (
    'boot_loader_ck_rx65n', 'boot_loader_rx671_ek', 'boot_loader_rx72n_envision_kit',
)
FLASH_VERSION = '5.31.saffti-custom.1'
FLASH_MACRO = 'FLASH_CFG_FCU_EN_NESTED_INT'
FLASH_URI = 'AWS_IOT_MCU_ROOT/Middleware/Renesas/r_flash_rx/r_flash_rx_vx.xx/r_flash_rx'
FLASH_LEAF = 'Middleware/Renesas/r_flash_rx'
FLASH_CAPABILITY = 'FLASH_RX_SAFFTI_FCU_NESTING_API'
FLASH_INPUTS = ('Makefile', 'r_flash_rx_vx.xx_extend.mdf',
                'r_flash_rx_vx.xx/r_config/r_flash_rx_config.h',
                'r_flash_rx_vx.xx/r_flash_rx/r_flash_rx_if.h', 'r_flash_rx_vx.xx.xml')
KERNEL_VERSION = '11.3.0'
SELECTOR = 'com.renesas.smc.toolchain.option.rtos.freertoslts'
CONFIG_PATHS = {'src/frtos_config/FreeRTOSConfig.h', 'src/frtos_config/FreeRTOSIPConfig.h',
                'src/frtos_config/rm_littlefs_flash_config.h'}
CONFIG_TAGS = {'refinfo', 'package', 'type', 'name', 'version', 'component', 'display', 'detail',
               'configgenpath', 'path', 'category', 'application', 'desc', 'details'}

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def validate_flash_module(repo: Path) -> None:
    """Reject an upstream-only leaf before it can silently ignore the new option."""
    leaf = repo / FLASH_LEAF
    require(all((leaf / path).is_file() for path in FLASH_INPUTS),
            'Flash leaf is not initialized with its configuration inputs')
    makefile = (leaf / 'Makefile').read_text(encoding='utf-8')
    version = re.findall(r'^VERSION[ \t]*=[ \t]*(\S+)[ \t]*$', makefile, re.M)
    require(version == [FLASH_VERSION], 'Flash leaf version differs from the selected SC package')
    package = ET.parse(leaf / FLASH_INPUTS[4]).getroot().find('package')
    dependencies = {dependency.findtext('module'): dependency.findtext('version')
                    for dependency in package.findall('dependency')}
    require(dependencies.get('r_bsp') == '7.71', 'Flash leaf BSP dependency version differs from this product')
    interface = (leaf / FLASH_INPUTS[3]).read_text(encoding='utf-8')
    identity = re.findall(r'^#define[ \t]+FLASH_RX_SAFFTI_VERSION[ \t]+"([^"\r\n]+)"[ \t]*$', interface, re.M)
    require(identity == [FLASH_VERSION], 'Flash interface version differs from the selected SC package')
    capability = re.findall(r'^#define[ \t]+' + FLASH_CAPABILITY + r'[ \t]+([^\r\n]+)', interface, re.M)
    require(len(capability) == 1 and re.fullmatch(r'\(?1\)?', capability[0].strip()),
            'Flash leaf has no reviewed FCU nesting API capability')
    template = (leaf / FLASH_INPUTS[2]).read_text(encoding='utf-8')
    default = re.findall(r'^#define[ \t]+' + FLASH_MACRO + r'[ \t]+([^\r\n]+)', template, re.M)
    require(len(default) == 1 and re.fullmatch(r'\(?0\)?', default[0].strip()),
            'Flash leaf nesting must remain opt-in by default')
    metadata = ET.parse(leaf / FLASH_INPUTS[1]).getroot()
    properties = metadata.findall('.//configuration/property[@id="' + FLASH_MACRO + '"]')
    require(len(properties) == 1 and properties[0].get('default') == '0' and
            [option.get('value') for option in properties[0].findall('option')] == ['0', '1'],
            'Flash leaf MDF does not preserve the explicit opt-in option')


def validate_flash(repo: Path) -> dict:
    """Bind generated configuration to the Flash leaf that the compiler reads."""
    validate_flash_module(repo)
    for name in FLASH_PROJECTS:
        project = repo / 'Projects' / name / 'e2studio_ccrx'
        expected = '1' if name.startswith('boot_loader_') else '0'
        description = ET.parse(project / '.project').getroot()
        links = [link for link in description.findall('linkedResources/link')
                 if link.findtext('name') == 'Vendor/r_flash_rx']
        require(len(links) == 1 and links[0].findtext('locationURI') == FLASH_URI,
                name + ': Flash no longer uses the reviewed leaf')
        scfg = ET.parse(project / (name + '.scfg')).getroot()
        components = scfg.findall('.//configuration[@name="r_flash_rx"]/component')
        require(len(components) == 1 and components[0].get('display') == 'r_flash_rx' and
                components[0].get('version') == FLASH_VERSION and
                components[0].get('id') == 'r_flash_rx' + FLASH_VERSION,
                name + ': SC Flash package version reverted')
        selections = components[0].findall('gridItem[@id="' + FLASH_MACRO + '"]')
        require(len(selections) == 1 and selections[0].get('selectedIndex') == expected,
                name + ': SC FCU nested interrupt selection reverted')
        qe = ET.parse(project / '.settings/com.renesas.smc.e2studio.qe.xml').getroot()
        segments = qe.findall('.//Segment[@id="r_flash_rx"]')
        require(len(segments) == 1 and segments[0].get('component') == 'r_flash_rx' + FLASH_VERSION,
                name + ': QE Flash package version reverted')
        selections = segments[0].findall('Setting[@id="' + FLASH_MACRO + '"]')
        require(len(selections) == 1 and selections[0].get('value') == expected,
                name + ': QE FCU nested interrupt selection reverted')
        header = (project / 'src/smc_gen/r_config/r_flash_rx_config.h').read_text(encoding='utf-8')
        definitions = re.findall(r'^#define[ \t]+' + FLASH_MACRO + r'[ \t]+([^\r\n]+)', header, re.M)
        require(len(definitions) == 1 and re.fullmatch(r'\(?' + expected + r'\)?', definitions[0].strip()),
                name + ': generated FCU nested interrupt setting reverted')
        cproject = ET.parse(project / '.cproject').getroot()
        entries = cproject.findall('.//sourceEntries/entry[@kind="sourcePath"]')
        require(any(entry.get('name') == 'Vendor/r_flash_rx/src' for entry in entries),
                name + ': compiler no longer selects the Flash leaf')
        source = [entry for entry in entries if entry.get('name') in ('', 'src')]
        require(bool(source) and all(
                ('src/smc_gen/r_flash_rx' if entry.get('name') == '' else 'smc_gen/r_flash_rx') in
                {item.rstrip('/') for item in entry.get('excluding', '').split('|')} for entry in source) and
                not any('smc_gen/r_flash_rx' in entry.get('name', '') for entry in entries),
                name + ': generated Flash body entered compiler inputs')
    return {'fit_version': FLASH_VERSION, 'project_count': len(FLASH_PROJECTS),
            'boot_nested_interrupts': True, 'app_nested_interrupts': False}

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
    flash = validate_flash(repo)
    return {'kernel_version': 'V'+KERNEL_VERSION, 'project_count': len(PROJECTS),
            'sc_product_config_version': version, 'source_copy_enabled': False,
            'gui_generation_observed': False, 'flash': flash}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    result = validate(args.repo_root.resolve())
    print('Common Kernel V11.3.0 and SC configuration verified for', result['project_count'], 'projects;',
          'Flash', result['flash']['fit_version'], 'verified for', result['flash']['project_count'], 'projects')
