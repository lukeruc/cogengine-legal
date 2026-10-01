---
name: legal-case
description: 对一份合同及其全部组成素材建立带原文出处的 SQLite 案件库；适用于合同建模入库、查询和对账。
---

# 合同案件入库

## 输入与依赖

先明确材料清单、新合同工作根目录或已有合同工作目录、全局词表路径。需转换时还需每份原件的转换配置。按本文件真实目录读取 `../../README.md`、`../../runtime.json`、`../../references/case-cli.md`、`../../references/data-formats.md`；按 README 核对安装根与命令路径。安装信息缺失、格式错误或路径失效时报告安装问题，不从 PATH 另找工具。需要转换时读取 `../legal-preprocess/SKILL.md`。读手说明位于本目录 `references/`。

## 合同工作目录

新合同的**第一步**是在工作根目录排他创建 `contract-YYYYMMDDTHHMMSSZ`（UTC）；同秒撞名依次加 `-02`、`-03`，不覆盖旧目录。把原件逐字复制到 `inputs/materials/001-<原文件名>` 等路径；全局词表复制到 `inputs/vocabulary/`，转换配置及所需相对文件复制到 `inputs/converters/`。后续 CLI 只读取合同工作目录内的工作副本，数据库固定为根目录的 `contract.sqlite`。每份素材的首次转换结果放在 `converted/001/0001/text.txt` 和 `metadata.json`，重转换用 `converted/001/0002/` 等新目录；已有转换结果也先复制到对应路径。素材编号随首次登记顺序固定，不重排。

读手任务、写入文件、工具回执、分组及报告分别放 `tasks/`、`submissions/`、`receipts/`、`groups/`、`reports/`；具体递增文件名和重复运行规则见 `../../references/case-cli.md`。每个子任务只写分配的合同工作目录内路径。续做同一合同、纠错或新增材料时沿用该目录及其 `contract.sqlite`；不另建目录或复制数据库。旧合同工作目录不自动迁移。文件名不是状态，实际进度仍查库。

## 已批准流程

1. 新案先按上节建目录并复制输入，再以案件内词表副本调用 `case_cli init` 冻结词表；已有案沿用目录，先查询 `progress`、词表哈希与当前回执。
2. 各份素材经预处理 skill 取得文本与元数据，用 `register` 登记原件和全文，再用 `split` 切分。异常影响阅读时依既有规则要求更好源件。
3. 派通读与事件认定读手，按 `references/preparation.md` 建立阅读目录、顺序通读、带问题回读，取得概要、事件及必要主体的完整 JSON；主会话 `write` 成功后取得正式事件完整查询记录。
4. 按不重叠条款批次派打标读手，参见 `references/tagging.md`。主会话逐文件 `write` 标签修订及无匹配缺口。
5. 运行 `group` 导出逐字分组；按 `references/handoff.md` 写完整任务及输入清单，比较负责条款集合，保证每条款只有一个完整提取责任。冻结词表和共用对象完整查询结果供读手读取，多标签副本只作上下文。
6. 各 unit 读手并行提取，参见 `references/extraction.md`。每个读手保存一份完整 `extraction` JSON，并返回路径、负责条款、数量与问题摘要。
7. 主会话每份文件调用一次 `write`。失败将具体 code/path 和必要版本交原读手修正整份文件；成功保存回执。
8. 运行 `reconcile`。按报告用既有 `write` 修正或撤销，再重新对账；报告有 errors 时如实交接未完成。

## 工具用法与恢复

从安装信息中取 `commands["legal-case"]` 的绝对路径，以当前合同工作目录为进程工作目录，按参数数组运行 `<init|register|split|write|query|group|reconcile> --db FILE ...`。例如 `argv=[runtime.commands["legal-case"],"write","--db",合同库绝对路径,"--input",提交文件绝对路径]`。各命令参数、输入输出格式、错误和退出码见 `../../references/case-cli.md`、`../../references/data-formats.md`；保留 stdout、stderr 与退出码。`write --input FILE` 是提取文件的唯一提交动作，文件内所有记录整份成功或整份失败。成功文件原样重提返回 `replayed=true` 和原 ID；修正内容须使用既有 object_id、当前 previous_record_id 和完整 data/evidence。写入后旧对账报告变为 stale。查询质量与进度以数据库为准，工作目录不是第二个状态库。

最终交接合同工作目录、案件库路径、case_id、词表哈希、本轮条款范围、最新报告及未解决问题。对账零错误仅证明机械条件，原文语义仍需按既定真实合同考卷审阅。
