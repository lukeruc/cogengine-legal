---
name: legal-case
description: 对一份合同及其全部组成素材建立带原文出处的 SQLite 案件库；适用于合同建模入库、查询和对账。
---

# 合同案件入库

## 安装路径

将下列占位路径替换为宿主提供的本文件绝对路径，先解析符号链接，再取父目录：

```python
from pathlib import Path

skill_dir = Path("/host/skills/legal-case/SKILL.md").resolve(strict=True).parent
install_root = skill_dir.parent.parent
runtime_path = install_root / "runtime.json"
print(runtime_path)
print(install_root / "references")
```

先完成上述定位，再按输出的绝对路径读取资料。本文件中的相对资料路径均以 `skill_dir` 为基准，与 shell 工作目录无关。CLI 的绝对路径从核验后的 `runtime.json` 取得。本 skill、参考资料及 CLI 均使用安装目录内的副本。

读取安装信息后，核对 `format_version` 为整数 `1`、`release_version` 为非空字符串、`install_root` 等于上述真实安装根、`environment_root` 指向其中的 `.venv`。`python` 及 `commands` 中的 `legal-case`、`legal-vocab`、`legal-preprocess` 必须是该环境内存在且可执行的绝对路径；保留环境内 Python 的启动路径。安装信息不符时报告安装问题，停止依赖它的业务调用。

## 输入与依赖

先明确材料清单、新合同工作根目录或已有合同工作目录、全局词表路径。需转换时还需每份原件的转换配置。按本文件真实目录读取 `../../runtime.json`、`../../references/case-cli.md`、`../../references/data-formats.md`。安装信息缺失、格式错误或路径失效时报告安装问题，不从 PATH 另找工具。需要转换时读取 `../legal-preprocess/SKILL.md`。sub-agent 说明位于本目录 `references/`。

## 合同工作目录

新合同的**第一步**是在工作根目录排他创建 `contract-YYYYMMDDTHHMMSSZ`（UTC）；同秒撞名依次加 `-02`、`-03`，不覆盖旧目录。把原件逐字复制到 `inputs/materials/001-<原文件名>` 等路径；全局词表复制到 `inputs/vocabulary/`，转换配置及所需相对文件复制到 `inputs/converters/`。后续 CLI 只读取合同工作目录内的工作副本，数据库固定为根目录的 `contract.sqlite`。每份素材的首次转换结果放在 `converted/001/0001/text.txt` 和 `metadata.json`，重转换用 `converted/001/0002/` 等新目录；已有转换结果也先复制到对应路径。素材编号随首次登记顺序固定，不重排。

 sub-agent 任务、写入文件、工具回执、分组及报告分别放 `tasks/`、`submissions/`、`receipts/`、`groups/`、`reports/`；具体递增文件名和重复运行规则见 `../../references/case-cli.md`。每个子任务只写分配的合同工作目录内路径。续做同一合同、纠错或新增材料时沿用该目录及其 `contract.sqlite`；不另建目录或复制数据库。旧合同工作目录不自动迁移。文件名不是状态，实际进度仍查库。

## 已批准流程

1. 新案先按上节建目录并复制输入，再以案件内词表副本调用 `case_cli init` 冻结词表；已有案沿用目录，先查询 `progress`、词表哈希与当前回执。
2. 各份素材经预处理 skill 取得文本与元数据，用 `register` 登记原件和全文，再用 `split` 切分。异常影响阅读时依既有规则要求更好源件。
3. 按 `references/preparation.md` 和 `references/reading-inputs.md` 固定版本并先准备完整阅读材料。完整条款连续分段，目标初值每任务 20,000 个 Unicode 字符；超长单条交同一 reader 分窗读完。各段派 reader 并行全读、写独立的原文依据笔记；收齐实际已读范围后交一个 summarizer 统一形成概要、主体和事件，单段由同一 reader 兼任。主会话提交一个 `preparation` JSON，`covered_clauses=[]`，成功后交接正式完整共用查询。
4. 按不重叠条款批次派 tagger，参见 `references/tagging.md`。主会话逐文件 `write` 标签修订及无匹配缺口。
5. 运行 `group` 导出逐字分组；按 `references/handoff.md` 写完整任务及输入清单，派发首先列出负责条款及全部规定的完整提取责任。任务 `unit_id` 仅提供分组上下文，不限制输出关系的单元；比较负责条款集合，保证每条款只有一个完整提取责任。冻结词表和共用对象完整查询结果供 extractor 读取，多标签副本只作上下文。
6. 按完整条款主责派 extractor 并行提取，参见 `references/extraction.md`。extractor 先识别规定、主体及完整限制，再选单元/适用槽并组织 JSON；不得假定其他 extractor 会提取本条款的剩余规定。每个 extractor 保存一份完整 `extraction` JSON，并返回路径、负责条款、数量与问题摘要。
7. 主会话读取摘要及提交文件的 `issues`，按下节处理明确问题，再每份文件调用一次 `write`。失败将具体 code/path 和必要版本交原 sub-agent 修正整份文件；成功保存回执。
8. 运行 `reconcile`。按报告用既有 `write` 修正或撤销，再重新对账；报告有 errors 时如实交接未完成。

## 两部分角色派发（主会话）

按职责读取 `templates/reader.md`、`templates/summarizer.md`、`templates/tagger.md` 或 `templates/extractor.md`。实际派发恰含“固定内容”和“本次任务要求”两部分；第一部分原样完整带入，第二部分填实身份、目标、责任/上下文、按顺序的输入、实际绝对路径、格式参数、独立输出、可用操作、自然语言关注或纠错要求及返回摘要，保存实际派发正文到现有 tasks。不能只发模板路径或临时改写权限。

角色实例用 reader、summarizer、tagger、extractor，同类并行加 -1、-2 等；宿主 ID 保留寻址，不能改名就在标题和摘要显示职责。task_id、旧 role 代码和正式 ID 不因显示名变化迁移；submitted_by 由主会话明确交付。单段 reader 完成后沿用原会话派发 summarizer 内容，不新开实例。

主会话查询并固定全部分页、正式版本和共享 ID。每个角色只拿自己的说明、完整数据、需要的工具说明与同版样例；纯阅读不用无关构造样例。明确授权可定位原文范围，不能把整个 tasks 或安装目录作为自由浏览权限。summarizer 的已完成 reader 笔记由主会话正式交付。检查路径存在、输出未占用，给足资料后再派发；不把数据库或正式 CLI 路径当子任务接口。

`preparation.md` §2 给 reader，§3—§4 给 summarizer；tagger 用 `tagging.md`，extractor 用 `extraction.md`。主会话操作分别在本文件、`reading-inputs.md`、`handoff.md`；各角色无需读取主会话编排说明来判断权限。纠错交原角色，资料/安装/实现问题由主会话处理，不新增 fixer/reviewer 环节。

## 按需使用的 sub-agent 辅助脚本

派发时读取 `references/helper-tools.md`，将核验后的 runtime.python 启动路径、本 skill 真实目录内 `scripts/find_quote.py`、`scripts/build_submission.py` 的绝对路径，以及分配的输入/输出绝对路径和用法直接交给 sub-agent。主会话准备固定版本的完整条款快照；sub-agent 可以按需生成锚数组、组装完整提交，也可以直接写同格式文件。公开构造 API 及 `examples/quote_requests.py`、`preparation.py`、`tagging.py`、`extraction.py` 和虚构 `fixture.json` 的用途见 helper-tools；将本角色所需样例绝对路径交付。

两个脚本只处理任务文件，不查询数据库或调用正式 CLI；sub-agent 需要补充材料和版本时由主会话交付。信封、请求及记录数组放 tasks 的分配子目录，完整提交放指定 submissions 路径。脚本不补法律判断、不覆盖已有文件；文件成功不表示入库或语义验收成功。主会话仍统一 write、处理 issues 和 reconcile，不增加任务字段或必经检查。

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
