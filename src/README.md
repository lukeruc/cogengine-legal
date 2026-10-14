# 法律关系建模工具：安装与使用

当前发行版本：`0.1.5`。GitHub 仓库的 `src/` 是完整交付源码目录，包含一个 Python 包、三个命令、四个 skill、共用说明及安装脚本。本项目为一份特定合同建立带原文出处的 SQLite 记录；合同数据不放在程序安装目录。

完整发行源码还包含仓库根目录下的 [词表示例](https://github.com/lukeruc/cogengine-legal/blob/v0.1.5/vocab/vocabulary.json)。使用时将其复制到自己的词表工作目录，再按第四步登记。安装程序不会自动将其设为默认词表。

## 安装前准备

- 从 [v0.1.5 发布页面](https://github.com/lukeruc/cogengine-legal/releases/tag/v0.1.5)下载完整源码并解压，或取得该标签对应的完整仓库。下文 `SOURCE_ROOT` 指向包含 `src/` 的源码根目录。只复制某一个 `SKILL.md` 无法安装或运行工具。
- 明确一个 **Python 3.11、3.12 或 3.13 的绝对路径**。该解释器须带 `sqlite3`、`venv` 和 pip；构建 wheel 时还须有 `setuptools>=68` 和 `wheel`。核心程序本身没有第三方 Python 运行依赖，`requirements.txt` 不能代替包安装。
- 选择一个可写的**安装根**。它应独立于本仓库源码目录和合同工作目录；下文以 `/path/to/legal-install` 示意。
- 宿主需要能读取完整 skill 目录及其相对引用、运行本地命令，并支持项目既定的子任务和人工文件意见交接。宿主注册方式由该宿主决定。

先检查选定解释器及构建工具。下文每个 shell 代码块均包含所需变量，可从任意工作目录独立执行。将路径替换为本机真实绝对路径，并在同一次 shell 调用中执行整个代码块；agent 若拆成多次工具调用，须在各次调用中重新提供所需变量，不能假定上一次的变量或工作目录仍被保留。

```bash
PYTHON_BIN="/absolute/path/to/python"
"$PYTHON_BIN" --version
"$PYTHON_BIN" -m pip --version
"$PYTHON_BIN" -c 'import sqlite3, venv, setuptools, wheel; print("安装前提可用")'
```

若仅缺构建工具，先为**选定的构建解释器**安装 `setuptools>=68` 和 `wheel`；这是构建依赖，不是本项目的核心运行依赖。真实 DOCX、PDF、OCR 转换程序及其依赖另行配置，安装本项目不会自动取得这些转换能力。

UTF-8 且无 BOM 的 `.md`、`.markdown`、`.txt` 文件无配置时可直接接收，后缀大小写不敏感。显式提供转换配置时优先使用该配置，失败不会静默改用直通。DOCX/PDF/扫描件缺少适用转换器时，agent 报告受影响材料及需补充的配置。

## 第一步：构建 wheel

指定源码根目录、构建解释器和 wheel 输出目录：

```bash
SOURCE_ROOT="/absolute/path/to/cogengine-legal"
PYTHON_BIN="/absolute/path/to/python"
DIST_DIR="/absolute/path/to/legal-dist"
"$PYTHON_BIN" "$SOURCE_ROOT/src/scripts/build_release.py" --output-dir "$DIST_DIR" --python "$PYTHON_BIN"
```

本版本正常生成文件名形如 `cogengine_legal-0.1.5-py3-none-any.whl`。检查实际产物文件名，再把它用于下一步。wheel 包含 `legal/` 的运行模块、`schema.sql` 和 `config/units.v1.json`；测试、真实合同、词表内容和特定合同的辅助脚本不进入运行包。四个 skill 与共用说明由安装脚本从同一份交付源码复制到安装根。

## 第二步：安装程序与共用环境

指定安装根和刚构建的 wheel：

```bash
SOURCE_ROOT="/absolute/path/to/cogengine-legal"
PYTHON_BIN="/absolute/path/to/python"
INSTALL_ROOT="/absolute/path/to/legal-install"
WHEEL_FILE="/absolute/path/to/legal-dist/cogengine_legal-0.1.5-py3-none-any.whl"
"$PYTHON_BIN" "$SOURCE_ROOT/src/scripts/install_release.py" \
  --install-root "$INSTALL_ROOT" \
  --python "$PYTHON_BIN" \
  --wheel "$WHEEL_FILE"
```

脚本先核对选定解释器的版本、SQLite、venv 和 pip，再在安装根创建本项目专用的 `.venv`。三个命令 `legal-case`、`legal-vocab`、`legal-preprocess` 及全部运行模块、SQL 与单位配置通过 wheel 安装为该环境内的独立副本。脚本从源码和安装根之外的临时目录核对包版本及资源，运行三个 `--help`，并用临时词表执行数据库初始化及查询。全部通过后，复制四个完整 skill 目录、共用说明、注册核对脚本和供安装维护时查阅的 README，再原子写入 `runtime.json`。临时词表和数据库不会成为正式合同数据。

成功回执包含 `"ok":true`、`"program_installed":true` 和 `"host_registration":"pending"`。最后一个字段表示**程序安装完成，宿主中的 skill 注册尚待完成**。失败时脚本向 stderr 输出 `{"ok":false,"error":"..."}`，不能把部分生成的目录视为成功安装。

安装后的主要布局：

```text
<install-root>/
  README.md                    安装维护说明，skill 运行不读取
  runtime.json                 工具及专用环境信息
  workspaces.json              工作区、合同工作根和词表列表的对应关系
  vocabularies/
    workspace-1.txt             用户创建的词表路径列表，首个非空行默认
  .venv/
  scripts/
    verify_registration.py
    prepare_task.py            主会话的启动、建案和材料准备入口
  skills/
    legal-case/
      SKILL.md
      scripts/find_quote.py
      scripts/build_submission.py
      scripts/complete_task.py
      references/startup.md
      references/helper-tools.md
      templates/               各角色模板，含两种 summarizer 分工
      examples/                文件构造样例及虚构夹具
    legal-vocab/SKILL.md
    legal-preprocess/SKILL.md
    legal-initialize/SKILL.md
  references/
    case-cli.md
    vocab-cli.md
    preprocess-cli.md
    data-formats.md
```

安装根还会有本项目的环境标记文件，用来防止安装脚本接管其他项目的环境。`.venv` 为这份安装共用；四个 skill、后续会话及不同合同不会分别创建环境。

安装后的 skill、CLI 和注册核对脚本均可脱离下载的源码运行。构建、安装使用源码；业务运行和注册核对只使用安装目录中的副本。删除下载的源码不会影响已安装工具，四个 skill 也不以 README 的存在或读取为运行前提。

## 第三步：在宿主中注册四个 skill

按宿主已有机制，分别注册 `<install-root>/skills/` 下的四个**完整目录**：`legal-case`、`legal-vocab`、`legal-preprocess`、`legal-initialize`。若宿主支持目录符号链接，可以链接整个 skill 目录；不要只复制 `SKILL.md`。宿主看到的入口最终必须能解析到安装根内对应的 `SKILL.md`，并能读取同根的 `runtime.json`、`references/` 及兄弟 skill。注册目标是安装后的目录；源码目录 `src/skills/` 不含运行所需的 `runtime.json`。

注册后，用安装目录中的脚本副本核对。`RUNTIME_PYTHON` 填入该安装 `runtime.json` 的 `python` 值；每个 `--skill` 的值改为**宿主实际看到的** `SKILL.md` 绝对路径，若宿主使用链接，就填链接位置下的路径：

```bash
RUNTIME_PYTHON="/absolute/path/from/runtime/python"
INSTALL_ROOT="/absolute/path/to/legal-install"
"$RUNTIME_PYTHON" "$INSTALL_ROOT/scripts/verify_registration.py" \
  --install-root "$INSTALL_ROOT" \
  --skill "legal-case=/host/skills/legal-case/SKILL.md" \
  --skill "legal-vocab=/host/skills/legal-vocab/SKILL.md" \
  --skill "legal-preprocess=/host/skills/legal-preprocess/SKILL.md" \
  --skill "legal-initialize=/host/skills/legal-initialize/SKILL.md"
```

核对脚本确认四个入口都指向同一安装根，所需共享说明齐全，安装信息中的三个命令存在并能执行帮助。成功时返回 `"host_registration":"verified"`。若宿主通过非文件路径机制注册，须用该宿主自己的方式验证同等条件；不能仅凭程序安装回执宣称四个 skill 已可用。

## 第四步：配置工作区与默认词表

工作区取 **agent 会话打开的目录**，按绝对路径匹配；合同原件位于哪里、后续 shell 切到哪里，都不改变这个值。一个安装可以登记多个工作区，每个工作区指定自己的合同工作根和词表列表。

安装程序初次生成的 `<install-root>/workspaces.json` 为 `{"format_version":1,"workspaces":[]}`。用户可直接编辑，也可明确要求 agent 代为配置。例如，假设安装根是 `/home/user/legal-install`、会话打开的是 `/home/user/legal-work`：

```json
{
  "format_version": 1,
  "workspaces": [
    {
      "workspace_root": "/home/user/legal-work",
      "contract_root": "/home/user/legal-work/contracts",
      "vocabulary_list": "/home/user/legal-install/vocabularies/legal-work.txt"
    }
  ]
}
```

将示例路径换成实际绝对路径。已有配置时在 `workspaces` 数组中增加或修改对应项，保留其他工作区；不要为同一工作区重复登记。字段含义如下：

| 字段 | 含义 |
|---|---|
| `workspace_root` | 会话打开的工作区目录，必须已存在。 |
| `contract_root` | 新合同工作目录的默认父目录，可在建案时创建；本次任务可明确指定其他位置。 |
| `vocabulary_list` | 该工作区的词表路径列表文件，必须放在本安装的 `vocabularies/` 内。 |

创建上例中的 `vocabularies/legal-work.txt`，用 UTF-8 保存，每行只填一个词表文件的绝对路径：

```text
/home/user/legal-work/vocabularies/construction-v1.json
/home/user/legal-work/vocabularies/supply-v1.json
```

词表本身可放在安装目录之外。**首个非空行是默认词表**，上例默认为 `construction-v1.json`。列表允许空白行和 LF/CRLF 换行；不支持注释、引号、`~`、变量、相对路径或重复路径。路径中的空格按实际文件名保留，不要为了缩进而添加空格。

日常管理只需编辑这份列表：

- **新增**：把另一份词表的绝对路径追加到末尾。空列表的第一项自然成为默认。
- **切换默认**：把所需路径移到第一个非空行。
- **仅本次换用**：在请求中指定另一份已登记词表的绝对路径，列表顺序保持不变。
- **取消登记**：删除对应行，不删除词表文件；删除第一项后，下一项成为默认。
- **治理更新**：`legal-vocab` 保留原文件并生成独立新文件；只有明确要求才登记新文件，只有明确要求才调整默认顺序。

新案只加载所选词表，复制到合同工作目录并在初始化时冻结。未登记文件不会自动选用，默认文件失效不会自动跳到下一项。缺少配置时，agent 报告具体缺项，不搜索目录猜测。

程序升级保留 `workspaces.json` 和 `vocabularies/`。旧案件继续使用自己的冻结词表，不因列表变动而更新；续做旧案不要求重新配置当前默认词表。尚无词表时，可先用 `legal-initialize` 归纳并审定，再登记；独立预处理也不需要默认词表。完整调用约定见 [启动与准备说明](skills/legal-case/references/startup.md)。

## 运行时如何找到命令

安装和运行时涉及的路径各有起点：

| 路径 | 起点与用途 |
|---|---|
| `SOURCE_ROOT/src/scripts/` | 下载的源码根目录，用于构建、安装 |
| `<install-root>/` | 安装后的 `runtime.json`、环境、skill、共用资料与脚本副本 |
| `<install-root>/scripts/verify_registration.py` | 安装后的注册核对脚本，使用该安装的 Python 执行 |
| `<install-root>/scripts/prepare_task.py` | 主会话的固定准备入口，处理运行信息、工作区选择和任务材料导出 |
| `<install-root>/workspaces.json`、`vocabularies/` | 用户管理的工作区配置与词表路径列表，与 `runtime.json` 分开保存 |
| 宿主提供的 `SKILL.md` 路径 | 可能经过符号链接，先解析为真实文件路径，再取父目录 |
| skill 中的 `../../runtime.json` 等资料路径 | 以该 `SKILL.md` 的真实目录为基准 |
| 共用 CLI 说明中的 `../runtime.json` | 以该说明文件的真实目录 `<install-root>/references/` 为基准 |
| 合同工作目录 | 业务命令的工作目录及合同数据存放位置 |

各 skill 的“固定启动”片段先解析宿主入口的符号链接，再从确定的安装位置调用 `scripts/prepare_task.py runtime`。该辅助程序读取并核验运行信息，返回安装根、专用 Python、三个命令及工作区配置文件的绝对路径。主会话使用成功回执进入当前阶段，无需列举安装目录、查找 README 或重复检查同一批路径。

`runtime.json` 顶层恰有 `format_version`、`release_version`、`install_root`、`environment_root`、`python`、`commands`；`commands` 恰含 `legal-case`、`legal-vocab`、`legal-preprocess`。核验后按参数数组执行所需命令的绝对路径，例如：

```text
argv = [runtime.commands["legal-case"], "query", "--db", "/absolute/contract.sqlite", "--view", "progress"]
cwd  = "/absolute/contract-work-directory"
```

因此无须激活环境、设置 `PYTHONPATH`，也无须让宿主切换 Python。相对输入先按用户原工作目录解析；传给 CLI 的合同工作副本路径使用绝对路径。含空格或中文的路径是单个参数，不把整条调用拼成 shell 字符串。安装信息缺失、根路径不符或命令失效时，skill 应报告安装问题，不能改用 PATH 上的同名工具。

入库 skill 的 `find_quote.py`、`build_submission.py` 和 `complete_task.py` 随完整目录安装，共用模块随 wheel 装入同一环境。主会话交付专用 Python、脚本和任务文件的绝对路径及适用说明；sub-agent 按需调用精确引句定位、固定字段修订及提交构造。用法见 [辅助脚本说明](skills/legal-case/references/helper-tools.md)。这些辅助脚本只处理文件，正式写入和数据库操作由主会话完成。runtime 的 commands 保持三个正式 CLI。

已有安装要采用这次源码变更时，重新构建 wheel，再用安装命令的 `--upgrade` 更新程序及 skill。安装脚本默认复用同版本程序；即使版本号相同，更新源码构建的程序副本也要使用 `--upgrade`，否则新脚本可能缺少对应共用模块。

三个命令的用途：

| 命令 | 用途 |
|---|---|
| `legal-preprocess` | 直接接收 Markdown/TXT 或按显式外部转换配置生成 `text.txt`、`metadata.json` |
| `legal-case` | 合同库初始化、登记、切分、写入、查询、分组、对账 |
| `legal-vocab` | 词表初始化、查阅、变更、比较、案件缺口汇总 |

完整参数与文件格式见 [预处理命令](references/preprocess-cli.md)、[案件命令](references/case-cli.md)、[词表命令](references/vocab-cli.md)和[数据格式](references/data-formats.md)。源码开发可从本目录使用 `python -m legal.case_cli` 等模块入口；安装后的 skill 使用 `runtime.json` 中的命令路径。

## 合同数据放在哪里

新合同首次入库时，案件 skill 使用已登记的合同工作根（或本次明确指定的工作根），创建唯一的 `contract-YYYYMMDDTHHMMSSZ[-NN]` 目录，将合同原件、选中词表和转换配置的工作副本放入其中，并在根部创建 `contract.sqlite`。转换结果、任务、提交文件、回执、分组与报告也保存在该目录。同一合同后续工作沿用原目录，不重复安装程序或建立 Python 环境。具体组织和命名见[案件命令说明](references/case-cli.md#入库文件位置和命名)。

## 重装、升级与常见问题

| 情况 | 处理 |
|---|---|
| 同一版本再次安装 | 使用相同命令与安装根；脚本核验并复用已有环境。 |
| 明确升级到新版 | 从新版完整交付构建 wheel，安装命令加 `--upgrade`，并重新核对四个 skill 的注册。CLI、skill 和说明须属于同一交付版本；已有工作区配置和词表列表保留。 |
| 本项目 `.venv` 损坏 | 在明确的安装操作中加 `--repair`；脚本只重建带本项目标记的环境。跨版本修复还需加 `--upgrade`。 |
| 需要把交付移到新位置 | 复制完整交付源码，在一个新的空安装根重新安装，并更新宿主注册；旧 `.venv` 和 `runtime.json` 的绝对路径不能直接沿用。 |
| `runtime.json` 缺失或根路径不符 | 停止业务调用；缺失时在原安装根重新执行显式安装，根路径不符时使用新的空安装根。不要在合同目录建环境或改用系统 PATH 中的命令。 |
| 已安装却找不到说明中的相对路径 | 核对是否注册了安装后的 skill，是否先解析了宿主入口的符号链接，以及是否按说明文件所在目录解析相对引用。 |
| 宿主只能复制单个 `SKILL.md` | 该方式无法访问共用说明和安装信息，不能视为完整注册；改用能保留目录关系的宿主机制。 |
| 新案提示工作区未登记 | 在 `workspaces.json` 登记会话打开的目录；合同文件所在目录不能代替会话工作区。 |
| 词表未登记、列表为空或默认词表失效 | 按第四步补全列表或修正选中路径；不要依赖自动搜索或跳选。 |
| 治理生成新版词表后仍使用旧版 | 新文件不会自动登记或变成默认；明确要求登记，并按需调整列表顺序。旧案件的冻结词表保持不变。 |
| 未配置 DOCX/PDF/OCR 转换程序 | 在需要转换时提供符合[预处理说明](references/preprocess-cli.md)的外部程序配置；案件和词表的 JSON/SQLite 操作仍可用。 |

安装与修复只作用于安装根。用户的合同工作目录、独立词表文件和转换器配置是单独资产。仅更新下载源码不会更新已有安装副本。

### 角色派发与文件构造

legal-case 随安装复制 `templates/reader.md`、`summarizer.md`、`summarizer-overview.md`、`tagger.md`、`extractor.md`，以及 `examples/` 中的构造样例与虚构夹具。主会话通过 `prepare_task.py` 导出材料，交付固定角色信息、共享任务上下文、个别任务要求三部分正文。各角色只取得完成任务所需的文件和用法，不需读取源码或 README。

reader 交阅读笔记。随后两个 summarizer 分别输出主体／事件和案件概要，主会话分别写入，两份均成功后再交接打标。后续角色直接使用正式概要作为共同背景。新初读和打标任务导出使用 v2；恢复旧任务时重新导出适用材料，保留旧库和旧任务文件。

结果构造使用主会话预填的绑定和 `complete_task.py`；同一专用环境中的 `legal.reader_helpers` 继续提供序列化、引用、出处、条款修订和组装函数。角色填写判断、依据、正文和明确的完成声明，正式写入仍由主会话完成。文件生成成功不表示已入库或语义完整。
