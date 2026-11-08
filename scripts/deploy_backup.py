"""Fail-closed wallet cutover and a validated backup before each deployment."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

from demo.db import make_engine, make_session_factory
from scripts.wallet_backup import export_wallet, validate, write_backup

HEALTH_ATTEMPTS = 3


def fetch_health(url, attempts=HEALTH_ATTEMPTS, pause=2.0):
    """Read /api/health with small retries; RuntimeError (clean) when unreachable."""
    last = "no attempt"
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(url.rstrip('/') + '/api/health', timeout=15) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = type(exc).__name__
            print(f'health check attempt {attempt}/{attempts} failed ({last})', flush=True)
            if attempt < attempts:
                time.sleep(pause)
    raise RuntimeError(
        'cannot reach the live service health endpoint after '
        f'{attempts} attempts ({last}); refusing to deploy without a backup — '
        'check the Render service/logs, do not bypass the backup') from None


def before_deploy(root, url, environment):
    health = fetch_health(url)
    if health.get('storage', {}).get('wallet') != 'database':
        checks = {row['name']: row for row in health.get('checks', [])}
        if not re.match(r'^0 postings\b', checks.get('books', {}).get('detail', '')) or \
                not re.match(r'^0 records\b', checks.get('ledger', {}).get('detail', '')):
            raise ValueError('live file wallet is nonempty; explicit export/cutover required before deploying')
    url = environment.get('DATABASE_URL', '')
    if not url:
        raise ValueError('durable wallet deployment requires DATABASE_URL')
    engine = make_engine(url)
    try:
        factory = make_session_factory(engine)
        backup = export_wallet(factory, allow_empty=True)
        validate(backup)
        directory = Path(root, '.backups')
        directory.mkdir(exist_ok=True)
        name = datetime.now(timezone.utc).strftime('wallet-%Y%m%d-%H%M%S-%f.json')
        path = directory / name
        write_backup(path, backup)
        print('Verified pre-deployment wallet backup:', str(path.relative_to(root)))
    finally:
        engine.dispose()
