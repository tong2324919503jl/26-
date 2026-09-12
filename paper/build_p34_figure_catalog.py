"""Package the candidate figures for selection without changing the manuscript."""
from pathlib import Path
import io
import json
import zipfile
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from pypdf import PdfReader, PdfWriter, Transformation

PAPER=Path(__file__).resolve().parent
ROOT=PAPER.parent
FIGS=PAPER/'figures'/'p34_candidates'
RESULTS=PAPER/'results'
W,H=landscape(A4)
FONT='CandidateSong'

def paragraph(c,text,x,y,width=745,size=10,color='#414950'):
    style=ParagraphStyle('body',fontName=FONT,fontSize=size,leading=size*1.48,
        textColor=HexColor(color),wordWrap='CJK')
    p=Paragraph(escape(text),style)
    _,h=p.wrap(width,1000);p.drawOn(c,x,y-h)
    return y-h

def page_buffer():
    b=io.BytesIO();return b,canvas.Canvas(b,pagesize=(W,H))

def seal(b,c):
    c.showPage();c.save();b.seek(0);return PdfReader(b).pages[0]

def main():
    pdfmetrics.registerFont(TTFont(FONT,str(PAPER/'fonts'/'simsun.ttc'),subfontIndex=0))
    files=sorted(FIGS.glob('[0-9][0-9]_*.json'))
    assert len(files)==10, f'Expected ten selected candidate families, got {len(files)}'
    metas=[json.loads(p.read_text(encoding='utf-8')) for p in files]
    RESULTS.mkdir(exist_ok=True)
    writer=PdfWriter()
    b,c=page_buffer()
    c.setFillColor(HexColor('#414950'));c.setFont(FONT,24)
    c.drawString(46,H-57,'问题三、四 · 论文候选图册')
    paragraph(c,'10 张候选图  |  中文宋体 · 柔和配色 · 图例外置 · 浅灰细框',47,H-77,size=11)
    c.setFillColor(HexColor('#EDF2F5'));c.rect(46,H-145,W-92,40,fill=1,stroke=0)
    paragraph(c,'题目两项指标：清除比例 Nc/N；平均定位清除时间 T/Nc。此册均为本地结果或机制示意，正式成绩待补。',57,H-116,width=W-114,size=10.5)
    c.setStrokeColor(HexColor('#CBD2D7'));c.setLineWidth(.6)
    top=H-178
    for i,m in enumerate(metas):
        yy=top-i*25
        c.setFillColor(HexColor('#6F91AB'));c.setFont(FONT,11);c.drawString(50,yy,m['id'][:2])
        c.setFillColor(HexColor('#414950'));c.drawString(82,yy,m['title'])
        c.setFont(FONT,9);c.drawRightString(W-52,yy,f'第 {i+2} 页')
        c.line(48,yy-9,W-48,yy-9)
    paragraph(c,'建议优先筛选：01 或 02 展示本地结果，05 解释时间瓶颈，06 或 07 展示实际样例，08、09 阐释覆盖机制；10 视正文篇幅选用。',48,125,size=10)
    paragraph(c,'清除比例在六组冻结测试中均为100%，因此采用紧凑结果栏；不为恒定数值另画一张空泛柱图。每张图后附适用位置与可直接使用的图注。',48,86,size=9.5)
    paragraph(c,'正文暂未替换。筛选时只需给出图号；单张PDF、SVG、高清PNG及复现脚本另附于图包。',48,48,size=9.5)
    writer.add_page(seal(b,c))
    guide=['# 问题三、四候选图筛选说明','','本轮只制作候选图，不替换正文，也不填造正式测试成绩。',
       '题目指标为清除比例 `Nc/N`、平均定位清除时间 `T/Nc`。旧图的220/400秒阈值通过率是额外本地指标，不能替代清除比例。',
       '', '| 编号 | 图 | 用途 |','| --- | --- | --- |']
    tex=['% 候选插图片段：选择后再加入正文，不一次性全部引用。',r'% 已存在的 graphicspath 若只含 figures/，文件名前保留 p34_candidates/。','']
    for i,m in enumerate(metas):
        b,c=page_buffer()
        c.setFillColor(HexColor('#6F91AB'));c.setFont(FONT,12);c.drawString(43,H-30,m['id'][:2])
        c.setFillColor(HexColor('#414950'));c.setFont(FONT,16);c.drawString(78,H-32,m['title'])
        c.setStrokeColor(HexColor('#D3D9DD'));c.setLineWidth(.6);c.line(43,H-45,W-43,H-45)
        paragraph(c,'建议：'+m.get('recommendation','根据正文篇幅选择。'),43,117,width=W-86,size=9.5)
        paragraph(c,'图注：'+m['caption'],43,93,width=W-86,size=8.8)
        sources=m['sources']
        if isinstance(sources,list):source='；'.join(s if isinstance(s,str) else str(s) for s in sources)
        else:source=str(sources)
        if len(source)>190:
            source='validation/speed_v4/ 冻结配对结果；或对应 problem3/4 示例、动作记录及当前几何证书。详见同名来源JSON。'
        paragraph(c,'来源：'+source,43,43,width=W-100,size=7.5,color='#7A838B')
        c.setFillColor(HexColor('#889299'));c.setFont(FONT,8);c.drawRightString(W-28,17,str(i+2))
        page=seal(b,c)
        figure=PdfReader(FIGS/(m['id']+'.pdf')).pages[0]
        fw,fh=float(figure.mediabox.width),float(figure.mediabox.height)
        scale=min((W-74)/fw,405/fh)
        tx=(W-fw*scale)/2;ty=128+(405-fh*scale)/2
        page.merge_transformed_page(figure,Transformation().scale(scale).translate(tx,ty))
        writer.add_page(page)
        guide.append(f"| {m['id'][:2]} | [{m['title']}]({m['id']}.pdf) | {m.get('recommendation','')} |")
        tex += [r'\begin{figure}[htbp]',r'\centering',
            r'\includegraphics[width=0.98\linewidth]{p34_candidates/'+m['id']+'.pdf}',
            r'\caption{'+m['title']+r'（本地结果或机制示意，详见候选图注）}',
            r'\label{fig:p34-candidate-'+m['id'][:2]+'}',r'\end{figure}','']
    writer.add_metadata({'/Title':'问题三四论文候选图册','/Author':'','/Subject':'本地结果与机制示意，供筛选，不是正式成绩'})
    output=RESULTS/'p34_figure_catalog.pdf'
    with output.open('wb') as f:writer.write(f)
    assert len(PdfReader(output).pages)==11
    guide += ['', '## 优先推荐', '',
        '- 01（详细分布）与02（方案对照）按论证重点选择；06（空间轨迹）与07（时间进度）可择一。',
        '- 05解释瓶颈，08与09解释覆盖机制，10解释光学兜底；03、04用于展开实验分析。',
        '- 不制作单独的100%清除率大柱图，不把缺失的正式结果画成零值，不混入概率提前停止实验结果。',
        '- 单张图内的说明可在选图后移至正文图注；当前保留以防独立传播时丢失证据范围。',
        '', '## 数据与复现', '',
        '01—05读取 `validation/speed_v4` 的冻结数据：每问开发384、留出512、压力256例。所有分支按案例ID和哈希逐例配对，核对两项指标、完成证书及计时分解。',
        '06—07只读取现有本地示例与537个已保存动作，不运行求解器。08使用当前22点证书；09—10为明确标识的几何机制示意。',
        '数据校验见 `data_audit.json`；逐图来源、局限和建议见同名JSON。PDF和SVG为矢量图，PNG为220 dpi预览。',
        '', '在仓库中依次运行：', '', '```powershell',
        'python paper/plot_p34_result_candidates.py','python paper/plot_p34_case_candidates.py',
        'python paper/plot_p34_mechanism_candidates.py','python paper/build_p34_figure_catalog.py','```',
        '', '绘图需要matplotlib、numpy；图册需要reportlab、pypdf。路径均由脚本自身位置确定。打包脚本可用Codex自带Python运行。',
        '图包内脚本只是复现入口副本，需要在原仓库数据结构下运行；图包未重复打包大体积原始冻结结果。']
    (FIGS/'README.md').write_text('\n'.join(guide)+'\n',encoding='utf-8')
    (FIGS/'candidate_includes.tex').write_text('\n'.join(tex),encoding='utf-8')
    archive=RESULTS/'p34_figure_candidates.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for f in sorted(FIGS.iterdir()):
            if f.is_file():z.write(f,'figures/'+f.name)
        z.write(output,output.name)
        for name in ['figure_candidate_style.py','plot_p34_result_candidates.py','plot_p34_case_candidates.py',
                     'plot_p34_mechanism_candidates.py','build_p34_figure_catalog.py']:
            z.write(PAPER/name,'reproduce/'+name)
    print(f'Catalog: {output}; pages=11; candidates=10; bundle={archive}')

if __name__=='__main__':main()
