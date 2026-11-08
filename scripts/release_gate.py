"""Run the release checks and attest the exact verified source tree."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / '.release' / 'verified.json'
EXCLUDE = {'node_modules', '.next', 'out', 'data', '__pycache__', 'test-results', 'playwright-report', '.vercel'}
SOURCE_DIRECTORIES = ('frame', 'demo', 'foundry', 'auth-server', 'web', 'scripts', 'supabase', 'probes', '.github')
SOURCE_FILES = ('Dockerfile', '.dockerignore', '.gitignore', 'requirements.txt', 'render.yaml', 'fly.toml')


def source_files(root=None):
    root = ROOT if root is None else Path(root)
    paths = []
    for directory in SOURCE_DIRECTORIES:
        paths.extend(p for p in (root / directory).rglob('*') if p.is_file()
                     and not any(part in EXCLUDE for part in p.relative_to(root).parts)
                     and not (directory == 'probes' and 'cache' in p.name))
    paths.extend(root / name for name in SOURCE_FILES)
    return sorted(paths)


def fingerprint():
    digest = hashlib.sha256()
    for path in source_files():
        digest.update(path.relative_to(ROOT).as_posix().encode() + b'\0' + path.read_bytes())
    return digest.hexdigest()


def verified():
    try:
        record = json.loads(RECEIPT.read_text())
        return isinstance(record, dict) and record.get('passed') is True and record.get('source') == fingerprint()
    except (OSError, ValueError):
        return False


def checks():
    npm = 'npm.cmd' if os.name == 'nt' else 'npm'
    return [
        ('postgres-config', [sys.executable, '-c',
         "import os; from urllib.parse import urlsplit; "
         "url=os.environ.get('OPERATOR_TEST_DATABASE_URL', ''); "
         "raise SystemExit(0 if urlsplit(url).scheme in ('postgres', 'postgresql', 'postgresql+psycopg') "
         "else 'Set OPERATOR_TEST_DATABASE_URL to an isolated Postgres test database')"]),
        ('core', [sys.executable, '-m', 'frame.selftest']),
        ('backend', [sys.executable, '-m', 'unittest', 'discover', '-s', 'demo', '-t', '.', '-p', 'test_*.py']),
        ('release-tools', [sys.executable, '-m', 'unittest', 'discover', '-s', 'scripts', '-t', '.', '-p', 'test_*.py']),
        ('frontend', [npm, 'test', '--prefix', 'web']),
        ('auth', [npm, 'test', '--prefix', 'auth-server']),
        ('frontend-audit', [npm, 'audit', '--prefix', 'web', '--omit=dev', '--audit-level=high']),
        ('auth-audit', [npm, 'audit', '--prefix', 'auth-server', '--omit=dev', '--audit-level=high']),
        ('build', [npm, 'run', 'build', '--prefix', 'web']),
        ('components', ['node', 'scripts/check_market_render.cjs']),
        ('render-preflight', [sys.executable, 'scripts/render_deploy.py', '--check']),
        ('docker-context', [sys.executable, 'scripts/docker_context.py']),
        ('structure', [sys.executable, 'scripts/verify.py']),
        ('browser', [npm, 'run', 'test:browser', '--prefix', 'web']),
    ]


def run_checks(commands=None):
    directory = RECEIPT.parent
    directory.mkdir(exist_ok=True)
    # A failed rerun must revoke an earlier approval, even for identical source.
    RECEIPT.unlink(missing_ok=True)
    before = fingerprint()
    report = {'passed': False, 'source': before, 'checks': []}
    report_path = directory / 'report.json'
    write_json(report_path, report)
    environment = dict(os.environ)
    environment.setdefault('npm_config_cache', str(directory / 'npm-cache'))
    environment.setdefault('npm_config_fetch_retries', '0')
    environment.setdefault('npm_config_fetch_timeout', '15000')
    for name, command in (checks() if commands is None else commands):
        print('Release gate:', name, flush=True)
        started = time.monotonic()
        log = directory / (name + '.log')
        with log.open('w', encoding='utf-8') as output:
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=output,
                                        stderr=subprocess.STDOUT, timeout=600, env=environment)
                code = result.returncode
            except (OSError, subprocess.TimeoutExpired) as exc:
                # Avoid logging environment values or database connection URLs.
                output.write('Check could not complete: ' + type(exc).__name__ + '\n')
                code = 124 if isinstance(exc, subprocess.TimeoutExpired) else 127
        report['checks'].append({'name': name, 'returncode': code,
                                 'seconds': round(time.monotonic() - started, 3),
                                 'log': log.name})
        write_json(report_path, report)
        print(('PASS' if code == 0 else 'FAIL') + ': ' + name + ' (' + log.name + ')', flush=True)
    after = fingerprint()
    report['source_unchanged'] = before == after
    report['passed'] = bool(report['checks']) and before == after and all(row['returncode'] == 0 for row in report['checks'])
    write_json(report_path, report)
    if report['passed']:
        write_json(RECEIPT, {'passed': True, 'source': after})
        print('Release gates passed; source receipt recorded')
    else:
        print('Release verification failed; see ' + str(report_path))
    return report


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def main():
    raise SystemExit(0 if run_checks()['passed'] else 1)


if __name__ == '__main__':
    main()
