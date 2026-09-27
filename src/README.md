# 法律关系建模工具

本目录是完整交付目录。三个命令共用 `legal/` Python 包，四个 skill 位于 `skills/`，共用说明在 `references/`。运行环境需要 Python 标准库及 SQLite；原件转换依赖显式配置的外部转换程序。

`requirements.txt` 当前没有第三方 Python 包条目；运行所需的 `sqlite3` 随带 SQLite 支持的 Python 标准库提供。执行 `python -m pip install -r requirements.txt` 不会安装 DOCX/PDF 转换程序。需要转换原件时，另按 `references/preprocess-cli.md` 配置外部转换器；已有 Markdown 文本的案件与词表命令不依赖转换器。

从本目录启动：

```bash
python -m legal.preprocess_cli --help
python -m legal.case_cli --help
python -m legal.vocab_cli --help
```

宿主通过链接或等价引用注册四个 `skills/*/SKILL.md`。skill 先解析自己的真实目录，再以 `../..` 找到本目录。仅复制一个 SKILL.md 无法取得 CLI 和共用说明。运行命令时可把本目录设为工作目录，或设置 `PYTHONPATH` 指向本目录；输入文件、案件库、词表、转换产物和人工审阅文件使用调用方指定的路径，不存放在源码目录。传给 CLI 的相对路径以调用时工作目录为基准；清单内相对路径以清单文件所在目录为基准。

入口与任务：

| 入口 | 任务 |
|---|---|
| `legal.preprocess_cli` | 调用配置的转换程序，生成 `text.txt` 和 `metadata.json` |
| `legal.case_cli` | 案件初始化、登记、切分、记录写入、查询、分组、对账 |
| `legal.vocab_cli` | 词表初始化、查阅、变更、比较与案件缺口汇总 |
| `skills/legal-preprocess/SKILL.md` | 一份原件的转换交接 |
| `skills/legal-case/SKILL.md` | 一份合同的建模入库 |
| `skills/legal-vocab/SKILL.md` | 已有词表的人工治理 |
| `skills/legal-initialize/SKILL.md` | 经两遍归纳与两道人审建立首版词表 |

命令和格式详见 `references/preprocess-cli.md`、`case-cli.md`、`vocab-cli.md`、`data-formats.md`。预处理转换配置必须显式指定；未配置转换器时，案件和词表命令仍可运行。
