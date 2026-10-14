# 主会话：固定启动与合同准备

先执行 SKILL.md 的 runtime 固定片段。成功后用回执中的 python 执行安装 scripts/prepare_task.py；全部参数用数组，输入通过 `--input` 的绝对 JSON 文件或 `-`/stdin 传递，保存完整 stdout、stderr 和退出码。失败退出 2，成功退出 0；失败的 remaining_paths 是本次清理未成功的实际残留，不可派发。

## 公共调用与回执

主会话固定入口为 `<install-root>/scripts/prepare_task.py`。`runtime` 用 SKILL.md 中的启动片段执行，其余操作使用成功回执中的专用 Python 启动路径；示例中的绝对路径须整体替换为实际路径，含空格或中文时保持为单个参数。

```bash
"/absolute/legal-install/.venv/bin/python" \
  "/absolute/legal-install/scripts/prepare_task.py" case \
  --input "/absolute/workspace/case-input.json"
```

`--input` 指向主会话已写好的严格 JSON 输入文件，也可为 `-`，从 stdin 传入相同 JSON。每个操作的输入顶层都含整数 `format_version=1`，只填写该操作列出的字段。`runtime_file` 专指安装生成的 `runtime.json`；它与 `runtime` 命令的成功回执文件不同。

| 操作 | 成功回执 `result` 中的内容 |
|---|---|
| `runtime` | `install_root`、`release_version`、`python`、`commands`、`workspace_root`、`workspaces_file`。其中 `workspaces_file` 为固定配置路径，启动成功不表示该工作区已登记词表。 |
| `case` | 新建的 `contract_dir`、预定 `db_path`、已复制输入 `copied` 数组。每项 copied 含 `source/target/sha256`；数据库由后续正式 `init` 创建。 |
| `reading` | 已生成的 `manifest_file` 和 `tasks` 数组。 |
| `synthesis` | 沿用输入的 `manifest_file`，以及两个新生成的任务，位于 `tasks` 数组。 |
| `tagging`、`extraction` | `manifest_file=null`，以及 `tasks` 数组。 |

各操作成功时顶层为 `{ok:true,operation,files,result}`；`files` 只列本次已生成文件。阶段操作的 `result.tasks` 每项含 `task_id/role/purpose/task_file/instructions_file/binding_file/output_file`：

- `task_file` 是已生成的管理 JSON；`instructions_file` 是已生成的完整派发正文，主会话按该路径读取并直接交付。
- `binding_file` 是已生成的固定参数 JSON；reader 为 null，其余交给角色构造工具读取，不让角色修改固定参数。
- `output_file` 是角色**稍后**应写出的文件路径：reader 为 Markdown 笔记，其他角色为最终提交 JSON。辅助导出成功时，不能把这个文件尚不存在视为失败。

程序自行从 `<install-root>/skills/legal-case/templates/` 加载模板。主会话传业务输入和产物路径，无需查找模板文件或把模板路径填入任何输出字段。

失败为 `{ok:false,scope:"task_files",errors:[{code,path,message,...}]}`，按实际 `path/message` 修正已说明的参数；不能靠故意缺参、虚构路径试运行推断接口。说明不足或与行为矛盾时，报告具体字段、输入和原错误。当前 `FILE_EXISTS` 也可能表示目标不在规定目录，需结合字段与提示检查。仅检查确定路径，不列目录定位资源；安装文件缺失报告其精确路径。存在 `remaining_paths` 时保留诊断，不把残留当成功任务或删除既有成果。

## 工作区配置

安装首次产生 `workspaces.json`，初值为 `{"format_version":1,"workspaces":[]}`。按用户要求登记后的配置例如：

```json
{"format_version":1,"workspaces":[{"workspace_root":"/absolute/session/workspace","contract_root":"/absolute/contracts","vocabulary_list":"/absolute/install/vocabularies/workspace-1.txt"}]}
```

根仅这两个字段，每项仅这三个字段。用户直接维护，主会话按明确要求编辑。工作区是会话打开目录，精确匹配且必须存在；列表必须在本安装 vocabularies 内。没有配置不向上搜索。升级保留配置和列表；runtime.json 字段不变。

列表严格 UTF-8，LF/CRLF，每行一个绝对词表文件路径，忽略空白行，首个非空行默认。不支持注释、引号、变量、~、相对路径、重复规范路径；除行结束符外路径空格不剥离。明确选择须在列表中，只加载选中词表内容；第一项失效不跳选第二项。新增登记追加末尾，只有明确要求才重排默认；空列表首项自然成为默认，应报告。取消登记不删除文件。

## 新合同

`case` 只准备新案目录与输入副本。各字段如下：

| 字段 | 内容、方向与存在要求 |
|---|---|
| `format_version` | 必填整数 `1`。 |
| `runtime_file` | 输入：本安装已存在的 `<install-root>/runtime.json`。 |
| `workspace_root` | 输入：会话打开的目录，使用固定启动成功回执中的路径。 |
| `materials` | 输入：非空数组，逐项列出本合同明确提供的原件。每项必填 `path`，文件须已存在；需转换时可填已有的 `converter_config`。两者均为绝对文件路径。 |
| `vocabulary` | 可选输入：本次选用的已登记词表绝对路径。省略时使用工作区列表首个非空项，不改变默认顺序。 |
| `contract_root` | 可选输出父目录：覆盖本次合同工作根。省略时使用工作区登记值。由程序在其下创建唯一 `contract-...` 目录，无需调用方提前分配合同目录名。 |

完整纯文本示例（保存为上述 `case-input.json`）：

```json
{
  "format_version": 1,
  "runtime_file": "/absolute/legal-install/runtime.json",
  "workspace_root": "/absolute/workspace",
  "materials": [
    {"path": "/absolute/original.md"}
  ]
}
```

DOCX/PDF 等材料项例如 `{"path":"/absolute/contract.docx","converter_config":"/absolute/docx-converter.json"}`，使用实际已配置的转换器；缺配置时报告，不猜测或编写替代转换程序。

用本文件开头的 `case --input FILE` 调用。缺选中词表或非法输入时不进入后续正式操作。程序创建 contract-UTC 目录，冲突加 -02/-03，复制原件与冻结前词表副本、配置及明确非代码文件，安装代码保持绝对引用。根据成功回执的 `copied` 取得实际副本路径，再逐次执行正式 `init`、预处理、`register`、`split` 并保存回执；`case` 自身不执行这些操作。

续做已有合同不用 case，沿用旧目录、旧库及冻结词表。初始化或独立预处理仅用 runtime，不要求工作区登记词表。

## 阶段入口

| 操作 | 输入要点与完整示例 |
|---|---|
| `reading` | 先写好总体说明，再指定任务导出目录和两个未来提交 JSON 路径；见 [reading-inputs.md §1](reading-inputs.md#1-reading准备初读任务)。 |
| `synthesis` | 使用 reading 的已存在 manifest 与全部 reader 实际回报；见 [reading-inputs.md §2](reading-inputs.md#2-synthesis准备两个归纳任务)。 |
| `tagging` | 指定互不重叠的条款对象／当前记录对，以及未来提交路径；见 [handoff.md §1](handoff.md#1-tagging准备打标任务)。 |
| `extraction` | 指定完整条款责任、已有分组文件和未来提交路径；见 [handoff.md §2](handoff.md#2-extraction准备提取任务)。 |

阶段操作的输入 JSON 放在合同 `tasks/` 下，避开要求为空的 `output_dir`。`task_context_file` 是主会话已写好的 `tasks/` 下非空 UTF-8 总体说明；`preparation_files` 或 plan 的 `output_file` 是 `submissions/` 下未占用的最终 JSON 路径。两者都与安装 `templates/*.md` 无关。

主会话直接交付三部分 instructions 正文，补第三部分的业务关注并确认白名单，不让子任务重复打开管理任务或模板。后续正式概要正文直接作为共同背景，注明 overview_id/text_versions；保留每次派发采用版本，不静默更新旧派发。
