"""Reproducible source-count-balanced local cases; no solver or network calls.

Every source count uses the same sampling model.  These cases are not an
official test set and are not divided into difficulty levels or train/test
splits.  Only an external runner may read case truth and metadata; a policy
must continue to receive its ObservationClient facade.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
DATASET = 'balanced_v1'
PROVENANCE = 'self_constructed_not_official'
SOURCE_COUNTS = tuple(range(10, 17))
DEFAULT_PER_COUNT = 714
SEED_CAPACITY = 1_000_000
SEED_BASE = 6_000_000_000
PROBLEM_SEED_STRIDE = 100_000_000
SCHEMA_VERSION = 1


def _validate_problem(problem: int) -> None:
    if type(problem) is not int or problem not in (3, 4):
        raise ValueError('problem must be the integer 3 or 4')


def _validate_per_count(per_count: int) -> None:
    if type(per_count) is not int or not 1 <= per_count <= SEED_CAPACITY:
        raise ValueError(f'per_count must be an integer in [1, {SEED_CAPACITY}]')


def case_seed(problem: int, source_count: int, index: int = 0) -> int:
    """Each problem and source count owns a new, disjoint million-seed range."""
    _validate_problem(problem)
    if type(source_count) is not int or source_count not in SOURCE_COUNTS:
        raise ValueError('source_count must be an integer in [10, 16]')
    if type(index) is not int or not 0 <= index < SEED_CAPACITY:
        raise ValueError(f'index must be an integer in [0, {SEED_CAPACITY})')
    return (SEED_BASE + problem * PROBLEM_SEED_STRIDE
            + (source_count - SOURCE_COUNTS[0]) * SEED_CAPACITY + index)


def generate_case(problem: int, source_count: int, index: int = 0) -> dict:
    """Build a single case without changing Python's shared random state."""
    seed = case_seed(problem, source_count, index)
    rng = random.Random(seed)
    channels = rng.sample(range(1, 21), source_count)
    directional_indices = (set(rng.sample(range(source_count),
                                          rng.randint(1, source_count - 1)))
                           if problem == 4 else set())
    sources = []
    for j, channel in enumerate(channels):
        angle = rng.uniform(0, 2 * math.pi)
        distance = 1800 * math.sqrt(rng.random())
        sources.append(dict(
            channel=channel,
            x=distance * math.cos(angle),
            y=distance * math.sin(angle),
            radius=rng.uniform(1000, 1500),
            orientation_deg=(rng.uniform(0, 360)
                             if j in directional_indices else None),
        ))
    return dict(
        case_id=f'local_p{problem}_{DATASET}_n{source_count}_{index:06d}',
        problem=problem,
        dataset=DATASET,
        provenance=PROVENANCE,
        seed=seed,
        source_count=source_count,
        noise='hash_uniform',
        sources=sources,
    )


def iter_cases(problem: int, per_count: int = DEFAULT_PER_COUNT) -> Iterator[dict]:
    """Interleave counts 10..16, so every complete seven-case block is balanced."""
    _validate_problem(problem)
    _validate_per_count(per_count)
    return (generate_case(problem, n, index)
            for index in range(per_count) for n in SOURCE_COUNTS)


def dataset_directory(problem: int, path: str | Path | None = None) -> Path:
    """Resolve custom relative paths under the corresponding problem directory."""
    _validate_problem(problem)
    if path is None:
        return ROOT / f'problem{problem}' / 'examples' / DATASET
    supplied = Path(path)
    if not supplied.is_absolute():
        supplied = ROOT / f'problem{problem}' / supplied
    if supplied.name == 'cases.jsonl':
        supplied = supplied.parent
    return supplied.resolve()


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _generator_sha256() -> str:
    # Normalize source newlines, so Git's checkout convention does not change
    # the generator fingerprint.  The dataset itself is written as LF bytes.
    return _sha256(Path(__file__).read_text(encoding='utf-8').encode('utf-8'))


def _manifest(problem: int, per_count: int, cases_bytes: bytes) -> dict:
    return dict(
        schema_version=SCHEMA_VERSION,
        dataset=DATASET,
        problem=problem,
        provenance=PROVENANCE,
        total_cases=len(SOURCE_COUNTS) * per_count,
        per_count=per_count,
        counts_by_source_count={str(n): per_count for n in SOURCE_COUNTS},
        cases_file='cases.jsonl',
        cases_sha256=_sha256(cases_bytes),
        generator_file='problem3/balanced_scenarios.py',
        generator_sha256=_generator_sha256(),
        sampling={
            'source_count': '10至16源，每种源数的样例数量完全相同。',
            'position': '各源独立按面积均匀分布于半径1800米的目标圆内。',
            'receiving_radius': '各源接收半径独立服从[1000,1500]米均匀分布。',
            'channel': '从1至20频道中无放回均匀抽取，每源占用独立频道。',
            'source_type': ('全部为全向源。' if problem == 3 else
                            '定向源数量在1至N-1中离散均匀抽取，再等概率选择对应源；其余为全向源。'),
            'orientation': ('不适用。' if problem == 3 else
                            '各定向源朝向独立服从[0,360)度均匀分布。'),
            'bearing_error': 'hash_uniform：误差由样例种子、频道及观测位置固定，在正负1度内；模拟读数保留两位小数。',
            'ordering': '每轮依次输出10至16源，完成一轮后增加该源数内的样例序号。',
            'scope': '自建本地样例；不划分数据子集或难度等级；各源数采用相同抽样分布。',
        },
        seed_ranges={str(n): dict(
            first=case_seed(problem, n, 0),
            last=case_seed(problem, n, per_count - 1),
            reserved_last=case_seed(problem, n, SEED_CAPACITY - 1),
        ) for n in SOURCE_COUNTS},
    )


def _validate_case(case: dict, problem: int, n: int, index: int) -> None:
    # Canonical bytes also reject bool/int or int/float substitutions that
    # Python dictionary equality alone treats as equal.
    if (not isinstance(case, dict)
            or _canonical_json(case) != _canonical_json(generate_case(problem, n, index))):
        raise ValueError(f'Case differs from reproducible generator: n={n}, index={index}')
    sources = case['sources']
    if len(sources) != n or len({s['channel'] for s in sources}) != n:
        raise ValueError('Invalid source count or duplicate channel')
    for source in sources:
        x, y, radius = source['x'], source['y'], source['radius']
        if not all(math.isfinite(v) for v in (x, y, radius)):
            raise ValueError('Non-finite source parameter')
        if math.hypot(x, y) > 1800 + 1e-9 or not 1000 <= radius <= 1500:
            raise ValueError('Source position or receiving radius is outside constraints')
        orientation = source['orientation_deg']
        if orientation is not None and not 0 <= orientation < 360:
            raise ValueError('Invalid directional orientation')
    directional = sum(s['orientation_deg'] is not None for s in sources)
    if (problem == 3 and directional != 0
            or problem == 4 and not 1 <= directional < n):
        raise ValueError('Invalid mixture of source types')


def _load_validated(problem: int, path: str | Path | None) -> tuple[list[dict], dict]:
    directory = dataset_directory(problem, path)
    cases_path = directory / 'cases.jsonl'
    manifest_path = directory / 'manifest.json'
    try:
        cases_bytes = cases_path.read_bytes()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Missing or unreadable dataset in {directory}: {exc}') from exc
    if not isinstance(manifest, dict):
        raise ValueError('Invalid manifest object')
    per_count = manifest.get('per_count')
    _validate_per_count(per_count)
    expected_manifest = _manifest(problem, per_count, cases_bytes)
    if manifest != expected_manifest:
        raise ValueError('Dataset manifest, file checksum or generator fingerprint mismatch')
    if not cases_bytes.endswith(b'\n') or b'\r' in cases_bytes:
        raise ValueError('Dataset must use LF lines with a final newline')
    lines = cases_bytes.splitlines()
    if len(lines) != per_count * len(SOURCE_COUNTS):
        raise ValueError('Dataset has an unexpected number of cases')
    cases, ids, seeds, contents = [], set(), set(), set()
    counts: Counter[int] = Counter()
    for position, line in enumerate(lines):
        try:
            case = json.loads(line)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f'Invalid JSON at line {position + 1}') from exc
        n = SOURCE_COUNTS[position % len(SOURCE_COUNTS)]
        index = position // len(SOURCE_COUNTS)
        _validate_case(case, problem, n, index)
        if line != _canonical_json(case):
            raise ValueError(f'Non-canonical JSON at line {position + 1}')
        content = _sha256(_canonical_json(case['sources']))
        if case['case_id'] in ids or case['seed'] in seeds or content in contents:
            raise ValueError('Duplicate case identifier, seed or source configuration')
        ids.add(case['case_id'])
        seeds.add(case['seed'])
        contents.add(content)
        counts[n] += 1
        cases.append(case)
    if dict(counts) != {n: per_count for n in SOURCE_COUNTS}:
        raise ValueError('Unbalanced source-count distribution')
    return cases, manifest


def load_cases(problem: int, path: str | Path | None = None) -> list[dict]:
    """Load all records only after integrity and full constraint validation."""
    return _load_validated(problem, path)[0]


load_suite = load_cases


def validate_dataset(problem: int, path: str | Path | None = None) -> dict:
    """Check every record, hashes, reproduction, balance and uniqueness."""
    return _load_validated(problem, path)[1]


def prepare_dataset(problem: int, per_count: int = DEFAULT_PER_COUNT,
                    path: str | Path | None = None) -> dict:
    """Create files once, or validate existing files; never silently overwrite."""
    _validate_problem(problem)
    _validate_per_count(per_count)
    directory = dataset_directory(problem, path)
    cases_path = directory / 'cases.jsonl'
    manifest_path = directory / 'manifest.json'
    if cases_path.exists() or manifest_path.exists():
        manifest = validate_dataset(problem, directory)
        if manifest['per_count'] != per_count:
            raise ValueError('Existing dataset uses a different per_count; choose a new directory')
        return manifest
    cases_bytes = b''.join(_canonical_json(case) + b'\n'
                           for case in iter_cases(problem, per_count))
    manifest = _manifest(problem, per_count, cases_bytes)
    directory.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also prevents an accidental overwrite between the
    # existence check and write.  An interrupted partial pair is rejected above.
    with cases_path.open('xb') as stream:
        stream.write(cases_bytes)
    with manifest_path.open('xb') as stream:
        stream.write(json.dumps(manifest, ensure_ascii=False, indent=2,
                                allow_nan=False).encode('utf-8') + b'\n')
    return validate_dataset(problem, directory)
