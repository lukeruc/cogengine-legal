# 法律关系建模工具：安装与使用

当前发行版本：`0.1.0`。GitHub 仓库的 `src/` 是完整交付源码目录，包含一个 Python 包、三个命令、四个 skill、共用说明及安装脚本。本项目为一份特定合同建立带原文出处的 SQLite 记录；合同数据不放在程序安装目录。

## 安装前准备

- 取得完整仓库，进入 `src/`。只复制某一个 `SKILL.md` 无法安装或运行工具。
- 明确一个 **Python 3.11、3.12 或 3.13 的绝对路径**。该解释器须带 `sqlite3`、`venv` 和 pip；构建 wheel 时还须有 `setuptools>=68` 和 `wheel`。核心程序本身没有第三方 Python 运行依赖，`requirements.txt` 不能代替包安装。
- 选择一个可写的**安装根**。它应独立于本仓库源码目录和合同工作目录；下文以 `/path/to/legal-install` 示意。
- 宿主需要能读取完整 skill 目录及其相对引用、运行本地命令，并支持项目既定的子任务和人工文件意见交接。宿主注册方式由该宿主决定。

先检查选定解释器及构建工具。下列命令在同一个 shell 会话中执行；路径均需替换为本机真实路径：

```bash
cd /path/to/cogengine-legal/src
PYTHON_BIN=/absolute/path/to/python
"$PYTHON_BIN" --version
"$PYTHON_BIN" -m pip --version
"$PYTHON_BIN" -c 'import sqlite3, venv, setuptools, wheel; print("安装前提可用")'
```

若仅缺构建工具，先为**选定的构建解释器**安装 `setuptools>=68` 和 `wheel`；这是构建依赖，不是本项目的核心运行依赖。真实 DOCX、PDF、OCR 转换程序及其依赖另行配置，安装本项目不会自动取得这些转换能力。

## 第一步：构建 wheel

仍在 `src/` 目录，指定一个 wheel 输出目录：

```bash
DIST_DIR=/absolute/path/to/legal-dist
"$PYTHON_BIN" scripts/build_release.py --output-dir "$DIST_DIR" --python "$PYTHON_BIN"
```

本版本正常生成文件名形如 `cogengine_legal-0.1.0-py3-none-any.whl`。检查实际产物文件名，再把它用于下一步。wheel 包含 `legal/` 的运行模块、`schema.sql` 和 `config/units.v1.json`；测试、真实合同、词表内容和特定合同的辅助脚本不进入运行包。四个 skill 与共用说明由安装脚本从同一份交付源码复制到安装根。

## 第二步：安装程序与共用环境

指定安装根和刚构建的 wheel：

```bash
INSTALL_ROOT=/absolute/path/to/legal-install
WHEEL_FILE=/absolute/path/to/legal-dist/cogengine_legal-0.1.0-py3-none-any.whl
"$PYTHON_BIN" scripts/install_release.py \
  --install-root "$INSTALL_ROOT" \
  --python "$PYTHON_BIN" \
  --wheel "$WHEEL_FILE"
```

脚本先核对选定解释器的版本、SQLite、venv 和 pip，再在安装根创建本项目专用的 `.venv`。三个命令 `legal-case`、`legal-vocab`、`legal-preprocess` 安装在同一环境。脚本从源码和安装根之外的临时目录核对包版本、SQL 与单位配置，运行三个 `--help`，并用临时词表执行数据库初始化及查询。全部通过后，复制 README、四个完整 skill 目录与共用说明，再原子写入 `runtime.json`。临时词表和数据库不会成为正式合同数据。

成功回执包含 `"ok":true`、`"program_installed":true` 和 `"host_registration":"pending"`。最后一个字段表示**程序安装完成，宿主中的 skill 注册尚待完成**。失败时脚本向 stderr 输出 `{"ok":false,"error":"..."}`，不能把部分生成的目录视为成功安装。

安装后的主要布局：

```text
<install-root>/
  README.md
  runtime.json
  .venv/
  skills/
    legal-case/SKILL.md
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

## 第三步：在宿主中注册四个 skill

按宿主已有机制，分别注册 `<install-root>/skills/` 下的四个**完整目录**：`legal-case`、`legal-vocab`、`legal-preprocess`、`legal-initialize`。若宿主支持目录符号链接，可以链接整个 skill 目录；不要只复制 `SKILL.md`。宿主看到的入口最终必须能解析到安装根内对应的 `SKILL.md`，并能读取同根的 `README.md`、`runtime.json`、`references/` 及兄弟 skill。

注册后，从仓库 `src/` 调用核对脚本。把每个 `--skill` 的值改为**宿主实际看到的** `SKILL.md` 路径；若宿主使用链接，就填链接位置下的路径：

```bash
"$PYTHON_BIN" scripts/verify_registration.py \
  --install-root "$INSTALL_ROOT" \
  --skill legal-case=/host/skills/legal-case/SKILL.md \
  --skill legal-vocab=/host/skills/legal-vocab/SKILL.md \
  --skill legal-preprocess=/host/skills/legal-preprocess/SKILL.md \
  --skill legal-initialize=/host/skills/legal-initialize/SKILL.md
```

核对脚本确认四个入口都指向同一安装根，所需共享说明齐全，安装信息中的三个命令存在并能执行帮助。成功时返回 `"host_registration":"verified"`。若宿主通过非文件路径机制注册，须用该宿主自己的方式验证同等条件；不能仅凭程序安装回执宣称四个 skill 已可用。

## 运行时如何找到命令

每个 skill 先解析自身文件的真实目录，从 `../../README.md`、`../../runtime.json` 和 `../../references/` 读取资料。`runtime.json` 顶层恰有 `format_version`、`release_version`、`install_root`、`environment_root`、`python`、`commands`；`commands` 恰含 `legal-case`、`legal-vocab`、`legal-preprocess`。skill 检查版本、真实安装根、`.venv` 及可执行文件后，按参数数组执行所需命令的绝对路径，例如：

```text
argv = [runtime.commands["legal-case"], "query", "--db", "/absolute/contract.sqlite", "--view", "progress"]
cwd  = "/absolute/contract-work-directory"
```

因此无须激活环境、设置 `PYTHONPATH`，也无须让宿主切换 Python。相对输入先按用户原工作目录解析；传给 CLI 的合同工作副本路径使用绝对路径。含空格或中文的路径是单个参数，不把整条调用拼成 shell 字符串。安装信息缺失、根路径不符或命令失效时，skill 应报告安装问题，不能改用 PATH 上的同名工具。

三个命令的用途：

| 命令 | 用途 |
|---|---|
| `legal-preprocess` | 按显式外部转换配置生成 `text.txt`、`metadata.json` |
| `legal-case` | 合同库初始化、登记、切分、写入、查询、分组、对账 |
| `legal-vocab` | 词表初始化、查阅、变更、比较、案件缺口汇总 |

完整参数与文件格式见 [预处理命令](references/preprocess-cli.md)、[案件命令](references/case-cli.md)、[词表命令](references/vocab-cli.md)和[数据格式](references/data-formats.md)。源码开发可从本目录使用 `python -m legal.case_cli` 等模块入口；安装后的 skill 使用 `runtime.json` 中的命令路径。

## 合同数据放在哪里

新合同首次入库时，案件 skill 在调用方指定的工作根下创建唯一的 `contract-YYYYMMDDTHHMMSSZ[-NN]` 目录，将合同原件、词表和转换配置的工作副本放入其中，并在根部创建 `contract.sqlite`。转换结果、任务、提交文件、回执、分组与报告也保存在该目录。同一合同后续工作沿用原目录，不重复安装程序或建立 Python 环境。具体组织和命名见[案件命令说明](references/case-cli.md#入库文件位置和命名)。

## 重装、升级与常见问题

| 情况 | 处理 |
|---|---|
| 同一版本再次安装 | 使用相同命令与安装根；脚本核验并复用已有环境。 |
| 明确升级到新版 | 从新版完整交付构建 wheel，安装命令加 `--upgrade`，并重新核对四个 skill 的注册。CLI、skill 和说明须属于同一交付版本。 |
| 本项目 `.venv` 损坏 | 在明确的安装操作中加 `--repair`；脚本只重建带本项目标记的环境。跨版本修复还需加 `--upgrade`。 |
| 需要把交付移到新位置 | 复制完整交付源码，在一个新的空安装根重新安装，并更新宿主注册；旧 `.venv` 和 `runtime.json` 的绝对路径不能直接沿用。 |
| `runtime.json` 缺失或根路径不符 | 停止业务调用；缺失时在原安装根重新执行显式安装，根路径不符时使用新的空安装根。不要在合同目录建环境或改用系统 PATH 中的命令。 |
| 宿主只能复制单个 `SKILL.md` | 该方式无法访问共用说明和安装信息，不能视为完整注册；改用能保留目录关系的宿主机制。 |
| 未配置 DOCX/PDF/OCR 转换程序 | 在需要转换时提供符合[预处理说明](references/preprocess-cli.md)的外部程序配置；案件和词表的 JSON/SQLite 操作仍可用。 |

安装与修复只作用于安装根。用户的合同工作目录、全局词表和独立转换器配置是单独资产。
