---
name: legal-initialize
description: 从用户指定的归纳语料经两遍提取与两道人审生成首版法律关系词表；适用于词表初始化。
---

# 首版词表初始化

## 安装路径

将下列占位路径替换为宿主提供的本文件绝对路径，先解析符号链接，再取父目录：

```python
from pathlib import Path

skill_dir = Path("/host/skills/legal-initialize/SKILL.md").resolve(strict=True).parent
install_root = skill_dir.parent.parent
runtime_path = install_root / "runtime.json"
print(runtime_path)
print(install_root / "references")
```

先完成上述定位，再按输出的绝对路径读取资料。本文件中的相对资料路径均以 `skill_dir` 为基准，与 shell 工作目录无关。CLI 的绝对路径从核验后的 `runtime.json` 取得。本 skill、参考资料及 CLI 均使用安装目录内的副本。

读取安装信息后，核对 `format_version` 为整数 `1`、`release_version` 为非空字符串、`install_root` 等于上述真实安装根、`environment_root` 指向其中的 `.venv`。`python` 及 `commands` 中的 `legal-case`、`legal-vocab`、`legal-preprocess` 必须是该环境内存在且可执行的绝对路径；保留环境内 Python 的启动路径。安装信息不符时报告安装问题，停止依赖它的业务调用。

## 输入与依赖

用户事先指定语料用途：`induction`、`rule_exam`、`held_out`、`legal_checklist`。还需工作目录、正式词表目标路径、需转换材料的原件与转换配置。按本文件真实目录读取 `../../runtime.json`、`../../references/vocab-cli.md`、`../../references/data-formats.md`；按当前遍次读取本目录 `references/first-pass.md` 或 `references/second-pass.md`。安装信息缺失、格式错误或路径失效时报告安装问题，不从 PATH 另找工具。转换用 `../legal-preprocess/SKILL.md`，真实合同建模验收用 `../legal-case/SKILL.md`。

## 两遍两道人审

1. 整理 `corpus.json`，记录每份材料用途、合同种类、来源、原件/文本路径与哈希、转换元数据。非 induction 不进入单元或槽的归纳证据集。
2. 第一遍按条款提取主题、可约定点、摘句、当事方和原文模态词，依据 `first-pass.md` 形成 `units-review.md`，用户直接写意见。
3. 读取第一道人审意见，整理 `units-approved.json`；未收到意见时停在此环节。
4. 第二遍依已审单元提取槽、值结构、例句、归属与条件适用说明，依据 `second-pass.md` 形成 `slots-review.md`；用户直接写意见。
5. 读取第二道人审意见，整理最终变更文件。主会话用词表 CLI 创建正式空词表并提交批准后的条目；形成词表、证据包、判定表，附残留条款、规则考卷表达结果和法律清单查漏结果。

## 工具用法与交接

从安装信息中取 `commands["legal-vocab"]` 的绝对路径，以指定工作目录为进程工作目录，按参数数组运行 `argv=[runtime.commands["legal-vocab"],"init","--vocabulary",词表绝对路径]`，再以 `--vocabulary FILE --input CHANGE.json` 提交正式条目。`list/show/diff` 用于检查结果；完整参数和文件格式见 `../../references/vocab-cli.md`、`../../references/data-formats.md`。保留 stdout、stderr 与退出码；不要用案件 `init` 代替词表生成。成功交付三件套路径、词表哈希、工具回执和未完成事项。错误需按 code/path 修正；人工意见有冲突或不能解释时向用户核实。工具不机械解析自然语言意见。

## 已有 sub-agent 的命名与派发

第一遍逐条阅读用 reader，第二遍槽提取用 extractor；已经发生的汇总职责用 summarizer。两道人审及其顺序不变。同类实例加 -1、-2，宿主 ID 保留寻址；task_id、证据身份与管理署名不因名称迁移。每次实际派发包含“固定内容”和“本次任务要求”两部分；固定内容给本角色职责及文件/操作/异常边界，第二部分填实际目标、语料用途、资料/版本、可读文件白名单（绝对路径、内容范围、用途、读取时机）、已执行核验交接、独立输出和自然语言要求，不能临时改权限。初始化两遍的固定内容在对应 first-pass/second-pass 说明；其他已经发生的阅读/汇总派发同样须直接带入以下共用规则：

按本角色职责处理第二部分明确分配的任务。以交付的角色说明和按需查阅的格式、工具用法、同版样例作为依据；固定正文已经交付，不重读模板。

只读取第二部分“可读文件白名单”列出的绝对文件路径，并按各项内容范围、用途和读取时机处理。固定索引只授权主会话指定字段和条目中的确定文件，不授权整个目录或 glob；说明限定章节时只向上下文输出该章节，不能整篇打印。公共工具按约定加载完整授权快照不要求模型通读全部记录；异常诊断只显示问题路径/类型或必要局部，不打印无关嵌套内容；文档链接、交叉引用和相邻路径不自动授权。可读自己在指定位置生成的文件，续做所需其他旧文件须明确交付。检查具体输入/输出用精确 stat/exists，不列举 tasks、submissions、安装目录或兄弟任务。可以在指定位置写本任务产物，使用宿主文件操作和交付的专用 Python 调用列明的辅助入口及公共函数。

不调用 legal-case、legal-vocab、legal-preprocess；不通过模块入口、内部数据库函数、sqlite3 或其他程序执行同等操作，包括只读查询。不自行安装工具、寻找 runtime/README、修改安装副本或建立环境。

其他任务的文件只有明确交付才可读，任务已结束也不自动授权。脚本执行权限不等于读源码权限；不主动读取辅助实现或搜索工具。Python 正常加载标准库、已安装模块和运行资源不算主动翻阅业务材料，工具及数据脚本额外读取业务文件仍受白名单约束。任务脚本可组织引句、标签、解释、身份和来源，允许必要的负责集合核对及明确字符错误的局部诊断；引文匹配/消歧交 find_quote，固定字段修订交 clause_revision，组装交 assemble 或 build_submission，不自编 ID 唯一性、通用 schema/来源覆盖或批量匹配校验再重复调用公共工具。

文件不存在、版本不符或所需材料未交付时，报告具体文件/字段路径、预期结构、实际问题、用途及影响，由主会话补充文件和授权并在同一任务交接留痕。必需字段缺失不能用空字典/数组兜底，真实合法空结果才可报告为空。可继续不受影响的部分。已说明的输入错误自行按错误码和字段路径修正；说明与程序行为矛盾、安装故障或职责冲突交主会话处理，不自行扩大权限。

保留完整工具 stdout、stderr 和原进程退出码，不用 echo 覆盖状态、2>/dev/null 或截断管道掩盖失败；回执截断恢复完整结果，原文截断补相应范围。按指定格式交付文件和摘要，列明未完成范围与问题。文件生成成功不表示已入库或语义完整；正式写入、回执和对账由主会话完成。

继续沿用本 skill 的语料文件/证据/审阅格式，不套用合同建模的交换 schema，不授予人工意见外的词表修改权限。
