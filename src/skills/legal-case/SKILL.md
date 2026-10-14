---
name: legal-case
description: 对一份合同及其全部组成素材建立带原文出处的 SQLite 案件库；适用于合同建模入库、查询和对账。
---

# 合同案件入库

## 固定启动

用安装支持的系统 Python 执行下列片段；替换 skill_file 为宿主交付路径、workspace_root 为本次会话打开目录的绝对路径。工作区在任务期间固定，后续 cd 或合同位置不改变它。

```python
import json
from pathlib import Path
import subprocess
import sys

skill_file = Path("/host/skills/legal-case/SKILL.md").resolve(strict=True)
workspace_root = "/absolute/session/workspace"
script = skill_file.parent.parent.parent / "scripts/prepare_task.py"
result = subprocess.run([sys.executable, str(script), "runtime", "--input", "-"],
    input=json.dumps({"format_version": 1, "skill_file": str(skill_file), "workspace_root": workspace_root}),
    text=True, capture_output=True, check=False)
print(result.stdout, end="")
print(result.stderr, end="", file=sys.stderr)
raise SystemExit(result.returncode)
```

成功回执 result 给出 install_root、python、commands、workspace_root 和 workspaces_file。其余准备辅助用该专用 python；相对资料以本 skill 真实目录为基准。只访问确定路径，不列安装树、读源码/README 或预读全部阶段。故障报告具体路径，不从 PATH 找替代工具。不需要词表的初始化、预处理及续做不读取默认词表配置。

## 当前阶段需要的说明

以下路径都以本 `SKILL.md` 解析符号链接后的真实目录为基准。`references/preparation.md` 位于 `<install-root>/skills/legal-case/references/`；共用命令说明位于 `<install-root>/references/`。按下面的确定链接进入当前阶段，无需在两个 references 目录之间搜索。

| 当前操作 | 读取内容 |
|---|---|
| 新案配置和 `prepare_task.py case` | [startup.md](references/startup.md)：配置、建案参数、公共调用与回执规则 |
| 预处理、登记、切分及正式写入 | [预处理 skill](../legal-preprocess/SKILL.md)；[case-cli.md](../../references/case-cli.md) 的当前命令章节 |
| 首次派 reader：`reading` | [reading-inputs.md §1](references/reading-inputs.md#1-reading准备初读任务) 的完整输入示例；[preparation.md §1—§2](references/preparation.md#1-主会话固定版本并准备全部材料) 的分段和阅读职责 |
| 收齐笔记，派两个 summarizer：`synthesis` | [reading-inputs.md §2—§3](references/reading-inputs.md#2-synthesis准备两个归纳任务) 的实际阅读回报与输出交接；[preparation.md §3—§4](references/preparation.md#3-summarizer主体与事件) 的两种职责 |
| 派 tagger：`tagging` | [handoff.md §1](references/handoff.md#1-tagging准备打标任务) 的调用；[tagging.md](references/tagging.md) 的分类要求 |
| 分组后派 extractor：`extraction` | [handoff.md §2—§3](references/handoff.md#2-extraction准备提取任务) 的调用与责任分配；[extraction.md](references/extraction.md) 的提取要求 |

**`reading` 的 `preparation_files` 是主会话预定的两个最终提交 JSON 路径。** 分别填合同 `submissions/` 下尚不存在的主体／事件提交和概要提交路径；模板由程序从安装 `templates/` 加载。不要把 `.md` 模板、任务说明或 `tasks/` 中间文件填入这个字段，也不要预先创建空提交文件。参数不明时查当前阶段的字段表和示例；说明缺失或与程序矛盾时报告具体字段，不通过故意缺参、虚构路径或目录遍历探测接口。

## 输入与准备

明确材料清单、新案或续做。新案读取本会话工作区对应 workspaces.json 项及安装 vocabularies 下的路径列表；首个非空行默认，明确选择必须已登记，一次选择不改顺序。缺配置或默认失效先报告具体项，不搜索词表或跳选后项。配置格式及准备调用见 `references/startup.md`，当前正式操作参数见 `../../references/case-cli.md`；业务格式在生成正式记录时按需读取。

新案使用 `<专用 Python> <install>/scripts/prepare_task.py case --input FILE` 校验选中词表、排他创建 contract-UTC 目录并复制明确原件、词表、转换配置及非代码资源；转换器复用安装绝对路径。所有后续产物保存在该合同目录，库为 contract.sqlite。同案续做沿用目录及冻结词表，不执行 case。原件、词表、配置副本在 inputs，转换在 converted，任务/提交/回执/分组/报告分别在 tasks/submissions/receipts/groups/reports；递增命名不覆盖旧文件。

## 已批准流程

1. 新案先用 case 固定准备创建目录并复制输入，再以案件内词表副本调用 `case_cli init` 冻结词表；已有案沿用目录，先查询 `progress`、词表哈希与当前回执。
2. 各份素材经预处理 skill 取得文本与元数据，用 `register` 登记原件和全文，再用 `split` 切分。异常影响阅读时依既有规则要求更好源件。
3. 进入初读才读 `references/preparation.md` 和 `references/reading-inputs.md`。用 reading 固定辅助导出 v2 原文窗口及 reader 三部分正文；reader 全读并记笔记。收齐真实范围后用 synthesis 导出两个独立 summarizer：主体/事件提交不含 overview，概要提交 records=[]。单段 reader 原会话接续主体/事件，另派概要任务。两份分别 write，顺序不限；失败仅修该份，不回滚成功结果。均成功、主读实际读全且问题明确处置后，查询正式概要作为下游共同背景及完整共用身份。
4. 按不重叠条款批次，用 `prepare_task.py tagging` 准备 tagger 输入与派发正文，调用见 `references/handoff.md`，分类职责见 `references/tagging.md`。主会话逐文件 `write` 标签修订及无匹配缺口。
5. 运行 `group` 导出逐字分组；按 `references/handoff.md` 指定责任计划，用 `prepare_task.py extraction` 导出完整任务及输入清单。派发首先列出负责条款及全部规定的完整提取责任。任务 `unit_id` 仅提供分组上下文，不限制输出关系的单元；比较负责条款集合，保证每条款只有一个完整提取责任。冻结词表和共用对象完整查询结果供 extractor 读取，多标签副本只作上下文。
6. 按完整条款主责派 extractor 并行提取，参见 `references/extraction.md`。extractor 先识别规定、主体及完整限制，再选单元/适用槽并组织 JSON；不得假定其他 extractor 会提取本条款的剩余规定。每个 extractor 保存一份完整 `extraction` JSON，并返回路径、负责条款、数量与问题摘要。
7. 主会话读取摘要及提交文件的 `issues`，按下节处理明确问题，再每份文件调用一次 `write`。失败将具体 code/path 和必要版本交原 sub-agent 修正整份文件；成功保存回执。
8. 运行 `reconcile`。按报告用既有 `write` 修正或撤销，再重新对账；报告有 errors 时如实交接未完成。

## 三部分派发及固定构造

reading、synthesis、tagging、extraction 成功回执的 `result.tasks` 逐项给出 task_file、instructions_file、binding_file、output_file。前三项是程序已生成的文件（reader 的 binding_file 为 null）；output_file 是角色后续应生成的产物路径，此时尚不存在。主会话按回执直接读取 instructions_file，交付完整正文，并在第三部分补业务关注和实际授权；第一部分固定角色、第二部分共同目标、第三部分个别范围及文件白名单。模板、管理 manifest、安装与机器快照不是全部角色的必读清单；任务说明已交付后不重复要求打开。

reader 直接交 Markdown。程序分别从本 skill 的 `templates/summarizer.md`、`templates/summarizer-overview.md` 生成两个 summarizer 的派发正文；主会话无需寻找、传入或重新展开模板。后续 tagger/extractor 的共同背景直接取正式 overview.body，并标记 overview_id/文本版本，不重新摘要。共用身份保持完整记录和出处。固定绑定只交给实际构造程序，角色使用同版 complete_task.py，填写业务记录/概要正文、显式 issues；extractor 自行明确覆盖清单。find_quote 和 clause_revision 继续处理精确锚及固定修订字段。

主会话统一调用正式 CLI；子任务不访问库、正式命令、其他并行任务或实现。角色名 reader、summarizer、tagger、extractor，同类加数字，署名由绑定明确指定。缺材料由主会话补交白名单，已授权原文可定向回读，纠错交原任务，不新增 fixer/reviewer 或全量互查。

按阶段读取 preparation.md、tagging.md、handoff.md；构造参考 helper-tools.md 按角色交适用章节。初读概要任务不读完整 node/evidence/value 格式，reader 不读构造格式。单份成功回执不证明两任务准备完成，对账也不替代准备条件。

## 接收结果与明确问题

在已有接收、提交和交接环节处理返回中明确暴露的问题，不代替 sub-agent 重新建模；同一问题已有处置及依据时复用。

| 摘要或提交 issues | 主会话处理 |
|---|---|
| 负责条款的其他单元内容交由其他 extractor | 对照唯一负责集合；本任务独占的条款交回原 extractor 完成。声称已有记录承载时，核对具体记录和对应内容 |
| 无assignment所以时间槽不可用 | 核对冻结快照及data-formats §1的通用槽规则，交回更正错误缺口及受影响内容，写入前完成更正 |
| 明知少条件或替换主体，仍声称完整 | 交回原 sub-agent 按已有能力修正；不能解决的具体部分、原因及影响如实交接 |
| 真实词表/值语法限制、材料未提供、原文歧义 | 用现有允许的记录及issues保留依据、影响和限制，不能伪装已解决 |
| 事件缺失或不能准确引用 | 保留原句、不匹配原因和影响；不能接受近似事件，也不扩大 extractor 的事件认定权限 |

未成功写入的整份文件可由原 sub-agent 先修正，CLI失败仍整份修正重提。成功写入后沿用稳定对象ID及追加版本，不覆写历史；gap不可修改或撤销，旧错误gap须报告固定身份及反证。

不要求issues为空，不将所有问题变成写入禁令。已确认可表达却未处理的内容须继续要求原 sub-agent 修正，或明确交接本轮未完成；真实歧义及表达限制可以交接，但不能宣称相关内容准确完整。处置记在已有返回摘要及最终报告，不另建审核步骤、字段或错误码。

## 工具用法与恢复

从安装信息中取 `commands["legal-case"]` 的绝对路径，以当前合同工作目录为进程工作目录，按参数数组运行 `<init|register|split|write|query|group|reconcile> --db FILE ...`。例如 `argv=[runtime.commands["legal-case"],"write","--db",合同库绝对路径,"--input",提交文件绝对路径]`。各命令参数、输入输出格式、错误和退出码见 `../../references/case-cli.md`、`../../references/data-formats.md`；保留完整 stdout、stderr 与原进程退出码，不用合并流并截断输出的管道代替完整结果。`write --input FILE` 是提取文件的唯一提交动作，文件内所有记录整份成功或整份失败。成功文件原样重提返回 `replayed=true` 和原 ID；修正内容须使用既有 object_id、当前 previous_record_id 和完整 data/evidence。写入后旧对账报告变为 stale。查询质量与进度以数据库为准，工作目录不是第二个状态库。

最终交接合同工作目录、案件库路径、case_id、词表哈希、本轮条款范围、最新报告及问题处置。分别说明写入及机械结果、已修正问题、仍未完成的规定和真实输入/表达限制。成功回执、提取完成记录及对账零错误不能消除已知语义错误；原文语义仍需按既定真实合同考卷审阅。
