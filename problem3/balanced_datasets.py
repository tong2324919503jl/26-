"""Dataset gateway: use the current local generator and read historical manifests."""
from __future__ import annotations

import json
from pathlib import Path

from problem3 import balanced_scenarios as _legacy
from problem3 import normal_scenarios as _default

DATASET = _default.DATASET
DEFAULT_PER_COUNT = _default.DEFAULT_PER_COUNT
SOURCE_COUNTS = _default.SOURCE_COUNTS
PROVENANCE = _default.PROVENANCE
ROOT = Path(__file__).resolve().parents[1]


def dataset_directory(problem: int, path: str | Path | None = None) -> Path:
    """Use the new default; retain each problem's relative-path convention."""
    return _default.dataset_directory(problem, path)


def _backend(problem: int, path: str | Path | None = None):
    directory = dataset_directory(problem, path)
    manifest_path = directory / 'manifest.json'
    if not manifest_path.exists():
        return _default, directory
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid dataset manifest') from exc
    if not isinstance(manifest, dict):
        raise ValueError('Invalid dataset manifest')
    name = manifest.get('dataset')
    backends = {_default.DATASET: _default, _legacy.DATASET: _legacy}
    if name not in backends:
        raise ValueError(f'Unsupported dataset version: {name}')
    return backends[name], directory


def load_cases(problem: int, path: str | Path | None = None) -> list[dict]:
    """Select the validator from manifest.dataset, then check all cases."""
    backend, directory = _backend(problem, path)
    return backend.load_cases(problem, directory)


load_suite = load_cases


def validate_dataset(problem: int, path: str | Path | None = None) -> dict:
    backend, directory = _backend(problem, path)
    return backend.validate_dataset(problem, directory)


def prepare_dataset(problem: int, per_count: int = DEFAULT_PER_COUNT,
                    path: str | Path | None = None) -> dict:
    """Create the current version or verify an explicitly selected existing one."""
    backend, directory = _backend(problem, path)
    return backend.prepare_dataset(problem, per_count, directory)
