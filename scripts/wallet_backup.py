"""Validated wallet backup/restore. Restore only into an empty wallet database.

python -m scripts.wallet_backup --backup .backups/wallet.json
python -m scripts.wallet_backup --check .backups/wallet.json
python -m scripts.wallet_backup --restore .backups/wallet.json
Uses DATABASE_URL via the same local/env discovery as the server. No DSN is printed.
"""
import argparse
from copy import deepcopy
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

from demo.wallet_snapshot import validate_postings
from demo.publisher_state import decode_state

NAMES = ("runtime:books", "runtime:rounds", "promos", "crash_pending",
          "crypto_charges", "asaas_charges", "publisher_state", "card_charges")


def digest(payload):
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def validate(backup):
    if not isinstance(backup, dict) or type(backup.get('format')) is not int or backup['format'] != 1:
        raise ValueError("invalid backup envelope")
    payload = backup.get("payload")
    if not isinstance(payload, dict) or set(payload) - set(NAMES) or "runtime:books" not in payload:
        raise ValueError("invalid backup documents")
    if backup.get("sha256") != digest(payload):
        raise ValueError("backup checksum or format mismatch")
    books = payload['runtime:books']
    if not isinstance(books, dict):
        raise ValueError('invalid wallet document')
    validate_postings(books.get('postings'))
    if "runtime:rounds" in payload and (not isinstance(payload['runtime:rounds'], dict)
            or not isinstance(payload["runtime:rounds"].get("rows"), list)
            or any(not isinstance(r, dict) for r in payload["runtime:rounds"]["rows"])):
        raise ValueError("invalid round history")
    for name in ("promos", "crash_pending"):
        if name in payload and not isinstance(payload[name], dict):
            raise ValueError("invalid runtime document")
    if 'publisher_state' in payload:
        decode_state(payload['publisher_state'])
    if 'crypto_charges' in payload:
        charges = payload['crypto_charges']
        if not isinstance(charges, dict):
            raise ValueError('invalid crypto invoices')
        for reference, row in charges.items():
            if not isinstance(reference, str) or not reference or not isinstance(row, dict) \
                    or row.get('deposit_id') != reference or not isinstance(row.get('player'), str) \
                    or not row['player'] or type(row.get('amount_minor')) is not int \
                    or row['amount_minor'] <= 0 or type(row.get('posted')) is not bool \
                    or not isinstance(row.get('provider_ref'), str):
                raise ValueError('invalid crypto invoice')
    if 'asaas_charges' in payload:
        charges = payload['asaas_charges']
        if not isinstance(charges, dict):
            raise ValueError('invalid Asaas invoices')
        for reference, row in charges.items():
            if not isinstance(reference, str) or not reference or not isinstance(row, dict) \
                    or row.get('deposit_id') != reference or not isinstance(row.get('player'), str) \
                    or not row['player'] or type(row.get('amount_minor')) is not int \
                    or row['amount_minor'] <= 0 or type(row.get('posted')) is not bool \
                    or not isinstance(row.get('provider_ref'), str) \
                    or not isinstance(row.get('provider_status', 'PENDING'), str):
                raise ValueError('invalid Asaas invoice')
    return payload


def make_backup(payload, *, allow_empty=False):
    # Only a genuinely empty destination can be represented as a new wallet.
    # Ancillary documents without books indicate a partial/corrupt cutover.
    payload = deepcopy(payload)
    if allow_empty and not payload:
        payload = {'runtime:books': {'postings': []}}
    backup = {"format": 1, "payload": payload, "sha256": digest(payload)}
    validate(backup)
    return backup


def export_wallet(factory, *, allow_empty=False):
    from sqlalchemy import inspect, select
    from demo.models import AsaasCharge, IdentityDocument
    with factory() as db:
        payload = {row.name: deepcopy(row.data) for row in db.scalars(
            select(IdentityDocument).where(IdentityDocument.name.in_(NAMES)))}
        asaas_rows = db.scalars(select(AsaasCharge).order_by(AsaasCharge.deposit_id)).all() \
            if inspect(db.bind).has_table('asaas_charges') else []
    if asaas_rows:
        payload['asaas_charges'] = {
            row.deposit_id: {
                'deposit_id': row.deposit_id,
                'player': row.player,
                'amount_minor': int(row.amount_minor),
                'provider_ref': row.provider_ref or '',
                'provider_status': row.provider_status or '',
                'qr_text': str((row.qr_payload or {}).get('qr_text') or ''),
                'copy_paste': str((row.qr_payload or {}).get('copy_paste') or ''),
                'qr_base64': str((row.qr_payload or {}).get('qr_base64') or ''),
                'created_at': str((row.qr_payload or {}).get('created_at') or ''),
                'posted': bool(row.posted),
                'paid_at': (row.paid_at.isoformat(timespec='seconds')
                            if getattr(row, 'paid_at', None) else ''),
            } for row in asaas_rows
        }
    return make_backup(payload, allow_empty=allow_empty)


def load_files(directory):
    directory = Path(directory)
    def rows(name):
        path = directory / name
        return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()] if path.exists() else []
    payload = {"runtime:books": {"postings": rows('books.jsonl')},
               "runtime:rounds": {"rows": rows('rounds.jsonl')}}
    for name, filename in (("promos", "promos.json"), ("crash_pending", "crash_pending.json"),
                           ("crypto_charges", "crypto_charges.json"),
                           ("asaas_charges", "asaas_charges.json")):
        path = directory / filename
        if path.exists():
            payload[name] = json.loads(path.read_text(encoding='utf-8'))
    backup = {"format": 1, "payload": payload, "sha256": digest(payload)}
    validate(backup)
    return backup


def restore_wallet(factory, backup):
    from sqlalchemy import inspect, select
    from demo.models import AsaasCharge, IdentityDocument
    payload = validate(backup)
    with factory.begin() as db:
        if db.scalar(select(IdentityDocument.name).where(IdentityDocument.name.in_(NAMES)).limit(1)):
            raise ValueError("destination already has wallet documents; restore refused")
        has_asaas_table = inspect(db.bind).has_table('asaas_charges')
        if has_asaas_table and db.scalar(select(AsaasCharge.deposit_id).limit(1)):
            raise ValueError('destination already has Asaas charges; restore refused')
        documents = {name: data for name, data in payload.items() if name != 'asaas_charges'}
        db.add_all(IdentityDocument(name=name, data=deepcopy(data), revision=0)
                   for name, data in documents.items())
        if not has_asaas_table:
            if payload.get('asaas_charges'):
                raise ValueError('destination has no asaas_charges table; restore refused')
            return
        for reference, row in (payload.get('asaas_charges') or {}).items():
            paid_at = str(row.get('paid_at') or '')
            db.add(AsaasCharge(
                deposit_id=reference,
                player=str(row.get('player') or ''),
                amount_minor=int(row.get('amount_minor') or 0),
                provider_ref=str(row.get('provider_ref') or ''),
                provider_status=str(row.get('provider_status') or ''),
                qr_payload={
                    'qr_text': str(row.get('qr_text') or ''),
                    'copy_paste': str(row.get('copy_paste') or ''),
                    'qr_base64': str(row.get('qr_base64') or ''),
                    'created_at': str(row.get('created_at') or ''),
                },
                posted=bool(row.get('posted')),
                paid_at=(datetime.fromisoformat(paid_at)
                         if paid_at else None),
            ))


def write_backup(target, backup):
    """Backups can contain publisher bearer tokens; create them privately."""
    validate(backup)
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
        json.dump(backup, output, ensure_ascii=False)
        output.flush()
        os.fsync(output.fileno())
    validate(json.loads(target.read_text(encoding='utf-8')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--backup")
    action.add_argument("--restore")
    action.add_argument("--check")
    action.add_argument("--import-files", help="explicit legacy JSONL cutover into an empty destination")
    args = parser.parse_args()
    if args.check:
        payload = validate(json.loads(Path(args.check).read_text(encoding="utf-8")))
        print("Backup valid:", len(payload["runtime:books"]["postings"]), "balanced postings")
        return
    from demo.db import database_url, make_engine, make_session_factory
    engine = make_engine(database_url())
    try:
        factory = make_session_factory(engine)
        if args.backup:
            backup = export_wallet(factory)
            target = Path(args.backup)
            write_backup(target, backup)
            print("Wallet backup created; checksum verified")
        else:
            backup = load_files(args.import_files) if args.import_files else json.loads(Path(args.restore).read_text(encoding="utf-8"))
            restore_wallet(factory, backup)
            print("Restored validated wallet into empty destination")
    except Exception as exc:
        raise SystemExit("Backup operation failed (" + type(exc).__name__ + "); no credentials logged") from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
