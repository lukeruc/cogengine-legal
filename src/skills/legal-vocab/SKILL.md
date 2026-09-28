---
name: legal-vocab
description: 对已有全局法律关系词表按案件缺口或律师要求进行人工治理；适用于词表增删、归属调整与汇总。
---

# 词表治理

## 输入与依赖

明确当前正式词表路径、工作目录，以及案件清单或律师提出的变更要求。按本文件真实目录读取 `../../README.md`、`../../runtime.json`、`../../references/vocab-cli.md`、`../../references/data-formats.md`。按 README 核对安装根与命令路径；安装信息缺失、格式错误或路径失效时报告安装问题，不从 PATH 另找工具。要查看尚未转换的原件时读取 `../legal-preprocess/SKILL.md`。

## 步骤

1. 案件缺口入口先用 `aggregate --cases FILE --output FILE` 汇总；律师要求入口直接读取要求。结合 `list/show`、当前词表及相关证据，判断现有词表能否表达。
2. 在工作目录写 `proposal.md`：问题、具体增删和归属处置、当前表达能力、证据与理由。用户直接在该文件中写自然语言意见。
3. 收到意见后按意见整理变更 JSON；主会话调用词表 CLI 的已批准 `add/remove` 或混合变更 `--input FILE`。若哈希变化，重新对照现有内容及意见；意见无法确定新冲突时向用户核实。
4. 交付建议及意见文件路径、实际变更文件、回执、前后哈希、ID 映射和差异摘要。旧案冻结快照不回填。

## 工具用法与继续条件

从安装信息中取 `commands["legal-vocab"]` 的绝对路径，以工作目录为进程工作目录并按参数数组调用 `--vocabulary FILE <init|list|show|add|remove|aggregate> ...`；混合变更使用 `--vocabulary FILE --input CHANGE.json`，`diff` 用 `--left/--right`。例如 `argv=[runtime.commands["legal-vocab"],"aggregate","--vocabulary",词表绝对路径,"--cases",清单绝对路径,"--output",报告绝对路径]`。完整参数、文件格式与回执见 `../../references/vocab-cli.md` 和 `../../references/data-formats.md`。保留 stdout、stderr 与退出码；错误 code/path 决定修正位置；`HASH_CONFLICT` 不自动替用户重写意见，`ORPHAN_DISPOSITION_REQUIRED` 必须明确槽去向。未经人工意见的建议不能当作已执行变更。治理低频按需，不自动重跑入库或初始化。
