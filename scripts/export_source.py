"""Export current Git-visible source, including uncommitted/untracked files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {'.git', 'node_modules', '__pycache__', '.next', 'out', '.venv',
             'venv', '.vercel', '.wrangler', '.aws', '.ssh', '.tmp',
             '.impeccable', '.taste-skill'}


def include(name):
    path = Path(name)
    if any(part in SKIP_DIRS for part in path.parts):
        return False
    if name.startswith(('demo/data/', 'design/auteur/qa/')):
        return False
    leaf = path.name.lower()
    if leaf.startswith('.env') and leaf not in {'.env.example', '.env.template'}:
        return False
    return not (leaf in {'.npmrc', '.netrc', 'credentials', 'id_rsa', 'id_ed25519'}
                or leaf.endswith(('.pem', '.key', '.p12', '.pfx', '.zip', '.tar.gz',
                                  '.pyc', '.sqlite', '.sqlite3', '.db')))


def export(root, destination):
    root, destination = root.resolve(), destination.resolve()
    if destination.is_relative_to(root):
        raise ValueError('Choose an output path outside the project tree')
    names = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
        cwd=root).decode('utf-8').split('\0')
    manifest = {}
    # Exclusive creation protects previous exports from being overwritten.
    with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(filter(None, names))):
            path = root / name
            if not include(name) or not path.is_file():
                continue
            if any(parent.is_symlink() for parent in [path, *path.parents]
                   if parent != root and parent.is_relative_to(root)):
                continue
            data = path.read_bytes()
            info = zipfile.ZipInfo.from_file(path, 'operator/' + name)
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
            manifest[name] = hashlib.sha256(data).hexdigest()
        archive.writestr('SOURCE-MANIFEST.json', json.dumps({
            'format': 1, 'files': manifest,
            'scope': 'Current source files; excludes credentials, runtime data, dependencies and selected generated artifacts. Not a database or Git-history backup.'
        }, indent=2) + '\n')
    with zipfile.ZipFile(destination) as archive:
        for name, digest in manifest.items():
            if hashlib.sha256(archive.read('operator/' + name)).hexdigest() != digest:
                raise ValueError('Archive verification failed: ' + name)
    return len(manifest)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='New ZIP path outside the project')
    args = parser.parse_args()
    print(f'Exported and hash-verified {export(ROOT, args.output)} source files to {args.output}')
