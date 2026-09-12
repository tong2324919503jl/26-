"""Verify the migrated practice source and matched public action trajectories.

No network, shared 7000-case data, or parameter selection is used. The package
and repository policies run in separate read-only workers receiving replies only.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RECORDS = ROOT / 'validation/practice_v5'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def package_files():
    manifest = json.loads((RECORDS / 'integration_manifest.json').read_text(encoding='utf-8'))
    archive = ROOT / manifest['archive']
    if digest(archive.read_bytes()) != manifest['archive_sha256']:
        raise ValueError('Practice archive fingerprint changed')
    files = {}
    with zipfile.ZipFile(archive) as stream:
        for item in stream.infolist():
            if item.is_dir():
                continue
            name = item.filename
            if not item.flag_bits & 0x800:
                name = name.encode('cp437').decode('gbk')
            parts = name.replace('\\', '/').split('/')[1:]
            if not parts or any(p in ('', '.', '..') or ':' in p for p in parts):
                raise ValueError('Unsafe package path')
            files['/'.join(parts)] = stream.read(item)
    source = json.loads(files['source_manifest.json'])
    for name, expected in source['copied_files_sha256'].items():
        if digest(files[name]) != expected:
            raise ValueError(f'Package source mismatch: {name}')
    for name, row in json.loads(files['package_manifest.json'])['files'].items():
        if digest(files[name]) != row['sha256'] or len(files[name]) != row['bytes']:
            raise ValueError(f'Package file mismatch: {name}')
    return manifest, source, files


def verify_source():
    manifest, source, files = package_files()
    mapping = manifest['module_mapping']
    modules = {a[:-3].replace('/', '.'): b[:-3].replace('/', '.') for a, b in mapping.items()}
    checked = []
    for src, dst in mapping.items():
        original = ast.parse(files[src].decode('utf-8-sig'))
        for node in ast.walk(original):
            if isinstance(node, ast.ImportFrom) and node.module in modules:
                node.module = modules[node.module]
        actual = ast.parse((ROOT / dst).read_text(encoding='utf-8-sig'))
        if ast.dump(original) != ast.dump(actual):
            raise AssertionError(f'Algorithm differs beyond import renaming: {dst}')
        checked.append(dst)
    for name in source['copied_files_sha256']:
        if name.startswith('experiments_v5/'):
            continue
        # Existing Git checkouts may have CRLF, while the source archive has LF.
        if (ROOT / name).read_bytes().replace(b'\r\n', b'\n') != files[name].replace(b'\r\n', b'\n'):
            raise AssertionError(f'Shared source or certificate changed: {name}')
        checked.append(name)
    return {'files_checked': len(checked), 'paths': checked,
            'comparison': 'AST after ImportFrom renaming; shared files byte-equal after LF normalization'}


class TraceWorker:
    def __init__(self, worker):
        self.worker = worker
        self.actions = []

    def write(self, value):
        self.worker.write(value)

    def read(self):
        value = self.worker.read()
        if value.get('type') == 'action':
            self.actions.append(value)
        return value


def verify_trajectories():
    from scripts.compare_teammate_p34 import Worker, episode
    from problem3.scenarios import SPLITS, generate_case
    manifest, _, files = package_files()
    rows = []
    # Reuse the package's already-used startup training source, never the 7000 set.
    old = SPLITS.get('train_v5')
    SPLITS['train_v5'] = (257000003, 384)
    try:
        with tempfile.TemporaryDirectory(prefix='practice-v5-verify-') as temporary:
            extracted = Path(temporary).resolve()
            for name, data in files.items():
                if not (name.endswith('.py') or name.endswith('.json')):
                    continue
                target = (extracted / name).resolve()
                if not target.is_relative_to(extracted):
                    raise ValueError('Package extraction escaped the temporary directory')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
            for problem in (3, 4):
                (extracted / f'problem{problem}/verification_candidate.py').write_text(
                    f'from experiments_v5.p{problem}_candidate import SearchPolicy\n', encoding='utf-8')
                original = Worker('ours', extracted, problem, f'problem{problem}.verification_candidate:SearchPolicy')
                try:
                    migrated = Worker('ours', ROOT, problem, f'problem{problem}.current_policy:SearchPolicy')
                    try:
                        for index in (0, 2, 6):
                            case = generate_case(problem, index, 'train_v5')
                            first, second = TraceWorker(original), TraceWorker(migrated)
                            a = episode(first, case, problem, {})
                            b = episode(second, case, problem, {})
                            if first.actions != second.actions or a['policy'] != b['policy']:
                                raise AssertionError(f'Package trajectory differs: p{problem}, training index {index}')
                            if not a['certified_full_clear'] or not b['certified_full_clear']:
                                raise AssertionError(f'Full-clear audit failed: p{problem}, index {index}')
                            if a['virtual_time_s'] != b['virtual_time_s']:
                                raise AssertionError('Physical cost changed')
                            rows.append({'problem': problem, 'training_index': index,
                                'algorithm_version': manifest['algorithm_versions'][str(problem)],
                                'action_count': len(first.actions),
                                'action_sha256': digest(json.dumps(first.actions, sort_keys=True).encode()),
                                'identical_actions_and_policy': True,
                                'certified_full_clear': True, 'source_count': a['source_count'],
                                'virtual_time_s': a['virtual_time_s']})
                            print(f'P{problem} training index {index}: identical actions and certified full clear', flush=True)
                    finally:
                        migrated.close()
                finally:
                    original.close()
    finally:
        if old is None:
            del SPLITS['train_v5']
        else:
            SPLITS['train_v5'] = old
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-only', action='store_true')
    args = parser.parse_args()
    source = verify_source()
    if args.source_only:
        print(json.dumps(source, indent=2))
        return 0
    import numpy
    rows = verify_trajectories()
    report = {'verified_at_utc': datetime.now(timezone.utc).isoformat(), 'passed': True,
        'python': sys.version.split()[0], 'numpy': numpy.__version__, 'source': source,
        'scope': 'Source migration and six matched local training cases; no 7000-case rerun or official calls',
        'official_platform_calls': 0, 'paired_cases': rows}
    (RECORDS / 'integration_verification.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
