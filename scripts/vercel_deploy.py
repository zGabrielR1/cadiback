"""Publish the verified committed frontend to the existing Vercel project.

Uses Vercel CLI's own signed-in credential store. Project settings and
production BACKEND_URL are retained. No dotenv files enter the upload.
"""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release_gate import ROOT, verified, source_files


def require_committed_frontend():
    # git archive publishes HEAD, so both tracked edits and new source files
    # must be committed before the verified working tree can be published.
    dirty = subprocess.check_output(
        ['git', 'status', '--porcelain', '--untracked-files=all', '--', 'web'],
        cwd=ROOT, text=True).strip()
    if dirty:
        raise SystemExit('Commit the verified frontend before publishing')
    tracked = set(subprocess.check_output(
        ['git', 'ls-tree', '-r', '--name-only', '-z', 'HEAD', '--', 'web'],
        cwd=ROOT).decode().split('\0'))
    if any(path.relative_to(ROOT).as_posix() not in tracked
           for path in source_files(ROOT) if path.is_relative_to(ROOT / 'web')):
        raise SystemExit('Verified frontend includes ignored source files; publication refused')


def main():
    if not verified():
        raise SystemExit('Run python scripts/release_gate.py before publishing')
    require_committed_frontend()
    link = ROOT / 'web' / '.vercel' / 'project.json'
    if not link.exists():
        raise SystemExit('Link web/ to the existing cadiback-web Vercel project first')
    project = json.loads(link.read_text())
    if project.get('projectName') != 'cadiback-web':
        raise SystemExit('Unexpected Vercel project; publication refused')
    archive = subprocess.check_output(['git','archive','--format=zip','HEAD','web'], cwd=ROOT)
    with tempfile.TemporaryDirectory(prefix='operator-vercel-') as directory:
        zipfile.ZipFile(io.BytesIO(archive)).extractall(directory)
        web = Path(directory, 'web')
        if any(p.name.startswith('.env') for p in web.rglob('*')):
            raise SystemExit('Dotenv file found in publication source; refused')
        (web / '.vercel').mkdir()
        shutil.copy2(link, web / '.vercel' / 'project.json')
        npx = 'npx.cmd' if os.name == 'nt' else 'npx'
        subprocess.run([npx,'--yes','vercel','--prod','--yes'], cwd=web, check=True)


if __name__ == '__main__':
    main()
