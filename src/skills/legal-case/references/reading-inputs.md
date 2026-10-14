# 初读固定辅助：主会话

本文件说明 `reading`、`synthesis` 的调用与交接，业务职责见 [preparation.md](preparation.md)。执行安装根 `scripts/prepare_task.py`，使用固定启动回执的 `result.python`；公共回执与错误处理见 [startup.md](startup.md#公共调用与回执)。所有示例路径均须替换为本次任务的实际绝对路径。

## 1. reading：准备初读任务

在本轮材料完成登记和条款切分后调用。主会话先在合同 `tasks/` 下写好非空 UTF-8 总体说明，只陈述用户目标、材料范围、任务分工和要求，不预设尚未读到的合同架构。

| 字段 | 方向、内容与存在要求 |
|---|---|
| `format_version` | 必填整数 `1`；这是调用输入版本。生成的初读 manifest/task 版本为 `2`。 |
| `db_path` | 输入：本合同已存在的 `contract.sqlite`。 |
| `output_dir` | 输出目录：本合同 `tasks/` 下新的或已存在但为空的子目录；程序在此生成阅读材料和任务文件。 |
| `task_context_file` | 输入：主会话已写好的总体说明文件，须位于本合同 `tasks/` 下；不要放进要求为空的 `output_dir`。 |
| `preparation_files.records` | 后续输出：主体／事件 summarizer 的完整 `phase=preparation` 提交 JSON 路径。须在本合同 `submissions/` 下，尚不存在。 |
| `preparation_files.overview` | 后续输出：概要 summarizer 的完整 `phase=preparation` 提交 JSON 路径。须在本合同 `submissions/` 下，尚不存在，且与 records 路径不同。 |
| `text_version_ids` | 可选：本轮主读的当前文本版本**对象 ID** 数组。省略时主读全部当前材料；增量任务使用实际 ID 指定完整材料。 |
| `target_chars` | 可选正整数，默认 `20000`，按完整条款连续分段的目标字符量。 |
| `window_chars` | 可选正整数，默认 `6000`，单个原文阅读窗口的最大字符量。 |

**`preparation_files` 只预定最终提交的位置。** `reading` 不读取或创建这两个提交文件；不要预建空文件，也不要填安装模板、派发 Markdown 或 `tasks/` 中间文件的路径。模板由程序从本 skill 的 `templates/` 自动加载。

### 完整输入与调用

将以下 JSON 保存为 `/absolute/contracts/contract-example/tasks/0001-reading-input.json`；先按上表准备 `task-context.md`。`contract-example` 代指已创建的本合同目录，两个提交文件编号按本案未占用序号分配：

```json
{
  "format_version": 1,
  "db_path": "/absolute/contracts/contract-example/contract.sqlite",
  "output_dir": "/absolute/contracts/contract-example/tasks/0001-initial-reading",
  "task_context_file": "/absolute/contracts/contract-example/tasks/task-context.md",
  "preparation_files": {
    "records": "/absolute/contracts/contract-example/submissions/0001-preparation-records.json",
    "overview": "/absolute/contracts/contract-example/submissions/0002-preparation-overview.json"
  },
  "target_chars": 20000,
  "window_chars": 6000
}
```

```bash
"/absolute/legal-install/.venv/bin/python" \
  "/absolute/legal-install/scripts/prepare_task.py" reading \
  --input "/absolute/contracts/contract-example/tasks/0001-reading-input.json"
```

输入 JSON 文件放在 `output_dir` 外，避免把待导出目录变为非空目录。也可用 `--input -` 通过 stdin 传入相同完整 JSON。

成功后按回执的 `result.manifest_file` 保留固定清单，按 `result.tasks` 读取各 `instructions_file` 并交付 reader。每项 `output_file` 是 reader 后续应写的 Markdown 笔记，`binding_file=null`；不要因笔记尚不存在而报缺文件。管理 task/manifest 供主会话交接使用，不另列为 reader 必读文件。

程序沿用完整条款连续分段，超长条款由一个 reader 分窗全读；原文逐字导出，管理标题不混入正文。reader 只拿目录、负责原文及必要上下文，不需要词表、共享状态或完整业务格式。全部查询、固定版本及导出由辅助程序完成，主会话无需先复制一套相同快照。

## 2. synthesis：准备两个归纳任务

收齐 reader 的笔记及实际已读、未读、截断回报后调用。主会话据实际回报填写 `reader_reports`；未读部分先交原 reader 补齐，不为通过机械检查改成空数组。

| 字段 | 方向、内容与存在要求 |
|---|---|
| `format_version` | 必填整数 `1`。 |
| `db_path` | 输入：本合同已存在的数据库。 |
| `manifest_file` | 输入：前次 `reading` 成功回执的 `result.manifest_file`，文件已存在且为 v2。 |
| `output_dir` | 输出目录：本合同 `tasks/` 下另一个新的或为空的子目录；不能复用已装有阅读材料的目录。 |
| `reader_reports` | 必填数组：与 manifest 中全部 reader 任务一一对应，每任务恰好一项。 |

`reader_reports` 每项恰含以下字段：

| 字段 | 内容 |
|---|---|
| `task_id` | `reading` 返回的任务 ID，不能用 reader 显示名替代。 |
| `notes_file` | 对应 reader 的已存在、非空 Markdown 笔记，必须等于该任务预定 `output_file`。 |
| `read_ranges` | 实际已读**主读**范围数组；并集应等于该任务分配范围，不混入只作背景的上下文范围。 |
| `unread_ranges` | 实际未读范围数组；成功归纳前须已读完，故应为 `[]`。 |
| `issues` | reader 返回的问题字符串数组，无问题时显式 `[]`。 |

每个范围项为 `{text_version_id,start_offset,end_offset}`：`text_version_id` 为文本版本对象 ID，位置按该全文 Unicode 字符计算，为 `[start_offset,end_offset)`，不是字节、条款内偏移或窗口编号。从派发范围和 reader 实际回报取得，不凭文件存在推断读完。

### 完整输入与调用

下面仅演示一个 reader 完成一个 `[0,1200)` 范围；UUID、范围、任务 ID 和笔记路径均为示意，必须换为本案实际回报。多段时在 `reader_reports` 中逐项填写全部 reader，不能只提交示例中的第一段。

```json
{
  "format_version": 1,
  "db_path": "/absolute/contracts/contract-example/contract.sqlite",
  "manifest_file": "/absolute/contracts/contract-example/tasks/0001-initial-reading/manifest.json",
  "output_dir": "/absolute/contracts/contract-example/tasks/0002-synthesis",
  "reader_reports": [
    {
      "task_id": "0001-reading",
      "notes_file": "/absolute/contracts/contract-example/tasks/0001-initial-reading/0001-notes.md",
      "read_ranges": [
        {
          "text_version_id": "11111111-1111-4111-8111-111111111111",
          "start_offset": 0,
          "end_offset": 1200
        }
      ],
      "unread_ranges": [],
      "issues": []
    }
  ]
}
```

保存为本合同 `tasks/0002-synthesis-input.json`，调用：

```bash
"/absolute/legal-install/.venv/bin/python" \
  "/absolute/legal-install/scripts/prepare_task.py" synthesis \
  --input "/absolute/contracts/contract-example/tasks/0002-synthesis-input.json"
```

`synthesis` 沿用 manifest 中的总体说明及 `preparation_files`，调用时不重复传入这两个字段。成功返回两个独立任务，`purpose=records/overview`，固定任务 ID 为 `summarizer-records`、`summarizer-overview`。程序生成各自 instructions 和 binding，绑定中写入初读时指定的最终提交路径；此时两个提交 JSON 仍未生成。

主会话按 `result.tasks` 直接读取 instructions，交付两个 summarizer。单段时 records 任务的 `continue_reader_task_id` 指原 reader，应沿用该会话；overview 另派。二者使用同批笔记与固定原文，互不依赖对方的中间产物。records 取得完整既有身份及适用来源/构造规则；overview 只形成六栏目概要，不需要节点、值、锚的完整业务格式。

## 3. 文件由谁生成，何时写入

| 文件 | 生成者与时机 | 后续使用 |
|---|---|---|
| `task_context_file` | 主会话在 `reading` 前撰写 | 辅助程序用来展开共享任务上下文 |
| manifest、阅读窗口、reader instructions | `reading` 辅助程序 | 主会话交付 reader；manifest 后交 `synthesis` |
| reader 笔记 | reader 实际全读后写出 | 主会话收回报后交 `synthesis` 和两个 summarizer |
| summarizer instructions、binding | `synthesis` 辅助程序 | 主会话交付正文；`complete_task.py` 读取固定绑定 |
| `preparation_files.records` | 主体／事件 summarizer 组织记录，通过 `complete_task.py` 生成 JSON | 主会话 `write`，内容不含 overview |
| `preparation_files.overview` | 概要 summarizer 写正文及 issues，通过 `complete_task.py` 生成 JSON | 主会话 `write`，内容为 `records=[]` 并含 overview |

主会话分别调用两次正式 `write` 并保留回执，次序不限。某份失败只续该份；已成功的结果及 ID 复用，回执丢失按幂等规则重放原提交。两份均成功、实际主读完整且影响交接的问题已处置后，才能进入打标。文件生成、旧概要存在或机械检查通过均不能代替这些条件。

## 4. 错误定位与恢复

- `preparation_files` 缺失：按 §1 填齐两个未来提交路径，不查找模板。
- 报错路径含 `/preparation_files/records` 或 `/preparation_files/overview`：核对是否位于本合同 `submissions/` 下、是否未占用、两路径是否不同。当前实现对“位置不合法”和“目标已存在”都可能返回 `FILE_EXISTS`；结合 `path/message` 判断，不能只据错误码认定磁盘已有文件。
- `output_dir` 非空：输入 JSON 和总体说明放在导出目录外；已成功导出的材料按回执复用，需重导出时用新的任务目录，不删除旧任务来腾位置。
- 笔记缺失、为空、未读或范围不符：修正实际交接或续原 reader，不能从文件大小推定阅读完成。
- 已提供的安装资源路径缺失：报告该精确路径及安装问题；不扫描 references/templates 或替换为猜测路径。
- 固定素材、文本或条款版本改变：重新准备受影响材料。无关提交只改变序号不使有效笔记失效。

v1 manifest 不作为 v2 读取。旧成果恢复时重新导出 v2，复用明确验证有效的笔记及回执，保留旧库和旧文件。辅助程序检查文件、固定版本和范围声明，不证明实际阅读或语义无遗漏。
