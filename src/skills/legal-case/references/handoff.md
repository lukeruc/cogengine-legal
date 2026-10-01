# 读手任务与完整输入交接

任务文件是既有派发步骤的工作文件，不记录第二份案件状态：

```json
{
  "format_version": 1,
  "task_id": "0003-extraction",
  "unit_id": null,
  "responsible_clauses": [{"object_id": "条款对象UUID", "record_id": "当前记录UUID"}],
  "context_clauses": [],
  "input_files": ["合同目录内的完整输入文件路径"],
  "output_file": "合同目录/submissions/0003-extraction.json"
}
```

UUID示意值在实际文件中使用查询所得正式ID。unit_id在普通unit任务中使用冻结UUID，无匹配／无内容等任务可null。context与responsible可相交；各任务responsible必须两两不交、并集等于本轮范围。条款引用同时保留object_id和所读record_id。输出路径唯一且未使用，失败修正原文件的规则仍由主会话控制。

每份任务的input_files明确包括：正式extraction说明、负责条款完整原文、对应分组上下文、完整冻结词表、最新概要、正式事件完整记录、其他已知共用节点查询结果和data-formats。输入用成功写入后的query导出，保留data／evidence／provenance和版本身份，依next_offset读完全部分页；空事件清单显式给出。槽表及仅ID／名称的对象简表不能代替它们。

案件任务只说明该合同的范围、输入和输出。缺口、值形态、当事人性质和来源级直接引用正式说明，避免临时任务把missing_slot误写为原文留空，或把modality放进parties。

已有内部辅助`legal.handoff.export_extraction_tasks(db_path, plans, output_dir, resource_root, clause_ids=None)`可以完成此导出，不是新增CLI。用安装的共用解释器导入该函数；resource_root是已核验的安装根，output_dir是合同tasks下新的空子目录。plans各项包含task_id、unit_id、responsible_clauses、context_clauses、group_file、output_file；主会话自行选定主责，group_file指向合同groups中的正式导出。clause_ids省略表示全部当前文本条款，指定时表示本轮范围。函数比较负责集合、当前条款版本、分组和配置身份，保存完整输入及规范任务，返回路径和数据库提交序号；派发前如数据库已变，重新核对版本而不是继续使用陈旧任务。

读手返回`{task_id,output_file,responsible_clauses,record_counts,issues}`，responsible_clauses仍是对象／记录ID对清单。主会话每份文件调用一次write，保存完整回执。回执成功和机械覆盖不能代替原文语义验收。
