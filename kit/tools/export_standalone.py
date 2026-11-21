#!/usr/bin/env python3
"""Export M Drive from a clean upstream checkout into an empty standalone directory."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

TREES = ('apps/m_drive/', 'kit/runtime/', 'kit/platform/', 'kit/localization/',
         'kit/emu/', 'kit/renderd/', 'kit/tools/oapgen/', 'deploy/')
TOOLS = '''build.py pack_data.py localize.py locale-revisions.json make_icon.js make_kit.py
preview.js hu-stub.js emu.js extract_sdk.js render_icons.py check_signals.py sigdoc.py
bake_fonts.py bake_cjk.py bake_cyrillic.py bake_korean.py sync_locales.py sync_zh.py
test_m_drive.js test_runtime.js test_dids.js test_diag_options.js test_engine.js
test_fit_to_unit.py test_id8_ui.py test_bm3_protocol.js test_zh.js'''.split()
FILES = {'LICENSE', 'NOTICE.zh-CN.md', '.gitignore', '.gitattributes', 'package.json',
         'mgu-repo.json', 'kit/icons/m_drive.svg', 'docs/screens/m_drive.png',
         'docs/rhmi-widgets.md', '.github/workflows/renderd.yml'}
FILES.update('kit/tools/' + name for name in TOOLS)


def write_json(file, value):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def export(source, target):
    if source == target or source in target.parents:
        raise SystemExit('Export outside the source checkout.')
    if target.exists() and any(target.iterdir()):
        raise SystemExit('The destination must be empty.')
    dirty = subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain'])
    if dirty:
        raise SystemExit('Commit source changes before exporting.')
    commit = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    tracked = subprocess.check_output(['git', '-C', str(source), 'ls-files', '-z']).decode().split('\0')
    for rel in tracked:
        if not rel or not (rel in FILES or rel.startswith(TREES)):
            continue
        dst = target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, dst)

    app = target / 'apps/m_drive'
    spec = json.loads((app / 'app.json').read_text())
    modules = {}
    for rel in spec.pop('sharedSources'):
        dst = app / Path(rel).name
        if dst.exists():
            raise SystemExit('Module collision: ' + str(dst))
        shutil.copy2(source / rel, dst)
        modules[dst.name] = {'source': rel, 'sha256': hashlib.sha256(dst.read_bytes()).hexdigest()}
    write_json(app / 'app.json', spec)
    contract = {'source_repository': 'https://github.com/cauliflowermossgrape/idrive7-apps',
                'source_commit': commit, 'modules': modules,
                'dme': {k: spec['config']['dme'][k] for k in ('ecu', 'iat', 'boost', 'baro', 'egs')}}
    write_json(target / 'kit/tools/fixtures/m_drive_contract.json', contract)

    catalog_file = target / 'mgu-repo.json'
    catalog = json.loads(catalog_file.read_text())
    build = catalog['apps']['build']
    build['network'] = []
    build['shared'] = [p for p in build['shared'] if not p.startswith('apps/')]
    catalog['tools'][1]['description'] = "Lets M Drive use the iDrive controller for controls, tabs and settings."
    write_json(catalog_file, catalog)

    test_file = target / 'kit/tools/test_m_drive.js'
    test = test_file.read_text()
    start = test.index("    await t('build: the shared Engine Config modules")
    end = test.index("    await t('build: sharedSources", start)
    test = test[:start] + '''    await t('build: bundled control modules preserve their source and staged bytes', async () => {
        const spec = JSON.parse(fs.readFileSync(path.join(ROOT, 'apps/m_drive/app.json'), 'utf8'));
        const contract = require('./fixtures/m_drive_contract.json');
        const crypto = require('crypto');
        assert.strictEqual(spec.sharedSources, undefined);
        assert.deepStrictEqual(Object.keys(contract.modules).sort(),
            ['adapters.js', 'auto.js', 'bm3_profiles.js', 'bm3_protocol.js', 'controller.js', 'diaglink.js', 'real_adapters.js', 'tune.js']);
        Object.keys(contract.modules).forEach((name) => {
            const source = fs.readFileSync(path.join(ROOT, 'apps/m_drive', name));
            assert.ok(source.equals(fs.readFileSync(path.join(JS, name))), name);
            assert.strictEqual(crypto.createHash('sha256').update(source).digest('hex'), contract.modules[name].sha256, name);
        });
        assert.ok(!fs.existsSync(path.join(STAGE, 'source/node_modules/oap-sdk/index.js')));
    });
''' + test[end:]
    test = test.replace("['apps/live_adjustments/tune.js']), ['tune.js']", "['kit/runtime/diag.js']), ['diag.js']")
    test = test.replace("['apps/live_adjustments/app.json']", "['apps/m_drive/app.json']")
    test = test.replace("['apps/live_adjustments/ui.js']", "['apps/m_drive/ui.js']")
    test = test.replace("/collides with the staged tune\\.js/", "/collides with the staged diag\\.js/")
    test = test.replace("['apps/live_adjustments/tune.js', 'apps/live_adjustments/tune.js']", "['kit/runtime/diag.js', 'kit/runtime/diag.js']")
    test = test.replace("telemetry candidates as M Vitals has them", "pinned telemetry candidates")
    test = test.replace("JSON.parse(fs.readFileSync(path.join(ROOT, 'apps', 'car_vitals', 'app.json'), 'utf8')).config.dme",
                        "require('./fixtures/m_drive_contract.json').dme")
    test_file.write_text(test)
    bm3 = target / 'kit/tools/test_bm3_protocol.js'
    bm3.write_text(bm3.read_text().replace('../../apps/live_adjustments/', '../../apps/m_drive/'))

    for rel in ('kit/tools/build.py', 'kit/tools/make_kit.py', 'deploy/make-car-kit.sh'):
        file = target / rel
        file.write_text(file.read_text().replace('car_vitals', 'm_drive'))
    shutil.copy2(Path(__file__), target / 'kit/tools/export_standalone.py')
    print('Exported ' + str(target) + ' from ' + commit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    export(args.source.resolve(), args.destination.resolve())
