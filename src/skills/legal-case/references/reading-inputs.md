# 初读材料导出辅助

这是既有 preparation 环节的 Python 库辅助，不新增 CLI 或数据库状态。使用核验安装的共用解释器导入 `legal.initial_reading`，资源根为同一安装根；职责见 [preparation.md](preparation.md)。

## 准备阅读材料

```python
from legal.initial_reading import export_initial_reading_tasks

result = export_initial_reading_tasks(
    db_path=contract_dir / "contract.sqlite",
    output_dir=contract_dir / "tasks/0001-initial-reading",
    resource_root=install_root,
    preparation_file=contract_dir / "submissions/0001-preparation.json",
    target_chars=20_000,
    window_chars=6_000,
)
```

示例的 contract_dir、install_root 是调用方实际绝对路径的 pathlib.Path；使用安装信息中共用解释器，不混用旧代码和新说明。原七个案件 CLI 命令不变。

- output_dir 是合同 tasks 下按现有序号分配的新/空子目录，不覆盖产物。
- preparation_file 是 submissions 下分配的新文件；归纳读手写 JSON，主会话调用现有 write。
- text_version_ids 省略时主读全部当前素材；增量时指定新增素材的当前文本对象 ID 集合，其他当前全文仍提供回读入口。不接受旧版本或半条款主读范围。
- target_chars 默认为 20,000 Unicode 字符，含标题、表格、空白；独立超长条款不拆任务。
- window_chars 默认为 6,000，按宿主单次输出能力调整，与任务目标独立。字符数不是 token 数，实际截断仍要补读。

辅助读全部分页，固定 case_id/序号，按素材内 sequence 排序；选中条款须逐字重建登记全文。只导出，不改数据库、登记原文或原件。

返回 manifest_file、tasks、files 和固定序号。导出位置：

| 文件 | 用途 |
|---|---|
| manifest.json / directory.md | 材料、版本、顺序、编号/区域、字符区间及初始未读清单 |
| materials.json / texts.json / clauses.json | 完整查询快照 |
| vocabulary.json / overview.json / events.json / shared-objects.json | 完整冻结词表及既有共用记录，空结果显式保存 |
| texts/*.txt / clauses/*.txt | 逐字全文/条款原文，供定位回读 |
| windows/*.txt | 无管理字段的连续原文窗口，任务附条款内及全文 Unicode 半开区间 |
| 0001-reading.json / 0001-reading.md 等 | 分段任务和管理标题/窗口顺序，含上级标题上下文入口 |
| 0001-notes.md 等 | 读手的独立输出路径；导出不预填已读笔记 |

任务是工作文件：main_reading_clauses 是对象/记录 ID 对；windows 列连续窗口；context_clauses 是阅读上下文；input_files 给明确输入位置。role=segment_reading 只产 Markdown 笔记，不分配事件 ID；只有一段时 role=reading_and_synthesis，附 preparation_file，由同一读手继续归纳。

说明和数据格式引用核验存在的安装绝对路径，保留安装内依赖关系，不复制出失效相对链接。派发前检查路径，读手顺序全读窗口，截断补读。

## 收齐后形成归纳任务

先检查读手回报的实际已读/未读/截断/问题范围，补齐受阻任务再收全部笔记。文件存在不等于读完。

```python
from legal.initial_reading import export_initial_synthesis_task

task = export_initial_synthesis_task(
    db_path=contract_dir / "contract.sqlite",
    manifest_file=result["manifest_file"],
    output_file=contract_dir / "tasks/0001-initial-reading/0002-synthesis.json",
)
```

归纳任务用 manifest 同目录下新的 JSON 文件。辅助检查当前素材/文本/条款版本和原文快照、笔记存在且非空，重新导出最新概要/正式事件/共用对象/词表到对应 *-shared.json，给一个归纳读手。单段的 continue_reader_task_id 指向原读手，不能另开 agent；单段也可以直接继续原任务，提交前查询最新共用身份。

归纳给唯一 preparation 输出和 covered_clauses=[]。已存在准备文件时先查库/回执判断重放或修正，不覆盖成新一套对象。辅助不解析笔记为业务 schema，不证明实际已读、问题解决或语义准确。

## 恢复

`check_reading_versions(db_path, manifest_file)` 核对当前素材/文本/条款版本及导出原文，返回当前序号与新增文本 ID。无关提交改变序号不自动否定有效笔记；受影响版本改变则重定阅读依据，新素材另行主读，旧共同条件按问题回读。

它不返回读完或语义通过；复用前仍检查笔记实际已读/未读。共用记录变化时归纳使用新完整查询，成功准备的正式身份和进度以数据库为准。
