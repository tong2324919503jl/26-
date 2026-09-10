# 2026 国赛 B 题

本仓库已选择 **B题：无线电干扰源的快速自动定位与清除**。前两问已将当前实现与队友提交的 ZIP 取长补短，统一在 `problem1/`、`problem2/` 中维护；包含模型说明、可运行算法、自建算例和本地验证。

## 从这里开始

| 入口 | 内容 |
| --- | --- |
| [B题资料](materials/problem_b/README.md) | 完整题面、两份原附件、可检索文本和原文件对照 |
| [问题1](problem1/README.md) | 精确半平面判别、旋转卡壳直径、覆盖圆与 20 米定位判据 |
| [问题2](problem2/README.md) | 四圆盘收信保证、目标圆条件化、连续读数上界与多层选点 |
| [验证报告](validation/report.md) | 文件完整性、算法测试、跨目录运行结果 |
| [合并说明](validation/merge_notes.md) | 两份方案的具体取舍、来源记录与同口径结果比较 |
| [工作约定](AGENTS.md) | 新文件命名、放置与后续协作规则 |

## 目录结构

```text
26-/
├── materials/problem_b/
│   ├── statement.pdf              # B题完整题面，含附录
│   ├── attachments/               # 两份原始Word附件的完整副本
│   ├── extracted/                 # UTF-8检索文本
│   ├── manifest.json              # 原路径、新路径、大小和SHA-256
│   └── README.md
├── problem1/
│   ├── solve.py                   # 第一问运行入口
│   ├── examples/                  # 自建输入
│   ├── results/                   # 计算结果
│   ├── tests/                     # 数学与程序验证
│   └── README.md                  # 模型和使用方法
├── problem2/
│   ├── solve.py                   # 第二问运行入口
│   ├── compare_strategies.py      # 同口径基线、预算与精度比较
│   ├── examples/
│   ├── results/
│   ├── tests/
│   └── README.md
├── scripts/
│   ├── prepare_materials.py       # 复制校验资料、重建检索文本
│   ├── verify_project.py          # 统一验证入口，含策略比较
│   └── verify_reference.py        # 可选的独立 HiGHS 几何核验
├── validation/                    # 验证报告
├── CUMCM2026Problems/             # 保留的原始完整题包
├── requirements.txt
└── AGENTS.md
```

根目录既有的选题难易度分析、文献清单和赛区注意事项保留，供回看。原始题包中的 A、C 题未调整。

## 运行

使用 Python 3.10 或以上版本。在仓库根运行：

```powershell
python problem1/solve.py
python problem2/solve.py
python scripts/verify_project.py
```

两问的默认输入来自各自 `examples/`，输出写入各自 `results/`。支持从任意目录使用脚本绝对路径启动；具体自定义参数见每问的 `README.md`。求解和统一验证不需要联网，也不需要模拟器账号。

单独重建策略比较可运行 `python problem2/compare_strategies.py`。若已安装 SciPy，可用 `python scripts/verify_project.py --reference` 加做独立求解器交叉核验；核心算法和默认验证仍只使用 Python 标准库。

队友原始 ZIP 保持不变，合并后的运行不依赖解压目录或 ZIP 内另一套工程。来源及采纳内容见合并说明。

如需重新提取题面文本：

```powershell
python -m pip install -r requirements.txt
python scripts/prepare_materials.py
```

原材料副本若被改动，整理脚本将停止并报告，不覆盖改动。完整性清单保留三份原材料及检索文本的哈希，统一验证会逐项核对。

## 结果的适用范围

第一问区分定位区域直径和最小覆盖圆，并用直径 40 米的有效测向反例说明为什么不能仅凭 `D≤40` 保证 20 米光学定位。第二问在安全域内用更紧的几何外包上界选点，保留解析上界作为快速基线；选点比较统一评分设置，不将上界的收紧等同于真实误差下降。离散搜索的结果受所选指标、网格步长等设置影响，未证明连续全局最优。

题面与附件没有给前两问的具体测量数据，`examples/` 中均是明确标注的自建算例。验证结果是本地算法检查，不是问题3、4的模拟器演练或正式测试成绩。本次未进行问题3、4的求解与正式测试。
