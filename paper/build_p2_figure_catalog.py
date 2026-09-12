"""Build a vector PDF catalog, contact sheets and a portable P2 candidate bundle."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import zipfile
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
FIGS = PAPER / 'figures' / 'problem2_candidates'
RESULTS = PAPER / 'results'
W, H = landscape(A4)
FONT = 'P2CandidateSong'
GROUPS = [(1, 6, '方法引入', 'intro'), (7, 13, '两种评分', 'scoring'),
          (14, 19, '选点与数值', 'selection')]


def paragraph(c, text, x, top, width, size=10, color='#202020'):
    # SimSun does not provide every Unicode subscript glyph. Plain indices
    # keep the catalog captions complete; artwork uses embedded math fonts.
    text = text.translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉', '0123456789'))
    style = ParagraphStyle('p2body', fontName=FONT, fontSize=size,
                           leading=size * 1.45, textColor=HexColor(color),
                           wordWrap='CJK')
    p = Paragraph(escape(text), style)
    _, height = p.wrap(width, 1000)
    p.drawOn(c, x, top - height)
    return top - height


def new_page():
    b = io.BytesIO()
    return b, canvas.Canvas(b, pagesize=(W, H))


def seal(b, c):
    c.showPage()
    c.save()
    b.seek(0)
    return PdfReader(b).pages[0]


def number(m):
    return int(m['id'].split('_')[1])


def contact_sheets(metas):
    font_path = str(PAPER / 'fonts' / 'simsun.ttc')
    label_font = ImageFont.truetype(font_path, 26)
    title_font = ImageFont.truetype(font_path, 38)
    sheets = []
    for first, last, title, name in GROUPS:
        subset = [m for m in metas if first <= number(m) <= last]
        rows = (len(subset) + 1) // 2
        sheet = Image.new('RGB', (1800, 96 + rows * 555), 'white')
        draw = ImageDraw.Draw(sheet)
        draw.text((34, 26), f'问题二 · {title}  /  {first:02d}–{last:02d}',
                  font=title_font, fill='#202020')
        for i, m in enumerate(subset):
            x, y = 24 + (i % 2) * 888, 100 + (i // 2) * 555
            draw.rectangle((x, y, x + 864, y + 535), outline='#cccccc', width=1)
            source = Image.open(FIGS / (m['id'] + '.png')).convert('RGB')
            source.thumbnail((834, 468), Image.Resampling.LANCZOS)
            sheet.paste(source, (x + (864 - source.width) // 2,
                                y + 12 + (468 - source.height) // 2))
            draw.text((x + 16, y + 493), f'{number(m):02d}  {m["title"]}',
                      font=label_font, fill='#202020')
        output = FIGS / f'p2_{name}_overview.png'
        sheet.save(output)
        sheets.append(output)
    return sheets


def build_catalog(metas):
    pdfmetrics.registerFont(TTFont(FONT, str(PAPER / 'fonts' / 'simsun.ttc'),
                                  subfontIndex=0))
    writer = PdfWriter()
    b, c = new_page()
    c.setFillColor(HexColor('#202020'))
    c.setFont(FONT, 24)
    c.drawString(43, H - 48, '问题二 · 论文候选图册')
    paragraph(c, '19 张候选图｜沿用问题一的白底、正常字重、蓝灰配色与几何坐标风格',
              44, H - 65, W - 88, 10.5)
    top = H - 103
    for first, last, title, _ in GROUPS:
        c.setFont(FONT, 11)
        c.setFillColor(HexColor('#27647b'))
        c.drawString(46, top, title)
        top -= 22
        for m in metas:
            if not first <= number(m) <= last:
                continue
            c.setFillColor(HexColor('#202020'))
            c.setFont(FONT, 10)
            c.drawString(58, top, f'{number(m):02d}   {m["title"]}')
            c.drawRightString(W - 48, top, f'第 {number(m) + 1} 页')
            c.setStrokeColor(HexColor('#e0e0e0'))
            c.setLineWidth(.35)
            c.line(47, top - 6, W - 47, top - 6)
            top -= 16
        top -= 9
    assert top > 54, top
    paragraph(c, '方法图对应当前正文与实现；数值均为自建离线算例。单图附独立图注和来源，供筛选后插入。',
              44, 45, W - 88, 9, '#737373')
    writer.add_page(seal(b, c))
    for m in metas:
        b, c = new_page()
        c.setFillColor(HexColor('#27647b'))
        c.setFont(FONT, 16)
        c.drawString(40, H - 34, f'{number(m):02d}')
        c.setFillColor(HexColor('#202020'))
        c.setFont(FONT, 17)
        c.drawString(77, H - 34, m['title'])
        c.setStrokeColor(HexColor('#cccccc'))
        c.setLineWidth(.5)
        c.line(40, H - 45, W - 40, H - 45)
        section = m['section']
        if m.get('recommendation'):
            section += '；' + m['recommendation']
        bottom = paragraph(c, '适用位置：' + section, 42, 143, W - 84, 9.2)
        bottom = paragraph(c, '图注：' + m['caption'], 42, bottom - 8, W - 84, 9.2)
        if m.get('notes'):
            bottom = paragraph(c, '说明：' + m['notes'], 42, bottom - 6,
                               W - 84, 8.1, '#737373')
        assert bottom >= 25, (m['id'], bottom)
        c.setFont(FONT, 7.5)
        c.setFillColor(HexColor('#737373'))
        c.drawString(42, 14, '逐图来源、数据与校验值见同名 JSON；图内未附说明段落。')
        c.drawRightString(W - 26, 14, str(number(m) + 1))
        page = seal(b, c)
        artwork = PdfReader(FIGS / (m['id'] + '.pdf')).pages[0]
        fw, fh = float(artwork.mediabox.width), float(artwork.mediabox.height)
        area_h = H - 45 - 165
        scale = min((W - 70) / fw, area_h / fh)
        tx, ty = (W - fw * scale) / 2, 161 + (area_h - fh * scale) / 2
        page.merge_transformed_page(artwork,
            Transformation().scale(scale).translate(tx, ty))
        writer.add_page(page)
        writer.add_outline_item(f'{number(m):02d} {m["title"]}', number(m))
    writer.add_metadata({'/Title': '问题二论文候选图册', '/Author': '',
                         '/Subject': '19张几何机制与自建离线结果候选图，供筛选'})
    RESULTS.mkdir(exist_ok=True)
    output = RESULTS / 'p2_figure_catalog.pdf'
    with output.open('wb') as stream:
        writer.write(stream)
    assert len(PdfReader(output).pages) == 20
    return output


def build_guide(metas):
    lines = ['# 问题二候选图筛选', '',
             '19张候选图，与当前问题一正文图保持白底、正常字重、蓝灰主色、黑色轴框、浅灰网格。几何图使用真实单位和比例，细小角度通过局部放大展示。', '',
             '正文尚未插入本批候选图。每张均有PDF、SVG、240 dpi PNG，以及独立图注、来源和数据校验值JSON。', '',
             '| 编号 | 候选图 | 正文位置 |', '| --- | --- | --- |']
    for m in metas:
        lines.append(f'| {number(m):02d} | [{m["title"]}]({m["id"]}.pdf) | {m["section"]} |')
    lines += ['', '## 建议先筛', '',
              '- 方法引入先看01、02；03、04解释为什么需要安全约束，05说明目标圆的作用。',
              '- 评分方法先看07、08、09、10；11把最坏读数扫描画成曲线，12补充交会角的影响，13展示单元增宽。',
              '- 选点与结果先看14、15、17；16适合对应数值表，18说明分层细化，19说明离散精度。',
              '', '## 图注与证据', '']
    for m in metas:
        lines += [f'### {number(m):02d} {m["title"]}', '', m['caption'], '']
        if m.get('notes'):
            lines += [m['notes'], '']
        lines += ['来源：' + '、'.join('`' + s + '`' for s in m['sources']), '']
    lines += ['## 复现', '',
              '在仓库中依次运行下列入口，均由脚本位置确定读写路径：', '',
              '```powershell', 'python paper/plot_p2_intro_candidates.py',
              'python paper/plot_p2_scoring_candidates.py',
              'python paper/plot_p2_selection_candidates.py',
              'python paper/build_p2_figure_catalog.py', '```', '',
              '制图需要matplotlib、numpy；图册需要reportlab、pypdf、Pillow。当前电脑制图使用Anaconda Python，图册使用Codex随附Python。',
              '图包保留仓库相对路径，并附问题二求解器及需要的原始结果快照。脚本只读取这些输入，在本批候选目录中输出，不覆盖原结果。', '',
              '四圆盘几何保证与自建样本验证分开；A、B、C均为最坏直径评分上界，不是真实定位误差。已访问近优点不等于连续区域的完整数值刻画。']
    (FIGS / 'README.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def bundle(metas, catalog):
    names = ['p2_candidate_style.py', 'plot_p2_intro_candidates.py',
             'plot_p2_scoring_candidates.py', 'plot_p2_selection_candidates.py',
             'build_p2_figure_catalog.py']
    files = set(FIGS.glob('*'))
    files.update(PAPER / name for name in names)
    files.update([catalog, PAPER / 'fonts' / 'simsun.ttc'])
    for m in metas:
        files.update(ROOT / s for s in m['sources'] if (ROOT / s).is_file())
    files.update((ROOT / 'problem2' / 'results').glob('*.json'))
    files.update((ROOT / 'problem2' / 'results').glob('*.csv'))
    files.update((ROOT / 'problem2' / 'results' / 'boundary').glob('*.json'))
    files.update((ROOT / 'problem2' / 'results' / 'boundary').glob('*.csv'))
    files.add(ROOT / 'problem2' / 'solve.py')
    output = RESULTS / 'p2_figure_candidates.zip'
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for path in sorted(files):
            if path.is_file():
                z.write(path, path.relative_to(ROOT).as_posix())
    return output


def main():
    paths = sorted(FIGS.glob('p2_[0-9][0-9]_*.json'))
    records = [json.loads(p.read_text(encoding='utf-8')) for p in paths]
    metas = [record for record in records if 'id' in record and 'caption' in record]
    assert [number(m) for m in metas] == list(range(1, 20))
    source_checks = 0
    for m in metas:
        for source, expected in m['source_sha256'].items():
            assert hashlib.sha256((ROOT / source).read_bytes()).hexdigest() == expected, source
            source_checks += 1
        for ext in ('pdf', 'svg', 'png'):
            assert (FIGS / (m['id'] + '.' + ext)).is_file()
        assert len(PdfReader(FIGS / (m['id'] + '.pdf')).pages) == 1
    sheets = contact_sheets(metas)
    catalog = build_catalog(metas)
    build_guide(metas)
    audit = {'candidate_count': len(metas), 'catalog_pages': 20,
             'source_hash_checks': source_checks,
             'source_hashes_current': True,
             'all_individual_pdfs_single_page': True,
             'figure_formats': ['pdf', 'svg', 'png'],
             'contact_sheets': [p.name for p in sheets],
             'scope': '当前论文方法与自建离线结果；未修改生产算法或论文正文。'}
    (FIGS / 'catalog_audit.json').write_text(json.dumps(audit, ensure_ascii=False,
        indent=2) + '\n', encoding='utf-8')
    archive = bundle(metas, catalog)
    print(json.dumps({'catalog': str(catalog), 'bundle': str(archive), **audit},
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
