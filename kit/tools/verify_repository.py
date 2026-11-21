#!/usr/bin/env python3
"""Verify the standalone app inventory, module provenance, and offline language builds."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
apps = sorted(p.name for p in (ROOT / 'apps').iterdir() if p.is_dir())
assert apps == ['m_drive'], apps
spec = json.loads((ROOT / 'apps/m_drive/app.json').read_text())
assert spec['id'] == 'm_drive' and 'sharedSources' not in spec
assert spec['mguHmi'] == ['ID7']
contract = json.loads((ROOT / 'kit/tools/fixtures/m_drive_contract.json').read_text())
for name, origin in contract['modules'].items():
    file = ROOT / 'apps/m_drive' / name
    assert hashlib.sha256(file.read_bytes()).hexdigest() == origin['sha256'], name
catalog = json.loads((ROOT / 'mgu-repo.json').read_text())
assert catalog['apps']['build']['network'] == []
assert all(not name.startswith('apps/') for name in catalog['apps']['build']['shared'])
assert 'oap-sdk' in (ROOT / '.gitignore').read_text().splitlines()
if (ROOT / '.git').exists():
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    assert not any(name == 'oap-sdk' or name.startswith('oap-sdk/') for name in tracked)
for language in ('ko', 'ru', 'zh-CN', 'en'):
    subprocess.run([sys.executable, str(ROOT / 'kit/tools/build.py'), '--preview-only',
                    '--language', language, 'm_drive'], cwd=ROOT, check=True)
stage = ROOT / 'dist/m_drive/source/javascript'
assert not (stage.parent / 'node_modules/oap-sdk/index.js').exists()
for name in contract['modules']:
    assert (stage / name).read_bytes() == (ROOT / 'apps/m_drive' / name).read_bytes(), name
print('PASS: only M Drive, bundled module provenance, four offline language builds, no SDK published')
