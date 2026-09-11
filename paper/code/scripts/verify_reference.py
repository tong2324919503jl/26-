"""Optional independent HiGHS check of problem 1; requires SciPy only here.

Adapted from the teammate bundle's scripts/verify_reference.py.  The current
Fraction-based solver, rather than the archived implementation, is checked.
All data are deterministic synthetic half-plane systems, not simulator runs.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from problem1.solve import HalfPlane, analyze_halfplanes


def verify(random_cases: int, seed: int) -> dict:
    import scipy
    from scipy.optimize import linprog

    rng = random.Random(seed)
    # Explicit low-dimensional cases complement generic random systems.
    cases = [
        ("empty", [(1, 0, 0), (-1, 0, -1)]),
        ("halfplane", [(1, 0, 2)]),
        ("strip", [(1, 0, 2), (-1, 0, 1)]),
        ("line", [(1, 0, 2), (-1, 0, -2)]),
        ("point", [(1, 0, 2), (-1, 0, -2), (0, 1, 3), (0, -1, -3)]),
        ("segment", [(1, 0, 2), (-1, 0, -2), (0, 1, 3), (0, -1, 0)]),
        ("triangle", [(-1, 0, 0), (0, -1, 0), (1, 1, 10)]),
        ("rectangle", [(1, 0, 8), (-1, 0, 3), (0, 1, 7), (0, -1, 2)]),
    ]
    for index in range(random_cases):
        planes = []
        for _ in range(rng.randint(2, 12)):
            a, b = 0, 0
            while (a, b) == (0, 0):
                a, b = rng.randint(-15, 15), rng.randint(-15, 15)
            planes.append((a, b, rng.randint(-100, 100)))
        cases.append((f"random_{index}", planes))

    directions = [(1, 0), (-1, 0), (0, 1), (0, -1),
                  (1, 1), (-1, 1), (1, -1), (-1, -1)]
    counts: Counter = Counter()
    failures = []
    supports_checked = 0
    for name, coefficients in cases:
        matrix = [[a, b] for a, b, _ in coefficients]
        limits = [c for _, _, c in coefficients]

        def reference(objective):
            return linprog(objective, A_ub=matrix, b_ub=limits,
                           bounds=[(None, None)] * 2, method="highs")

        actual = analyze_halfplanes(HalfPlane(*row) for row in coefficients)
        feasible = reference((0, 0))
        references = []
        if feasible.status == 2:
            expected = "empty"
        elif feasible.status == 0:
            references = [reference(direction) for direction in directions]
            if any(result.status not in (0, 3) for result in references):
                failures.append({"case": name, "error": "Reference support solve failed"})
                continue
            expected = "unbounded" if any(result.status == 3 for result in references) else "bounded"
        else:
            failures.append({"case": name, "error": feasible.message})
            continue
        counts[expected] += 1
        category = actual["status"] if actual["status"] in ("empty", "unbounded") else "bounded"
        if category != expected:
            failures.append({"case": name, "expected": expected, "actual": actual["status"]})
            continue
        if expected == "bounded":
            for objective, result in zip(directions, references):
                value = min(objective[0] * x + objective[1] * y for x, y in actual["vertices"])
                supports_checked += 1
                if abs(value - result.fun) > 1e-7 * max(1.0, abs(result.fun)):
                    failures.append({"case": name, "objective": objective,
                                     "actual_support": value, "reference_support": result.fun})

    return {"passed": not failures, "reference": "scipy.optimize.linprog / HiGHS",
            "scipy_version": scipy.__version__, "seed": seed,
            "random_halfplane_systems": random_cases, "explicit_edge_cases": 8,
            "classification_counts": dict(counts), "bounded_support_values_checked": supports_checked,
            "failures": failures,
            "scope": "Deterministic synthetic geometry; no official simulator. HiGHS has floating tolerances; extreme near-parallel cases remain in the exact solver's own regression suite."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=int, default=500)
    parser.add_argument("--seed", type=int, default=611209)
    parser.add_argument("--output", type=Path, default=Path("validation/reference_geometry.json"))
    args = parser.parse_args()
    if args.cases < 1:
        parser.error("--cases must be positive")
    try:
        result = verify(args.cases, args.seed)
    except ImportError:
        parser.error("This optional check requires SciPy; the solvers and standard validation do not.")
    output = args.output if args.output.is_absolute() else ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
