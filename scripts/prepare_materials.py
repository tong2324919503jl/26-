"""Copy B originals and create searchable companions; paths are repo-relative."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
MATERIALS = ROOT / "materials" / "problem_b"
SOURCES = (
    ("CUMCM2026Problems/B题/B题.pdf", "statement.pdf"),
    ("CUMCM2026Problems/B题/附件/附件1.docx", "attachments/attachment_1_simulator_guide.docx"),
    ("CUMCM2026Problems/B题/附件/附件2.docx", "attachments/attachment_2_api_protocol.docx"),
)
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inline_text(node: ET.Element) -> str:
    """Keep both Word text and OMML math tokens (math layout is flattened)."""
    parts = []
    for item in node.iter():
        if item.tag in (f"{{{NS['w']}}}t", f"{{{NS['m']}}}t"):
            parts.append(item.text or "")
        elif item.tag == f"{{{NS['w']}}}tab":
            parts.append(" ")
        elif item.tag in (f"{{{NS['w']}}}br", f"{{{NS['w']}}}cr"):
            parts.append("\n")
    return "".join(parts)


def docx_markdown(path: Path) -> tuple[str, dict]:
    with ZipFile(path) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Damaged DOCX member: {path}: {bad}")
        doc = ET.fromstring(archive.read("word/document.xml"))
    body = doc.find("w:body", NS)
    if body is None:
        raise ValueError(f"Missing document body: {path}")
    lines = [f"# {path.stem}", "",
             "> 本文件由原 Word 正文按段落和表格顺序自动提取，供检索和程序读取。",
             "> 已保留 Word 公式中的文字，但上下标、分式等结构被线性化；图像未转录，公式与图示请以原 DOCX 为准。", ""]
    tables = 0
    for block in body:
        if block.tag == f"{{{NS['w']}}}p":
            value = inline_text(block)
            if value.strip():
                lines.extend([value, ""])
        elif block.tag == f"{{{NS['w']}}}tbl":
            tables += 1
            rows = []
            for row in block.findall("w:tr", NS):
                cells = []
                for cell in row.findall("w:tc", NS):
                    value = "<br>".join(inline_text(p) for p in cell.findall("w:p", NS))
                    cells.append(value.replace("|", "\\|").replace("\n", "<br>"))
                rows.append(cells)
            if rows:
                width = max(map(len, rows))
                rows = [r + [""] * (width - len(r)) for r in rows]
                lines.append("| " + " | ".join(rows[0]) + " |")
                lines.append("| " + " | ".join(["---"] * width) + " |")
                lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
                lines.append("")
    return "\n".join(lines), {
        "table_count": tables,
        "math_expression_count": len(body.findall(".//m:oMath", NS)),
        "text_token_count": sum(1 for n in body.iter() if n.tag in (f"{{{NS['w']}}}t", f"{{{NS['m']}}}t")),
    }


def main() -> None:
    from pypdf import PdfReader

    MATERIALS.mkdir(parents=True, exist_ok=True)
    (MATERIALS / "extracted").mkdir(exist_ok=True)
    entries = []
    for original, relative in SOURCES:
        source = ROOT / original
        target = MATERIALS / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        digest = sha256(source)
        if target.exists() and sha256(target) != digest:
            raise ValueError(f"Refusing to overwrite changed material: {target}")
        if not target.exists():
            shutil.copy2(source, target)
        entry = {"source": original, "working_copy": target.relative_to(ROOT).as_posix(),
                 "bytes": source.stat().st_size, "sha256": digest}
        if target.suffix == ".pdf":
            reader = PdfReader(target)
            text = "# B题题面检索文本\n\n> 自动提取；公式排版、图示和原始表格以 statement.pdf 为准。\n\n"
            text += "\n\n".join(f"## 原题第 {i} 页\n\n{page.extract_text()}" for i, page in enumerate(reader.pages, 1))
            entry["page_count"] = len(reader.pages)
        else:
            text, statistics = docx_markdown(target)
            entry.update(statistics)
        extracted = MATERIALS / "extracted" / f"{target.stem}.md"
        text = "\n".join(line.rstrip() for line in text.splitlines()).rstrip() + "\n"
        extracted.write_text(text, encoding="utf-8", newline="\n")
        entry["extracted_text"] = extracted.relative_to(ROOT).as_posix()
        entry["extracted_sha256"] = sha256(extracted)
        entries.append(entry)
    manifest = {"schema_version": 1, "policy": "Original bundle retained; working copies are byte-identical.", "files": entries}
    (MATERIALS / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Prepared {len(entries)} B materials and searchable companions.")


if __name__ == "__main__":
    main()
