# 主会话：打标与提取任务交接

打标用 `prepare_task.py tagging`，分组后的完整提取用 `prepare_task.py extraction`。两个入口都由主会话调用，程序准备同版模板、查询快照和固定绑定；主会话按成功回执直接交付派发正文。公共调用与回执见 [startup.md](startup.md#公共调用与回执)。进入本阶段再读本文件，不把主会话编排说明列为 sub-agent 必读材料。

以下示例路径和 UUID 均为示意；实际必须使用本案路径、当前条款对象／记录 ID、冻结单元 ID 和正式分组文件。输入 JSON 放在 `tasks/` 下、导出目录之外；不能把输入文件先写入要求为空的 `output_dir`。

## 1. tagging：准备打标任务

本轮两个 preparation 提交均成功、主读完成且影响交接的问题已处置后，主会话按互不重叠的完整条款批次分配责任。必要上下文单列，不能据旧概要或单份成功回执跳过准备条件。

| 顶层字段 | 内容与存在要求 |
|---|---|
| `format_version` | 必填整数 `1`。 |
| `db_path` | 输入：本合同已存在的数据库。 |
| `output_dir` | 输出目录：本合同 `tasks/` 下新的或已存在但为空的子目录。 |
| `task_context_file` | 输入：主会话已写好的 `tasks/` 下非空 UTF-8 总体说明。程序另从正式数据库查询概要，将 `overview.body` 原样加入共同背景。 |
| `plans` | 输入：非空的任务计划数组。逐项字段如下。 |

每个 plan 恰含：

| 字段 | 内容与来源 |
|---|---|
| `task_id` | 主会话指定的本次任务 ID，用作文件名；批内唯一，不含目录分隔符，不用 `.`、`..`、`units`、`overview`。 |
| `responsible_clauses` | 非空的 `{object_id,record_id}` 数组，来自当前正式条款查询。各任务主责互不重叠，主会话保证本轮待打标条款全部分配。 |
| `context_clauses` | 同格式数组，只供理解背景，无需额外修订；无上下文时显式 `[]`。 |
| `output_file` | **未来输出**：本合同 `submissions/` 下唯一、尚不存在的完整 tagging 提交 JSON 路径；由 tagger 完成判断后用构造工具生成。 |

### 完整输入与调用

下面演示一个负责单条款的 plan；实际在 plans 中填齐本轮全部批次。保存为本合同 `tasks/0003-tagging-input.json`：

```json
{
  "format_version": 1,
  "db_path": "/absolute/contracts/contract-example/contract.sqlite",
  "output_dir": "/absolute/contracts/contract-example/tasks/0003-tagging",
  "task_context_file": "/absolute/contracts/contract-example/tasks/task-context.md",
  "plans": [
    {
      "task_id": "tagging-1",
      "responsible_clauses": [
        {
          "object_id": "11111111-1111-4111-8111-111111111111",
          "record_id": "22222222-2222-4222-8222-222222222222"
        }
      ],
      "context_clauses": [],
      "output_file": "/absolute/contracts/contract-example/submissions/0003-tagging-1.json"
    }
  ]
}
```

```bash
"/absolute/legal-install/.venv/bin/python" \
  "/absolute/legal-install/scripts/prepare_task.py" tagging \
  --input "/absolute/contracts/contract-example/tasks/0003-tagging-input.json"
```

成功后 `result.tasks` 给出各管理 task、instructions、binding 和未来 output 路径。生成的 tagging task 内部版本为 `2`；它由程序生成，不作为调用方应手写的 plan。此时最终提交尚不存在。

tagger 拿负责条款完整原文、明确上下文、完整单元定义和概要背景。导出的 `units.json` **直接是单元数组**，每项有单元 id/description 等字段；对应 clause 快照是 `{case_id,checked_sequence,items}`。分类规则见 [tagging.md](tagging.md)。主会话按回执读取 instructions 并交付，随后逐份正式 `write`。标签修订产生新的条款记录版本，分组和提取须使用写入后的当前版本。

## 2. extraction：准备提取任务

打标成功后先运行正式 `group`，取得合同 `groups/` 下的逐字 JSON 分组文件。主会话指定每条款的唯一完整提取责任，再调用本入口。一个任务负责的条款可形成多个单元的关系，`unit_id` 仅说明分组上下文。

顶层必填 `format_version=1`、`db_path`、`output_dir`、`task_context_file`、`plans`，前四项的含义与 tagging 相同。可选 `clause_ids` 是本轮完整提取范围的**条款对象 ID** 数组；省略时取全部当前文本的条款，指定时取所列范围。各 plan 的主责并集必须恰好等于本轮范围，不得通过缩小范围掩盖应处理条款。

每个 plan 恰含以下六项；不能把导出后的 `input_files`、`instructions_file` 或 `binding_file` 混入调用输入：

| 字段 | 内容与来源 |
|---|---|
| `task_id` | 主会话指定的批内唯一任务文件名，不含目录分隔符，不用 `.` 或 `..`。 |
| `unit_id` | 对应分组的冻结单元 UUID；unmatched/no_content 分组为 null。须与 `group_file` 中的值一致，不限制本任务输出关系的单元。 |
| `responsible_clauses` | 非空的 `{object_id,record_id}` 数组，使用打标等修订完成后的当前版本；各任务主责两两不交。 |
| `context_clauses` | 同格式数组，仅供理解，可与主责相交；无上下文时 `[]`。 |
| `group_file` | **已有输入**：正式 `group` 导出的 JSON 文件，位于本合同 `groups/` 下，案件、词表、单元及条款版本均与当前库一致。 |
| `output_file` | **未来输出**：本合同 `submissions/` 下唯一、尚不存在的完整 extraction 提交 JSON 路径。 |

### 完整输入与调用

下面演示明确只处理一个条款的任务，`clause_ids` 与主责并集一致。实际全合同提取时省略 `clause_ids`，并在 plans 中完整分配全部条款。示例中的单元与条款 ID 必须换为本案正式值，`group_file` 取实际 group 成功回执给出的文件路径。

```json
{
  "format_version": 1,
  "db_path": "/absolute/contracts/contract-example/contract.sqlite",
  "output_dir": "/absolute/contracts/contract-example/tasks/0004-extraction",
  "task_context_file": "/absolute/contracts/contract-example/tasks/task-context.md",
  "clause_ids": ["11111111-1111-4111-8111-111111111111"],
  "plans": [
    {
      "task_id": "extraction-1",
      "unit_id": "33333333-3333-4333-8333-333333333333",
      "responsible_clauses": [
        {
          "object_id": "11111111-1111-4111-8111-111111111111",
          "record_id": "44444444-4444-4444-8444-444444444444"
        }
      ],
      "context_clauses": [],
      "group_file": "/absolute/contracts/contract-example/groups/0001/unit-example.json",
      "output_file": "/absolute/contracts/contract-example/submissions/0004-extraction-1.json"
    }
  ]
}
```

保存为本合同 `tasks/0004-extraction-input.json`，调用：

```bash
"/absolute/legal-install/.venv/bin/python" \
  "/absolute/legal-install/scripts/prepare_task.py" extraction \
  --input "/absolute/contracts/contract-example/tasks/0004-extraction-input.json"
```

程序查询全部分页并导出完整冻结词表、正式概要、事件及共用对象、条款快照和分组副本，保留 data/evidence/provenance 及版本身份；检查当前版本、分组归属和责任并集。主会话无需另外导入内部导出函数、手工重建同一批快照或展开模板。

## 3. 完整责任与交接

派发先列出 `responsible_clauses`，明确 extractor 须完整提取这些条款中的全部规定。任务 `unit_id` 仅提供分组上下文；每项输出关系的 `relation.unit_id` 按该项规定在完整冻结词表中选择，两者不要求相等。extractor 不能自行假定其他任务会处理负责条款中的剩余单元。

派发示例：“完整提取 CLAUSE 16、17、20 的全部规定；知识产权分组提供相关上下文。”同一任务可形成多个单元的关系；不要将其派成“只提取这些条款中的知识产权内容”。原文编号只作说明，正式责任以对象/记录ID对为准。

输出的 extraction 管理 task 保持内部 `format_version=1`，包含 task_id、unit_id、responsible_clauses、context_clauses、input_files、output_file，由程序生成。instructions/binding 路径通过 `result.tasks` 返回；不要将这个输出文件与调用时的 plans 混淆。任务文件是既有派发步骤的工作文件，不记录第二份案件状态。

context与responsible可相交，但context不产生额外完整提取责任；各任务responsible必须两两不交、并集等于本轮范围。这个比较证明分配完整，不证明输出已提全。条款引用同时保留object_id和所读record_id。输出路径唯一且未使用，失败修正原文件的规则仍由主会话控制。

每份任务的input_files明确包括：正式extraction说明、负责条款完整原文、对应分组上下文、完整冻结词表、最新概要、正式事件完整记录、其他已知共用节点查询结果和data-formats。输入用成功写入后的query导出，保留data／evidence／provenance和版本身份，依next_offset读完全部分页；空事件清单显式给出。槽表及仅ID／名称的对象简表不能代替它们。

案件任务只说明该合同的范围、输入和输出。缺口、值形态、当事人性质和来源级直接引用正式说明，避免临时任务把missing_slot误写为原文留空，或把modality放进parties。

派发正文给出 [helper-tools.md](helper-tools.md) 的适用用法、专用 Python、已安装脚本及输入/输出的绝对路径。find_quote 使用完整 clauses 查询快照，不能使用分组摘要；complete_task 读取固定绑定，角色明确填写业务记录、issues 和覆盖数组。工具只处理授权文件；extractor 不调用正式 CLI 或数据库，需补 ID/原文由主会话交付。派发前如数据库已变，核对受影响版本，不继续使用陈旧任务。

 extractor 返回`{task_id,output_file,responsible_clauses,record_counts,issues}`，responsible_clauses仍是对象／记录ID对清单。主会话读取摘要和提交文件中的issues，按 [SKILL.md](../SKILL.md#接收结果与明确问题) 处理已暴露的未完成或矛盾，再每份文件调用一次write并保存完整回执。声称其他任务或已有记录承载时须核对实际责任、具体记录及对应内容，不能只接受转交说明。真实限制保留原句、原因和影响，不要求issues为空；回执成功和机械覆盖不能代替原文语义验收。

导出的 input_files 包含本角色 helper-tools、引句/提取样例及虚构夹具，不携带模板路径。主会话从成功回执的 instructions_file 读取完整正文，第三部分补本次业务关注和明确授权，保存实际派发；导出清单的资料可按需查阅，不是全部前置必读。完整负责条款、相关上下文、词表定义/槽/归属、概要及正式共享记录仍开始读取，不能为了少调用漏业务限制。数据格式/值类型/构造工具按具体用途查授权章节。

完整 clauses 快照可以授权公共匹配工具读取全部记录；模型阅读和完整提取责任仍限定任务条款及指定上下文。记录是 item.data，查询外层 evidence/provenance 不能混进 data，旧 ID/前驱保持。共享空 items 是明确结果，缺必需字段不兜底为空。辅助执行不授权读源码，文档链接不自动授权其他文件；缺材料/版本交主会话追加文件授权，同一交接留痕，不浏览别的任务补洞。

当前主会话用 prepare_task extraction 固定导出，三部分 instructions 与只读 binding 经 input_files/返回表交付，任务 JSON 的既有字段不变。正式 overview.body 原样成为共同背景，注明身份/文本版本；完整共享对象不按关键词筛选。角色通过 complete_task 固定入口提交，覆盖声明由本人明确给出。

## 4. 错误与续做

- 缺 plan 字段：按本阶段字段表补齐。主责、输出路径等由主会话明确分配，不探测占位输入。
- `FILE_EXISTS` 指向 `output_file`：核对目标是否在本合同 submissions、是否未占用、是否与其他任务重复；当前代码也用此码报告非法输出位置。
- 目录非空或已有输出：保留旧成果；按回执确定复用、修正或分配新路径，不覆盖成功提交。
- `STALE_REVISION`：重新取得受影响条款的当前记录版本，必要时重导出 group 和任务；不要只修改前驱来跳过内容核对。
- `COVERAGE_INVALID`：核对计划的责任并集、重叠和本轮范围。上下文不计作完整提取责任。
- 所需安装资源缺失：按原错误报告精确路径，不扫描安装目录寻找另一套文件。

某份正式写入失败只交原任务修正整份文件；已成功结果复用原 ID，后续修改使用追加版本。处理这些问题不新增审核角色或第二份案件状态。
