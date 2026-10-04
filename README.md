# cogengine-legal

[中文](README.md) · [English](README.en.md)

**处理法律关系信息的基础工具。** 当前以合同为应用对象，将合同规定的权利义务、条件、限制及相互联系，整理为带原文依据的结构化记录，供查询、复核和后续应用使用。

核心产出是一份 SQLite 合同数据库，包含原件、全文、关系记录、出处和修订历史。项目以“读库即读合同”为目标：使用者能够取得合同规定的内容，并逐项返回原文核对。

## 项目解决的问题

使用 agent 处理合同，一次正确的结果并不足以证明同一方法能够持续、可靠地用于业务。上下文组织可以改善阅读和理解的条件，实际结果仍需要核对，遗漏和误解也需要能够定位、修正。

本项目让 agent 按共同的记载规则提取法律关系，由程序检查并保存结果。合同内容、原文依据和更正历史形成可持续维护的记录，供后续任务共同使用。合同审查、履约管理和争议分析等应用，可以在这些记录上加入各自的规则、事实和判断。

关于项目的完整思路，见[工程师版文章](docs/legal-relations-engineering.md)和[律师版文章](docs/legal-relations-engineering-for-lawyers.md)。

## 输入与产出

### 需要提供什么

- **合同材料**：一份合同及其组成文件，例如正文、附件和补充协议。
- **经审定的词表**：约定法律关系的类别、需要记载的事项及其表达方式。词表由使用者准备，也可以通过本项目的初始化 skill 归纳并审定。
- **转换配置**：需要处理 Word、PDF 或扫描件时，明确指定实际转换程序及其调用方式。
- **工作目录**：指定合同数据的存放位置；同一合同后续处理沿用原有目录。

### 会得到什么

| 产出 | 内容及用途 |
|---|---|
| 合同数据库 `contract.sqlite` | 原件、全文、案件所用词表、主体和法律关系、具体条件与数值、出处及修订历史。可查询、核对和整体移交。 |
| 合同工作目录 | 保存输入工作副本、转换文本、阅读笔记、提取文件、工具回执和报告，供续做与排查问题。 |
| 本轮交接结果 | 说明数据库位置、处理范围、对账结果、未完成内容，以及材料或表达能力的限制。 |

新合同的数据集中保存在指定工作根下的 `contract-YYYYMMDDTHHMMSSZ[-NN]/` 中，数据库位于该目录根部。程序安装目录与合同工作目录各自独立。

## 一个简短示例

以下是一段自拟约定：

> 甲方为买方，乙方为卖方。合同总价为 100 万元。买方应在验收合格后 30 日内，向卖方支付合同总价的 20%。

这项安排可以表示为以下相互关联的内容：

| 内容 | 记载示意 |
|---|---|
| 当事人 | 甲方为买方，乙方为卖方 |
| 付款关系 | 买方承担付款义务，卖方受领付款 |
| 金额依据 | 合同总价为 100 万元；本次付款按总价的 20% 计算 |
| 付款期限 | 验收合格后 30 日内 |
| 原文依据 | 主体称谓、总价、付款及起算条件分别对应支持它们的原句 |

查询这项付款义务时，可以取得金额、计算依据和期限，再沿出处核对原文。记录保留“合同总价 × 20%”及“验收合格后 30 日内”的含义；其中记载的验收条件，并不表示验收已经实际发生。

## 提供哪些工具

项目包含四个供 agent 使用的 skill，以及三个承担具体操作的命令行工具。skill 说明如何组织任务、阅读材料和交接结果；CLI 执行数据校验、保存和查询。

### 四个 skill

| Skill | 用途 |
|---|---|
| [`legal-preprocess`](src/skills/legal-preprocess/SKILL.md) | 调用已配置的外部转换程序，将原件转为可登记的文本和元数据。 |
| [`legal-case`](src/skills/legal-case/SKILL.md) | 组织单份合同的入库、阅读与关系提取，提交结果并完成查询、对账和纠错。 |
| [`legal-initialize`](src/skills/legal-initialize/SKILL.md) | 从指定语料归纳首版词表，通过文件意见完成人工审定。 |
| [`legal-vocab`](src/skills/legal-vocab/SKILL.md) | 根据案件缺口或专业人员提出的要求，维护和调整词表。 |

### 三个 CLI

| 命令 | 用途 |
|---|---|
| `legal-preprocess` | 执行转换配置，核对转换产物。 |
| `legal-case` | 初始化合同库、登记材料、切分条款、写入、查询、分组和对账。 |
| `legal-vocab` | 创建、查阅、变更和比较词表，汇总案件中的词表缺口。 |

四个 skill 共用同一套 CLI。三个命令安装在一个专用 Python 环境中；安装后的 skill 根据安装信息调用命令，无须每次手动激活环境。

## 如何开始使用

### 推荐：让 agent 帮你安装

将下面这段话复制给 agent：

```text
请帮我安装并配置 cogengine-legal。项目地址：https://github.com/lukeruc/cogengine-legal。请先阅读项目 README 及其中链接的安装说明，再按文档完成安装配置。
```

### 1. 准备运行条件

- **Python 3.11、3.12 或 3.13**，带有 `sqlite3`、`venv` 和 pip；构建还需要 `setuptools>=68` 与 `wheel`。
- **能够运行 skill 的 agent 宿主**：支持读取完整 skill 目录及其引用文件、运行本地命令、组织子任务，并支持通过文件接收人工意见。
- **适用的正式词表**。合同入库前需要具备词表；尚无词表时，可在完成安装和 skill 注册后，通过 `legal-initialize` 归纳并审定。归纳与验收材料的用途由使用者指定。
- **实际文档转换程序及配置**。Word、PDF、OCR 的转换能力由外部程序提供，具体支持的文件格式取决于所配置的程序。

核心 Python 程序没有第三方运行依赖。agent 宿主、模型和外部转换程序需另行准备。

### 2. 安装程序并注册 skill

取得完整仓库，在仓库根目录执行以下命令；将示例绝对路径替换为本机路径：

```bash
cd src
PYTHON_BIN=/absolute/path/to/python
DIST_DIR=/absolute/path/to/legal-dist
INSTALL_ROOT=/absolute/path/to/legal-install

"$PYTHON_BIN" scripts/build_release.py --output-dir "$DIST_DIR" --python "$PYTHON_BIN"
"$PYTHON_BIN" scripts/install_release.py \
  --install-root "$INSTALL_ROOT" \
  --python "$PYTHON_BIN" \
  --wheel "$DIST_DIR/cogengine_legal-0.1.0-py3-none-any.whl"
```

安装脚本创建或复用安装根中的 `.venv`，安装三个命令，并复制四个 skill 和共用资料。随后按宿主已有机制，注册 `<install-root>/skills/` 下的四个完整 skill 目录，并使用[注册核对脚本](src/scripts/verify_registration.py)核对。

程序安装成功回执中的 `"host_registration":"pending"` 表示还需完成宿主注册。详细操作、路径绑定和故障处理见[安装与使用说明](src/README.md)。

### 3. 处理第一份合同

完成注册并准备好词表和转换配置后，可以向 agent 提供以下请求，将路径替换为实际文件位置：

```text
请使用 legal-case，将以下材料作为一份合同入库：

合同原件：/absolute/path/to/contract.docx
附件：/absolute/path/to/appendix.pdf
正式词表：/absolute/path/to/vocabulary.json
DOCX 转换配置：/absolute/path/to/docx-converter.json
PDF 转换配置：/absolute/path/to/pdf-converter.json
合同工作根目录：/absolute/path/to/contracts

请返回合同工作目录、数据库路径、本轮对账结果和仍未完成的事项。
```

agent 会按 skill 建立合同工作目录、准备材料、组织阅读与提取，并通过 CLI 校验和写入。交接后，可继续要求 agent 查询该合同中某一方的义务、条件及原文依据；开发者也可以直接调用 CLI，查询参数见[案件命令说明](src/references/case-cli.md)。

## 当前范围与状态

- **范围**：针对一份合同及其组成文件，记录文本规定的内容。实际履行情况、条款效力及跨合同组合分析由后续应用处理。
- **版本**：当前源码版本为 `0.1.0`；GitHub 尚未创建 Tag 或 Release。上述步骤从源码构建安装。
- **实现**：已提供四个 skill、三个 CLI、安装及注册核对脚本；[自动化测试](src/tests/)随源码维护。
- **质量边界**：程序可检查格式、引用、出处和条款覆盖等明确约束。校验通过仍不能证明合同含义已经完整、准确地表达，实际提取质量需要结合具体合同检验。
- **词表与材料**：词表的适用范围、原件质量和模型表现都会影响结果。无法表达或材料不足的内容须在交接中说明；没有查询到记录，不能直接推定合同未作约定。

## 文档导航

| 阅读目的 | 入口 |
|---|---|
| 了解项目思路与技术原理 | [法律关系的工程化表达](docs/legal-relations-engineering.md) · [English](docs/legal-relations-engineering.en.md) |
| 从法律工作的角度了解项目 | [法律关系的工程化表达（律师版）](docs/legal-relations-engineering-for-lawyers.md) · [English](docs/legal-relations-engineering-for-lawyers.en.md) |
| 安装、注册、升级与故障处理 | [安装与使用说明](src/README.md) |
| 查询命令与输入输出格式 | [案件 CLI](src/references/case-cli.md) · [词表 CLI](src/references/vocab-cli.md) · [预处理 CLI](src/references/preprocess-cli.md) · [数据格式](src/references/data-formats.md) |
| 浏览对外文档 | [文档目录](docs/README.md) |
