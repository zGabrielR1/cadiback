"""Build and serve Tournament Blue locally, isolated from the normal export.

Usage: python scripts/local_blue.py [--port 8766] [--no-build]
Requires web/node_modules (npm --prefix web ci). Never deploys.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
BUILD = Path(tempfile.gettempdir()) / 'operator-blue-local'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8766)
    parser.add_argument('--no-build', action='store_true')
    args = parser.parse_args()
    if not args.no_build:
        if not (ROOT / 'web/node_modules/next').exists():
            parser.error('Install dependencies first: npm --prefix web ci')
        BUILD.mkdir(exist_ok=True)
        for name in ('app', 'lib', 'public'):
            dest = BUILD / name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(ROOT / 'web' / name, dest)
        for name in ('package.json', 'package-lock.json', 'next.config.js'):
            shutil.copy2(ROOT / 'web' / name, BUILD / name)
        if not (BUILD / 'node_modules/next').exists():
            shutil.copytree(ROOT / 'web/node_modules', BUILD / 'node_modules',
                            symlinks=True, dirs_exist_ok=True)
        build_env = dict(os.environ, NEXT_PUBLIC_LOCAL_BLUE='1')
        build_env.pop('VERCEL', None)
        build_env.pop('NEXT_OUTPUT', None)
        subprocess.run(['npm', 'run', 'build'], cwd=BUILD, env=build_env, check=True)
    if not (BUILD / 'out/index.html').exists():
        parser.error('No local Blue export. Run without --no-build first.')
    # Independent local account/books data, never the production database.
    os.environ['OPERATOR_DATA_DIR'] = str(BUILD / 'demo-data')
    os.environ['DATABASE_URL'] = ''
    sys.path.insert(0, str(ROOT))
    from demo import server
    server.WEB_OUT = str(BUILD / 'out')
    print(f'Tournament Blue: http://localhost:{args.port} (local only)', flush=True)
    server.run(host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
