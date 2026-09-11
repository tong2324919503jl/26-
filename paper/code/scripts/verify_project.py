"""Verify preserved inputs, four solutions, and their regression suites."""
from __future__ import annotations

import hashlib
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = ROOT / "validation"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", action="store_true",
                        help="Also run the optional independent SciPy/HiGHS geometry check")
    args = parser.parse_args()
    checks = []

    def record(name, action):
        started = time.perf_counter()
        try:
            detail = action()
            check = {"name": name, "passed": True, "detail": detail}
        except Exception as exc:
            check = {"name": name, "passed": False, "detail": str(exc)}
        check["elapsed_seconds"] = round(time.perf_counter() - started, 3)
        checks.append(check)
        print(f"{'PASS' if check['passed'] else 'FAIL'} {name}", flush=True)

    def materials():
        manifest = json.loads((ROOT / "materials/problem_b/manifest.json").read_text(encoding="utf-8"))
        if len(manifest["files"]) != 3:
            raise AssertionError("Expected exactly three original B material files")
        for entry in manifest["files"]:
            for key in ("source", "working_copy"):
                path = ROOT / entry[key]
                if path.stat().st_size != entry["bytes"] or sha256(path) != entry["sha256"]:
                    raise AssertionError(f"Material content mismatch: {entry[key]}")
            extracted = ROOT / entry["extracted_text"]
            if sha256(extracted) != entry["extracted_sha256"]:
                raise AssertionError(f"Extracted text mismatch: {extracted.name}")
            if not extracted.read_text(encoding="utf-8").strip():
                raise AssertionError(f"Empty extracted text: {extracted.name}")
            copy = ROOT / entry["working_copy"]
            if copy.suffix == ".docx":
                with ZipFile(copy) as archive:
                    if archive.testzip() is not None:
                        raise AssertionError(f"Corrupt DOCX: {copy.name}")
                    ET.fromstring(archive.read("word/document.xml"))
            elif not copy.read_bytes().startswith(b"%PDF-"):
                raise AssertionError("Missing PDF header")
        return {"original_files_checked": 3, "searchable_text_files_checked": 3,
                "method": "SHA-256 and byte counts; DOCX ZIP CRC and XML parsing; PDF signature"}

    def command(args: list[str], cwd: Path):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        completed = subprocess.run([sys.executable, *args], cwd=cwd, env=env,
                                   capture_output=True, text=True, encoding="utf-8", timeout=240)
        output = (completed.stdout + completed.stderr).strip()
        if completed.returncode:
            raise AssertionError(f"Exit {completed.returncode}\n{output}")
        return {"exit_code": 0, "output": output}

    record("original_materials_and_searchable_copies", materials)
    for problem in ("problem1", "problem2", "problem3", "problem4"):
        def suite(problem=problem):
            tests = ROOT / problem / "tests"
            if not list(tests.glob("test_*.py")):
                raise AssertionError(f"No tests found: {problem}")
            result = command(["-m", "unittest", "discover", "-s", f"{problem}/tests", "-v"], ROOT)
            if "Ran 0 tests" in result["output"]:
                raise AssertionError(f"No tests executed: {problem}")
            return result

        record(f"{problem}_tests", suite)

        def outside_cwd(problem=problem):
            with tempfile.TemporaryDirectory(prefix="cumcm_b_verify_") as temporary:
                return command([str(ROOT / problem / "solve.py")], Path(temporary))

        record(f"{problem}_solve_from_outside_repository", outside_cwd)

    def strategy_comparison():
        with tempfile.TemporaryDirectory(prefix="cumcm_b_comparison_") as temporary:
            return command([str(ROOT / "problem2/compare_strategies.py")], Path(temporary))

    record("problem2_strategy_comparison_from_outside_repository", strategy_comparison)

    def scoring_benchmark():
        with tempfile.TemporaryDirectory(prefix="cumcm_b_scoring_") as temporary:
            return command([str(ROOT / "problem2/benchmark_scoring.py")], Path(temporary))

    record("problem2_early_stop_equivalence_from_outside_repository", scoring_benchmark)

    for problem_number in (3, 4):
        def search_smoke(problem_number=problem_number):
            with tempfile.TemporaryDirectory(prefix="cumcm_b_search_") as temporary:
                return command([str(ROOT / "scripts/benchmark_search.py"), "--problem", str(problem_number),
                                "--split", "stress", "--count", "8", "--strategies", "adaptive",
                                "--tag", "verification"], Path(temporary))
        record(f"problem{problem_number}_search_smoke_from_outside_repository", search_smoke)
    if args.reference:
        with tempfile.TemporaryDirectory(prefix="cumcm_b_reference_") as temporary:
            record("independent_highs_geometry_reference",
                   lambda: command([str(ROOT / "scripts/verify_reference.py")], Path(temporary)))

    def outputs():
        files = []
        for problem in ("problem1", "problem2", "problem3", "problem4"):
            results = ROOT / problem / "results"
            if not results.is_dir() or not any(results.iterdir()):
                raise AssertionError(f"Missing results: {problem}")
            for path in sorted(results.rglob("*")):
                if not path.is_file():
                    continue
                if path.stat().st_size == 0:
                    raise AssertionError(f"Empty result: {path}")
                if path.suffix == ".json":
                    json.loads(path.read_text(encoding="utf-8"))
                elif path.suffix == ".jsonl":
                    for line in path.read_text(encoding="utf-8").splitlines():
                        json.loads(line)
                elif path.suffix == ".csv":
                    with path.open(encoding="utf-8-sig", newline="") as stream:
                        rows = list(csv.reader(stream))
                    if len(rows) < 2 or not rows[0] or any(len(r) != len(rows[0]) for r in rows[1:]):
                        raise AssertionError(f"Invalid or empty CSV table: {path}")
                elif path.suffix == ".svg":
                    ET.parse(path)
                files.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size,
                              "sha256": sha256(path)})
        return files

    record("result_files_readable", outputs)

    def documentation_links():
        count = 0
        paths = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "materials/problem_b/README.md",
                 ROOT / "simulation_guide.md", ROOT / "validation/search_experiments.md"]
        for problem in ("problem1", "problem2", "problem3", "problem4"):
            paths.extend(sorted((ROOT / problem).rglob("*.md")))
        paths.append(ROOT / "validation/merge_notes.md")
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            content = path.read_text(encoding="utf-8")
            for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
                if "://" in target or target.startswith("#"):
                    continue
                target = target.split("#", 1)[0].strip("<>")
                if not (path.parent / target).exists():
                    raise AssertionError(f"Broken link in {relative}: {target}")
                count += 1
        return {"local_links_checked": count}

    def write_reports() -> bool:
        passed = all(check["passed"] for check in checks)
        test_counts = {}
        for check in checks:
            if check["name"] in tuple(f"problem{n}_tests" for n in range(1,5)) and isinstance(check["detail"], dict):
                match = re.search(r"Ran (\d+) tests?", check["detail"].get("output", ""))
                if match:
                    test_counts[check["name"].split("_")[0]] = int(match.group(1))
        report = {"verified_at_utc": datetime.now(timezone.utc).isoformat(),
                  "python_version": sys.version.split()[0], "passed": passed,
                  "unit_test_counts": test_counts,
                  "scope": "Local problems 1 to 4; synthetic examples and local mock HTTP; no official simulator run.",
                  "checks": checks}
        REPORT_DIR.mkdir(exist_ok=True)
        (REPORT_DIR / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = ["# B题四问验证报告", "", f"总结果：{'全部通过' if passed else '存在失败，请查看具体记录'}。", "",
                 f"验证时间（UTC）：{report['verified_at_utc']}；Python：{report['python_version']}。", "",
                 "自动测试：" + "，".join(f"问题{n} {test_counts.get(f'problem{n}',0)} 项" for n in range(1,5)) + "。", "",
                 "| 检查项 | 结果 |", "| --- | --- |"]
        labels = {"original_materials_and_searchable_copies": "原材料与检索副本完整性",
                  "problem1_tests": "第一问数学与程序测试", "problem2_tests": "第二问数学与程序测试",
                  "problem1_solve_from_outside_repository": "第一问从仓库外目录运行",
                  "problem2_solve_from_outside_repository": "第二问从仓库外目录运行",
                  "problem2_strategy_comparison_from_outside_repository": "同口径策略比较及跨目录复现",
                  "problem2_early_stop_equivalence_from_outside_repository": "提前停止的评分与选点等价性及计算量",
                  "independent_highs_geometry_reference": "独立 HiGHS 几何核验",
                  "result_files_readable": "结果文件完整且可读取", "documentation_links": "说明文档本地链接"}
        lines.extend(f"| {labels.get(check['name'], check['name'])} | {'通过' if check['passed'] else '失败'} |" for check in checks)
        lines.extend(["", "验证包括三份资料及三个文本副本的一致性、四问测试、从仓库以外目录启动求解与策略对比、问题三四各8例困难样本回归、结果文件可读取性和说明文档链接。",
                      "", "算例均为自行构造，只验证本地数学算法；没有运行问题3、4的官方演练或正式测试。",
                      "", "详细测试名称、输出、耗时、结果文件摘要见 [report.json](report.json)。",
                      "", "复现：在仓库根运行 `python scripts/verify_project.py`。加 `--reference` 可额外运行独立 SciPy/HiGHS 几何核验（仅这一可选项需要 SciPy）。",
                      "", f"本次独立参考核验：{'已执行，结果见上表及 reference_geometry.json' if args.reference else '未请求；已有 reference_geometry.json 不代表本次已重跑'}。"])
        (REPORT_DIR / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return passed

    # Generate this report before checking links pointing to it on a clean checkout.
    write_reports()
    record("documentation_links", documentation_links)
    return 0 if write_reports() else 1


if __name__ == "__main__":
    raise SystemExit(main())
