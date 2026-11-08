"""Fail-closed wallet cutover and a validated backup before each deployment."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import urllib.request

from demo.db import make_engine, make_session_factory
from scripts.wallet_backup import export_wallet, validate, write_backup


def before_deploy(root, url, environment):
    with urllib.request.urlopen(url.rstrip('/') + '/api/health', timeout=30) as response:
        health = json.load(response)
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
