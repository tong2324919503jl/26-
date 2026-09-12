"""Balanced local cases with a predefined, truncated-normal construction score.

The score changes physical geometry and visibility.  It is not an observed
solver difficulty, and implies neither normal solving times nor monotonic
performance.  Cases and audit metadata stay outside the policy process.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
from typing import Iterator


ROOT = Path(__file__).resolve().parents[1]
DATASET = 'balanced_normal_v2'
PROVENANCE = 'self_constructed_not_official'
SOURCE_COUNTS = tuple(range(10, 17))
DEFAULT_PER_COUNT = 1000
SEED_BASE = 7_000_000_000
PROBLEM_SEED_STRIDE = 100_000_000
SEED_BLOCK = 1_000_000
SEED_CAPACITY = SEED_BLOCK - 1  # The last seed in a block shuffles score ranks.
SCHEMA_VERSION = 2
NORMAL = statistics.NormalDist()
LOWER_CDF, UPPER_CDF = NORMAL.cdf(-3), NORMAL.cdf(3)
DIFFICULTY_BANDS = ('z_lt_minus1', 'minus1_le_z_le_1', 'z_gt_1')


def _validate_problem(problem: int) -> None:
    if type(problem) is not int or problem not in (3, 4):
        raise ValueError('problem must be the integer 3 or 4')


def _validate_per_count(per_count: int) -> None:
    if type(per_count) is not int or not 1 <= per_count <= SEED_CAPACITY:
        raise ValueError(f'per_count must be an integer in [1, {SEED_CAPACITY}]')


def _seed_start(problem: int, source_count: int) -> int:
    _validate_problem(problem)
    if type(source_count) is not int or source_count not in SOURCE_COUNTS:
        raise ValueError('source_count must be an integer in [10, 16]')
    return SEED_BASE + problem * PROBLEM_SEED_STRIDE + (source_count - 10) * SEED_BLOCK


def case_seed(problem: int, source_count: int, index: int = 0) -> int:
    first = _seed_start(problem, source_count)
    if type(index) is not int or not 0 <= index < SEED_CAPACITY:
        raise ValueError(f'index must be an integer in [0, {SEED_CAPACITY})')
    return first + index


@lru_cache(maxsize=32)
def difficulty_quantiles(per_count: int = DEFAULT_PER_COUNT) -> tuple[float, ...]:
    """Use midpoint quantiles, without clipping or rejection-sampling artifacts."""
    _validate_per_count(per_count)
    return tuple(round(NORMAL.inv_cdf(LOWER_CDF + (k + .5) / per_count * (UPPER_CDF - LOWER_CDF)), 12)
                 for k in range(per_count))


@lru_cache(maxsize=128)
def _difficulty_order(problem: int, source_count: int, per_count: int) -> tuple[int, ...]:
    _validate_per_count(per_count)
    order = list(range(per_count))
    random.Random(_seed_start(problem, source_count) + SEED_BLOCK - 1).shuffle(order)
    return tuple(order)


def _physical_sources(problem: int, n: int, seed: int, score: float) -> list[dict]:
    """Use fixed latent draws so increasing score preserves physical directions.

    Positions expand by a common scale, receiving radii shrink, directional
    sources form nested subsets, and their directions only switch in-to-out.
    These are construction properties, not a claim about any solver's cost.
    """
    if (isinstance(score, bool) or not isinstance(score, (int, float))
            or not math.isfinite(score) or not 0 <= score <= 1):
        raise ValueError('score must be a finite number in [0, 1]')
    rng = random.Random(seed)
    channels = rng.sample(range(1, 21), n)
    latent = [(rng.random(), rng.random(), rng.random(), rng.random(), rng.random())
              for _ in channels]
    count_draw = rng.random()
    ranking = rng.sample(range(n), n)
    count = min(n - 1, 1 + math.floor((n - 2) * score + count_draw)) if problem == 4 else 0
    directional = set(ranking[:count])
    support_radius = 900 + 900 * score
    sources = []
    for j, (channel, values) in enumerate(zip(channels, latent)):
        radial_u, angular_u, radius_u, outward_u, jitter_u = values
        angle = math.tau * angular_u
        distance = support_radius * math.sqrt(radial_u)
        orientation = None
        if j in directional:
            deviation = 0 if outward_u < score else 180
            orientation = round((math.degrees(angle) + deviation + 180 * jitter_u - 90) % 360, 9) % 360
        sources.append(dict(channel=channel, x=round(distance * math.cos(angle), 9),
                            y=round(distance * math.sin(angle), 9),
                            radius=round(1350 - 350 * score + 150 * radius_u, 9),
                            orientation_deg=orientation))
    return sources


def generate_case(problem: int, source_count: int, index: int = 0,
                  *, per_count: int = DEFAULT_PER_COUNT) -> dict:
    seed = case_seed(problem, source_count, index)
    _validate_per_count(per_count)
    if index >= per_count:
        raise ValueError('index must be smaller than per_count')
    rank = _difficulty_order(problem, source_count, per_count)[index]
    z = difficulty_quantiles(per_count)[rank]
    score = round((z + 3) / 6, 12)
    return dict(case_id=f'local_p{problem}_{DATASET}_n{source_count}_{index:06d}',
                problem=problem, dataset=DATASET, provenance=PROVENANCE,
                seed=seed, source_count=source_count, noise='hash_uniform',
                construction_difficulty=dict(z=z, score=score, quantile_index=rank,
                                             quantile_count=per_count),
                sources=_physical_sources(problem, source_count, seed, score))


def iter_cases(problem: int, per_count: int = DEFAULT_PER_COUNT) -> Iterator[dict]:
    _validate_problem(problem)
    _validate_per_count(per_count)
    return (generate_case(problem, n, index, per_count=per_count)
            for index in range(per_count) for n in SOURCE_COUNTS)


def dataset_directory(problem: int, path: str | Path | None = None) -> Path:
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


def _pretty_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8') + b'\n'


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    location = (len(ordered) - 1) * probability
    lower, upper = math.floor(location), math.ceil(location)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (location - lower)


def _summary(values: list[float]) -> dict:
    return dict(mean=statistics.mean(values), population_std=statistics.pstdev(values),
                minimum=min(values), maximum=max(values),
                quantiles={str(p): _quantile(values, p) for p in (.05, .25, .5, .75, .95)})


def _band(z: float) -> str:
    return DIFFICULTY_BANDS[0 if z < -1 else (2 if z > 1 else 1)]


def origin_receiving_distance(source: dict) -> float:
    """Exact distance from origin to a source's closed receiving disk/half-disk."""
    x, y, radius = source['x'], source['y'], source['radius']
    orientation = source['orientation_deg']
    if orientation is None:
        return max(0., math.hypot(x, y) - radius)
    angle = math.radians(orientation)
    a = -x * math.cos(angle) - y * math.sin(angle)
    b = x * math.sin(angle) - y * math.cos(angle)
    if a >= 0:
        return max(0., math.hypot(x, y) - radius)
    return math.hypot(a, max(0., abs(b) - radius))


def source_mst_length(sources: list[dict]) -> float:
    """Euclidean MST of the origin and source locations, for external audit only."""
    points = [(0., 0.)] + [(s['x'], s['y']) for s in sources]
    visited = [False] * len(points)
    nearest = [math.inf] * len(points)
    nearest[0] = 0.
    total = 0.
    for _ in points:
        j = min((i for i in range(len(points)) if not visited[i]), key=nearest.__getitem__)
        total += nearest[j]
        visited[j] = True
        for i, point in enumerate(points):
            if not visited[i]:
                nearest[i] = min(nearest[i], math.dist(points[j], point))
    return total


def _geometry(case: dict) -> dict:
    sources, n = case['sources'], case['source_count']
    directional = [s for s in sources if s['orientation_deg'] is not None]
    result = dict(
        mean_source_distance_from_origin_m=statistics.mean(math.hypot(s['x'], s['y']) for s in sources),
        mean_receiving_radius_m=statistics.mean(s['radius'] for s in sources),
        mean_pairwise_source_distance_m=statistics.mean(
            math.hypot(a['x'] - b['x'], a['y'] - b['y'])
            for i, a in enumerate(sources) for b in sources[i + 1:]),
        source_mst_m_per_source=source_mst_length(sources) / n,
        mean_origin_to_receiving_region_m=statistics.mean(origin_receiving_distance(s) for s in sources),
        directional_fraction=len(directional) / n,
    )
    if directional:
        alignment = [math.cos(math.radians(s['orientation_deg']) - math.atan2(s['y'], s['x']))
                     for s in directional]
        result['directional_outward_fraction'] = statistics.mean(v > 0 for v in alignment)
        result['directional_mean_outward_cosine'] = statistics.mean(alignment)
    return result


def _pearson(left: list[float], right: list[float]) -> float | None:
    a, b = statistics.mean(left), statistics.mean(right)
    numerator = sum((x - a) * (y - b) for x, y in zip(left, right))
    denominator = math.sqrt(sum((x - a) ** 2 for x in left) * sum((y - b) ** 2 for y in right))
    return numerator / denominator if denominator else None


def _ranks(values: list[float]) -> list[float]:
    indices = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.] * len(values)
    start = 0
    while start < len(indices):
        end = start + 1
        while end < len(indices) and values[indices[end]] == values[indices[start]]:
            end += 1
        for i in indices[start:end]:
            ranks[i] = (start + end - 1) / 2
        start = end
    return ranks


def _round_audit(value):
    """Keep summary fingerprints insensitive to insignificant libm last bits."""
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, dict):
        return {key: _round_audit(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_round_audit(item) for item in value]
    return value


def _distribution(problem: int, cases: list[dict]) -> dict:
    groups = {}
    for n in SOURCE_COUNTS:
        group = sorted((c for c in cases if c['source_count'] == n),
                       key=lambda c: c['construction_difficulty']['score'])
        scores = [c['construction_difficulty']['score'] for c in group]
        zs = [c['construction_difficulty']['z'] for c in group]
        geometry = [_geometry(c) for c in group]
        names = tuple(geometry[0])
        bins = []
        for k in range(10):
            begin, end = len(group) * k // 10, len(group) * (k + 1) // 10
            if begin == end:
                continue
            bins.append(dict(bin=k + 1, case_count=end - begin,
                             score_min=scores[begin], score_max=scores[end - 1],
                             score_mean=statistics.mean(scores[begin:end]),
                             mean_geometry={name: statistics.mean(g[name] for g in geometry[begin:end])
                                            for name in names}))
        groups[str(n)] = dict(
            case_count=len(group), score=_summary(scores), z=_summary(zs),
            interval_counts={band: sum(_band(z) == band for z in zs) for band in DIFFICULTY_BANDS},
            geometry={name: _summary([g[name] for g in geometry]) for name in names},
            equal_frequency_score_bins=bins,
            score_correlations={name: dict(
                pearson=_pearson(scores, [g[name] for g in geometry]),
                spearman=_pearson(_ranks(scores), _ranks([g[name] for g in geometry])),
            ) for name in names})
    return _round_audit(dict(
        schema_version=1, problem=problem, dataset=DATASET, provenance=PROVENANCE,
        scope='External construction audit only; no solver outcomes, no official results.',
        quantile_rule='z_k = Phi^-1(Phi(-3) + (k+0.5)/m * (Phi(3)-Phi(-3))); d=(z_k+3)/6',
        interpretation={
            'score': '预定义连续构造难度；不是已验证的求解难度，也不保证求解耗时正态或逐例单调。',
            'source_mst_m_per_source': '原点与所有源位置的欧氏最小生成树长度除以源数，仅为空间分散代理；不是清除路程的严格下界。',
            'mean_origin_to_receiving_region_m': '原点到每个源可收信圆盘或半圆盘的精确最短距离，再对源求平均；仅为观测接近负担代理。',
            'correlations': '只在同一问题、同一源数内计算，Pearson与采用平均秩的Spearman；常量向量相关系数为null。',
            'bins': '连续分数的十个等频统计箱，不是独立数据集或算法评价等级。',
        },
        audit_decimal_places=9, by_source_count=groups,
    ))


def _readme(problem: int, per_count: int) -> bytes:
    zs = difficulty_quantiles(per_count)
    counts = [sum(_band(z) == band for z in zs) for band in DIFFICULTY_BANDS]
    text = f'''# 问题{problem}：正态形状构造难度的均衡本地样例

本目录为自建本地样例，非官方演练或正式测试。共{per_count * 7}例，10至16源各{per_count}例，不划分开发/留出/压力集合。

## 连续构造难度

令m={per_count}，k=0,...,m-1，Phi为标准正态分布函数：

- z_k = Phi^(-1)(Phi(-3) + (k+0.5)/m × (Phi(3)-Phi(-3)))。
- d_k = (z_k+3)/6；每种源数使用全部m个等概率分位点，独立固定种子打乱次序。
- z小于-1、介于-1至1、超过1的样例分别为{counts[0]}、{counts[1]}、{counts[2]}例。它们仅用于分布统计，不另分数据集合。

这里的难度是**预定义构造参数**，会改变物理场景；不保证未定稿solve的实际耗时呈正态分布，也不保证逐例耗时随d单调。结果不得写成已通过算法验证的简单/中等/困难等级。

## 物理采样公式

各源独立抽取u_r、u_theta、u_R、u_out、u_jitter，均服从[0,1)均匀分布。

- 位置支撑半径L(d)=900+900d米；源位置r=L(d)√u_r，theta=2πu_theta，再转为直角坐标。因此每个d下按面积均匀采样，所有源始终位于1800米目标圆内。
- 接收半径R=1350-350d+150u_R米，始终在1000至1500米内。
- 从1至20频道无放回均匀抽取N个，每源独占一个频道。问题三所有源全向。
- 问题四定向数K=1+floor((N-2)d+u_K)，其中u_K独立均匀抽取；固定随机排列的前K源为定向，其余全向，保证1≤K≤N-1。
- 定向源以概率d朝外、1-d朝内：phi=theta的角度值+[u_out<d时取0°，否则取180°]+(180u_jitter-90)°，最终化为[0,360)度。两个半圆先验覆盖所有相对朝向，包含接近切向的朝向；朝向使用源位置的径向方向作为基准。
- 方位误差采用hash_uniform，由样例种子、频道与检测位置固定，范围为正负1度，模拟读数保留两位小数；同位置复测不会降低误差。

对同一组潜在随机数，增大d会等比例放大源位置与两两距离，减小接收半径，使定向源数量不降，并使既有定向源只可能从朝内切换为朝外。这些构造属性不能代替实际算法表现评估。

最终位置、接收半径和朝向保留9位小数，z和d保留12位，外部审计统计保留9位，以减少跨机器浮点末位差异。上述构造关系以未舍入公式为准。

中等构造分数d约0.5时，位置支撑半径约1350米，小于旧balanced_v1的1800米。两个版本的样例分布不同；跨样例池的耗时均值差异不能当作算法提升，算法比较须在同一固定样例池上进行。

## 文件与核验

- cases.jsonl：每轮依次排列10至16源。每条包含construction_difficulty连续分数及源真值，仅供生成、批测调度和事后统计，策略进程不接收这些字段。
- manifest.json：文件哈希、生成器指纹、样例数量、独立种子范围、分布公式及各源数汇总。
- distribution.json：在每个固定源数内，记录分数分布、几何统计、十等频箱与Pearson/Spearman相关。

几何审计中的“原点与源位置最小生成树长度/N”仅为空间分散代理，**不是清除路程严格下界**；“原点到各源可收信区域的最短距离均值”仅为观测接近负担代理。所有统计均不使用求解结果选样或调参。

数据生成和校验只使用标准库，不运行solve，不连接平台。存在的数据必须逐条可重复重建且哈希一致；发现修改或缺失即拒绝覆盖。该版本独立于旧balanced_v1，旧样例与旧预览保留。
'''
    return text.encode('utf-8')


def _manifest(problem: int, per_count: int, cases_bytes: bytes,
              distribution_bytes: bytes, readme_bytes: bytes, distribution: dict) -> dict:
    groups = distribution['by_source_count']
    return dict(
        schema_version=SCHEMA_VERSION, dataset=DATASET, problem=problem, provenance=PROVENANCE,
        total_cases=7 * per_count, per_count=per_count,
        counts_by_source_count={str(n): per_count for n in SOURCE_COUNTS},
        cases_file='cases.jsonl', cases_sha256=_sha256(cases_bytes),
        distribution_file='distribution.json', distribution_sha256=_sha256(distribution_bytes),
        readme_file='README.md', readme_sha256=_sha256(readme_bytes),
        generator_file='problem3/normal_scenarios.py',
        generator_sha256=_sha256(Path(__file__).read_text(encoding='utf-8').encode('utf-8')),
        sampling=dict(
            score='m midpoint quantiles of standard normal truncated to [-3,3], then d=(z+3)/6; independent fixed permutation per source count',
            position='area-uniform disk with L(d)=900+900d meters',
            receiving_radius='1350-350d+150u_R meters, u_R~Uniform[0,1)',
            channels='N channels sampled uniformly without replacement from 1..20',
            directional_count='P3: 0; P4: 1+floor((N-2)d+u_K), u_K~Uniform[0,1)',
            directional_selection='first K indices from an independent fixed random permutation',
            directional_orientation='radial angle + (0 with probability d, else 180 degrees) + Uniform[-90,90) degrees, modulo 360; full directional support',
            bearing_error='hash_uniform fixed by seed/channel/position; +/-1 degree before rounding to 0.01 degree',
            scope='Predefined construction difficulty; no solver outcomes or official results; solving times need not be normal or monotonic',
        ),
        rounding=dict(source_parameters_decimal_places=9, z_and_score_decimal_places=12,
                      audit_decimal_places=9),
        seed_ranges={str(n): dict(first=case_seed(problem, n), last=case_seed(problem, n, per_count - 1),
                                 reserved_last=case_seed(problem, n, SEED_CAPACITY - 1),
                                 difficulty_shuffle_seed=_seed_start(problem, n) + SEED_BLOCK - 1)
                     for n in SOURCE_COUNTS},
        difficulty_summary_by_source_count={n: {k: g[k] for k in ('case_count', 'score', 'z', 'interval_counts')}
                                            for n, g in groups.items()},
        geometry_summary_by_source_count={n: g['geometry'] for n, g in groups.items()},
    )


def _validate_case(case: object, problem: int, n: int, index: int, per_count: int) -> None:
    if (not isinstance(case, dict)
            or _canonical_json(case) != _canonical_json(generate_case(problem, n, index, per_count=per_count))):
        raise ValueError(f'Case differs from reproducible generator: n={n}, index={index}')
    sources = case['sources']
    if len(sources) != n or len({s['channel'] for s in sources}) != n:
        raise ValueError('Invalid source count or duplicate channel')
    for source in sources:
        x, y, radius = source['x'], source['y'], source['radius']
        if (not all(math.isfinite(v) for v in (x, y, radius))
                or math.hypot(x, y) > 1800 + 1e-9 or not 1000 <= radius <= 1500):
            raise ValueError('Invalid source position or receiving radius')
        orientation = source['orientation_deg']
        if orientation is not None and not 0 <= orientation < 360:
            raise ValueError('Invalid source orientation')
    directional = sum(s['orientation_deg'] is not None for s in sources)
    if problem == 3 and directional != 0 or problem == 4 and not 1 <= directional < n:
        raise ValueError('Invalid source type mixture')


def _load_validated(problem: int, path: str | Path | None) -> tuple[list[dict], dict]:
    directory = dataset_directory(problem, path)
    try:
        manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
        data = {name: (directory / name).read_bytes()
                for name in ('cases.jsonl', 'distribution.json', 'README.md')}
    except (OSError, ValueError) as exc:
        raise ValueError(f'Missing or unreadable dataset in {directory}: {exc}') from exc
    if not isinstance(manifest, dict):
        raise ValueError('Invalid manifest object')
    per_count = manifest.get('per_count')
    _validate_per_count(per_count)
    for name, content in data.items():
        if not content.endswith(b'\n') or b'\r' in content:
            raise ValueError(f'{name} must use LF and a final newline')
    lines = data['cases.jsonl'].splitlines()
    if len(lines) != per_count * 7:
        raise ValueError('Unexpected number of case records')
    cases, ids, seeds, contents = [], set(), set(), set()
    counts: Counter[int] = Counter()
    for position, line in enumerate(lines):
        try:
            case = json.loads(line)
        except (ValueError, UnicodeDecodeError) as exc:
            raise ValueError(f'Invalid JSON at line {position + 1}') from exc
        n, index = SOURCE_COUNTS[position % 7], position // 7
        _validate_case(case, problem, n, index, per_count)
        if line != _canonical_json(case):
            raise ValueError(f'Non-canonical JSON at line {position + 1}')
        content = _sha256(_canonical_json(case['sources']))
        if case['case_id'] in ids or case['seed'] in seeds or content in contents:
            raise ValueError('Duplicate case ID, seed or source configuration')
        ids.add(case['case_id']); seeds.add(case['seed']); contents.add(content)
        counts[n] += 1
        cases.append(case)
    if dict(counts) != {n: per_count for n in SOURCE_COUNTS}:
        raise ValueError('Unbalanced source-count distribution')
    distribution = _distribution(problem, cases)
    if data['distribution.json'] != _pretty_json(distribution):
        raise ValueError('Construction audit differs from actual case data')
    if data['README.md'] != _readme(problem, per_count):
        raise ValueError('Dataset README differs from its defined sampling model')
    if manifest != _manifest(problem, per_count, data['cases.jsonl'], data['distribution.json'],
                             data['README.md'], distribution):
        raise ValueError('Manifest, checksum or generator fingerprint mismatch')
    return cases, manifest


def load_cases(problem: int, path: str | Path | None = None) -> list[dict]:
    return _load_validated(problem, path)[0]


load_suite = load_cases


def validate_dataset(problem: int, path: str | Path | None = None) -> dict:
    return _load_validated(problem, path)[1]


def prepare_dataset(problem: int, per_count: int = DEFAULT_PER_COUNT,
                    path: str | Path | None = None) -> dict:
    _validate_problem(problem)
    _validate_per_count(per_count)
    directory = dataset_directory(problem, path)
    names = ('cases.jsonl', 'distribution.json', 'README.md', 'manifest.json')
    if any((directory / name).exists() for name in names):
        manifest = validate_dataset(problem, directory)
        if manifest['per_count'] != per_count:
            raise ValueError('Existing per_count differs; choose a new directory')
        return manifest
    cases = list(iter_cases(problem, per_count))
    data = {'cases.jsonl': b''.join(_canonical_json(case) + b'\n' for case in cases),
            'README.md': _readme(problem, per_count)}
    distribution = _distribution(problem, cases)
    data['distribution.json'] = _pretty_json(distribution)
    data['manifest.json'] = _pretty_json(_manifest(problem, per_count, data['cases.jsonl'],
                                                  data['distribution.json'], data['README.md'], distribution))
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        with (directory / name).open('xb') as stream:
            stream.write(data[name])
    return validate_dataset(problem, directory)
