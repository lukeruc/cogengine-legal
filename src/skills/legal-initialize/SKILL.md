---
name: legal-initialize
description: 从用户指定的归纳语料经两遍提取与两道人审生成首版法律关系词表；适用于词表初始化。
---

# 首版词表初始化

## 固定启动

用安装支持的系统 Python 执行下列片段；替换 skill_file 为宿主交付路径、workspace_root 为本次会话打开目录的绝对路径。工作区在任务期间固定，后续 cd 或合同位置不改变它。

```python
import json
from pathlib import Path
import subprocess
import sys

skill_file = Path("/host/skills/legal-initialize/SKILL.md").resolve(strict=True)
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

用户事先指定语料用途：`induction`、`rule_exam`、`held_out`、`legal_checklist`。还需工作目录、正式词表目标路径、需转换材料的原件与转换配置。当前正式工具调用时读 `../../references/vocab-cli.md`，构造词表时按需查 `../../references/data-formats.md`；按当前遍次读取本目录 `references/first-pass.md` 或 `references/second-pass.md`。安装信息缺失、格式错误或路径失效时报告安装问题，不从 PATH 另找工具。转换用 `../legal-preprocess/SKILL.md`，真实合同建模验收用 `../legal-case/SKILL.md`。

## 两遍两道人审

1. 整理 `corpus.json`，记录每份材料用途、合同种类、来源、原件/文本路径与哈希、转换元数据。非 induction 不进入单元或槽的归纳证据集。
2. 第一遍按条款提取主题、可约定点、摘句、当事方和原文模态词，依据 `first-pass.md` 形成 `units-review.md`，用户直接写意见。
3. 读取第一道人审意见，整理 `units-approved.json`；未收到意见时停在此环节。
4. 第二遍依已审单元提取槽、值结构、例句、归属与条件适用说明，依据 `second-pass.md` 形成 `slots-review.md`；用户直接写意见。
5. 读取第二道人审意见，整理最终变更文件。主会话用词表 CLI 创建正式空词表并提交批准后的条目；形成词表、证据包、判定表，附残留条款、规则考卷表达结果和法律清单查漏结果。

## 工具用法与交接

从安装信息中取 `commands["legal-vocab"]` 的绝对路径，以指定工作目录为进程工作目录，按参数数组运行 `argv=[runtime.commands["legal-vocab"],"init","--vocabulary",词表绝对路径]`，再以 `--vocabulary FILE --input CHANGE.json` 提交正式条目。`list/show/diff` 用于检查结果；完整参数和文件格式见 `../../references/vocab-cli.md`、`../../references/data-formats.md`。保留 stdout、stderr 与退出码；不要用案件 `init` 代替词表生成。成功交付三件套路径、词表哈希、工具回执和未完成事项。错误需按 code/path 修正；人工意见有冲突或不能解释时向用户核实。工具不机械解析自然语言意见。

## 已有 sub-agent 的命名与派发

第一遍逐条阅读用 reader，第二遍槽提取用 extractor；已经发生的汇总职责用 summarizer。两道人审及其顺序不变。同类实例加 -1、-2，宿主 ID 保留寻址；task_id、证据身份与管理署名不因名称迁移。每次实际派发包含“固定角色信息、共享任务总体上下文、个别任务要求”三部分；第一部分给当前角色职责，第二部分交共同目标与材料边界，第三部分填实际目标、语料用途、资料/版本、可读文件白名单（绝对路径、内容范围、用途、读取时机）、已执行核验交接、独立输出和自然语言要求，不能临时改权限。初始化两遍的固定内容在对应 first-pass/second-pass 说明；其他已经发生的阅读/汇总派发同样须直接带入以下共用规则：

按本角色职责处理第三部分明确分配的任务。以交付的角色说明和按需查阅的格式、工具用法、同版样例作为依据；固定正文已经交付，不重读模板。

只读取第三部分“可读文件白名单”列出的绝对文件路径，并按各项内容范围、用途和读取时机处理。固定索引只授权主会话指定字段和条目中的确定文件，不授权整个目录或 glob；说明限定章节时只向上下文输出该章节，不能整篇打印。公共工具按约定加载完整授权快照不要求模型通读全部记录；异常诊断只显示问题路径/类型或必要局部，不打印无关嵌套内容；文档链接、交叉引用和相邻路径不自动授权。可读自己在指定位置生成的文件，续做所需其他旧文件须明确交付。检查具体输入/输出用精确 stat/exists，不列举 tasks、submissions、安装目录或兄弟任务。可以在指定位置写本任务产物，使用宿主文件操作和交付的专用 Python 调用列明的辅助入口及公共函数。

不调用 legal-case、legal-vocab、legal-preprocess；不通过模块入口、内部数据库函数、sqlite3 或其他程序执行同等操作，包括只读查询。不自行安装工具、寻找 runtime/README、修改安装副本或建立环境。

其他任务的文件只有明确交付才可读，任务已结束也不自动授权。脚本执行权限不等于读源码权限；不主动读取辅助实现或搜索工具。Python 正常加载标准库、已安装模块和运行资源不算主动翻阅业务材料，工具及数据脚本额外读取业务文件仍受白名单约束。任务只使用本场景的文件格式，不套用案件提交工具；只组织所交付材料及自身结果，不重写通用校验。

文件不存在、版本不符或所需材料未交付时，报告具体文件/字段路径、预期结构、实际问题、用途及影响，由主会话补充文件和授权并在同一任务交接留痕。必需字段缺失不能用空字典/数组兜底，真实合法空结果才可报告为空。可继续不受影响的部分。已说明的输入错误自行按错误码和字段路径修正；说明与程序行为矛盾、安装故障或职责冲突交主会话处理，不自行扩大权限。

保留完整工具 stdout、stderr 和原进程退出码，不用 echo 覆盖状态、2>/dev/null 或截断管道掩盖失败；回执截断恢复完整结果，原文截断补相应范围。按指定格式交付文件和摘要，列明未完成范围与问题。文件生成成功不表示已入库或语义完整；正式写入、回执和对账由主会话完成。

继续沿用本 skill 的语料文件/证据/审阅格式，不套用合同建模的交换 schema，不授予人工意见外的词表修改权限。
