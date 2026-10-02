# 读手任务与完整输入交接

派发先列出 `responsible_clauses`，明确读手须完整提取这些条款中的全部规定。任务 `unit_id` 仅提供分组上下文；每项输出关系的 `relation.unit_id` 按该项规定在完整冻结词表中选择，两者不要求相等。读手不能自行假定其他任务会处理负责条款中的剩余单元。

派发示例：“完整提取 CLAUSE 16、17、20 的全部规定；知识产权分组提供相关上下文。”同一任务可形成多个单元的关系；不要将其派成“只提取这些条款中的知识产权内容”。原文编号只作说明，正式责任以对象/记录ID对为准。

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

UUID示意值在实际文件中使用查询所得正式ID。unit_id在普通分组任务中使用冻结UUID，无匹配／无内容等任务可null。context与responsible可相交，但context不产生额外完整提取责任；各任务responsible必须两两不交、并集等于本轮范围。这个比较证明分配完整，不证明输出已提全。条款引用同时保留object_id和所读record_id。输出路径唯一且未使用，失败修正原文件的规则仍由主会话控制。

每份任务的input_files明确包括：正式extraction说明、负责条款完整原文、对应分组上下文、完整冻结词表、最新概要、正式事件完整记录、其他已知共用节点查询结果和data-formats。输入用成功写入后的query导出，保留data／evidence／provenance和版本身份，依next_offset读完全部分页；空事件清单显式给出。槽表及仅ID／名称的对象简表不能代替它们。

案件任务只说明该合同的范围、输入和输出。缺口、值形态、当事人性质和来源级直接引用正式说明，避免临时任务把missing_slot误写为原文留空，或把modality放进parties。

已有内部辅助`legal.handoff.export_extraction_tasks(db_path, plans, output_dir, resource_root, clause_ids=None)`可以完成此导出，不是新增CLI。用安装的共用解释器导入该函数；resource_root是已核验的安装根，output_dir是合同tasks下新的空子目录。plans各项包含task_id、unit_id、responsible_clauses、context_clauses、group_file、output_file；主会话自行选定主责，group_file指向合同groups中的正式导出。clause_ids省略表示全部当前文本条款，指定时表示本轮范围。函数比较负责集合、当前条款版本、分组和配置身份，保存完整输入及规范任务，返回路径和数据库提交序号；派发前如数据库已变，重新核对版本而不是继续使用陈旧任务。

读手返回`{task_id,output_file,responsible_clauses,record_counts,issues}`，responsible_clauses仍是对象／记录ID对清单。主会话读取摘要和提交文件中的issues，按 [SKILL.md](../SKILL.md#接收结果与明确问题) 处理已暴露的未完成或矛盾，再每份文件调用一次write并保存完整回执。声称其他任务或已有记录承载时须核对实际责任、具体记录及对应内容，不能只接受转交说明。真实限制保留原句、原因和影响，不要求issues为空；回执成功和机械覆盖不能代替原文语义验收。
