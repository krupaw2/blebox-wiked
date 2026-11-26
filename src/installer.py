#!/usr/bin/env python3
"""Install a version-matched BleBox overlay. Never edit the HA container."""
import argparse
import ast
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request

# Source assets are embedded only when building the standalone installer.
PAYLOAD = (Path(__file__).parent / 'wiked.py').read_text(encoding='utf-8')
INPUT_PAYLOAD = (Path(__file__).parent / 'wiked_inputs.py').read_text(encoding='utf-8')
TRANSLATIONS = {lang: json.loads((Path(__file__).parent / 'translations' / f'{lang}.json').read_text(encoding='utf-8')) for lang in ('en', 'pl')}




def native_source(target, version):
    # Prefer a copy of the actual installed integration, including translations.
    if shutil.which('docker'):
        result = subprocess.run(['docker','cp','homeassistant:/usr/src/homeassistant/homeassistant/components/blebox/.',str(target)],capture_output=True,text=True)
        if result.returncode == 0 and (target/'manifest.json').exists():
            return 'installed Core (docker cp)'
    if not re.fullmatch(r'20\d\d\.\d{1,2}\.\d+', version):
        raise RuntimeError('Expected exact stable HA Core version, e.g. 2026.11.2')
    def download_dir(rel, dest):
        url = f'https://api.github.com/repos/home-assistant/core/contents/{rel}?ref={version}'
        req = urllib.request.Request(url, headers={'User-Agent':'WIKED-BleBox-Installer','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(req, timeout=30) as r:
            entries = json.load(r)
        dest.mkdir(parents=True, exist_ok=True)
        for e in entries:
            path = dest/e['name']
            if e['type'] == 'dir':
                download_dir(e['path'], path)
            elif e['type'] == 'file':
                with urllib.request.urlopen(e['download_url'], timeout=30) as r:
                    path.write_bytes(r.read())
    download_dir('homeassistant/components/blebox', target)
    return f'official Core tag {version}'


def patch(target, version):
    init = target/'__init__.py'
    source = init.read_text(encoding='utf-8')
    pattern = r'(?m)^(\s*)await hass\.config_entries\.async_forward_entry_setups\(entry, PLATFORMS\)\s*$'
    # Fail closed if upstream integration layout differs.
    if not all(x in source for x in ('api_host = ApiHost(', 'coordinator = BleBoxCoordinator(', 'entry.runtime_data = coordinator')):
        raise RuntimeError('Unsupported native BleBox setup layout; nothing installed')
    source, n = re.subn(pattern, lambda m: f'{m[1]}from .wiked import async_prepare\n{m[1]}await async_prepare(hass, entry, coordinator, api_host)\n{m[1]}if getattr(coordinator, "wiked", None) is not None:\n{m[1]}    from .wiked_inputs import async_prepare_inputs\n{m[1]}    await async_prepare_inputs(hass, entry, coordinator.wiked, websession)\n{m[1]}await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)\n', source)
    if n != 1:
        raise RuntimeError('Cannot locate unique platform setup hook; nothing installed')
    if 'Platform.NUMBER' not in source:
        source, n = re.subn(r'(?m)^(PLATFORMS\s*=\s*\[)', r'\1\n    Platform.NUMBER,', source)
        if n != 1:
            raise RuntimeError('Cannot locate native platform list')
    if 'Platform.EVENT' not in source:
        source, n = re.subn(r'(?m)^(PLATFORMS\s*=\s*\[)', r'\1\n    Platform.EVENT,', source)
        if n != 1:
            raise RuntimeError('Cannot locate native platform list for events')
    if 'websession = get_maybe_authenticated_session' not in source:
        raise RuntimeError('Unsupported native BleBox session layout')
    init.write_text(source,encoding='utf-8')
    for platform in ('cover','light','switch','binary_sensor','button'):
        file = target/f'{platform}.py'
        source = file.read_text(encoding='utf-8')
        # The upstream functions have stable signature; guard actual source before wrapping.
        if not re.search(r'async def async_setup_entry\(', source) or 'runtime_data' not in source:
            raise RuntimeError(f'Unsupported {platform} setup layout')
        source += f'''\n\n# WIKED extension: native behavior retained for other products.\n_native_async_setup_entry = async_setup_entry\n\nasync def async_setup_entry(hass, config_entry, async_add_entities):\n    wiked = getattr(config_entry.runtime_data, "wiked", None)\n    if wiked is None:\n        return await _native_async_setup_entry(hass, config_entry, async_add_entities)\n'''
        if platform != 'cover':
            source += f'    from .wiked import entities_for\n    async_add_entities(entities_for(wiked, "{platform}"))\n'
        else:
            # Transitional: keep existing cover working until replacement tested.
            source += '    return await _native_async_setup_entry(hass, config_entry, async_add_entities)\n'
        file.write_text(source,encoding='utf-8')
    event = target/'event.py'
    if event.exists():
        raise RuntimeError('Native event platform already exists; review required')
    event.write_text("from .wiked_inputs import async_setup_entry\n", encoding='utf-8')
    (target/'wiked_inputs.py').write_text(INPUT_PAYLOAD,encoding='utf-8')
    ast.parse(INPUT_PAYLOAD)
    compile(INPUT_PAYLOAD,'wiked_inputs.py','exec')
    number = target/'number.py'
    if number.exists():
        number_source = number.read_text(encoding='utf-8')
        if not re.search(r'async def async_setup_entry\(', number_source):
            raise RuntimeError('Unsupported number setup layout')
        number_source += "\n\n_native_async_setup_entry = async_setup_entry\n\nasync def async_setup_entry(hass, config_entry, async_add_entities):\n    wiked = getattr(config_entry.runtime_data, 'wiked', None)\n    if wiked is None:\n        return await _native_async_setup_entry(hass, config_entry, async_add_entities)\n    from .wiked import entities_for\n    async_add_entities(entities_for(wiked, 'number'))\n"
    else:
        number_source = "\"\"\"WIKED local lighting durations.\"\"\"\n\nasync def async_setup_entry(hass, config_entry, async_add_entities):\n    wiked = getattr(config_entry.runtime_data, 'wiked', None)\n    if wiked is not None:\n        from .wiked import entities_for\n        async_add_entities(entities_for(wiked, 'number'))\n"
    number.write_text(number_source,encoding='utf-8')
    compile(number_source,'number.py','exec')
    # Native update platform stays untouched; copy full native component and config flow.
    (target/'wiked.py').write_text(PAYLOAD + "\n\n_base_entities_for = entities_for\n\ndef entities_for(coordinator, platform):\n    entities = _base_entities_for(coordinator, platform)\n    if platform == 'button' and getattr(coordinator, 'input_events', None) is not None:\n        from .wiked_inputs import WikedConfigureInputs\n        entities.append(WikedConfigureInputs(coordinator))\n    return entities\n",encoding='utf-8')
    manifest_path = target/'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['version'] = '0.1.4'
    manifest['dependencies'] = sorted(set(manifest.get('dependencies', [])) | {'webhook'})
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    if (target/'strings.json').exists() and not (target/'translations'/'en.json').exists():
        (target/'translations').mkdir(exist_ok=True)
        shutil.copy2(target/'strings.json',target/'translations'/'en.json')
    install_translations(target)
    # HA uses Python >=3.13; older terminal Python may not parse native PEP695.
    ast.parse(PAYLOAD)
    compile(PAYLOAD,'wiked.py','exec')


def merge_translations(original, additions):
    """Preserve native translations; reject conflicting WIKĘD keys."""
    for key, value in additions.items():
        if isinstance(value, dict):
            if key not in original:
                original[key] = {}
            if not isinstance(original[key], dict):
                raise RuntimeError(f'Translation conflict: {key}')
            merge_translations(original[key], value)
        elif key in original and original[key] != value:
            raise RuntimeError(f'Translation conflict: {key}')
        else:
            original[key] = value
    return original


def install_translations(target):
    directory = target / 'translations'
    directory.mkdir(exist_ok=True)
    for lang, additions in TRANSLATIONS.items():
        path = directory / f'{lang}.json'
        original = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        merged = merge_translations(original, additions)
        path.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--config',default='/config')
    p.add_argument('--version')
    p.add_argument('--native-source',type=Path,help='Exact installed BleBox directory, if available')
    p.add_argument('--remove',action='store_true')
    p.add_argument('--upgrade',action='store_true',help='Replace only a previously installed WIKED overlay')
    a=p.parse_args()
    config=Path(a.config)
    if not (config/'configuration.yaml').exists():
        raise RuntimeError('Not an HA config directory')
    custom=config/'custom_components'; dest=custom/'blebox'; marker=dest/'.wiked-overlay'
    if a.remove:
        if not marker.is_file():
            raise RuntimeError('Refusing to remove a non-WIKED integration')
        # Preserve a copy outside custom_components so rollback does not lose files.
        backup=config/'blebox_wiked_removed'
        if backup.exists():
            raise RuntimeError(f'Backup already exists: {backup}')
        dest.rename(backup)
        print(f'Removed overlay; backup: {backup}. Restart Core to restore native integration.')
        return
    if dest.exists() and not (a.upgrade and marker.is_file()):
        raise RuntimeError(f'{dest} already exists; refusing to overwrite it. Use --upgrade only for WIKED overlay.')
    version=a.version
    if not version:
        try:
            info=json.loads(subprocess.check_output(['ha','core','info','--raw-json'],text=True))
            version=info.get('data',info)['version']
        except Exception as ex:
            if not a.native_source:
                raise RuntimeError('Cannot determine HA Core version; use --version EXACT_VERSION') from ex
            version='local'
    custom.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='wiked-',dir=config) as tmp:
        stage=Path(tmp)/'blebox'; stage.mkdir()
        if a.native_source:
            shutil.copytree(a.native_source,stage,dirs_exist_ok=True)
            origin=str(a.native_source)
        else:
            origin=native_source(stage,version)
        patch(stage,version)
        (stage/'.wiked-overlay').write_text(f'{version}\n{origin}\n')
        if dest.exists():
            backup = Path(tempfile.mkdtemp(prefix='blebox_wiked_backup-',dir=config))/'blebox'
            dest.rename(backup)
            try:
                stage.rename(dest)
            except BaseException:
                backup.rename(dest)
                raise
            print(f'Previous overlay backup: {backup}')
        else:
            stage.rename(dest)
    print(f'Installed WIKED overlay from {origin} into {dest}.')

if __name__=='__main__':
    main()
