---
name: legal-vocab
description: 对已有全局法律关系词表按案件缺口或律师要求进行人工治理；适用于词表增删、归属调整与汇总。
---

# 词表治理

## 固定启动

用安装支持的系统 Python 执行下列片段；替换 skill_file 为宿主交付路径、workspace_root 为本次会话打开目录的绝对路径。工作区在任务期间固定，后续 cd 或合同位置不改变它。

```python
import json
from pathlib import Path
import subprocess
import sys

skill_file = Path("/host/skills/legal-vocab/SKILL.md").resolve(strict=True)
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

## 输入与依赖

明确原词表、未占用的新结果文件路径、工作目录，以及案件清单或律师提出的变更要求。当前正式工具调用时读 `../../references/vocab-cli.md`，构造词表时按需查 `../../references/data-formats.md`。安装信息缺失、格式错误或路径失效时报告安装问题，不从 PATH 另找工具。要查看尚未转换的原件时读取 `../legal-preprocess/SKILL.md`。

## 步骤

1. 案件缺口入口先用 `aggregate --cases FILE --output FILE` 汇总；律师要求入口直接读取要求。结合 `list/show`、当前词表及相关证据，判断现有词表能否表达。
2. 在工作目录写 `proposal.md`：问题、具体增删和归属处置、当前表达能力、证据与理由。用户直接在该文件中写自然语言意见。
3. 收到意见后按意见整理变更 JSON；保留原文件，以排他创建的独立副本作为变更目标；主会话调用词表 CLI 的已批准 `add/remove` 或混合变更 `--input FILE`。若哈希变化，重新对照现有内容及意见；意见无法确定新冲突时向用户核实。
4. 交付原文件与新结果文件、意见/变更文件、实际回执、前后哈希、ID 映射和差异。失败副本不是成功结果；不得覆盖已有目标。治理不修改注册列表或默认项，只有明确要求才追加新路径；默认调整另据明确要求。解除登记只删列表项不删文件，报告第一项变化。旧案冻结快照不回填。

## 工具用法与继续条件

从安装信息中取 `commands["legal-vocab"]` 的绝对路径，以工作目录为进程工作目录并按参数数组调用 `--vocabulary FILE <init|list|show|add|remove|aggregate> ...`；混合变更使用 `--vocabulary FILE --input CHANGE.json`，`diff` 用 `--left/--right`。例如 `argv=[runtime.commands["legal-vocab"],"aggregate","--vocabulary",词表绝对路径,"--cases",清单绝对路径,"--output",报告绝对路径]`。完整参数、文件格式与回执见 `../../references/vocab-cli.md` 和 `../../references/data-formats.md`。保留 stdout、stderr 与退出码；错误 code/path 决定修正位置；`HASH_CONFLICT` 不自动替用户重写意见，`ORPHAN_DISPOSITION_REQUIRED` 必须明确槽去向。未经人工意见的建议不能当作已执行变更。治理低频按需，不自动重跑入库或初始化。

## 已有 sub-agent 的命名与派发

已有证据阅读任务用 reader，已有汇总职责用 summarizer；不为名称新增派发或审核步骤。同类实例加 -1、-2，宿主 ID 保留寻址；task_id、证据身份与管理署名不因名称迁移。每次实际派发包含“固定角色信息、共享任务总体上下文、个别任务要求”三部分；第一部分给当前角色职责，第二部分交共同目标与材料边界，第三部分填实际目标、语料用途、资料/版本、可读文件白名单（绝对路径、内容范围、用途、读取时机）、已执行核验交接、独立输出和自然语言要求，不能临时改权限。已有阅读/汇总派发须直接带入以下共用规则，并固定本任务的证据阅读或归纳职责：

按本角色职责处理第三部分明确分配的任务。以交付的角色说明和按需查阅的格式、工具用法、同版样例作为依据；固定正文已经交付，不重读模板。

只读取第三部分“可读文件白名单”列出的绝对文件路径，并按各项内容范围、用途和读取时机处理。固定索引只授权主会话指定字段和条目中的确定文件，不授权整个目录或 glob；说明限定章节时只向上下文输出该章节，不能整篇打印。公共工具按约定加载完整授权快照不要求模型通读全部记录；异常诊断只显示问题路径/类型或必要局部，不打印无关嵌套内容；文档链接、交叉引用和相邻路径不自动授权。可读自己在指定位置生成的文件，续做所需其他旧文件须明确交付。检查具体输入/输出用精确 stat/exists，不列举 tasks、submissions、安装目录或兄弟任务。可以在指定位置写本任务产物，使用宿主文件操作和交付的专用 Python 调用列明的辅助入口及公共函数。

不调用 legal-case、legal-vocab、legal-preprocess；不通过模块入口、内部数据库函数、sqlite3 或其他程序执行同等操作，包括只读查询。不自行安装工具、寻找 runtime/README、修改安装副本或建立环境。

其他任务的文件只有明确交付才可读，任务已结束也不自动授权。脚本执行权限不等于读源码权限；不主动读取辅助实现或搜索工具。Python 正常加载标准库、已安装模块和运行资源不算主动翻阅业务材料，工具及数据脚本额外读取业务文件仍受白名单约束。任务只使用本场景的文件格式，不套用案件提交工具；只组织所交付材料及自身结果，不重写通用校验。

文件不存在、版本不符或所需材料未交付时，报告具体文件/字段路径、预期结构、实际问题、用途及影响，由主会话补充文件和授权并在同一任务交接留痕。必需字段缺失不能用空字典/数组兜底，真实合法空结果才可报告为空。可继续不受影响的部分。已说明的输入错误自行按错误码和字段路径修正；说明与程序行为矛盾、安装故障或职责冲突交主会话处理，不自行扩大权限。

保留完整工具 stdout、stderr 和原进程退出码，不用 echo 覆盖状态、2>/dev/null 或截断管道掩盖失败；回执截断恢复完整结果，原文截断补相应范围。按指定格式交付文件和摘要，列明未完成范围与问题。文件生成成功不表示已入库或语义完整；正式写入、回执和对账由主会话完成。

继续沿用本 skill 的语料文件/证据/审阅格式，不套用合同建模的交换 schema，不授予人工意见外的词表修改权限。

治理 reader 只读指定缺口及原文证据，summarizer 只整理本轮明确变更目标的建议；不探索其他案件或管理注册表。续做交当前有效成果、人审意见及修正范围，未收到人工意见不执行变更。
