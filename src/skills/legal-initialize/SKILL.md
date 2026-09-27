---
name: legal-initialize
description: 从用户指定的归纳语料经两遍提取与两道人审生成首版法律关系词表；适用于词表初始化。
---

# 首版词表初始化

## 输入与依赖

用户事先指定语料用途：`induction`、`rule_exam`、`held_out`、`legal_checklist`。还需工作目录、正式词表目标路径、需转换材料的原件与转换配置。按本文件真实目录读取 `../../README.md`、`../../references/vocab-cli.md`、`../../references/data-formats.md`；按当前遍次读取本目录 `references/first-pass.md` 或 `references/second-pass.md`。转换用 `../legal-preprocess/SKILL.md`，真实合同建模验收用 `../legal-case/SKILL.md`。

## 两遍两道人审

1. 整理 `corpus.json`，记录每份材料用途、合同种类、来源、原件/文本路径与哈希、转换元数据。非 induction 不进入单元或槽的归纳证据集。
2. 第一遍按条款提取主题、可约定点、摘句、当事方和原文模态词，依据 `first-pass.md` 形成 `units-review.md`，用户直接写意见。
3. 读取第一道人审意见，整理 `units-approved.json`；未收到意见时停在此环节。
4. 第二遍依已审单元提取槽、值结构、例句、归属与条件适用说明，依据 `second-pass.md` 形成 `slots-review.md`；用户直接写意见。
5. 读取第二道人审意见，整理最终变更文件。主会话用词表 CLI 创建正式空词表并提交批准后的条目；形成词表、证据包、判定表，附残留条款、规则考卷表达结果和法律清单查漏结果。

## 工具用法与交接

从完整目录运行 `python -m legal.vocab_cli init --vocabulary FILE`，再用 `--vocabulary FILE --input CHANGE.json` 提交正式条目。`list/show/diff` 用于检查结果；不要用案件 `init` 代替词表生成。成功交付三件套路径、词表哈希、工具回执和未完成事项。错误需按 code/path 修正；人工意见有冲突或不能解释时向用户核实。工具不机械解析自然语言意见。
