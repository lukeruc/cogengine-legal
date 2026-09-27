---
name: legal-case
description: 对一份合同及其全部组成素材建立带原文出处的 SQLite 案件库；适用于合同建模入库、查询和对账。
---

# 合同案件入库

## 输入与依赖

先明确材料清单、案件库路径或已有库、全局词表路径、工作目录。需转换时还需每份原件的输出目录和转换配置。按本文件真实目录读取 `../../README.md`、`../../references/case-cli.md`、`../../references/data-formats.md`；需要转换时读取 `../legal-preprocess/SKILL.md`。读手说明位于本目录 `references/`。

## 已批准流程

1. 新案调用 `case_cli init` 冻结词表；已有案先查询 `progress`、词表哈希与当前回执。
2. 各份素材经预处理 skill 取得文本与元数据，用 `register` 登记原件和全文，再用 `split` 切分。异常影响阅读时依既有规则要求更好源件。
3. 派通读与事件认定读手，按 `references/preparation.md` 取得概要、事件及必要主体的完整 JSON；主会话 `write` 成功后取得正式事件 ID。
4. 按不重叠条款批次派打标读手，参见 `references/tagging.md`。主会话逐文件 `write` 标签修订及无匹配缺口。
5. 运行 `group` 导出逐字分组；比较负责条款集合，保证每条款只有一个完整提取责任。多标签副本只作上下文。
6. 各 unit 读手并行提取，参见 `references/extraction.md`。每个读手保存一份完整 `extraction` JSON，并返回路径、负责条款、数量与问题摘要。
7. 主会话每份文件调用一次 `write`。失败将具体 code/path 和必要版本交原读手修正整份文件；成功保存回执。
8. 运行 `reconcile`。按报告用既有 `write` 修正或撤销，再重新对账；报告有 errors 时如实交接未完成。

## 工具用法与恢复

从完整目录运行 `python -m legal.case_cli <init|register|split|write|query|group|reconcile> --db FILE ...`，各命令参数及返回见共用案件说明。`write --input FILE` 是提取文件的唯一提交动作，文件内所有记录整份成功或整份失败。成功文件原样重提返回 `replayed=true` 和原 ID；修正内容须使用既有 object_id、当前 previous_record_id 和完整 data/evidence。写入后旧对账报告变为 stale。查询质量与进度以数据库为准，工作目录不是第二个状态库。

最终交接案件库路径、case_id、词表哈希、本轮条款范围、最新报告及未解决问题。对账零错误仅证明机械条件，原文语义仍需按既定真实合同考卷审阅。
