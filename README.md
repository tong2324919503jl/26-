# 2026 国赛 B 题

本仓库已选择 **B题：无线电干扰源的快速自动定位与清除**。本次完成问题1、问题2的独立目录、模型说明、可运行算法、自建算例和本地验证。

## 从这里开始

| 入口 | 内容 |
| --- | --- |
| [B题资料](materials/problem_b/README.md) | 完整题面、两份原附件、可检索文本和原文件对照 |
| [问题1](problem1/README.md) | 示向扇形交会、定位多边形直径与覆盖圆 |
| [问题2](problem2/README.md) | 第二检测点选择策略、候选区域与定位指标 |
| [验证报告](validation/report.md) | 文件完整性、算法测试、跨目录运行结果 |
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
│   ├── examples/
│   ├── results/
│   ├── tests/
│   └── README.md
├── scripts/
│   ├── prepare_materials.py       # 复制校验资料、重建检索文本
│   └── verify_project.py          # 统一验证入口
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

如需重新提取题面文本：

```powershell
python -m pip install -r requirements.txt
python scripts/prepare_materials.py
```

原材料副本若被改动，整理脚本将停止并报告，不覆盖改动。完整性清单保留三份原材料及检索文本的哈希，统一验证会逐项核对。

## 结果的适用范围

第一问给出计算方法，并区分定位区域直径和最小覆盖圆。第二问给出可解释的选点准则与候选区域；离散搜索的结果受所选指标、网格步长等设置影响。

题面与附件没有给前两问的具体测量数据，`examples/` 中均是明确标注的自建算例。验证结果是本地算法检查，不是问题3、4的模拟器演练或正式测试成绩。本次未进行问题3、4的求解与正式测试。
