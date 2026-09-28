# 法律关系建模工具

交付版本：`0.1.0`。本目录包含共用的 `legal/` Python 包、四个 `skills/` 和 `references/`。三个命令共用同一安装环境；合同输入和产物保存在独立工作目录。核心运行代码只依赖 Python 标准库和 SQLite。真实 DOCX、PDF、OCR 转换由显式配置的外部程序承担。

## 构建与安装

选择支持 Python 3.11、3.12 或 3.13 且含 `sqlite3`、`venv` 的解释器。构建机器需要该解释器的 pip、setuptools 和 wheel；安装机器的专用环境需要 pip。`requirements.txt` 只描述核心运行依赖，不能代替包安装。

从本源码目录运行，先构建 wheel，再指定安装根及解释器安装：

```bash
/absolute/path/to/python scripts/build_release.py --output-dir /path/to/dist --python /absolute/path/to/python
/absolute/path/to/python scripts/install_release.py --install-root /path/to/legal-install --python /absolute/path/to/python --wheel /path/to/dist/cogengine_legal-0.1.0-py3-none-any.whl
```

安装脚本检查解释器与版本，在安装根创建一次 `.venv`，安装 wheel，核对三个生成命令、已安装包的 SQL 和单位配置，并从临时工作目录执行帮助、词表初始化、数据库初始化与查询。核验成功才原子写入 `runtime.json`。再次安装同版本会复用环境；显式升级可加 `--upgrade`。项目环境损坏时可显式加 `--repair`，只重建带本项目标记的 `.venv`，不接管其他环境；修复到不同版本还需同时加 `--upgrade`。安装根与源码位置及合同工作目录相互独立。安装脚本报告 `host_registration: pending`，表示还需按宿主现有机制注册四个完整 skill 目录；未完成注册时，不应报告整体安装完成。注册后可用 `scripts/verify_registration.py --install-root ROOT --skill legal-case=PATH --skill legal-vocab=PATH --skill legal-preprocess=PATH --skill legal-initialize=PATH` 核对宿主看到的四个 `SKILL.md` 路径及实际工具调用。

安装后的目录至少有 `README.md`、`runtime.json`、`.venv/`、`skills/` 和 `references/`。可以把完整交付复制到新位置后重新安装；已经创建的 `.venv` 和绝对路径不能依赖直接搬移。仅复制单个 `SKILL.md` 不构成完整安装。四个 skill 必须与 wheel 属于同一版本。

## 命令绑定与路径

每个 skill 先解析自身文件的真实目录，再从 `../../runtime.json` 读取安装信息，从 `../../references/` 读取共用说明。`runtime.json` 顶层恰有 `format_version`、`release_version`、`install_root`、`environment_root`、`python`、`commands`，其中 `commands` 恰有 `legal-case`、`legal-vocab`、`legal-preprocess`。检查 `format_version` 为整数 `1`、发行版本为本说明的 `0.1.0`、安装根等于 skill 真实根、环境位于根目录 `.venv`、解释器和三个命令位于该环境内且存在并可执行；路径均须为绝对路径。格式或路径不符时报告安装问题，不从 `PATH` 寻找同名工具，也不临时安装另一份环境。

运行时从 `commands` 选择 `legal-case`、`legal-vocab` 或 `legal-preprocess` 的绝对路径，按参数数组调用，并保留 stdout、stderr 和退出码。无须激活环境、设置 `PYTHONPATH` 或切换宿主解释器。合同入库及其预处理以当前合同工作目录为进程工作目录；独立预处理、词表初始化及治理使用各自指定工作目录。先按用户原工作目录解析相对输入，再把需要的合同输入复制到合同工作目录并传入绝对路径；清单内部的相对路径仍按清单所在目录解析。含空格或中文的路径保持为一个参数。

三个安装命令分别为：

| 命令 | 任务 |
|---|---|
| `legal-preprocess` | 调用配置的转换程序，生成 `text.txt` 和 `metadata.json` |
| `legal-case` | 合同库初始化、登记、切分、记录写入、查询、分组、对账 |
| `legal-vocab` | 词表初始化、查阅、变更、比较与案件缺口汇总 |

四个入口分别为 `skills/legal-preprocess/SKILL.md`、`skills/legal-case/SKILL.md`、`skills/legal-vocab/SKILL.md`、`skills/legal-initialize/SKILL.md`。它们共用上述三个命令；初始化与治理都调用词表命令。完整参数和格式见 `references/preprocess-cli.md`、`references/case-cli.md`、`references/vocab-cli.md`、`references/data-formats.md`。命令短名只是安装信息中的键，skill 实际执行 `runtime.json` 给出的绝对路径。

使用案件 skill 建立新合同时，先在指定工作根目录创建唯一的 `contract-YYYYMMDDTHHMMSSZ[-NN]` 合同工作目录，再把原件、词表和转换配置复制进去；数据库固定命名为 `contract.sqlite`，转换结果、任务、提交文件、回执、分组和报告均保存在此目录。续做同一合同沿用该目录。具体分层与命名见 [case-cli.md](references/case-cli.md#入库文件位置和命名)。CLI 本身仍接收显式路径，不代建合同工作目录。

源码开发时仍可从本目录运行 `python -m legal.case_cli`、`python -m legal.vocab_cli`、`python -m legal.preprocess_cli`；这不是安装后 skill 的调用方式。
