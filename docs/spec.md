# 法律关系建模底座 — 实现与验收规格

> 本文件与 `design.md` 共同组成规格。本文把设计中的输入、状态变化、输出和验收条件写成确定规则；用户已于 2026-09-26 明确转入代码实现（decisions §1.34）。代码目录约束见 §1，原规格阶段的裁决及外部组件边界见 §15。

## 1. 范围、文件布局与规格效力

### 1.1 代码位置与完整目录

**所有项目代码必须位于 `/home/luke/projects/cogengine/legal/src` 之下。** 包括生产代码、测试代码、命令入口、预处理适配代码、辅助脚本、SQL 建库及迁移脚本、供工具执行的规格校验代码。不得另在 `legal/tests`、根目录 `scripts` 等位置放置代码。

七件交付物作为一个完整目录交付，源码根为 `legal/src`。CLI 是程序入口，skill 是工作流说明入口，两者共用同一套实现；七件交付物不等于七份独立复制的程序。以下布局为路径规格；实现已按用户后续指示开始：

| 路径（相对 `legal/`） | 内容 |
|---|---|
| `src/README.md` | 完整目录的使用说明：运行前提、目录、宿主注册、路径解析、三个 CLI 的启动方法与转换器配置 |
| `src/legal/` | Python 包；`__init__.py`、三个 CLI 入口及 design §17.1 的共用模块 |
| `src/legal/schema.sql` | 按本文 §7 实现的完整建库脚本 |
| `src/legal/config/units.v1.json` | §5.3 的首版单位配置；不含默认法律词表 |
| `src/skills/` | 四个 skill；每个有独立目录和 `SKILL.md`，详见 §1.3—§1.4 |
| `src/references/` | 四个 skill 共用的三个 CLI 用法和数据格式说明，详见 §1.4 |
| `src/tests/` | 自动验收测试及仅供测试使用的夹具 |
| `src/scripts/` | 仅在确有需要时设置的开发、检查辅助脚本；不放第四个业务 CLI |
| `docs/` | 设计、规格、决策及历史讨论；文档内语法和 SQL 块是规格正文 |
| `material/` | 语料及用途清单，不属于代码 |

`src/legal` 是 Python 包目录，`legal/src` 是其父目录；两个 `legal` 分别是项目目录与包名，不代表两套程序。三个模块入口从 `legal/src` 启动。具体对应见 §1.3；宿主如何找到 skill 与程序见 §1.5。

入口位置一览（未来目录，省略共用 Python 模块和具体参考文件）：

```text
legal/
├── docs/                         设计与裁决
├── material/                     开发语料
└── src/                          完整交付目录的根
    ├── README.md                 通用使用说明
    ├── legal/                    共用 Python 包
    │   ├── preprocess_cli.py     预处理 CLI
    │   ├── case_cli.py           案件 CLI
    │   └── vocab_cli.py          词表 CLI
    ├── skills/
    │   ├── legal-preprocess/SKILL.md
    │   ├── legal-case/SKILL.md
    │   ├── legal-vocab/SKILL.md
    │   └── legal-initialize/SKILL.md
    ├── references/               共用工具用法与数据格式
    └── tests/                    开发验收代码与夹具
```

### 1.2 约束层次

1. 最新用户裁决优先；`decisions.md` 留存已确认事项。
2. `principles.md` 规定目的与边界；`design.md` 说明结构、流程及理由。
3. 本文规定对应实现的精确契约。不能以宽松接受未知字段、静默补值或自动推断替代契约。
4. 本文的测试词表、合同短句及 ID 仅作夹具，不构成正式词表或真实合同验收结论。
5. “必须”是验收要求。没有实现或未执行的验收，不得记为通过；规格的文档检查不等于系统验收。

规格版本为 `1`；案件 schema、交换格式、值语法和性质代码各自为 `1`。实现须分别保存和校验，不以一个版本号替代全部。首版只支持上述1版，遇到其他格式读写均报 UNSUPPORTED_VERSION；未来支持旧版时须另有解释器与用例。运行前提是 Python 标准库及其 SQLite；不依赖第三方 JSON/YAML/数据库包。文件访问、数据库异常和不支持的格式必须按 §9 返回，不擅自迁移。

### 1.3 七件交付物逐项定位

以下均为相对 `legal/src/` 的未来路径。CLI 文件是入口，其可运行内容还包括同目录的共用模块、SQL 与配置；不能只复制入口文件。skill 的交付内容包括 `SKILL.md` 及其引用资源，也不能只复制一份入口说明。

| 交付物 | 入口路径 | 启动或识别名称 | 直接依赖 | 输入与最终交接 |
|---|---|---|---|---|
| 预处理 CLI | `legal/preprocess_cli.py` | `python -m legal.preprocess_cli` | `preprocessing`、`formats`；显式配置的外部转换程序 | 原件、转换配置、输出目录 → `text.txt`、`metadata.json`、JSON 回执；§9.7 |
| 案件 CLI | `legal/case_cli.py` | `python -m legal.case_cli` | 存储、切分、校验、查询等共用模块及 SQL/单位配置 | 词表、材料、记录或查询参数 → SQLite 案件库、回执、导出或对账结果；§9.1—§9.4、§11 |
| 词表 CLI | `legal/vocab_cli.py` | `python -m legal.vocab_cli` | `vocabulary`、`formats`、案件只读查询模块 | 词表、变更或案件清单 → 词表、差异或缺口汇总；§9.5 |
| 预处理 skill | `skills/legal-preprocess/SKILL.md` | `name: legal-preprocess` | 预处理 CLI 及其用法说明 | 转换要求 → 经校验的路径、哈希、异常或明确失败；§10.2 |
| 案件 skill | `skills/legal-case/SKILL.md` | `name: legal-case` | 案件 CLI、预处理 skill、读手说明 | 某合同全部素材、词表、案件/工作路径 → 案件库及当前对账结果；§10.3、design §16.3 |
| 词表治理 skill | `skills/legal-vocab/SKILL.md` | `name: legal-vocab` | 词表 CLI；涉及原始证据转换时用预处理 skill | 明确案件清单或律师要求、当前词表、人工意见 → 经工具执行的变更与摘要；§10.5 |
| 初始化 skill | `skills/legal-initialize/SKILL.md` | `name: legal-initialize` | 词表 CLI、预处理 skill、两遍归纳读手说明；建模验收使用案件 skill | 用户分配用途的语料、两道人审意见 → 词表 v0、证据包、判定表；§10.4、design §16.4 |

四个 skill 的 `name` 固定如表，目录名与之相同。每个 `SKILL.md` 均以 YAML frontmatter 声明 `name` 与 `description`；description 必须写清适用任务：文件转换、合同建模入库、已有词表治理、从语料生成首版词表。不得把“案件 init”和“词表初始化归纳”写成同一个触发条件。正文包含输入、依赖读取、已批准步骤、工具用法、输出及失败/恢复规则。

### 1.4 运行时说明与引用文件

以下为完整目录必须携带的说明文件。它们是七件交付物的组成部分，不另计为独立交付物；未来编写时根据对应规格整理，不要求使用者另取本项目 `docs/` 才能运行。表中的“依据”用于实现追踪，不作为运行时跨目录读取要求。

| 路径（相对 `legal/src/`） | 必须包含的内容 | 依据 |
|---|---|---|
| `README.md` | §1.5 的通用注册与运行约定；原件转换为外部依赖；七个入口索引；输出路径规则 | §1、§9.7 |
| `references/preprocess-cli.md` | 全部参数、转换配置、外部程序协议、两文件输出、哈希、错误、register 交接示例 | §9.7 |
| `references/case-cli.md` | 已批准的七个命令、参数及互斥规则、查询/导出、回执、重放、版本冲突、对账状态 | §8—§9、§11、design §15.1—§15.2 |
| `references/vocab-cli.md` | 初始化/查询/增删/diff/聚合、混合变更、哈希冲突、孤立槽处置、正式文件唯一写入口 | §9.5、design §15.3 |
| `references/data-formats.md` | JSON 基础规则、词表与值结构、记录信封、全部记录类型/来源/引用、概要和任务交接、合法样例及常见错误；足以构造完整提交 | §2—§6、§10、design §4、§14 |
| `skills/legal-case/references/preparation.md` | 通读与事件认定任务的输入、概要及 preparation 产物、参与者/同一事项复用、先写入取得 ID 的交接 | §10.1、design §16.3 第3环节 |
| `skills/legal-case/references/tagging.md` | 不重叠条款批次、完整标签修订、无匹配缺口；不把标签产物当完整关系提取 | design §16.3 第4环节 |
| `skills/legal-case/references/extraction.md` | 负责集/上下文集、全部共享上下文、二元建模、出处、完整 JSON、无内容/缺口、回执失败后修正 | §10.1、design §16.3 第5—8环节 |
| `skills/legal-initialize/references/first-pass.md` | 只用归纳语料、逐条款证据、三资格/默认吸并、候选单元及第一道人审文件 | §10.4、design §16.4 |
| `skills/legal-initialize/references/second-pass.md` | 已审单元输入、槽和值结构、归属/证据、第二道人审、三件套及既定检查 | §10.4、design §16.4 |

所有路径以入口文件的**真实目录**为基准解析：每个 `SKILL.md` 读 `../../README.md` 取得运行约定；共用说明用 `../../references/<文件名>`；本 skill 的读手说明用 `references/<文件名>`；预处理交接读 `../legal-preprocess/SKILL.md`；初始化中实际建模验收读取 `../legal-case/SKILL.md`。注册位置是链接时先解析到源目录，不能相对宿主工作目录猜路径。

资源加载要求：预处理 skill 读取预处理用法；案件 skill 读取案件用法和数据格式，派相应读手时附上对应说明；初始化 skill 读取词表用法、数据格式和当前归纳遍次的说明；治理 skill 读取词表用法和数据格式。需要转换时再读取预处理 skill。每个 skill 的“工具用法”部分要说明本流程实际调用哪些命令，并直链上述完整用法；不得仅写“使用适当工具”。

这些引用不会自动创建子会话或调用另一个宿主命令。主会话读取相应说明后，使用所在环境已有的工具执行。子任务需要的数据格式和输入文件由主会话显式交付，不能假设读手继承了主会话已读资料。

### 1.5 通用安装、定位与调用约定

首版保持宿主通用，不指定 Codex、Claude Code 等环境的安装目录、专用命令或配置格式。一个兼容环境必须能够读取 skill 文件及其引用、运行本地进程、使用指定工作目录与文件，并支持既定流程中的子任务调度和人工文件意见交接。具体注册动作使用该环境已有机制；本项目不新增安装 CLI 或调度服务。

1. **完整放置。** 交付至少包含 `README.md`、`legal/`、`skills/`、`references/`，保留彼此相对位置；不依赖原开发机器的 `legal/docs` 或 `contract_v3` 工作区。开发源码还含 `tests/` 等支持资产。使用时可以移动或复制整个目录，`/home/luke/projects/cogengine/legal/src` 仅为本项目源码存放要求，不硬编码进可搬移的运行入口。
2. **注册四个入口。** 将 §1.3 的四个 skill 目录提供给宿主，保证源路径可解析且引用可读取。可以指向源目录，也可以对完整目录的部署副本注册；不能只复制 `SKILL.md` 或单个 skill 目录后宣称已完成安装。宿主若只支持互相隔离的单 skill 包，则不满足本版共用目录的调用约定，不能靠复制 Python 实现形成四套程序。
3. **找到程序。** `SKILL.md` 所在真实目录的上两级即 `src` 根；三个 CLI 均从该根启动。选定可用的 Python 解释器，其标准库须包含 `sqlite3`；SQL 和单位配置相对 Python 包定位，不相对案件工作目录定位。模块内部不依赖宿主 API。
4. **传入明确路径。** 调用方先按用户原工作目录解析用户给出的相对路径，再将绝对路径传给以 `src` 为工作目录的 CLI 进程；清单内相对路径仍按清单位置解释。原件、案件库、词表、任务输出与转换配置不会因启动目录变化而被意外写进源码。通过 argv 数组传参；含空格、中文等路径作为一个参数，不拼 shell 命令。
5. **配置转换能力。** 按 §9.7 给出外部程序配置及其实际依赖。案件/词表 CLI 的 JSON/SQLite 操作不因转换器尚未安装而无法启动；需要转换某份原件时才要求相应能力。未配置转换器不得默认搜索机器上的其他项目或猜测工具。
6. **确认可用。** 四个入口及其全部引用可读取；三个 `--help` 可启动；预处理按配置通过受控输入输出验收。真实格式支持范围另按实际转换器的逐格式集成结果声明。注册成功与合同语义建模通过验收是不同事实。

CLI 启动方式固定为：工作目录=`<完整目录根>`，argv 分别为 `[<Python解释器>,"-m","legal.preprocess_cli",...]`、`[<Python解释器>,"-m","legal.case_cli",...]`、`[<Python解释器>,"-m","legal.vocab_cli",...]`。人工直接使用 CLI 也遵守相同约定，无需先启动 skill。项目不要求固定解释器绝对路径、专用环境变量、pip 安装或单独构建目录。

### 1.6 程序、设计文档与运行产物的区别

| 内容 | 所在位置与作用 |
|---|---|
| 七件可复用交付物及运行时参考 | `legal/src/`；完整目录一起交付，四个 skill 共用三个 CLI |
| 设计与裁决文件 | `legal/docs/`；说明开发依据，供开发与评审使用，不是 skill 运行必需路径 |
| 开发验收测试、夹具、辅助代码 | `legal/src/tests/`、按需 `legal/src/scripts/`；支撑实现，不计入七件独立交付物 |
| 开发语料与用途清单 | `legal/material/` 或用户明确提供的位置；不是工具内置的词表或案例 |
| 案件数据库 | 调用方指定的 `--db`；成功登记的原件、文本和模型随一个 SQLite 文件移交 |
| 正式词表 | 调用方指定的 `--vocabulary`；独立的用户资产，工具不预置领域内容 |
| 转换结果与工作文件 | 调用方指定的输出/工作目录；包括 text/metadata、任务 JSON、意见文件、证据包和报告；文件角色见 §9—§10 |

案件入库和初始化需要一个工作目录，但不强制统一的案件文件夹树，不设全局案件注册表。运行产物不会反向成为七件程序交付物的一部分。

## 2. 通用类型与规范化

### 2.1 输入规则

| 类型 | 精确规则 |
|---|---|
| 字符串 | Unicode 字符串；不得含无法编码为 UTF-8 的孤立代理码点。原文允许空白、换行、组合字符，禁止隐式规范化 |
| 非空字符串 | 必须至少含一个非空白字符；检查不改写保存内容 |
| 整数 | JSON 整数，布尔值不能充当整数；各字段另规定上下界 |
| 十进制字符串 | 见下方正则的整串匹配；不接受指数、加号、分组符 |
| UUID | 小写、带连字符的规范 UUID 字符串；工具新生成 UUID v4；不从名称推导 |
| SHA-256 | 恰好 64 个小写十六进制字符 |
| 时间戳 | UTC，`YYYY-MM-DDTHH:MM:SS.ffffffZ`；仅供管理记录 |
| 路径 | 输入文件路径由调用方提供；相对路径按调用时工作目录解释；清单内路径按清单文件所在目录解释 |
| JSON Pointer | 空串表示整个 `data`；其他以 `/` 开头，按 `~0/~1` 解码。拒绝非法转义、数组的 `-`、非规范下标以及不存在的路径 |

十进制的正则为：

```text
-?(0|[1-9][0-9]*)(\.[0-9]+)?
```

所有契约对象只接受列出的字段。可选字段缺席才使用默认值；`null` 只有明确允许时合法。数组保留顺序；声明为集合的数组拒绝重复，默认不擅自去重。所有 `format_version` 必须是整数 `1`。JSON 文件不接受注释、尾逗号、重复键、非有限数字、UTF-8 BOM 或尾随第二个值。JSON 数字仅用于已规定的整数位置；合同数值始终是字符串。

管理文本，例如 `issues`、异常说明、人工意见，不作为法律断言，不自动生成模型字段。

### 2.2 哈希

定义规范序列化为：对象键按 Unicode 码点排序，保留非 ASCII 字符，不输出多余空白，数组保序，输出 UTF-8；等价于标准库 `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)` 的字节输出。不得先做 Unicode NFC、换行转换或浮点转换。

- **write 提交**：对通过静态格式检查的完整输入对象序列化后 SHA-256；包含 `phase/issues/overview` 等实际提供字段；在补默认值、分配 ID、解析 local 引用之前计算。缺席字段与显式默认值是不同提交内容。
- **词表**：先补齐条目的空列表默认值；unit/slot 按 ID 排序，assignment 按 `(unit_id,slot_id)` 排序；条目内部的 examples、aliases、replaces 保持原顺序，再规范序列化。目录与单文件等价内容得到相同逻辑哈希。
- **单位配置**：单位按 code 排序后规范序列化；包含配置版本、别名等全部内容。
- **原件**：直接对输入字节计算；**全文**：对解码后未修改文本的 UTF-8 字节计算。读文本时保留 CR、LF、CRLF，不使用会统一换行的读取方式。
- **register**：对 `{operation:"register",original_hash,text_hash,metadata}` 的规范序列化计算；metadata 排除原件、文本、元数据文件路径提示。原始路径只在首次成功记录保存，重提不改写它。
- **split**：对 `{operation:"split",text_version_id,algorithm_version}` 计算；algorithm_version 由 §12 固定。

同一案件的哈希唯一性包括命令种类，防止跨命令误命中。成功回执查找在依赖当前版本的验证之前；并发执行须在取得写事务后再查一次。哈希命中后回执中的生成 ID、顺序、时间及计数均复用，只将 `replayed` 置为 true。

## 3. 写入信封、字段与引用

### 3.1 信封

| 字段 | 必需 | 类型、默认值及约束 |
|---|---|---|
| `format_version` | 是 | 1 |
| `case_id` | 是 | UUID，与目标案件一致 |
| `vocabulary_hash` | 是 | SHA-256，与冻结快照一致 |
| `submitted_by` | 是 | 非空字符串 |
| `phase` | 是 | preparation/tagging/extraction/correction |
| `covered_clauses` | 是 | `{object_id,record_id}` 数组；二者确属同一条款；object_id 不重复 |
| `records` | 是 | §3.2 记录数组；可以为空，但不能用空提交声明提取完成 |
| `issues` | 是 | 非空字符串的数组，可以为空 |
| `overview` | 否 | 仅 preparation：`{text_versions:[业务引用],body:非空字符串,authored_by:非空字符串}`；版本列表非空、不重复 |

非 extraction 的 covered_clauses 必须为空。extraction 必须至少声明一个负责条款；correction 可修正相同业务对象，但不会凭此新增提取完成记录。preparation 可仅更新概要，不伪造事件。CLI 不验证提交者字符串是否真是指定 agent；事件的认定权属于 skill 的职责约束，验收须检查任务交接。

### 3.2 单记录

必填 `local_id,kind,data,evidence`。local_id 是非空字符串，批内唯一，不解析其命名含义。可选 `object_id,previous_record_id` 必须同时出现；同时缺席为新对象，同时出现为修订。status 默认 active；只接受 active/withdrawn。仅 withdrawn 必须有非空 withdrawal_reason；active 不接受该字段。

新增对象不得 withdrawn。撤销时 data 和 evidence 须与所撤销前驱的已解析内容相等（对象键顺序不影响相等），不得夹带内容修改；撤销理由单独保存。新对象和修订均返回 local_id 映射。同一 object_id 在一个文件中最多出现一次。

write 接受 clause、anchor、node、relation、detail、reference、gap、no_content；material/text_version 只能由 register 建立。空合同容器只能由 init 建立；write 可修订该唯一容器并补有依据的名称，不能另外创建合同容器。

material/text_version/gap 不允许修订、撤销或恢复。其余记录按 §8 追加完整版本；节点的 node_kind 和关系的 relation_kind 不允许原 ID 改类，改类需撤销旧对象、新建对象。唯一合同容器是案件身份，不能撤销；可以修订其有依据的名称。

### 3.3 三类引用

本节所称“业务引用”和“固定引用”是既有对象引用/版本引用的简写，不增加模型对象。

| 引用位置 | 输入 | 入库后 |
|---|---|---|
| 业务引用 | 恰有 `object_id` 或 `local_id` | `{object_id}`；按当前有效版本解析 |
| 固定引用 | 恰有 `record_id` 或 `local_id` | `{record_id}`；锁定原版本 |
| 值内部分引用 | `{record_id,value_path}`，或在允许固定引用处 `{local_id,value_path}` | `{record_id,value_path}`；路径必须指向目标 data 中 `/value` 本身或其后代 |

固定 local_id 指向本批生成的记录版本，包括修订版本。value_path 只能用于 detail 或 node:defined_value；指向中间 object/list 容器合法，指向名称、出处等非 value 字段非法。`/value2` 不是 `/value` 后代。对象引用不能带 value_path。

固定到历史记录的**业务**引用仍须检查目标对象当前未撤销；固定**证据**引用可以指向后来被撤销的对象。不能通过把业务目标改写成 record_id 绕过撤销依赖校验。锚的条款引用、来源锚、推断前提、历史缺口的位置引用属于证据引用；引用索引依路径和类型判别，不只看是 object_id 还是 record_id。

引用目标不可解析报 REFERENCE_NOT_FOUND，类别不符报 REFERENCE_TYPE_MISMATCH，业务目标撤销报 WITHDRAWN_TARGET。同批引用先分配全部 ID，再校验候选最终视图，无需输入排序。

### 3.4 data 精确字段表

下表 `*` 表示必填。其余字段缺席才取说明中的默认值。`node_kind/relation_kind/reference_kind` 是结构判别字段，不能省略。

| kind | 字段与约束 |
|---|---|
| clause | `text_version*` 业务引用；`sequence*` 正整数；`text*` 原样字符串；`start_offset*,end_offset*` 非负整数；`tags*` UUID 集合；`classification*` unclassified/ordinary/no_content/unmatched；`original_number` 字符串或 null，默认 null |
| anchor | `clause*` 固定条款引用；`quote*` 非空原样字符串（全空白引文也允许，只要非零长度）；`occurrence` 正整数，唯一匹配时默认 1 |
| node:subject | `node_kind*` subject；`canonical_name*` 非空字符串；`identifiers` 默认 []，每项恰为 `{scheme:非空字符串,value:非空字符串}` |
| node:event | `node_kind*` event；`name*,description*` 非空字符串；`participants*` 数组，项恰为 `{subject:主体业务引用,role:非空字符串}`；`object` 为 text/reference 值；`batch_or_stage` 非空字符串。原文未给参与者可用 []，不能补造 |
| node:defined_value | `node_kind*` defined_value；`name*` 非空字符串；`value*` §5 值；`scope` 非空业务目标引用数组，缺席表示合同范围 |
| node:external_benchmark | `node_kind*` external_benchmark；`name*,description*` 非空字符串；不接受 value 字段 |
| node:contract | `node_kind*` contract；`name` 非空字符串；init 仅含 node_kind |
| relation:party | `relation_kind*` party；`unit_id*` 快照 UUID；`parties*` 恰两个 `{subject,nature,functional_labels?}`；subject 指主体，nature 取 design §5.4 八值；functional_labels 为非空字符串数组，默认 []；`modality` 四值或 null，默认 null |
| relation:contract | `relation_kind*` contract；`unit_id*`；`subject*` 唯一合同容器业务引用；`modality` 同上；禁止 parties |
| detail | `owner*` 关系业务引用；`slot_id*` 快照 UUID；`value*` 符合槽结构或显式 null |
| reference | `reference_kind*,from*,to*` 及 §3.5 对应字段；不得混用其他引用类型的专属字段 |
| gap | `clause*` 固定条款引用；`gap_kind*` unmatched_unit/missing_slot/structure_anomaly；`description*,reported_by*` 非空字符串；`suggested_unit_id` 快照 UUID；`related_object` 固定引用 |
| no_content | `clause*` 业务条款引用；`reason*` 非空字符串 |

条款必须满足 `0 <= start_offset <= end_offset <= len(text_version.text)`、text 等于原文切片、tags 属于冻结词表。ordinary 的 tags 非空；其余 classification 的 tags 为空。初次 split 为 unclassified；打标不得改动原文、地址和编号。一般 correction 可修正切分边界，之后以字符覆盖对账检验整组。

parties 必须引用两个不同主体对象；不强制八性质配对，也不依模态补性质。redirect 后两端归入同一节点的情形作为身份冲突展示，工具不得自动删除原关系。

一个关系允许同槽多条 detail；查询全部返回，不取最后一条、不自动覆盖。不通过添加数据库唯一约束禁止合同中并存的规定。

### 3.5 解释性引用的完整类型约束

“规定”在本表严格指 relation 或 detail，不是新记录类别。所有业务引用可取当前对象；只有表内明示的位置可固定版本。

| reference_kind | from | to | 其他字段 |
|---|---|---|---|
| appellation | 固定 clause | 业务 node:subject | 必填 label 非空；scope 可为 material 或 node:contract 的业务引用，默认本合同 |
| role | 业务 node:contract | 业务 node:subject | label 必填非空 |
| composition | 业务 node:contract | 业务 material | label 必填非空 |
| definition | 业务 relation/detail，或固定 clause | 业务 node:defined_value | term 必填非空 |
| event_of | 业务 node:event | 业务 relation | 无 |
| scope | 业务 relation/detail | relation/detail/clause/node 的引用数组，允许固定版本及 value_path | exclude 同类数组，默认 []；to 和 exclude 至少一个非空，各自不重复、交集为空 |
| priority | relation/detail/clause 的业务引用或固定引用 | 同左 | 无 |
| amendment | relation/detail/clause 的业务引用或固定引用 | 同左 | 无 |
| redirect | 业务 node | 相同 node_kind 的业务 node | 两端原始 ID 不同；不得成环 |
| distinct | 业务 node | 业务 node | 两端 ID 不同；允许不同 node_kind；不产生重定向 |

业务 scope 固定到旧版本时，返回该版本内容，不解释成当前值。不同版本即不同目标；工具不把同一对象的不同历史值自动合并。

## 4. 出处覆盖及推断

### 4.1 来源结构

| level | 必填字段 | 禁止混入 |
|---|---|---|
| 1 | `level,anchors`；anchors 非空固定 anchor 引用数组 | II 级格式参数、III 级推断字段 |
| 2 | `level,anchors,surface,format_contract,format_parameters`；surface 非空；其余见 §6 | premises/explanation/asserted_by |
| 3 | `level,premises,explanation,asserted_by`；premises 非空固定记录引用数组，说明、署名非空 | 用 anchors 取代 premises、格式参数 |

每条 evidence 恰有 path 与 source；同一记录的 path 不重复，必须能在 data 定位。父路径的来源覆盖其后代；后代单独给出来源时，以最长匹配路径解释该字段，父路径不掩盖后代来源级。`/a` 不覆盖 `/ab`。

必需覆盖的断言字段：

- node：除 node_kind 及空列表外的所有已填写内容。contract 空容器无断言；其 name 后补即要来源。
- relation：unit_id、每个 subject/nature、每个功能标签、非空 modality；contract 型的 subject 同样要来源。
- detail：owner、slot_id、value，包括 value:null。
- reference：from/to 及 label/term/scope/exclude 的实际内容。
- gap：clause、gap_kind、description 及可选业务指向；reported_by 为管理署名。
- no_content：clause 与 reason。
- clause：tags 非空时覆盖标签判断；已分类时覆盖 classification。text/address/number 是原文定位字段，不需自己为自己作证。split 创建的 unclassified 无来源。

record_id、kind、local_id、status、withdrawal_reason 等管理字段不要求法律出处。anchor 的 evidence 必须 []；锚可指旧条款版本来说明新标签。一个根路径来源可以覆盖同源内容；关系三部分无需为相同引文机械重复填写，但每一部分必须可计算出有效覆盖。

### 4.2 原文与前提

锚出现序号按重叠匹配计算，例如 `aaaa` 中 `aa` 有 0、1、2 三个起点。唯一匹配给 occurrence=2 也报错；不连续引文即使含省略号也按连续字符串验证，不作特殊容错。

每个来源 III 的每个前提必须是带断言来源的记录或 anchor；禁止以 overview、material、text_version、无依据的空合同容器充当前提。遍历其实际来源，所有叶分支都须落到可验证锚；递归栈发现环即报 SOURCE_CYCLE，即便同一环另有一条出路也不能把循环论证当依据。共享非循环子图可以复用，不算环。

来源 I/II 的 anchors 固定版本。语义依据与引文出现位置可以不同：appellation 的 from 固定出现处；其 anchors 还可包含别处定义。机械称谓检查要求 label 是 from 条款的子串，且至少一个来源锚或可追溯前提锚落在该出现条款；不要求每一身份定义锚都含该 label。歧义同名对象并存展示，不据字符串强制合并。

出处查询对每一固定前提返回 `current_record_id` 与 `changed/withdrawn`，不替换该前提内容。原文根链为 anchor → clause → text_version → material；每步的 ID、条款顺序及引文位置均能取得。

## 5. 值语法与单位

### 5.1 基础与容器

所有值恰由 form 或 type 判别；不能同时出现。完整字段如下：

| 形态 | 必填 | 可选及限制 |
|---|---|---|
| quantity | `form:"quantity",amount,unit` | 非空 amount 为十进制字符串；有原文留空依据时可 null，仍保留已知 unit；unit 必须存在于冻结配置 |
| time/date | `form:"time",kind:"date",value,precision` | boundary_text 非空；precision year/month/day；非空值为 YYYY/YYYY-MM/YYYY-MM-DD，年份 0001—9999，日历合法；原文日期栏明确留空时 value 可 null |
| time/relative | `form:"time",kind:"relative",event,offset,relation` | event 业务事件引用；offset 量且为时间单位；relation before/after/within_before/within_after/at；boundary_text 可选 |
| time/duration | `form:"time",kind:"duration",length` | length 非负时间量；boundary_text 可选 |
| time/interval | `form:"time",kind:"interval",start,end` | start/end 可各自为 date、relative 或指事件的 reference 值；boundary_text 可选；不接受 duration 或嵌套 interval |
| condition/event | `form:"condition",operator:"event",event` | 业务事件引用 |
| condition/all、any | `form:"condition",operator,operands` | 至少一个 condition 值；保序 |
| condition/not | `form:"condition",operator:"not",operand` | 恰一个 condition 值 |
| condition/compare | `form:"condition",operator:"compare",left,comparison,right` | comparison eq/ne/lt/le/gt/ge；两边为 quantity、time 或指向这两类值的 reference |
| condition/count | `form:"condition",operator:"count",condition,comparison,number,mode` | condition 为条件值；number 非负整数，原文次数栏留空时可 null；mode continuous/total；period 可为 duration/interval |
| formula | `form:"formula",operator,operands` | add/subtract/multiply/divide/min/max；减除恰两项，其余至少两项；叶 quantity/reference，可递归 formula |
| text | `form:"text",surface` | surface 非空原样字符串；normalized 非空字符串可选 |
| reference | `form:"reference",target` | 默认业务引用；可固定 detail/defined_value 及 value_path；目标类别受使用位置或槽声明限制 |
| object | `type:"object",fields` | fields 为字段名→值的对象，与 value_schema 对应 |
| list | `type:"list",items` | items 为值数组，允许 []；每项使用同一项声明 |

相对时间除 at 外非空 offset 必须非负，以 relation 表方向；at 允许有符号量。interval 只接收已经表明起止的端点；原文确有端点栏但留空可按下文 null 规则记载，原文未提供端点不能补造一个 null。工具不计算现实到期日。

按本轮用户裁决，**所有有原文依据的留空值位置均允许 null**，包括 detail.value、defined_value.value、容器成员及列表项。它是原文留空的值，不是第七种 form。先识别 null，再跳过该位置的 form/one_of 匹配，但仍要求来源覆盖且至少有一个可追溯锚定位字段说明及空白；III 级不能凭无空白原文的推断创造 null。required_fields 要求键存在，带有依据的 null 满足存在性；可选键缺席仍与显式 null 区分。

null 不用于关系端点、引用 ID、槽 ID、算子等结构标识。明确可空的标量位置为 quantity.amount、time/date.value、condition/count.number；quantity 的单位已知但金额留空时保留 `{form:"quantity",amount:null,unit:"CNY"}`，不丢掉币种。整体值、容器成员、算式操作数、时间量/端点等值位置也可按上述规则为 null，计算保持未定，不按零处理。text.surface 是原文转录，不用 null 代替原始文本；文本型字段本身留空时该整个 text 值取 null。条件、时间中需要实际事件 ID 的结构仍须给出该 ID；不能为漏识别事件填 null。引用一个值留空的定义值仍是合法引用，查询同时显示目标 value=null。机械检查验证 null 位置有可追溯出处；原文是否确实留空属于提取判断，不另加一个自动判空的语义检查器。

formula 引用仅指 detail 值、defined_value 或 external_benchmark，不允许主体/事件/条款作数值叶。比较引用不能指 external_benchmark 的现实数值。类型检查沿引用读取结构，遇到值依赖环报 VALUE_CYCLE；该规则不禁止 event_of 等语义图中的非求值环。

单位可判定时，加减/min/max 的量纲必须一致；乘除保留表达式，不创建新单位。比例与无量纲量允许参与金额乘除。不能从单位信息判定的外部基准公式只检查叶类型并返回未求值结构；不联网补数值。除数为明确零量时报 INVALID_VALUE；不对现实未知分母作断言。

### 5.2 槽结构语法

value_schema 每层恰一种：

- `{form}`：form 属于六形态；quantity 可带非空且不重复的 allowed_units；text 可带非空且不重复的 enum；reference 可带非空且不重复的 target_kinds。禁止把约束加到其他形态。
- `{type:"object",fields,required_fields}`：fields 为非空字段名到子结构的映射；required_fields 默认为 []，是 fields 键的无重复子集。未声明字段拒绝。
- `{type:"list",items}`：items 为一份子结构。
- `{one_of:[结构...]}`：至少两个分支；先分别匹配，恰一分支通过才通过，零或多个均报 INVALID_VALUE。

text 的 enum 比较 normalized（已填时）否则比较 surface；枚举匹配不改变来源级。reference 的 target_kinds 使用 design §6.7 代码；解析固定版本时以该版本类型和值为准，同时检查业务目标未撤销。quantity 的 allowed_units 精确比较代码，不用别名自动替换。

### 5.3 单位配置契约

结构为 `{format_version:1,version:非空字符串,units:[...]}`；每项字段恰为 `code,name,dimension,scale,reference_unit,aliases`。code/name/dimension/reference_unit 非空；scale 正十进制字符串；aliases 为无重复非空字符串列表。code 全配置唯一；reference_unit 必须存在且同 dimension；基准单位指向自身且 scale=1，其余直接指基准，不使用多级换算链。

首版配置版本 `units.v1` 的确定内容如下；未列出的单位不被 v1 量值接受，仍可按原文文本表示，不伪造换算。配置扩展独立升版本，旧案不变。每行除明确指定外，scale=`"1"`、reference_unit=code、aliases=[]：

| code | name | dimension | 特殊参数 |
|---|---|---|---|
| CNY | 人民币元 | currency:CNY | aliases=[元,人民币元] |
| USD | 美元 | currency:USD | aliases=[美元] |
| EUR | 欧元 | currency:EUR | aliases=[欧元] |
| GBP | 英镑 | currency:GBP | aliases=[英镑] |
| JPY | 日元 | currency:JPY | aliases=[日元] |
| HKD | 港元 | currency:HKD | aliases=[港元,港币] |
| day | 日（未区分计日规则） | time:day | aliases=[日,天] |
| calendar_day | 自然日 | time:calendar_day | aliases=[自然日] |
| business_day | 工作日 | time:business_day | aliases=[工作日] |
| month | 月 | time:month | aliases=[月] |
| year | 年 | time:year | aliases=[年] |
| hour | 小时 | time:hour | aliases=[小时] |
| minute | 分钟 | time:minute | aliases=[分钟] |
| second | 秒 | time:second | aliases=[秒] |
| ratio | 比例 | ratio | 无 |
| percent | 百分比 | ratio | scale="0.01"，reference_unit=ratio，aliases=[%,％] |
| count | 次数 | count | aliases=[次] |

各时间单位不自动互换，包括 month/year，不混入未约定的计期规则。此表是工具能力范围，不声称覆盖全部国际计量标准；币种代码只是固定配置，不查询汇率。

时间类型接受 dimension 为 `time:` 前缀的单位，货币采用 `currency:`，比例为 ratio，计数为 count。未知代码报 UNKNOWN_UNIT；未配置单位可以用原文文本保留并报告表达问题，不能临时扩配置。正式配置扩展须有工具版本和测试，不通过案内词表治理偷改。

## 6. 格式契约算法

### 6.1 decimal.v1

参数恰为 `decimal_places,group_separator,decimal_separator,sign_style,scale,unit_surface,unit_position,prefix,suffix,number_unit_separator`，全部必填。decimal_places 非负整数；scale 正十进制字符串；group_separator 为 `""`、`,`、` ` 或 `，`；decimal_separator 为 `.` 或 `,` 且不得等于非空 group_separator；sign_style minus/plus/none；unit_position before/after；其他字段字符串。

surface 按 prefix + 数字/单位排列 + suffix 分解。前后字面量与分隔必须逐字匹配；数字只有一段，整数部分至少一位，每组三位（首组一至三位），小数部分恰 decimal_places 位，小数位为 0 时不允许小数分隔符。minus 允许负数前 `-`、非负数无符号；plus 对非负数要求 `+`、负数要求 `-`；none 禁止符号且值非负。禁止指数和括号负数。

独立解析所得十进制数乘 scale，必须与被来源覆盖的 quantity.amount 数值相等，且单位代码由该 quantity 提供；参数 unit_surface 只描述原文单位写法。再用 amount/scale 还原，要求恰能用规定小数位表达，不能四舍五入；按符号、分组、单位位置、前后字面量生成 surface，必须逐字符相等。prefix/suffix/unit_surface/number_unit_separator 不得含 ASCII 数字；年月日等汉字单位可以保留。用整数系数及十进制位数作精确运算，或配置足以精确容纳本次输入的 Decimal 上下文；禁止默认28位精度导致悄悄舍入。测试须含超过28位的金额。

II 级 evidence.path 必须直接指向整个非空 quantity 值且 amount 非 null；不能只指 amount 或一个含多个量的复合根。surface 必须是至少一个引用锚 quote 的连续子串。decimal.v1 只证明显式格式与倍率一致，单位或倍率与合同原文的语义是否相符仍需可追溯和语义验收，不宣称机械推断了“万元”的含义。

### 6.2 date.v1

参数恰为 `precision,component_widths,separators,prefix,suffix`。precision 与目标 date 一致；year/month/day 对应 1/2/3 个组件、0/1/2 个 separators；年份宽度 4，月日宽度为 1 或 2。组件只接受 ASCII 数字，按宽度输出（宽度 1 表示不补零，而非只能一位）；分隔与前后字面量逐字相等。

按表层解析日历组件，验证合法性，再形成规范日期；与目标值一致后反向输出，恰等 surface 才通过。suffix 可承载 `日`、`月`、`年`，不能把日期数字放在字面量里。evidence.path 直接指整个 time/date 值且其 value 非 null，surface 要出现在锚 quote 中。不接受相对日期、农历推算或含糊补月补日。显式留空按普通有锚来源表达，不伪造机械变换。

### 6.3 确定样例

| 契约与参数要点 | surface | 目标 | 预期 |
|---|---|---|---|
| decimal，2 位，`,` 分组，`.` 小数，minus，scale=1，单位 USD 在后，中间空格 | `1,234.50 USD` | 1234.50 USD | 通过；改目标 1234.51 必失败 |
| decimal，0 位，无分组，scale=10000，单位 万元 在后 | `12万元` | 120000 CNY | 通过；改 scale=1000 必失败 |
| decimal，2 位且其他同首例 | `12,34.50 USD` | 1234.50 USD | 分组错误，失败 |
| date，day，[4,1,1]，分隔 年/月，后缀 日 | `2026年9月5日` | 2026-09-05/day | 通过；不得丢失原表层 |
| date，day，[4,2,2]，分隔 `-`/`-` | `2026-02-29` | 同名 date | 非法日期，失败 |

## 7. 完整物理表定义

以下 DDL 是未来 `src/legal/schema.sql` 的规范内容；它取代 design §12.1 的核心片段示意。JSON 字段的完整语法、类型表与 data_json 一致性、追加纪律由同一事务校验器保证，不能仅凭 SQL 接受就当业务有效。对外不开放任意 SQL 写接口。

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
CREATE TABLE case_info (
 singleton INTEGER NOT NULL PRIMARY KEY CHECK(singleton=1),
 case_id TEXT NOT NULL UNIQUE, contract_object_id TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL, tool_version TEXT NOT NULL,
 schema_version INTEGER NOT NULL CHECK(schema_version=1),
 value_format_version INTEGER NOT NULL CHECK(value_format_version=1),
 code_version INTEGER NOT NULL CHECK(code_version=1),
 vocabulary_format_version INTEGER NOT NULL CHECK(vocabulary_format_version=1),
 vocabulary_hash TEXT NOT NULL, vocabulary_files_json TEXT NOT NULL,
 unit_config_json TEXT NOT NULL, unit_config_hash TEXT NOT NULL,
 FOREIGN KEY(contract_object_id) REFERENCES objects(object_id)
   DEFERRABLE INITIALLY DEFERRED
);
CREATE TABLE vocabulary_units (
 unit_id TEXT NOT NULL PRIMARY KEY, entry_json TEXT NOT NULL
);
CREATE TABLE vocabulary_slots (
 slot_id TEXT NOT NULL PRIMARY KEY, entry_json TEXT NOT NULL
);
CREATE TABLE vocabulary_assignments (
 unit_id TEXT NOT NULL REFERENCES vocabulary_units(unit_id),
 slot_id TEXT NOT NULL REFERENCES vocabulary_slots(slot_id),
 PRIMARY KEY(unit_id,slot_id)
);
CREATE TABLE submissions (
 submission_id TEXT NOT NULL PRIMARY KEY,
 sequence INTEGER NOT NULL UNIQUE CHECK(sequence>=1),
 content_hash TEXT NOT NULL UNIQUE, submitted_by TEXT NOT NULL,
 phase TEXT NOT NULL CHECK(phase IN
 ('init','register','split','preparation','tagging','extraction','correction')),
 input_json TEXT NOT NULL, receipt_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE objects (
 object_id TEXT NOT NULL PRIMARY KEY,
 kind TEXT NOT NULL CHECK(kind IN
 ('material','text_version','clause','anchor','node','relation','detail','reference','gap','no_content')),
 created_submission_id TEXT NOT NULL REFERENCES submissions(submission_id)
);
CREATE TABLE record_versions (
 record_id TEXT NOT NULL PRIMARY KEY,
 object_id TEXT NOT NULL REFERENCES objects(object_id),
 revision INTEGER NOT NULL CHECK(revision>=1),
 previous_record_id TEXT REFERENCES record_versions(record_id),
 submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
 status TEXT NOT NULL CHECK(status IN ('active','withdrawn')),
 withdrawal_reason TEXT, data_json TEXT NOT NULL,
 UNIQUE(object_id,revision),
 CHECK((revision=1 AND previous_record_id IS NULL) OR
       (revision>1 AND previous_record_id IS NOT NULL)),
 CHECK((status='active' AND withdrawal_reason IS NULL) OR
       (status='withdrawn' AND revision>1 AND withdrawal_reason IS NOT NULL
        AND length(trim(withdrawal_reason))>0))
);
CREATE UNIQUE INDEX one_successor_per_record ON record_versions(previous_record_id)
 WHERE previous_record_id IS NOT NULL;
CREATE TABLE assertion_sources (
 record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 path TEXT NOT NULL, level INTEGER NOT NULL CHECK(level IN (1,2,3)),
 source_json TEXT NOT NULL, PRIMARY KEY(record_id,path)
);
CREATE TABLE record_links (
 record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 path TEXT NOT NULL,
 target_object_id TEXT REFERENCES objects(object_id),
 target_record_id TEXT REFERENCES record_versions(record_id),
 PRIMARY KEY(record_id,path),
 CHECK((target_object_id IS NULL) != (target_record_id IS NULL))
);
CREATE TABLE materials (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 name TEXT NOT NULL, media_type TEXT NOT NULL, content_hash TEXT NOT NULL,
 registered_order INTEGER NOT NULL UNIQUE CHECK(registered_order>=1),
 original_bytes BLOB NOT NULL, original_path TEXT
);
CREATE TABLE text_versions (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 material_id TEXT NOT NULL REFERENCES objects(object_id),
 version_number INTEGER NOT NULL CHECK(version_number>=1),
 conversion_method TEXT NOT NULL, converter_version TEXT NOT NULL,
 text TEXT NOT NULL, text_hash TEXT NOT NULL, anomalies_json TEXT NOT NULL,
 UNIQUE(material_id,version_number)
);
CREATE TABLE clauses (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 text_version_id TEXT NOT NULL REFERENCES objects(object_id),
 sequence INTEGER NOT NULL CHECK(sequence>=1),
 original_number TEXT, text TEXT NOT NULL,
 start_offset INTEGER NOT NULL CHECK(start_offset>=0),
 end_offset INTEGER NOT NULL CHECK(end_offset>=start_offset),
 tags_json TEXT NOT NULL,
 classification TEXT NOT NULL CHECK(classification IN
 ('unclassified','ordinary','no_content','unmatched'))
);
CREATE TABLE anchors (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 clause_record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 quote TEXT NOT NULL CHECK(length(CAST(quote AS BLOB))>0),
 occurrence INTEGER NOT NULL CHECK(occurrence>=1),
 start_offset INTEGER NOT NULL CHECK(start_offset>=0),
 end_offset INTEGER NOT NULL CHECK(end_offset>start_offset)
);
CREATE TABLE nodes (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 node_kind TEXT NOT NULL CHECK(node_kind IN
 ('subject','event','defined_value','external_benchmark','contract')),
 name TEXT
);
CREATE TABLE relations (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 relation_kind TEXT NOT NULL CHECK(relation_kind IN ('party','contract')),
 unit_id TEXT NOT NULL REFERENCES vocabulary_units(unit_id),
 party_0_id TEXT REFERENCES objects(object_id),
 party_1_id TEXT REFERENCES objects(object_id),
 contract_id TEXT REFERENCES objects(object_id),
 modality TEXT CHECK(modality IN ('obligation','power','permission','immunity')),
 CHECK((relation_kind='party' AND party_0_id IS NOT NULL AND party_1_id IS NOT NULL
        AND party_0_id!=party_1_id AND contract_id IS NULL) OR
       (relation_kind='contract' AND party_0_id IS NULL AND party_1_id IS NULL
        AND contract_id IS NOT NULL))
);
CREATE TABLE details (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 owner_id TEXT NOT NULL REFERENCES objects(object_id),
 slot_id TEXT NOT NULL REFERENCES vocabulary_slots(slot_id),
 value_json TEXT NOT NULL
);
CREATE TABLE references_data (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 reference_kind TEXT NOT NULL CHECK(reference_kind IN
 ('appellation','role','composition','definition','event_of','scope','priority','amendment','redirect','distinct')),
 from_json TEXT NOT NULL, to_json TEXT NOT NULL
);
CREATE TABLE gaps (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 clause_record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 gap_kind TEXT NOT NULL CHECK(gap_kind IN ('unmatched_unit','missing_slot','structure_anomaly')),
 description TEXT NOT NULL, reported_by TEXT NOT NULL
);
CREATE TABLE no_content_records (
 record_id TEXT NOT NULL PRIMARY KEY REFERENCES record_versions(record_id),
 clause_id TEXT NOT NULL REFERENCES objects(object_id), reason TEXT NOT NULL
);
CREATE TABLE case_overviews (
 overview_id TEXT NOT NULL PRIMARY KEY,
 submission_id TEXT NOT NULL UNIQUE REFERENCES submissions(submission_id),
 text_versions_json TEXT NOT NULL, body TEXT NOT NULL, authored_by TEXT NOT NULL
);
CREATE TABLE extraction_completions (
 submission_id TEXT NOT NULL REFERENCES submissions(submission_id),
 clause_id TEXT NOT NULL REFERENCES objects(object_id),
 clause_record_id TEXT NOT NULL REFERENCES record_versions(record_id),
 PRIMARY KEY(submission_id,clause_id)
);
CREATE TABLE reconciliation_reports (
 report_id TEXT NOT NULL PRIMARY KEY,
 checked_sequence INTEGER NOT NULL REFERENCES submissions(sequence),
 scope_json TEXT NOT NULL, rule_version TEXT NOT NULL,
 result_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE INDEX record_submission ON record_versions(submission_id);
CREATE INDEX sources_level ON assertion_sources(level,record_id);
CREATE INDEX links_object ON record_links(target_object_id);
CREATE INDEX links_record ON record_links(target_record_id);
CREATE INDEX clauses_address ON clauses(text_version_id,sequence);
CREATE INDEX anchor_clause ON anchors(clause_record_id);
CREATE INDEX node_kind ON nodes(node_kind);
CREATE INDEX relation_unit ON relations(unit_id);
CREATE INDEX relation_party_0 ON relations(party_0_id);
CREATE INDEX relation_party_1 ON relations(party_1_id);
CREATE INDEX detail_owner_slot ON details(owner_id,slot_id);
CREATE INDEX reference_type ON references_data(reference_kind);
CREATE INDEX gap_type_clause ON gaps(gap_kind,clause_record_id);
CREATE INDEX completion_clause ON extraction_completions(clause_id);
CREATE VIEW current_records AS
 SELECT r.* FROM record_versions r WHERE NOT EXISTS
 (SELECT 1 FROM record_versions n WHERE n.object_id=r.object_id AND n.revision>r.revision);
CREATE VIEW active_records AS
 SELECT * FROM current_records WHERE status='active';
```

### 7.1 派生列、索引及一致性

每个 record_versions 行恰有一个与 objects.kind 对应的类型行。nodes.name 对 subject 取 canonical_name、其余取 name，空合同为 NULL；relations 的端点按原数组顺序填列；anchor 缓存位置为条款内部字符区间。detail 的 null 保存为 JSON 文本 `null`，不是 SQL NULL。

record_links.path 以 `/data/...` 或 `/evidence/<序号>/source/...` 表示在完整记录内的位置，因此业务字段与来源路径不碰撞；value_path 保留在 data_json 中，不成为独立对象。来源数组按 path 排序保存后生成路径索引，所有引用都必须出现在索引中。type 表、sources 和 links 由一份已解析记录生成；禁止单独修改。

所有成功提交相关行只追加；工具不 UPDATE/DELETE 这些行。词表、case_info 开工后冻结。初始化失败不留下可用的半库；目标预先存在时不覆盖。写事务采用 BEGIN IMMEDIATE，SQL 插入顺序为 submissions、objects、全部版本、类型/来源/引用/完成/概要，全部成功才提交；UUID 与完整回执在插入前已算好，无需回头更新 receipt_json。case_info 与词表在同一个 init 事务写入。

init 内部 input_json 为 `{operation:"init",case_id,vocabulary_hash,unit_config_hash}`，内容哈希按 §2.2 规范计算；phase=init、submitted_by=`case_cli`、sequence=1。其他命令成功时 sequence 为当前 max+1；register/split 的内部 submitted_by 分别为 `case_cli`、`splitter:contract_v3.article.2`（旧提交仍保留旧版本标识）。vocabulary_files_json 为按路径排序的 `[{path,content_hash}]`，content_hash 是各源文件实际字节 SHA-256，与合并词表逻辑哈希分开；tool_version 为实现发布版本，不在本次规格虚构已发布版本。

前驱同对象、revision 连续、不可变类别、当前条款 sequence 不重复、指向正确类别以及 JSON 内容相等属于事务内强制条件。历史 clauses 可以同地址，不能以全表 UNIQUE(text_version,sequence) 拒绝标签修订。

reconcile 报告用一致快照读取并保存 checked_sequence；报告自身不占新的业务 submission sequence，所以不会刚写出就让自己过时。数据库错误回滚报告写入并返回 3，不假报对账已完成。

## 8. 状态变化与提交后条件

### 8.1 校验顺序

严格 JSON及字段形状 → 格式/案件/快照版本 → 内容哈希命中 → 分配本批 ID → 验证前驱及允许修订类别 → 构造候选当前视图 → 类型、词表、引用和值 → 锚与出处 → 全部现存业务依赖 → 覆盖记录 → 同一事务写入与回执。

独立错误按 records 输入序号、字段 path、错误 code 排序；上限 100 条，超限 errors_truncated=true。依赖不存在时报告根错误，不再为其虚构锚验证失败；不会以错误列表被截断为理由接受提交。先确定的错误阶段失败后不运行需要该阶段成功的数据处理。

每一成功提交的后条件：旧业务行的内容和数量不减少；每个输入记录恰产生一个版本；新对象数等于未带 object_id 的记录数；修正对象身份不变；全部业务引用在最终视图有效；每个正式断言有来源；receipt 与所有结果一起提交。失败的后条件：以上各表、完成记录、概要和 submission 计数均无变化。

### 8.2 完成记录的条件

covered_clauses 的版本必须属于所声明对象，与候选当前条款的 `text_version,sequence,text,start_offset,end_offset,original_number` 相同；只变 tags/classification 可接受旧读版本。条款必须已分类；unmatched 必须有锚定该条款的 unmatched_unit 缺口，no_content 必须有同条款无规定内容记录，ordinary tags 非空。

每个声明完成条款，在本批至少有一个当前 active 的 node/relation/detail/reference/gap/no_content，其证据根链回到该条款相同原文区间。仅 anchor、clause 标签、overview 或以前提交的事件不算本批产物。节点作为本批真正提取内容可以支持条款覆盖，不能只因事件库非空就跳过条款。

完成事实可追加多次，重放同成功文件不追加第二次。新一次完整重提必须使用现有 ID 修订或撤销已有对象；程序不靠自然语言判同义。当前进度认可历史完成记录的条件是条款原文身份仍一致且目前仍有有效内容/缺口/无内容记录。后来撤销全部模型内容，会在归类覆盖中失去内容支撑，不自动删除原完成事实。

### 8.3 候选视图与历史

用户已确认可恢复误撤销对象：以最新 withdrawn 版本作 previous_record_id，提交 status=active 的完整 data/evidence。对象 ID 不变、revision 加一，沿用 write，不设置恢复命令。全部引用、值及出处重新验证；不会自动恢复原来一并撤销的细节或依赖，需恢复者在同批逐项提交。撤销历史永久可查。

一般修订检查 candidate 中所有 active 业务记录，包括本批未涉及的记录。关系改 unit 后，既有 detail 的槽须仍适用，否则要求同批修订/撤销；节点改类禁止；撤销关系时仍有 active detail 或条件等依赖则失败。被一并撤销的记录不再贡献当前业务依赖。

固定历史证据不参与“必须同批改引用”的要求；查询提示前提变化。缺口的 clause/related_object 按用户确认固定发现时版本；不阻止对象以后撤销，也不自动把旧缺口变成新条款的覆盖依据。合同文本 amendment/priority 只保存指向，不改变 active 状态和修订链。正文与补充协议矛盾不会因登记较晚而被折叠。

redirect 检查全部当前 redirect 有向图无环。多个不同终点，或与 distinct 相冲突时保留冲突列表；只有唯一且无矛盾的终点才给出 canonical_id。冲突不由登记时间裁决，不自动重写原关系端点。

## 9. 命令、输出和错误

### 9.1 公共行为

案件/词表命令集合按 design §15；预处理使用用户确认的独立模块入口及 §9.7 参数，不设业务子命令。三个 CLI 每次命令默认 stdout 一份 UTF-8 JSON 对象并以换行结束，stderr 只作进度/诊断；机器结果无 ANSI。`--help` 为文本且退出 0，不访问数据库或启动转换器。参数错误仍输出结构化错误，退出 2，不让 argparse 自行输出不可解析的成功外观。

案件命令的 --db 位于子命令后；词表 --vocabulary 允许位于子命令前或后，但只能给一次。词表混合变更以顶层 --input 调用，不能再带子命令；diff 仅要求 --left/--right，不要求另给 --vocabulary。单值参数重复给出报 INVALID_ARGUMENT；仅文档明确允许重复的过滤器及 --unit 可重复。

通用失败为 `{ok:false,errors:[{code,path,message,...}],errors_truncated:false}`；未知字段报 UNKNOWN_FIELD；语法错误报 INVALID_JSON；读取失败报 FILE_ERROR；数据库错误报 DATABASE_ERROR。path 指输入 JSON Pointer；纯命令参数用 `/arguments/<参数名>`。local_id、目标 ID、current_record_id 仅在帮助定位且确有其值时返回；失败不含尚未落库的生成 ID。

退出码：0 成功；2 参数/输入/业务校验失败；3 文件/数据库/外部转换进程故障；4 完成六查但有 errors。写后响应传输失败不改变已经提交的事务，调用方使用原输入重提。文件输出已有则 FILE_EXISTS，退出 3，不覆盖。

除 §14 的符号占位外，所有 JSON 响应中的 ID 都是规范 UUID；列出的所有字段必须返回，空集合用 [] 或 {}，无值用明确说明的 null，不忽有忽无。人类 message 不作为严格字面断言，code/path/结果结构是稳定契约。

### 9.2 init、register、split、write

| 命令 | 完整成功结果字段（加 `ok:true`） |
|---|---|
| init | `case_id,contract_object_id,vocabulary_hash,unit_config_hash,schema_version:1,submission_id` |
| register | `submission_id,content_hash,replayed,material:{object_id,record_id},text_version:{object_id,record_id,version_number},original_hash,text_hash,anomalies` |
| split | `submission_id,content_hash,replayed,text_version_id,algorithm_version,clauses:[{object_id,record_id,sequence,start_offset,end_offset,original_number}],gaps:[{object_id,record_id}],character_coverage:{passed,source_length,clauses_length}` |
| write | `submission_id,content_hash,replayed,id_map,counts,covered_clauses,issues,overview_id`；overview_id 无概要时 null |

write 的 id_map 包含全部 local_id，映射 `{object_id,record_id,revision}`；counts 仅列本次出现的 kind 及版本条数，修正也计一条；covered_clauses 返回条款 object_id 数组，原 record_id 清单仍存在 input_json 和完成表。直接单记录调用包装 phase=correction、covered_clauses=[]、issues=[]，case_id/vocabulary_hash 从目标库读取；不接受 --input 与任何记录直接参数混用，不借直接调用把整条款标完成。

register 元数据完整结构：`{name,media_type,conversion_method,converter_version,anomalies,material_id?}`。前四项非空字符串；anomalies 为 `{code,message,start_offset?,end_offset?}` 数组，位置同时有或同时无，提供时为全文合法字符区间。material_id 为重转换既有素材的对象 ID，缺席才新建。输入原件 bytes、text 文件及 metadata 全部读取和校验成功才开始写入；原件哈希与既有素材不符时报 ORIGINAL_MISMATCH。重转换新增独立 text_version 对象而不修订旧文本对象，version_number 为该 material 下 max+1；同成功 register 内容重放不递增。

init 拒绝现有目标，无“初始化即覆盖”。register 原件路径不同但内容同且元数据同视作重放；没有 material_id 的改内容提交会建立新素材，不按同名推断重转换。split 已有成功同版本同算法结果则返回它；有既存条款却不是该成功切分的首次执行场景时拒绝 SPLIT_ALREADY_EXISTS，不静默重切。

### 9.3 query

默认 `view=records,format=json,limit=100,offset=0`。limit 正整数、offset 非负整数。--object/--record 互斥；--record 不可配 --history；--history 可配 --object 或过滤器，不与原件导出组合。相同过滤参数取 OR，不同种取 AND；未知 ID 的过滤结果为 no_record，显式 --object/--record 根本不存在则 NOT_FOUND、退出 2；对象存在但当前已撤销且未加 --include-withdrawn 时返回 no_record。显式 --record 或 --history 查询历史时包含撤销版本，不需要另加该开关。不支持的参数组合报 INVALID_ARGUMENT，不静默忽略。

records 未给 kind/object/record 时默认列 node/relation/detail/reference/gap/no_content。显式 --kind 可选十种记录类别；--object/--record 可读取任何类别。material 的 BLOB 始终不混进 JSON；text_version 全文仅在显式选择该对象/类别时返回。不会把所有登记全文混入默认业务检索。events/clauses 等专用 view 自行限定类别。

每次 JSON 查询返回：

`{ok:true,case_id,view,result_status,total,offset,limit,next_offset,items,quality}`。

result_status 为 found/no_record；total 为分页前匹配数；next_offset 有下一页时是 offset+返回数，否则 null。分页对象按 `(创建submission顺序,object_id,revision)` 排序，history 内 revision 升序。offset 超范围时 items=[]、total 保留实际匹配数，result_status 仍由 total 决定。

record item 结构：`{object_id,record_id,revision,previous_record_id,submission_id,kind,status,withdrawal_reason,data,evidence,provenance,details,missing_slots,gaps,identity,expansion_sequence,matched_paths}`。首版 previous_record_id=null；active 的 withdrawal_reason=null，withdrawn 返回原撤销理由。

按 decisions §1.30，当前查询以读取快照最大 submission.sequence 展开业务关联；--record/--history 的每份历史记录以其写入时的 sequence 展开：对每个稳定对象引用，取该序号及以前最新版本，对细节也只取当时已经存在的版本。固定 record_id 永远保持指定版本。expansion_sequence 明示这个技术记录序号，不表达合同法律上的生效时点。历史关系不能附上后来才修正的细节并伪装为原记录；后来前提已变化的提示另查当前版本。matched_paths 列来源级/槽过滤命中的数据路径并去重排序，无这两项过滤时为 []。

- evidence 是有路径的原来源；provenance 为 `{path,level,anchors:[{anchor_record_id,clause_id,clause_record_id,text_version_id,material_id,sequence,quote,start_offset,end_offset}],premises:[{record_id,current_record_id,changed,withdrawn}]}` 数组，按断言来源 path 返回。
- relation 的 details 返回展开序号时的全部 active 细节完整记录项（detail 不再反向嵌套 owner）。缺席槽为适用专属槽与通用槽减去该时已填槽的 ID 集；显式 value:null 视为已填，其值本身为空，不列入 missing_slots。查询带 --slot 时仍返回关系全部细节并按全部实际细节算缺席，matched_paths 指示匹配，避免过滤造成假缺席。
- gaps 返回有关条款/related_object 的短项 `{object_id,record_id,gap_kind,description,target_changed,target_withdrawn}`，后两项为该缺口固定目标相对当前的变化布尔值；完整内容可按 record_id 查询。历史发现不冒充当前还未解决，不设置 resolved 状态。其他 kind 的 details、missing_slots 使用 []。
- identity 恒为 `{resolution,endpoints}`。node 的 resolution 为 `{original_id,canonical_id,candidates,conflicts}`，endpoints=[]；party relation 的 resolution=null，endpoints 按原 parties 顺序各给同一解析结构；其他记录为 `{resolution:null,endpoints:[]}`。无重定向时 canonical_id=original_id，candidates=[original_id]；冲突时 canonical_id=null，candidates 为排序后的全部候选，conflicts 项为 `{record_ids,code}`，code 为 multiple_targets/distinct_conflict/collapsed_parties，record_ids 排序列有关引用或关系版本。不改 data 原值。

--party 匹配 party relation 的原始主体 ID 及无冲突的归一终点，detail 随 owner；有冲突不把候选终点当确立同一性扩大匹配，但查询原始 ID 仍显示候选。--unit 匹配 relation.unit_id 及其 detail；--slot 匹配 detail.slot_id 及至少拥有一条匹配 detail 的 relation。--source-level 筛选实际命中的断言路径，item 增加 `matched_paths`，其他级别依据仍完整返回；relation 可由其 detail 的匹配命中，路径用 `/details/<object_id>/...` 区分。--clause 按证据根链或条款本身的稳定 ID 匹配；固定旧版本仍可关联，provenance 明示版本。

专用 view 的 items：materials 为上述 record item（data 是素材管理数据，不输出 BLOB）；clauses 为条款 record item 含全文；events 仅 node:event；gaps 为历史缺口 record item；vocabulary 为 `{format_version,units,slots,assignments,hash}` 单项；overview 为 `{overview_id,submission_id,text_versions,body,authored_by}`，默认最新一项、--history 时全部；progress 为 §11.3 单项；report 为 §11.1 完整报告，默认最新一项、--history 时全部。不存在概要或报告时 items=[]。view 与 kind 类型相冲突报 INVALID_ARGUMENT。vocabulary/overview/progress/report 不接受 kind/object/record/party/unit/slot/source-level/clause 过滤；只允许 overview/report 使用 history。专用管理 view 按其创建顺序分页；vocabulary/progress 单项使用相同分页外壳。

原件导出只接受 view=materials、--object、--format original、--output 及 --db。读取 BLOB 并核对哈希，排他创建目标，返回 `{ok:true,material_id,output,content_hash,size}`；失败不留完整性未确认的目标。Markdown 导出是同一 JSON 结果的可读渲染，必须保留 ID、引文、来源级、空值与缺口区别；不保证排版空格一致。普通 --output 成功后 stdout 返回 `{ok:true,output,format}`，文件才是完整查询结果。

### 9.4 group

默认选择每素材最新 text_version 的当前 active 条款，可 --text-version 限定一个已登记版本。范围内任一 unclassified 则拒绝 UNCLASSIFIED_CLAUSE。不执行提取，也不写案件库，不改变对账状态。

每个有条款的 unit 导出 `unit-<uuid>.json`；no_content 和 unmatched 分别导出同名 JSON。每份格式为 `{format_version:1,case_id,vocabulary_hash,unit_id,classification,clauses:[{object_id,record_id,material_id,text_version_id,sequence,original_number,text,tags,context_clauses}]}`；`context_clauses` 为在同一文本版本中先于本条的上级标题区间列表，每项有 `{object_id,sequence,text}`，只供阅读。普通 unit 的 classification=ordinary，其余 unit_id=null。text 是该 article 或例外区间的逐字内容，不在其内插标题；地址独立字段；上下文副本不计入字符覆盖或第二份提取职责。所有条款按 `(素材登记序,文本版本号,sequence,object_id)` 排序。

输出目录必须不存在或为空，已有文件拒绝，不覆盖。成功返回 `{ok:true,files:[{path,unit_id,classification,clause_ids}],clause_count}`；clause_count 按唯一条款计数。多标签副本允许出现在多个文件中；无标签特殊分类也有文件，不能在责任分配中丢失。目录写出失败删除本命令已新建的不完整文件；未返回成功的目录不得被 skill 当作完整交接。

### 9.5 词表 CLI

init 生成精确空结构 `{format_version:1,units:[],slots:[],assignments:[]}`，返回 `{ok:true,vocabulary_hash}`。list/show 返回 `{ok:true,kind,items}`，items 按 ID 或归属对排序；show 无目标 NOT_FOUND。diff 返回 `{ok:true,left_hash,right_hash,added,removed,assignment_added,assignment_removed,illegal_content_changes}`；同 ID 改内容是差异结果中违规项，退出 2；纯增删退出 0。added/removed 项为 `{kind,entry}`，归属增删项为 `{unit_id,slot_id}`，非法变化项为 `{kind,id,before,after}`，均按 kind、ID 排序；kind 顺序 unit、slot。

加载单文件为 design §4 完整结构；目录递归加载 `.json/.yaml` 普通文件，每份同样是完整结构（可空部分），按相对路径排序合并。相同 ID 完全相同内容只计一次，不同内容报 DUPLICATE_ID；重复归属报 DUPLICATE_ASSIGNMENT。空目录等价空词表；其他扩展文件不加载。unit 与 slot 各自命名空间唯一；所有正式新增 ID 都由工具生成。id、origin_unit_id、replaces 成员均为规范 UUID；origin/replaces 可指历史已删除条目。name/description 非空，aliases/examples 为非空字符串数组，列表默认 []；slot 必需 value_schema。assignment 恰有 unit_id/slot_id 且都能解析。

混合变更顶层必须有 `format_version,expected_hash,operations`，orphan_slots 默认 []。operation/local 引用按 design §15.3；entry 不接受 id。删除不存在条目报 NOT_FOUND；同一 ID 重复删除报 DUPLICATE_OPERATION；新增 ID 不可由调用方指定，避免删除后复用旧 ID。最终状态决定是否孤立，不按操作顺序让槽临时升为通用。

若原非通用槽在最终状态仍存在而其旧归属全失，必须有一条有效 disposition；remove 删除槽、general 清空归属、reassign 设为所列非空最终有效 unit 集。slot 已显式 remove 不再要求 orphan 清单；orphan 清单中不适用的槽、重复槽、被显式 remove 又重复处置均报 ORPHAN_DISPOSITION_INVALID。保留部分旧归属不要求额外处置。不能借 orphan 修改槽内容。

变更成功返回 `{ok:true,before_hash,after_hash,id_map,changes}`，changes 是与 diff 同结构的增删/归属项，不包含非法改内容。expected_hash 不符 HASH_CONFLICT，文件不变；不自动重算 hash 后强行执行原意见。正式写入为单文件；目录输入写操作报 READ_ONLY_LAYOUT。当前流程由主会话串行提交，同一词表不支持多个并行写会话；实现不得以“稍后最后写入者覆盖”为并发保证。

aggregate 的 cases 文件精确为 `{format_version:1,cases:[路径字符串]}`，路径不重复。任一库无法读取或格式不支持，整体失败，不生成声称完整的报告。结果文件结构为 `{format_version:1,current_vocabulary_hash,cases:[{path,case_id,vocabulary_hash,quality,gaps:[{record,related_units,related_slots}]}]}`；record 为 query 的完整 gap item，related_units/related_slots 为该缺口直接引用的冻结条目和 related_object 的 unit/slot 条目，去重后按 ID 排列；无对应项用 []。保持输入案件顺序、缺口按建立顺序。成功 stdout 返回 `{ok:true,output,case_count,gap_count}`；不自动附新增槽建议，建议由治理 agent 形成。

### 9.6 稳定错误分类

| code | 条件 |
|---|---|
| INVALID_JSON / UNKNOWN_FIELD / INVALID_ARGUMENT | 语法、未知字段、参数组合或基础类型错误 |
| UNSUPPORTED_VERSION / CASE_MISMATCH / VOCABULARY_MISMATCH | 版本或目标不符 |
| DUPLICATE_LOCAL_ID / DUPLICATE_ID / DUPLICATE_ASSIGNMENT / DUPLICATE_OPERATION | 对应唯一性失败 |
| REFERENCE_NOT_FOUND / REFERENCE_TYPE_MISMATCH / WITHDRAWN_TARGET | 引用不存在、类型不符、业务目标撤销 |
| STALE_REVISION / IMMUTABLE_RECORD / KIND_CHANGE | 前驱过时、不可变记录修改、对象改类 |
| INVALID_VALUE / UNKNOWN_UNIT / VALUE_CYCLE | 值形状、单位、值依赖问题 |
| MISSING_SOURCE / SOURCE_CYCLE | 断言缺依据或循环论证 |
| ANCHOR_NOT_FOUND / ANCHOR_AMBIGUOUS / ANCHOR_OCCURRENCE | 无引文、多义未消歧、序号越界 |
| ROUNDTRIP_FAILED / UNKNOWN_FORMAT_CONTRACT | 变换失败或未知格式契约 |
| SLOT_NOT_APPLICABLE / COVERAGE_INVALID / UNCLASSIFIED_CLAUSE | 槽归属、提取声明或分组前提错误 |
| REDIRECT_CYCLE / WITHDRAWAL_DATA_CHANGED | 重定向环或撤销夹带改写 |
| HASH_CONFLICT / ORPHAN_DISPOSITION_REQUIRED / ORPHAN_DISPOSITION_INVALID | 词表基准过时或孤立槽处置失败 |
| NOT_FOUND / ORIGINAL_MISMATCH / SPLIT_ALREADY_EXISTS / READ_ONLY_LAYOUT | 对象、原件、重切或词表布局不满足接口 |
| CONVERTER_FAILED | 转换进程返回非零；错误含 converter_exit_code，退出 3 |
| CONVERTER_OUTPUT_INVALID / ORIGINAL_CHANGED | 转换产物不满足 §9.7，或转换期间原件字节发生变化；退出 2 |
| FILE_EXISTS / FILE_ERROR / DATABASE_ERROR | 文件或存储故障，退出 3 |

对账里的检查失败使用 §11 的检查 code；不混同于命令无法执行。

### 9.7 预处理 CLI

这是七件交付物中的统一入口，使用标准库启动和校验外部转换程序。PDF、Word、OCR 等转换引擎及其依赖由使用环境显式配置；本项目程序本身不因此导入第三方解析库，也不宣称支持未配置的格式。已有 `contract_v3` 转换工具只能作为候选外部程序；扫描器的复用按 §12，不能据此自动选中另一套转换引擎。

#### 9.7.1 命令和配置

目标命令为：

```text
python -m legal.preprocess_cli --input <原件路径> --output-dir <输出目录> --converter-config <转换配置JSON>
```

三个参数均必需且只能出现一次；无位置参数、无隐式默认配置、无子命令。原件须为可读取普通文件；输出目录不存在或为空，非空报 FILE_EXISTS，不覆盖。参数路径按 §2.1 和 §1.5 解释。一次调用转换一份原件；多份材料沿用调用方的逐份调用，不新增目录批量扫描机制。

配置恰为 `{format_version:1,argv:[字符串,...]}`。argv 至少含可执行程序及两个占位参数，每项为非空字符串；argv[0] 为实际程序的绝对路径，其余相对文件参数按配置文件所在目录解释。`{input}`、`{output_dir}` 必须分别作为完整 argv 元素恰好出现一次，不能位于 argv[0]；不支持嵌入字符串的替换、其他占位名或 shell 表达式。配置符合 §2.1 严格 JSON 规则。

以下仅示意配置协议，不指定实际转换器或可执行路径：

```json
{
  "format_version": 1,
  "argv": [
    "/absolute/path/to/converter-adapter",
    "--input", "{input}",
    "--output-dir", "{output_dir}"
  ]
}
```

外部程序可以本身满足协议，或由其配置方提供适配入口；本项目未来编写的任何适配代码仍须放在 legal/src 内。配置方负责选择支持目标格式的程序，不按扩展名自动寻找其他工具。配置错误报 INVALID_ARGUMENT/UNKNOWN_FIELD/UNSUPPORTED_VERSION，JSON 语法错误报 INVALID_JSON；这些错误均在启动转换器前返回。

#### 9.7.2 转换进程与两文件协议

1. 读取原件，计算原始字节 SHA-256。建立本次专用临时输出目录，将原件绝对路径和该临时目录绝对路径替换进 argv；转换进程工作目录为配置文件所在目录。按 argv 直接启动、不经 shell；转换器不得改写原件。
2. 转换器以 0 表示已完成，非零为失败。其 stdout/stderr 作为诊断转到本 CLI 的 stderr，不混入 stdout 的 JSON 回执。无法启动报 FILE_ERROR；非零报 CONVERTER_FAILED，含实际 converter_exit_code，不因存在 text.txt 而改报成功。
3. 转换器在临时目录根产出两个普通文件：`text.txt` 是严格 UTF-8、无 BOM 的文本；`metadata.json` 是 §9.2 的 `{name,media_type,conversion_method,converter_version,anomalies}`，均为必需字段，不含 material_id。前四项非空字符串，anomalies 位置必须是该文本的合法字符区间。其他诊断文件不进入最终产物。
4. 本 CLI 读取并校验两个文件；缺失、非法 JSON、错误字段或位置、错误编码均报 CONVERTER_OUTPUT_INVALID，error.path 指 `/converter_output/text` 或 `/converter_output/metadata` 下具体字段，message 保留原因。输出读取故障仍为 FILE_ERROR。保留文本字节、CR/LF 和空白；不重排标题、合并段落、补全内容、删除 OCR 噪音或执行 §12 的案内条款切分。
5. 再读取原件计算哈希，与开始值不同则 ORIGINAL_CHANGED。全部检查通过后排他写出最终目录的 `text.txt` 与 `metadata.json`；metadata 可按 §2.2 规范序列化，不改变字段内容。对最终字节核算哈希后返回成功，临时目录清理。发生可处理的发布错误时清理本次已创建的最终文件，不删除调用方原有文件；清理失败在 errors 附报 FILE_ERROR，不伪装无残留。

输出目录写入不是数据库事务：进程被强制终止时可能残留文件，未收到成功回执不得把其当完整交接；再次调用面对非空目录仍按 FILE_EXISTS 返回，可改用新的输出目录。预处理不提供案件 write 的内容重放语义。以上是文件失败处理，不新增案件流程状态。

转换报告中的异常由转换器产生，统一入口校验结构、逐字保留说明，不自动证明转换文字与原件语义一致。空文本也不静默生成条款；是否影响后续阅读按既有异常处理规则执行。文本内容形成何种段落/表格标记由已选转换器说明，并纳入逐格式验收。

#### 9.7.3 返回与下游引用

成功 stdout 恰为 `{ok:true,input,output_dir,text,metadata,original_hash,text_hash,anomalies}`，前四个路径字段为绝对路径，哈希按 §2.2；anomalies 与 metadata 中数组相同，退出 0。失败外壳与 §9.1 相同；预处理不返回对账退出码 4。

预处理 skill 将成功回执交给调用方。案件 skill 以其中 input/text/metadata 作为 `register --original/--text/--metadata` 输入，然后调用案件 `split`；初始化 skill 将相同结果登记进语料清单，不因此建立案件库。对既有素材重转换时，调用方依 §9.2 提供带 material_id 的登记元数据，转换 CLI 不推断案件身份。

预处理 CLI 不接收数据库或词表参数、不创建案内条款 ID、不做法律分类。扫描异常进入案件缺口表的动作仍属于案件 split，预处理 anomalies 通过 register 保存；两类异常不混为一个执行阶段。

## 10. 四个 skill 的契约与验收

本节细化 design §16 已批准步骤的输入、输出和完成条件，四个入口及全部引用资源已在 §1.3—§1.5 定位。当前只规定 SKILL.md 必须包含的内容，不创建实际 skill 文件，也不建立新的审批状态机。

### 10.1 共用读手交接

任务文件为 `{format_version:1,task_id,unit_id,responsible_clauses,context_clauses,input_files,output_file}`。task_id 非空；unit_id 可 null；条款清单为对象/记录 ID 对；负责集与上下文集可以有交集，但完整提取职责只取 responsible。所有任务负责集合两两不交、并集等于本轮条款范围；调用前比较 ID 集即可验证。

读手返回 `{task_id,output_file,responsible_clauses,record_counts,issues}`。主会话读取 JSON 格式及摘要并调用 write；成功以数据库回执为准，不以读手宣称完成为准。失败将 errors 和必要版本交回原读手；不替其猜改合同含义。读手只能使用分配的输出路径，不能持有数据库写入职责。

每个关系提取任务的 input_files 必须含：任务说明、负责条款完整文本、对应分组上下文、冻结词表、当前概要、已入库事件及其 ID/出处、已知共用对象查询结果、本文交换格式。空事件列表也是明确输入，不因没有事件而伪造一个。事件认定任务与关系任务职责不同；不得给关系读手“自行补提所有事件”的附加步骤。

### 10.2 预处理

入口为 `skills/legal-preprocess/SKILL.md`，输入是明确的原件、输出目录和转换配置路径。读取共用预处理用法后，调用 §9.7 的统一 CLI；成功交接完整 JSON 回执，失败交接 code/path/message 及诊断，不提供伪造的 text/metadata 路径。skill 只解释和调用工具，不判断法律含义；影响阅读的质量问题由调用方依既有规则要求更好源件。

验收用受控的转换器夹具检验调用、错误和元数据交接；真实 PDF/Word/OCR 支持范围由所接工具提供，集成验收逐种格式记录，不把尚未配置的转换器记为通过。预处理适配代码未来也在 src 内。

### 10.3 入库

严格使用 design §16.3 八个编排环节（对照 decisions §1.7 九项原子动作），没有额外的人审闸。事件 write 成功并取得正式 ID 后才能派关系任务；打标任务条款不重叠；各 unit 关系任务并行，文件由主会话串行 write。重启后 query progress 以及重复 write 的回执即可恢复，不依赖独立任务状态库。

入口为 `skills/legal-case/SKILL.md`。开始前明确合同材料清单、已有库或新库路径、新库需用的词表路径、工作目录；需转换的材料另有输出位置和转换配置。源文件转换读取预处理 skill；随后使用案件 CLI 的 init/register/split/write/query/group/reconcile。三个读手说明按 §1.4 派发。最终交接案件库路径、case_id、词表哈希、本轮范围、最新对账回执及未解决问题；对账有 errors 时交接结果须写明未完成。

入库完成的可观察条件：所声明本轮范围的六查报告零 errors，checked_sequence 等于当前最大 submission sequence，报告范围确实覆盖本轮条款；报告只覆盖单一旧文本不能宣称整个案件完成。notices 单列。新增材料、重新转换、修正写入后旧报告仍保留并显示过时。

### 10.4 初始化

corpus 清单至少表达每份材料的用户指定用途、合同种类、来源、原件/文本路径及 SHA-256、转换元数据。用户既有清单字段可由读取层映射，不为本次规格任务迁移实际语料。用途分 induction/rule_exam/held_out/legal_checklist，后两类分别承接真实验收与法律文本查漏；非 induction 不得进入单元或槽的归纳证据集。

入口为 `skills/legal-initialize/SKILL.md`，另需明确工作目录和正式词表目标路径。需转换的语料使用预处理 skill；两遍任务分别读取 first-pass.md/second-pass.md。正式条目使用词表 CLI 的 init、混合变更、list/show/diff，不借案件 init 生成词表；考卷/留出合同的实际建模验收仍由既有案件 skill 承接。输出除三件套路径外，还须给正式词表哈希、工具回执和未完成事项。

第一遍逐条款结果必须含主题、可约定点、摘句、当事方、原文模态词；证据位置为 `{file,text_hash,start_offset,end_offset,quote}`，切片等于 quote。候选单元审阅文件列三资格、默认吸并判断及证据；用户自然语言意见由 agent 整理为定稿清单。未收到意见不能进入第二遍。

第二遍输出按已定单元列槽、value_schema、例句、归属、条件适用说明。第二道人审后才形成正式变更文件并调用词表 CLI；最终词表、证据包、判定表三者对应，残留条款、考卷可表达性、法律清单结果附后。人审文件格式不强制；机器交接文件遵守本规格，不能把“存在 review 文件”当作批准。

### 10.5 治理

输入为明确的案件清单或用户要求，proposal 文件明确问题、当前是否可表达、拟增删条目、孤立槽处置及依据。人工意见后 agent 整理同一个变更文件；主会话调用已批准 CLI。成功摘要须与回执的 before/after_hash、ID 映射和差异一致；旧案的冻结表逐字不变。

入口为 `skills/legal-vocab/SKILL.md`，另需明确当前词表路径与工作目录。按输入使用 aggregate、list/show、混合变更或已批准的 add/remove、diff；不因进入治理而自动重跑入库或初始化。输出建议/意见文件路径、实际提交文件与回执、变更摘要；未经人工意见的建议不作为已执行变更。需要查看尚未转换的证据时读取预处理 skill 的调用说明。

自然语言意见互相冲突或无法决定新的哈希冲突时向用户核实。意见文件不设计机械审批语法，工具也不以它的存在替代用户决策。git/PR 交付遵循实际仓库及既有授权；环境缺失时报告待交付，不能伪造已发布。

## 11. 六查、质量状态与数值提示

### 11.1 范围和报告

默认 scope 为每素材最新 text_version 的 ID 集；--text-version 指定一个 ID。当前业务记录的结构、引用与出处全部检查，不能因其只锚定旧转换版本而漏掉；字符/分类覆盖和值候选按所选文本范围检查。--history 额外检查全部历史业务记录及其实际证据，字符覆盖对每个发生过条款变更的提交序号取当时最新条款集合，不把所有修订片段叠加拼接；未曾完整提取的中间版本不因 --history 被追认必须已提取。旧时引用以当时视图检验，不把后来撤销误作当年错误。

返回 `{ok:true,report_id,checked_sequence,scope:{text_version_ids,history},rule_version:"1",passed,checks,errors,notices}`。对账确已完成即 ok=true；passed 取 errors 是否为空，false 时退出 4。checks 为六项 `{name,passed,error_count,notice_count}`，固定顺序 character_coverage/anchors/value_candidates/value_roundtrip/classification_coverage/appellations。每个诊断至少含 `code,message,record_id,path,text_version_id,clause_id`，不存在的位置用 null；值提示另给原文 start_offset/end_offset/surface/related_gaps。排序按检查顺序、文本ID、条款序号、位置、记录ID、path、code；缺值排前。

| 检查 | 精确失败条件与 code |
|---|---|
| character_coverage | 当前条款按 sequence 排列，sequence 从 1 连续；区间首0、相邻首尾相接、末尾全文长度；切片逐字相同。不满足 CHARACTER_COVERAGE；无条款而全文非空也失败 |
| anchors | 引文及版本链按 §4.2；失败沿用 ANCHOR_*，不自动换锚 |
| value_candidates | §11.2 未对应候选一律 VALUE_CANDIDATE_DIFFERENCE notice，无 errors |
| value_roundtrip | 对所有适用 II 级来源执行 §6；失败 ROUNDTRIP_FAILED/UNKNOWN_FORMAT_CONTRACT |
| classification_coverage | unclassified、ordinary无标签、缺少对应完整提取完成事实、无当前有效内容支撑、断言缺出处分别 CLASSIFICATION_MISSING/EXTRACTION_INCOMPLETE/CONTENT_UNSUPPORTED/MISSING_SOURCE |
| appellations | 已记录 label 出现位置、主体目标及来源按 §4.2；错误 APPELLATION_INVALID；关系主体与事件参与者的引用/出处类型错误同时列入；不扫描未知称谓 |

全局业务不变量（引用、槽结构、版本链）在对账读取时复核并归入其对应的 anchors/value_roundtrip/classification_coverage/appellations 检查，不另造第七查。重定向语义冲突作为 IDENTITY_CONFLICT notice；定向环为结构错误，不可作为合法当前图。

### 11.2 值候选定位

按每条款原文从左向右识别：优先日期，再百分数，再数字；同起点取最长匹配，选中后跳到末尾，避免日期里的年/月/日又各报一次。日期候选为四位年后 `年` 加一至二位月及可选日，或 `YYYY-MM`/`YYYY-MM-DD`；百分数是十进制数紧邻 `%/％`；数字为可选负号、整数（含规范三位逗号分组）、可选小数。以 ASCII 数字为数字字符；不识别中文大写金额，不承诺穷举自然语言数值。

候选的 start/end 为全文字符位置。若 quantity 或 time/date 的来源锚范围覆盖该候选，且候选表层能对应其 II 级 surface，或其 I 级表层数值/日期与值按配置可作精确格式比较，则为已对应。不能仅因一个大段锚里存在某个值，就把该段全部其他数字算已对应；数字在别处相同也不抵销。

无法做上述确定比较的一律留下 notice，可附所在条款缺口。页码、条号误入候选不报漏提。提示词法变化须改变规则版本；不影响入库原子成功条件。

### 11.3 查询质量和进度

quality 为 `{state,report_id,checked_sequence,current_sequence,scope,errors_count,notices_count}`。state 四值：not_checked（无任何报告）、passed（当前范围且当前序号零错误）、failed（当前范围且当前序号有错误）、stale（有报告但范围/序号已变化）。query 的 quality 取全案当前默认范围：先选覆盖此范围且 checked_sequence 等于当前序号的最新报告，否则返回最近报告并标 stale；没有任何报告才 not_checked。无报告的 ID/checked_sequence/scope/counts 为 null；不把 null 错误数当零。

progress item 为 `{materials,unclassified_clauses,uncompleted_clauses,latest_overview_id,event_ids,quality}`，materials 每项恰为 `{material_id,text_version_id,split_completed,clause_count}`；条款列表为 object_id 数组，event_ids 为当前active事件ID数组，latest_overview_id 无时null。整个所选范围无任何条款时，不能以零条款循环得到“入库完成”：对账 classification_coverage 返回 EMPTY_SCOPE 错误。报告不过不会禁用其他命令。

## 12. 条款切分

### 12.1 参照源码与复用边界

用户提供了 `/home/luke/projects/skills/contract_v3`。已核对的具体文件为 `src/contract_core/scripts/scan_structure.py`，源字节 SHA-256：

```text
d48b432865dcc66fb3693dc07b6b12b364b8d558c9d01dde317ff085c1cb16b3
```

该版本只导出章节/条款行号、标题及异常；读取时使用普通 read_text，会归一化换行；条款结束行延伸到后续条款前；无编号部分不会独立成为完整条款清单。因此不能把它的 total_chars、title 或 line_end 直接作为本项目原文和字符覆盖的依据。

原算法版本 `contract_v3.adapted.1` 的空行切片规则已被验收报告 §4.0 否定。整改后的版本为 `contract_v3.article.2`；识别器仍以已核对的 contract_v3 扫描方法为基础，组织层级和 article 范围参照其 render_structure、split_topics 行为，但不把渲染后的重排文本入库。旧版回执和条款对象保留，已有文本版本不自动重切。

### 12.2 标题候选识别

保留源码的识别次序与限制：

1. 语言判断取前100个 LF 分隔行；CJK 比例大于0.3为 zh，小于0.1为 en，其余 bilingual；空样本为 en。分母去 LF 和 ASCII 空格，其余保留。
2. 只在识别副本上去首尾空白、开头最多6个 `#`、随后 `>` 引用标记、整行成对1—3个星号包裹。原文不变；所有边界仍是原始物理行的开始位置。
3. 附件 token 优先；中文为“附件”加源码支持的中文数或数字，英文 Appendix/Exhibit/Schedule/Annex 不区分词大小写，编号只允许大写字母或数字。同行多个 token 只是识别提示，原文整行不被重排或合成。
4. zh/bilingual 按中文章→编/部分→节→条→十进制识别；en/bilingual 再按 ARTICLE→Section→Clause→数字段落识别。
5. 中文字符集合和英文续接词排除集合以固定源码为准。中文子项正则虽已定义，主扫描没有用它建立单独条款，不能因看到常量就声称子项已独立识别。
6. 十进制每段1—3位、至多4层，拒绝继续连接数字或点；数字后紧接年月日号点时分秒不作标题。单层裸数字没有行内标题不作标题；两层以上可独占一行。
7. 原扫描器的 `chapters/articles` 是候选结构，不直接等于本项目最终的打标层级。英文 `ARTICLE`、单层十进制编号在不同合同中可能是章或首层 article；依据转换文本中的标题层级、编号序列、相邻标题与正文共同判定。有章时选章下一级 article；无章时选第一层合同条目。文档题名、目录、附件目录不是据标题级别自动判定为章。无法可靠判定时保留文字并产生结构异常，不将孤立条件或续段伪装成 article。
8. 交叉引用仅因软换行来到行首，不得成为标题边界。需要可靠标题标记或独立编号条款形态，并检查前后文是否为同一句的续接。`_resolve_decimal_chapters`、`_apply_party_restart` 只供候选判断，不删除正文；标题借读不改变原文。

Markdown 标题层级的确定规则：先排除目录、附表目录及显式 `.unnumbered` 的导航标题；顶层若显式写“第…条”、`ARTICLE`、`Clause` 或 `Section`，按无章合同处理，顶层即 article。顶层显式写章标题时，其下一层为 article。没有这些字样时，若下一层标题分别出现在至少两个顶层标题之下，按有章合同处理；否则顶层为 article。下一层明确写条标题时也按有章合同处理。article 以下更深标题仅属于其正文，不独立切分。对无法由上述证据可靠认定的输入，应保留完整原文并在结构异常中显明不确定性；转换程序应尽可能输出真实标题层级及可见编号。

旧源码的精确识别函数作为此版本的参照；源码变化须核对哈希、升级算法版本及用例。已经保存的条款不自动重切。识别的局限通过无编号段提示保留，不为本次规格悄悄修改词法范围。

### 12.3 从候选到无丢字条款

以下为 principles 既定四项适配的确定落位：直接写条款、地址消歧、无编号段显式记录、异常入缺口表。

1. **物理行**：以 LF 分行，保留 LF 及前面的 CR；无末尾换行也保存最后一行。仅 CR 的源文本按一行保存，不改写。每个行首位置由原字符串字符数累计，Unicode 按码点计，不按 UTF-8 字节或可见字形计。
2. **分析单位**：一个可靠识别的 article 标题开始一条可独立打标的基础区间，延续至下一个同层 article、上级章节或独立附件区域之前；其内部更深层标题、全部段落、条件、例外、表格及表后说明都在该区间。章标题及章引言作为独立、可寻址的上下文区间，不与相邻 article 在基础覆盖中重叠。前言、签署页等非 article 区域同样有基础区间；其中独立规定允许例外打标提取。编号可空，`sequence` 只表示区间顺序。
3. **边界来源**：只采用可靠的结构标题或独立条款编号起点及真正独立的前言、附件等区域起点。空行、普通段落起点、表格行及其起止、内部子标题均不成为 article 边界。纯正文的行首 `Clause`、`Schedule` 等交叉引用若与前句续接，不产生边界。无法判定归属的连续范围保留并记 structure_anomaly，不逐空行制造疑似条款。
4. **表格与上下文**：表格随所属 article 完整保留，表头、费率行、共同限制及表后说明须可共同阅读。章标题和共用引言可作为分组阅读上下文重复提供，但其基础区间仍只占全文字符一次。转换若已丢失行列关系，应由预处理异常说明，切分器不猜列坐标。
5. **字符覆盖**：加入0和全文长度，按已接受的区域起点构造连续半开区间；所有区间不重叠且拼接逐字符等于登记全文。区间之间的空白归前一区间，开头空白归开头区域；空文本零区间，全空白非空文本保留一个区间。不得借用 render_structure 的清理、重排和软换行合并结果替换原文。
6. **编号与地址**：按区间顺序赋 sequence=1..N；原文编号按已登记文本的真实标题保存，可空、可重复，不以编号当稳定 ID。真实 DOCX 自动编号应由显式配置的转换器写入新 `text.txt` 并与原件核对；只看目录不能凭空补号。既有文本及锚不就地更改。
7. **异常**：编号跳跃、重复、混用以及不确定归属仍记 structure_anomaly；无编号不自动生成异常，也不自动宣称无内容。每条异常锚到相关原文，reported_by 使用 `splitter:contract_v3.article.2`。字符不守恒则整次 split 失败。
8. **事务**：条款、新锚、结构缺口及成功回执同一事务；classification=unclassified、tags=[]，不写 extraction_completions。结构 gap 的证据可引用本批锚，锚再固定本批条款。split 的原始管理输入和回执保留算法版本。

### 12.4 固定样例

以下 `\n`/`\r\n` 为输入字符串中的实际换行，列表每项是完整预期片段。所有片段拼接必须等于输入；sequence 按列表顺序。

| 输入 | 预期片段与编号 | 异常 |
|---|---|---|
| `第一条 付款。\n第三条 交付。\n第三条 验收。\n` | 三行各一片段，编号第一条/第三条/第三条 | skip、duplicate；地址各不同 |
| `1. 合同价款\n1.1 支付价款。\n1.3 结算。\n`（无章标题） | 全文为第一层 article 1. 的一个区间，1.1/1.3 为内部规定 | 不能仅因小节编号或换行另设独立责任 |
| `CHAPTER I PAYMENT\nSection 1 Amount\nBuyer pays.\nSection 2 Delivery\n` | 章标题独立区间；Section 1 连同正文；Section 2 独立 article | 章标题供两个 article 作上下文 |
| `合同名称\n甲方：甲\n\n双方另有约定。\n` | 全文一个非 article 区间，编号 null | 不按空行切分；内容是否独立打标由正文判断 |
| `> **1.1 付款。**\r\n> 1.2\r\n收到后付款。\r\n` | 第一行；第二三行合一，编号1.1/1.2 | 原样保留全部标记及CRLF |
| `第一条 正文。\n附件一 清单 附件二 图纸\n第二条 后续。\n` | 三行各一片段，附件原文不拆写 | 后续第二条必须被识别，不被附件区吞掉 |
| `提前\n60\n天通知。\n` | 全文一个非 article 区间，编号 null | 60 不是标题；结构归属不确定时记一次异常 |
| `第一条 价格。\n\n\|品名\|金额\|\n\|A\|100\|\n第二条 交付。` | 第一 article 连同空行和整表；第二 article | 表格不独立切分；末尾不补换行 |
| 空串 | [] | split成功但入库不能据此宣称完成，六查EMPTY_SCOPE |
| ` \r\n\n` | 原字符串一片段 | 无数字编号提示，不丢空白 |

字符地址样例：输入 `第一条 甲。\n第二条 乙。`，两个区间必须为 `[0,7)`、`[7,13)`；该断言可直接发现按字节计数或擅自丢换行的实现错误。

## 13. 验收执行约定

未来测试代码全部位于 src/tests，使用标准库 unittest。每个用例建立独立临时目录和案件库，通过与产品一致的解析/事务路径或实际 CLI 进程调用；不得只在测试里重写同一规则后相互比较。

标识和时间的非确定性：以响应取得的 UUID 绑定符号，再检查引用相等、对象稳定、版本变化、哈希和计数；不把 UUID 字面值写死。除 UUID/时间/临时路径外，预期 code、path、退出码和业务内容均确定。进程重启后仍须通过重放/历史/原件检查。

三层结果分别报告：①规格文档的一致性检查；②实现对下列行为用例的通过率；③真实合同语义验收。实现虽已开始，第二、三层仍须实际执行后才可标绿。用例名称与 design §17.2 一一对应，失败定位具体要求。

## 14. 固定输入与验收断言

### 14.1 共用最小场景

只在测试中用 U 表示付款单元，S 表示金额槽，T 表示通用文本槽；其正式 ID 用 UUID 生成并绑定。U 的 name=付款、description=测试付款；S 的 value_schema 为 quantity(CNY) 与 reference(node:defined_value) 的 one_of；归属为 U→S；T 的 schema 为 text 且无归属。真实程序 init 不自动创建这些条目。

原始字节取 UTF-8 的 `第一条 甲向乙支付100元。\n`；文本保持相同。调用 init→register→split 得到 C。preparation 同批建立全句锚及主体甲、乙，来源根路径引用该锚；tagging 为 C 追加 ordinary、tags=[U]，来源引用旧 C 版本上的锚。随后 extraction 负责 C，以局部编号 A/R/D 建锚、付款关系、金额细节，全部有来源：

```json
{
  "local_id": "R",
  "kind": "relation",
  "data": {
    "relation_kind": "party",
    "unit_id": "${U}",
    "parties": [
      {"subject": {"object_id": "${甲}"}, "nature": "obligor"},
      {"subject": {"object_id": "${乙}"}, "nature": "recipient"}
    ],
    "modality": null
  },
  "evidence": [{"path": "", "source": {"level": 1, "anchors": [{"local_id": "A"}]}}]
}
```

`${...}` 是测试文件生成前的符号替换记法，不是产品接受的 ID。A 固定到 C 的读取版本且 quote=`甲向乙支付100元。`；D 为 `{owner:{local_id:"R"},slot_id:S,value:{form:"quantity",amount:"100",unit:"CNY"}}`，证据同 A。不得提交原样占位符声称案例可运行。

### 14.2 行为用例

| 编号 | 输入与操作 | 必须观察到的结果 |
|---|---|---|
| A01 | 同 JSON 重复键、NaN、bool 作为 sequence、非法 UTF-8 各独立提交 | 退出2；INVALID_JSON 或 INVALID_ARGUMENT；所有正式表计数不变 |
| A02 | A 的 quote 改不存在；C 为 `aaaa` 时 quote=`aa` 无 occurrence、再 occurrence=2 | 首次 ANCHOR_NOT_FOUND；第二次 ANCHOR_AMBIGUOUS；补2通过且起点1、终点3 |
| A03 | 合法 R/D 后追加一条引用不存在目标的最后记录 | 全份退出2；R/D/新锚/完成/回执均不入库 |
| A04 | 最小 extraction 成功，换文件名、缩进及对象键顺序重提 | 第二次 replayed=true；其余回执相等；表计数与首次成功后相等 |
| A05 | D.amount 从 "100" 改为等值 "100.00"，保留原锚并给正确 previous；成功后重提同文件 | object_id 相同、record_id不同、revision+1；重提成功复用，不因前驱过时失败 |
| A06 | D.amount="100.0"、"100.00" 两个不同修正文件使用同一前驱及原锚，顺序提交 | 第一个成功；第二个 STALE_REVISION，包含 current_record_id；第二份零写入 |
| A07 | 只为 C 补标签；再按 record_id 查旧 C/旧锚 | C ID稳定；旧文本不变；anchor仍解析原版本；原完成资格不因只有标签改变消失 |
| A08 | 单独撤销 R；再把 R、D 一起撤销 | 前次 WITHDRAWN_TARGET 且零写入；后次成功，默认查不到两者，history含原记录和撤销理由 |
| A09 | 以完整前驱数据撤销 R，同时新建 R1/R2 和其明示细节 | 新对象ID独立；没有自动复制共享金额；只有合同依据明确存在的关系才在夹具中出现 |
| A10 | 关闭连接，复制单个 db 到另目录，删除原输入文件后导出原件 | 导出字节与初始字节完全相等，SHA-256相等；无需原路径 |
| A11 | 同关系 modality 缺席及 null 两种合法文件；不存在统一 polarity | 两种均通过且不补 obligation；禁止行为按文本槽可读，未知 polarity 字段拒绝 |
| A12 | 提前 preparation 写事件 E，无 extraction | event 可查询；C 仍 uncompleted；不得仅凭事件锚通过提取覆盖 |
| A13 | C tags=[U,U2]，group；两个任务把 C 都放负责集 | 分组含两个副本且文本相等；分配集合检查失败，禁止启动有重复责任的任务 |
| A14 | 原文另有日期/编号，未提对应值；合法 appellation 名称及无绑定错误分别测试 | 数值仅 notice；已有无效绑定为 error；不宣称发现原文未识别称谓 |
| A15 | 一个关系未建 S、一个 S.value=null 且原文留空、一个有 missing_slot 缺口 | query 分别表现 missing_slots、显式null、gaps；三者不合并；不得产生0 |
| A16 | 删除 U 导致 S 无归属，先无处置，再分别 remove/reassign/general（独立库） | 首次 ORPHAN_DISPOSITION_REQUIRED、hash不变；三个明确处置各按结果通过 |
| A17 | 案件冻结词表后修改全局，查询旧案同槽解释 | 使用旧快照；vocabulary_hash 与旧配置不变 |
| A18 | 未提取时 reconcile，再 query/register/write；写后查旧通过报告状态 | 对账退出4但其余操作可做；新增提交后 state=stale；需要新对账才 passed |
| A19 | A→B、B→A 的 redirect 同批；另测 A→B 和 A→C | 环整批 REDIRECT_CYCLE；分歧保留 candidates/conflicts，不按后写覆盖 |
| A20 | 正文及补充材料相反内容，amendment 指向关系 | 两者均active且可查；原对象版本不因材料登记顺序递增 |
| A21 | 固定 detail 版本的 /value/items/0 子值引用，之后修订数组顺序 | 原路径读旧值；把 value_path 改挂 object_id 拒绝；历史输出提示changed |
| A22 | evidence缺unit来源、III级闭环、II级值改数、有效III级所有前提有锚 | 分别 MISSING_SOURCE、SOURCE_CYCLE、ROUNDTRIP_FAILED；有根的无环图通过 |
| A23 | 整份业务已写成功但模拟丢弃stdout，重启进程重提 | 回执取回同ID与计数，不新增记录 |
| A24 | preparation含overview与非法事件记录 | 全份失败，overview也不保存；修好后同事务两者保存 |
| A25 | 查询同类两party过滤、party+unit、分页最后页、未知过滤ID | OR/AND符合§9.3；total分页前值；末页next=null；无匹配返回no_record退出0 |
| A26 | 已有目标文件执行init、导出或group；写入中模拟I/O失败 | 不覆盖用户文件；返回3；数据库或词表没有部分更新 |
| A27 | 词表one_of重叠分支、重复归属、缺失unit、未知字段 | 对应校验失败；不接受“某分支过了就行”或静默丢字段 |
| A28 | 不同snapshot同名槽缺口聚合，及其中一个库不存在 | 前者保持原案ID/解释；后者整体失败，无伪完整报告 |
| A29 | R/D 撤销后，只恢复 D；再同批恢复 R/D | 首次 WITHDRAWN_TARGET；后次各自同ID追加active版本，历史含撤销；不自动恢复其他记录 |
| A30 | 原有 gap 固定 C/R 的发现版本，随后撤销 R 或拆分 C | 缺口原行不变且可回查；不阻止有完整依赖处置的纠错；查询提示changed/withdrawn，不当新条款覆盖 |
| A31 | defined_value.value=null；list第一项amount=null、第二项实值，各有原文留空或实值锚 | 通过；返回空位置原样，未改为0或缺席；去掉空位置依据则 MISSING_SOURCE |
| A32 | 依 §12.4 输入逐项 register/split，另重复同成功 split | 各片段、编号、位置及异常与表一致；重提同ID，不增条款或缺口 |
| A33 | 当前D已改为"100.00"，用--record查询原R版本，再查当前R | 历史展开只含该版本提交时的D="100"，当前展开含D="100.00"；expansion_sequence明确且不改原R版本 |
| A34 | decimal表层"123456789012345678901234567890.12元"，2小数、无分组、scale=1 | 精确通过；目标末位改成13必须失败，不因默认精度舍入而误通过 |
| A35 | 受控转换器依 §9.7 产出含 CRLF 和中文的 text、合法 metadata；stdout/stderr 均打印日志 | 最终文本字节不变、哈希可复算；CLI stdout 只有成功 JSON，日志在 stderr；register 能原样读取两文件 |
| A36 | 分别使用坏配置、非零退出转换器、缺 metadata、非法 UTF-8、非法异常区间、改写原件的受控转换器 | 对应 INVALID_ARGUMENT、CONVERTER_FAILED、CONVERTER_OUTPUT_INVALID、ORIGINAL_CHANGED；未发布成功产物，未调用 register；夹具原件均为临时测试数据 |
| A37 | 向非空输出目录转换；另模拟发布第二个文件时 I/O 失败 | 前者 FILE_EXISTS 且旧文件不变；后者退出3并清理本次文件，清理失败如实附报；均无成功回执 |

### 14.3 共同约束的模型验收夹具

原文固定为“甲乙共同向丙支付100万元，任一方付清后，两项付款义务均终止。”前置事件 E 的描述为任一方付清该共同款项，参与者与依据完整。测试词表另提供共同安排单元、总额引用槽、终止条件槽、原文说明槽；只用作此样例。

必须有且只有两条当事人付款关系：甲→丙、乙→丙；共同定义值 V=1000000 CNY；两条关系的金额细节均指 V。合同规定 M 的内容明确“共同总额”及条件 E、原文含义，scope.to 同时指两条付款关系。查询只读结构与出处即可回答共同总额为100万元、任一方付清的影响覆盖两条关系；不得把两条记录相加输出200万元，不自动新增甲↔乙义务。

局部例外夹具原文“该报告仅作为付款条件，不作为质量合格依据”：用同一个限定记录及 scope 的适用/排除目标，查询中目标分别指两个细节；不能标整个合同不适用。分期夹具用两个 list 项把第一期10%/E1/10日、第二期90%/E2/30日分别对应；交换条件与金额须被只读库问题判错。上述语义断言用人工指定夹具期望检查，不构建通用合同理解核对器。

### 14.4 skill 的行为验收

| 场景 | 预期 |
|---|---|
| 人工意见尚未写入 | 初始化停在原有人审环节，不把空意见或时间经过当同意 |
| 用户指定 held_out 合同 | 第一、二遍归纳证据不得使用该文件；验收仍可读取其建模结果 |
| unit读手输出失败 | 主会话每文件一次write，原读手修正，其他成功文件不重提取 |
| 重启时工作目录回执丢失 | 从库查询/重放取回结果；不依赖独立任务状态机 |
| 词表建议获准后hash变化 | 工具拒绝旧hash；agent对照新内容，无法由原意见决定才询问用户 |
| 转换器不存在或转换失败 | 预处理明确报失败；未登记伪造文本；不开始下游关系提取 |

真实合同考卷继续记录可答且对、可答但错、不可答及原文/缺口证据；没有用户提供的期望答案时不能自行规定“达到某百分比即整体通过”。所有机械强制用例必须全通过；语义验收结果按既有流程交人看报告。

### 14.5 七件交付物的目录与引用验收

| 场景 | 必须满足的断言 |
|---|---|
| 检查完整目录 | §1.3 七个入口全部存在；四个 name 与目录一致；§1.4 全部引用可读；无项目代码位于 legal/src 外 |
| 将运行目录复制到含中文和空格的新路径，原 docs/contract_v3 不可访问 | 三个模块的 --help 成功；四个 skill 只靠完整目录内文件可获得全部指引；程序没有硬编码原工作区路径 |
| 从另一案件工作目录提供相对输入路径 | skill 先解析为正确绝对路径；CLI 在程序根启动仍读写指定数据；不在源码目录产生案件库、词表或任务文件 |
| 宿主通过链接或等价引用加载 skill | 以真实源目录找到共用资料、兄弟 skill 和 CLI；宿主不支持该引用方式时明确未注册成功，不假装复制单文件即可使用 |
| 仅复制某一个 SKILL.md | 视为不完整安装；报告缺少引用资源，不临时生成第二套 CLI 或到其他项目猜路径 |
| 未安装转换器，仅运行案件/词表帮助及 JSON/SQLite 操作 | 不尝试导入外部转换库；转换调用缺有效配置时明确失败，既有建模操作仍可用 |
| 逐个检查四个 skill 的工具用法 | 每个都可定位实际入口、参数、输入/输出格式、错误与继续条件；案件主会话每份提取文件只调用一次 write |

以上为未来实现与交付验收，当前只做文档一致性检查，不声称已完成宿主注册或程序运行。

## 15. 本轮裁决与完成边界

- decisions §1.25 记录原规格阶段“只完成 spec、不开始实现”的范围；后续用户已明确转入实现，见 decisions §1.34。全部代码位于 legal/src。
- 用户允许追加 active 完整版本恢复误撤销对象，见 §1.26、本文 §8.3。
- 用户确认缺口固定发现时版本，见 §1.27、本文 §3—§4、§8.3。
- 用户提供 contract_v3 源码供参考；已核对并固定来源版本，沿用已定适配范围，见 §1.28、本文 §12，不再把源码缺失列作前提。
- 用户确认原文留空可在复合值内部与定义值使用 null，见 §1.29、本文 §5.1。
- 用户确认历史关系查询展开该版本写入时的细节，当前查询仍展开最新内容，见 §1.30、本文 §9.3。
- 用户确认七件交付物组成完整目录、四个 skill 共用 CLI，预处理提供统一入口，首版保持宿主通用；见 decisions §1.31—§1.33、本文 §1、§9.7、§10、§14.5。

本轮提交的设计问题均已收到答复。技术字段约束和参数默认值是规格细化，不冒充逐条用户裁决。未来实现如发现不能按本契约执行的冲突，须先修正规格，不能让代码无声改变含义。

**外部组件边界明确保留**：真实 PDF/Word/OCR 的具体工具尚未选定，本文限定其输入输出及失败行为，不声称已经完成该外部工具内部设计；人工审阅与真实合同考卷的语义质量不能由格式测试证明。核心工具及四个 skill 的实现与验收规格已写明；代码已开始落地，自动验收程序尚未创建，行为与真实合同验收尚未执行。
