# Protein to CB 🧬

**在 Codex 中说出蛋白名称和突变，自动寻找结构、检查覆盖并调用 Conformational Biasing。**

> 用 CB 分析人源 STING 的 WT 和 G166E，自动找合适的参考构象，解释结果。

这层工作流把 RCSB PDB／UniProt 接到作者的 CB 方法之前，保留结构来源、序列背景、编号映射与评分记录。科学模型和评分方法来自 [Ting Lab 的 ConformationalBiasing](https://github.com/alicetinglab/ConformationalBiasing)；本项目提供聊天流程、工具封装、输入检查和安装维护。

## 日常怎么用

在 Codex 中自然地提出请求，或使用 `$protein-to-cb`：

- “查找人源 STING 可以用于 CB 的两种构象。”
- “用这些参考结构评估 WT 和 G166E，给我解释分数。”
- “我只有蛋白名，没有 mutant 的 PDB，检查能不能评分。”

只给蛋白名时，先完成身份解析与结构可用性检查；聊天里已有明确的突变面板就继续评分。物种不明确时会询问；没有可靠第二构象或目标位点未解析时会说明缺口。不会把搜索列表最前面的两个结构自动视为两个生物学状态，也不会自行扩大突变面板。

**Mutant 不需要自己的 PDB。** 将 mutant 序列分别放在两份已选择的参考状态主链上评分即可；前提是位点在两个状态中均有正确映射。CB 不生成 mutant 的新三维结构。

## 首次安装

已验证：macOS arm64、Python 3.12、CPU。其他系统/GPU尚未完成同等数值验收。需要网络安装依赖和查询公共数据库；不需要 PDB／UniProt API key。Codex 本身需要已可用。

从本仓库目录运行一次：

```sh
python3.12 scripts/setup.py
python3.12 scripts/install_codex.py
```

然后重启 Codex 或 MCP 连接。此后日常操作在聊天中完成。安装会保留其他 Codex 设置，修改配置前建立私有备份；已有同名但指向其他位置的连接会保留并停止安装，避免覆盖正在使用的版本。已经装好原始流程的用户可以继续使用，维护本仓库不要求重新安装。

已有兼容环境时可用 `python3.12 scripts/setup.py --reuse-python /absolute/path/to/python`，不会向该环境安装软件包。运行环境位置保存在被 Git 忽略的本地文件中。预览 Codex 配置可运行 `python3.12 scripts/install_codex.py --preview`。

## 结果怎么看

输出包含结构来源、参考背景、共享覆盖、完整序列表、每态原始分数、相对 WT 差值及原生标准化分数。每次运行产生独立结果目录。

- 原始分数越高，表示模型下序列与固定主链越相容。
- `mutant − WT < 0` 表示该状态的相容性下降，不能直接称为活性降低。
- 两态差值只能提出构象偏向线索；不是自由能、状态概率或活性倍数。
- 仅有 WT 和一个 mutant 时，面板标准化可能退化。两个状态同向变化会得到相同的 ±1，最终 bias 为 0；这不证明没有构象效应。
- 激活、结合、酶活或选择性需要状态与功能的独立证据；这套工具不是通用功能预测器。

详见 [分数与原文实验解释](docs/scoring.md)。

## 检查与维护

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/check_runtime.py --score --network
```

第二行启动两台真实 MCP 服务器，检查固定源码／权重，运行三变体 LplA 数值验收，并做公共数据库查询。其他系统存在浮点差异时应单独评估；不要放宽容差来掩盖原因。输出记录在被 Git 忽略的 `runs/doctor/`。如果复用环境，使用该环境解释器替换 `.venv/bin/python`。

GitHub Actions 默认检查轻量单元测试，不声称复现模型分数或生物学实验。版本维护使用普通提交／PR；没有部署自动更新或定时运行。

## 项目结构

| 路径 | 内容 |
|---|---|
| `skills/protein-to-cb/` | Codex 可自动触发的技能、RCSB／UniProt MCP 和面板构建 |
| `backend/` | 已验证的 CB MCP 包、固定上游源码和带模型的 ColabDesign wheel |
| `scripts/` | 一次性环境准备、保留既有设置的配置安装、真实运行检查 |
| `tests/` | 序列／身份／覆盖／配置检查，以及固定 LplA 验收输入 |

后端包含固定的模型 wheel（约 24 MB），不包含 Python 虚拟环境。不会将个人 Codex 配置、登录凭据、论文 PDF 或本地运行目录纳入版本管理。

## 来源与引用

- CB：Cavanagh et al., *Science* (2026), [10.1126/science.adv7953](https://doi.org/10.1126/science.adv7953)。固定代码提交与校验和见 `backend/SOURCE_PROVENANCE.json`。
- ProteinMPNN：[10.1126/science.add2187](https://doi.org/10.1126/science.add2187)。
- [RCSB Search API](https://search.rcsb.org/)／[Data API](https://data.rcsb.org/) 与 [UniProt REST](https://www.uniprot.org/help/api)。
- 第三方版权和许可证见 [backend/THIRD_PARTY_NOTICES.md](backend/THIRD_PARTY_NOTICES.md)。本项目的工作流集成代码使用 MIT；第三方内容保留各自许可。

