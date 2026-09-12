"""Create corrected paper copies of the user's September 12 Draw.io figures.

The original Chinese-named Draw.io/PNG files are never modified. Export these
editable copies with draw.io --export --format pdf --crop --output PATH FILE.
"""
from pathlib import Path
import html
import re
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
FIGURES = HERE.parent


def markup(lines, size=16):
    return '<div style="font-family:SimSun;font-size:%spx;line-height:1.2;font-weight:normal;">%s</div>' % (
        size, '<br>'.join(lines.split('\n')))


def revise_p1():
    tree = ET.parse(FIGURES / '问题一算法流程图.drawio')
    root = tree.find('.//root')
    cells = {n.get('id'): n for n in root.findall('mxCell')}
    changes = {
        'RkxC13zxXOI5UCIjbvwe-1': '输入检测点、\n示向度与误差',
        'RkxC13zxXOI5UCIjbvwe-5': '扇区建模\n观测转换为半平面',
        'RkxC13zxXOI5UCIjbvwe-12': '筛选交点与可行性见证\n确定可行点与候选顶点',
        'RkxC13zxXOI5UCIjbvwe-14': '存在共同\n可行点？',
        'RkxC13zxXOI5UCIjbvwe-19': '存在非零\n衰退方向？',
        'RkxC13zxXOI5UCIjbvwe-44': '否',
        'RkxC13zxXOI5UCIjbvwe-42': '是',
        'RkxC13zxXOI5UCIjbvwe-22': '否',
        'RkxC13zxXOI5UCIjbvwe-23': '是',
        'RkxC13zxXOI5UCIjbvwe-11': '有界区域\n分类并求直径 D',
        'RkxC13zxXOI5UCIjbvwe-8': '覆盖性判断',
        'RkxC13zxXOI5UCIjbvwe-25': '最小覆盖圆',
        'RkxC13zxXOI5UCIjbvwe-26': '直径圆',
        'RkxC13zxXOI5UCIjbvwe-9': '20米阈值',
        'RkxC13zxXOI5UCIjbvwe-46': '返回状态',
        'eNKVNzA_65YRwpMAGb4x-5': '空集\n无共同可行位置',
        'eNKVNzA_65YRwpMAGb4x-7': '无界，直径为∞',
    }
    for ident, lines in changes.items():
        cells[ident].set('value', markup(lines))
    # Larger regular-weight text at the same main node locations.
    for ident, x, y, w, h in [
        ('RkxC13zxXOI5UCIjbvwe-1', 10, 7, 140, 50),
        ('RkxC13zxXOI5UCIjbvwe-5', 0, 7, 160, 50),
        ('RkxC13zxXOI5UCIjbvwe-12', 0, 8, 201, 48),
        ('RkxC13zxXOI5UCIjbvwe-14', 16, 29, 115, 52),
        ('RkxC13zxXOI5UCIjbvwe-19', 18, 30, 118, 52),
        ('RkxC13zxXOI5UCIjbvwe-11', 2, 12, 132, 45),
    ]:
        cells[ident].find('mxGeometry').attrib.update(x=str(x),y=str(y),width=str(w),height=str(h))
    for group, back, label in [
        ('31','30','25'), ('33','27','26'), ('36','29','9'),
    ]:
        prefix = 'RkxC13zxXOI5UCIjbvwe-'
        cells[prefix+group].find('mxGeometry').attrib.update(x='20',width='122')
        cells[prefix+back].find('mxGeometry').attrib.update(x='0',width='122')
        cells[prefix+label].find('mxGeometry').attrib.update(x='0',width='122')
    cells['RkxC13zxXOI5UCIjbvwe-37'].find('mxGeometry').attrib.update(x='10',width='141')
    # Fix light/dark CSS so the exported paper colors are deterministic.
    for c in cells.values():
        for attr in ['style','value']:
            value = c.get(attr, '')
            value = re.sub(r'light-dark\((#[\da-fA-F]+),\s*#[\da-fA-F]+\)',r'\1',value)
            c.set(attr,value)
    tree.write(HERE / 'p1_algorithm_flowchart_paper.drawio',encoding='utf-8',xml_declaration=True)


def revise_p2():
    # A balanced three-column snake follows the user's soft pink original.
    # All text backgrounds are explicitly transparent, including edge labels.
    k = 37.8
    width, height = 15.9, 9.12
    transparent = 'labelBackgroundColor=none;fontBackgroundColor=none;'
    node_style = ('rounded=0;whiteSpace=wrap;html=1;fillColor=#F5CCD0;'
                  'strokeColor=#B98585;strokeWidth=1;shadow=0;fontFamily=SimSun;'
                  'fontColor=#352B2C;fontSize=13;spacing=3;' + transparent)
    mxfile = ET.Element('mxfile', host='Electron', version='29.6.6')
    diagram = ET.SubElement(mxfile, 'diagram', name='论文版：均衡布局', id='p2-paper-20260912')
    model = ET.SubElement(diagram, 'mxGraphModel', grid='0', page='1',
                          pageWidth=str(width*k), pageHeight=str(height*k), shadow='0')
    root = ET.SubElement(model, 'root')
    ET.SubElement(root, 'mxCell', id='0')
    ET.SubElement(root, 'mxCell', id='1', parent='0')

    def vertex(ident, x, y, w, h, text='', style=node_style, size=13):
        value = markup(text, size).replace('font-weight:normal;',
                                          'font-weight:normal;background:transparent;')
        cell = ET.SubElement(root, 'mxCell', id=ident, value=value,
                             style=style, vertex='1', parent='1')
        ET.SubElement(cell, 'mxGeometry', x=str((x-w/2)*k), y=str((y-h/2)*k),
                      width=str(w*k), height=str(h*k), attrib={'as':'geometry'})
        return cell

    def edge(ident, source, target, side1, side2, pts=()):
        sides = {'e':(1,.5),'w':(0,.5),'s':(.5,1),'n':(.5,0)}
        ex, ey = sides[side1]; ix, iy = sides[side2]
        style = ('endArrow=classic;endSize=6;html=1;rounded=0;strokeColor=#AB7476;'
                 f'strokeWidth=1.05;exitX={ex};exitY={ey};entryX={ix};entryY={iy};'
                 'exitDx=0;exitDy=0;entryDx=0;entryDy=0;edgeStyle=none;' + transparent)
        cell = ET.SubElement(root, 'mxCell', id=ident, value='', style=style,
                             edge='1', parent='1', source=source, target=target)
        geo = ET.SubElement(cell, 'mxGeometry', relative='1', attrib={'as':'geometry'})
        if pts:
            arr = ET.SubElement(geo, 'Array', attrib={'as':'points'})
            for x,y in pts:
                ET.SubElement(arr, 'mxPoint', x=str(x*k), y=str(y*k))
        return cell

    background = ('rounded=0;html=1;fillColor=#FCF2F2;strokeColor=#C8A2A3;'
                  'strokeWidth=.9;dashed=1;dashPattern=9 7;' + transparent)
    vertex('background', width/2, height/2, width, height, style=background)
    vertex('score-background', 7.95, 4.83, 5.04, 8.14, style=(
        'rounded=0;html=1;fillColor=#F9E6E8;strokeColor=none;' + transparent))
    heading = ('text;html=1;align=center;verticalAlign=middle;fillColor=none;'
               'strokeColor=none;fontFamily=SimSun;fontColor=#493537;' + transparent)
    for ident,x,text in [('h1',2.7,'信息约束与候选构造'),
                         ('h2',7.95,'逐候选计算评分'),
                         ('h3',13.2,'分层选点与输出')]:
        vertex(ident,x,.88,4.6,.4,text,heading)

    for args in [
        ('input',2.7,1.75,4.1,1.05,'第一检测点与第一示向度\n误差界、移动预算 L'),
        ('prior',2.7,3.35,4.1,1.05,'构造第一观测相容区域 U₁\n并入目标圆与距离约束'),
        ('safe',2.7,4.95,4.1,1.44,'构造四圆盘安全域 C<sub>safe</sub>\n结合移动预算及5米条件\n确定正常测向候选域 F'),
        ('generate',2.7,6.55,4.1,1.36,'按本层步长生成候选点\n保留旧点，补充镜像点\n与安全边界点'),
        ('candidate',2.7,8.15,4.1,1.05,'取本层候选点 q∈F\n依次计算单点评分'),
        ('analytic',7.95,8.15,4.1,1.05,'先计算解析上界 A(q)\n构造 Q(q)，置 b₀=0'),
        ('cell',7.95,6.55,4.1,1.36,'逐读数单元求直径 Dₖ\n几何约束同步半步增宽\n更新 bₜ=max{bₜ₋₁,Dₖ}'),
        ('full',7.95,1.75,4.1,1.05,'完整扫描：B(q)=bₜ\nC(q)=min{A(q),B(q)}'),
        ('aggregate',13.2,1.75,4.1,1.05,'汇总本层全部候选评分\n更新当前优选点'),
        ('final',13.2,4.95,4.1,1.05,'按0.1°读数网格统一精度\n复核全部已访问候选'),
        ('output',13.2,6.55,4.1,1.05,'输出推荐第二检测点\n及近优候选区域代表点'),
        ('posterior',13.2,8.15,4.1,1.05,'获得实际第二示向度后\n构造后验外包并求直径'),
    ]:
        vertex(*args)
    diamond = ('rhombus;html=1;whiteSpace=wrap;fillColor=#F3D0D4;'
               'strokeColor=#B98585;strokeWidth=1;fontFamily=SimSun;'
               'fontColor=#352B2C;fontSize=13;' + transparent)
    vertex('early',7.95,4.95,3.9,1.05,'bₜ≥A(q)？',diamond)
    vertex('complete',7.95,3.35,3.9,1.05,'全部单元已扫描？',diamond)
    vertex('levels',13.2,3.35,4.1,1.05,'预设搜索层已完成？',diamond)

    for a,b in [('input','prior'),('prior','safe'),('safe','generate'),
                ('generate','candidate'),('aggregate','levels'),
                ('levels','final'),('final','output'),('output','posterior')]:
        edge(a+'-'+b,a,b,'s','n')
    edge('candidate-analytic','candidate','analytic','e','w')
    for a,b in [('analytic','cell'),('cell','early'),
                ('early','complete'),('complete','full')]:
        edge(a+'-'+b,a,b,'n','s')
    edge('full-aggregate','full','aggregate','e','w')
    edge('early-aggregate','early','aggregate','e','w',
         [(10.55,4.95),(10.55,1.75)])
    edge('complete-cell','complete','cell','w','w',
         [(5.25,3.35),(5.25,6.55)])
    edge('levels-generate','levels','generate','e','w',
         [(15.64,3.35),(15.64,.23),(.24,.23),(.24,6.55)])
    for ident,x,y,w,h,txt,size in [
        ('early-no',8.23,4.15,.45,.34,'否',12),
        ('complete-yes',8.23,2.55,.45,.34,'是',12),
        ('complete-no',5.47,3.67,.42,.34,'否',12),
        ('early-yes',10.17,5.41,1.92,.65,'是：C=A\n停止该点扫描',11),
        ('levels-yes',13.48,4.15,.45,.34,'是',12),
        ('levels-no',15.43,3.09,.40,.34,'否',12),
        ('refine-label',7.95,.44,10.6,.35,
         '围绕当前优选点缩小步长，进入下一层',11),
    ]:
        vertex(ident,x,y,w,h,txt,heading,size)
    ET.ElementTree(mxfile).write(HERE/'p2_algorithm_flowchart_paper.drawio',
                                encoding='utf-8',xml_declaration=True)


if __name__ == '__main__':
    revise_p1()
    revise_p2()
