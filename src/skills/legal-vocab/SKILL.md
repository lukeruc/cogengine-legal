---
name: legal-vocab
description: 对已有全局法律关系词表按案件缺口或律师要求进行人工治理；适用于词表增删、归属调整与汇总。
---

# 词表治理

## 安装路径

将下列占位路径替换为宿主提供的本文件绝对路径，先解析符号链接，再取父目录：

```python
from pathlib import Path

skill_dir = Path("/host/skills/legal-vocab/SKILL.md").resolve(strict=True).parent
install_root = skill_dir.parent.parent
runtime_path = install_root / "runtime.json"
print(runtime_path)
print(install_root / "references")
```

先完成上述定位，再按输出的绝对路径读取资料。本文件中的相对资料路径均以 `skill_dir` 为基准，与 shell 工作目录无关。CLI 的绝对路径从核验后的 `runtime.json` 取得。本 skill、参考资料及 CLI 均使用安装目录内的副本。

读取安装信息后，核对 `format_version` 为整数 `1`、`release_version` 为非空字符串、`install_root` 等于上述真实安装根、`environment_root` 指向其中的 `.venv`。`python` 及 `commands` 中的 `legal-case`、`legal-vocab`、`legal-preprocess` 必须是该环境内存在且可执行的绝对路径；保留环境内 Python 的启动路径。安装信息不符时报告安装问题，停止依赖它的业务调用。

## 输入与依赖

明确当前正式词表路径、工作目录，以及案件清单或律师提出的变更要求。按本文件真实目录读取 `../../runtime.json`、`../../references/vocab-cli.md`、`../../references/data-formats.md`。安装信息缺失、格式错误或路径失效时报告安装问题，不从 PATH 另找工具。要查看尚未转换的原件时读取 `../legal-preprocess/SKILL.md`。

## 步骤

1. 案件缺口入口先用 `aggregate --cases FILE --output FILE` 汇总；律师要求入口直接读取要求。结合 `list/show`、当前词表及相关证据，判断现有词表能否表达。
2. 在工作目录写 `proposal.md`：问题、具体增删和归属处置、当前表达能力、证据与理由。用户直接在该文件中写自然语言意见。
3. 收到意见后按意见整理变更 JSON；主会话调用词表 CLI 的已批准 `add/remove` 或混合变更 `--input FILE`。若哈希变化，重新对照现有内容及意见；意见无法确定新冲突时向用户核实。
4. 交付建议及意见文件路径、实际变更文件、回执、前后哈希、ID 映射和差异摘要。旧案冻结快照不回填。

## 工具用法与继续条件

从安装信息中取 `commands["legal-vocab"]` 的绝对路径，以工作目录为进程工作目录并按参数数组调用 `--vocabulary FILE <init|list|show|add|remove|aggregate> ...`；混合变更使用 `--vocabulary FILE --input CHANGE.json`，`diff` 用 `--left/--right`。例如 `argv=[runtime.commands["legal-vocab"],"aggregate","--vocabulary",词表绝对路径,"--cases",清单绝对路径,"--output",报告绝对路径]`。完整参数、文件格式与回执见 `../../references/vocab-cli.md` 和 `../../references/data-formats.md`。保留 stdout、stderr 与退出码；错误 code/path 决定修正位置；`HASH_CONFLICT` 不自动替用户重写意见，`ORPHAN_DISPOSITION_REQUIRED` 必须明确槽去向。未经人工意见的建议不能当作已执行变更。治理低频按需，不自动重跑入库或初始化。

## 已有 sub-agent 的命名与派发

已有证据阅读任务用 reader，已有汇总职责用 summarizer；不为名称新增派发或审核步骤。同类实例加 -1、-2，宿主 ID 保留寻址；task_id、证据身份与管理署名不因名称迁移。每次实际派发包含“固定内容”和“本次任务要求”两部分；固定内容给本角色职责及文件/操作/异常边界，第二部分填实际目标、语料用途、资料/版本、绝对路径、独立输出和自然语言要求，不能临时改权限。已有阅读/汇总派发须直接带入以下共用规则，并固定本任务的证据阅读或归纳职责：

按本角色职责处理第二部分明确分配的任务。以提供的角色说明、data-formats、工具用法和固定样例作为格式依据。

可以读取第二部分列出的输入、明确授权的原文范围，以及本任务自行生成的文件；可以在指定位置写入本任务产物，运行列明的文件辅助脚本和构造函数。可以使用宿主文件操作与专用环境 Python 执行必要的短调用片段。

不调用 legal-case、legal-vocab、legal-preprocess；不通过模块入口、内部数据库函数、sqlite3 或其他程序执行同等操作，包括只读查询。不自行安装工具、寻找 runtime/README、修改安装副本或建立环境。

不读取其他并行任务的中间产物，不以其他任务文件作为格式样例。正常执行不主动阅读辅助脚本及包内实现；由 Python 正常加载已安装模块不属于主动阅读实现。调用片段只组织本任务数据与调用公开函数，不复制通用构造、校验或数据库逻辑。

文件不存在、版本不符或所需材料未交付时，报告具体缺失及影响，由主会话补充。可继续不受影响的部分。已说明的输入错误自行按错误码和字段路径修正；说明与程序行为矛盾、安装故障或职责冲突交主会话处理，不自行扩大权限。

按指定格式交付文件和摘要，列明未完成范围与问题。文件生成成功不表示已入库或语义完整；正式写入、回执和对账由主会话完成。

继续沿用本 skill 的语料文件/证据/审阅格式，不套用合同建模的交换 schema，不授予人工意见外的词表修改权限。
