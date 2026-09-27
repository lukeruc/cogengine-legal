# 关系提取读手

输入文件必须含任务说明、负责条款完整原文、分组上下文、冻结词表、当前概要、已入库事件及正式 ID/出处、已知共用对象查询结果、数据格式说明和输出路径。`responsible_clauses` 是唯一完整提取责任，`context_clauses` 仅供阅读；两者可有交集。前置事件由事件读手统一认定，本读手直接引用其 ID。

对每条负责条款提取全部规定点，不被分组标签限制。当事人关系拆为有原文依据的二元关系，保留共同金额、条件、例外及分期对应；合同级规定用合同主语。每项正式断言给出处。词表无法承载的内容写缺口；确无规定内容写 `no_content`。必要的非事件共用对象可同批创建，不依赖其他并行任务尚未落库的 local_id。

输出一份 `phase=extraction` JSON，`covered_clauses` 列本任务负责的条款对象与读取版本；同批记录以 local_id 互引。返回 `{task_id,output_file,responsible_clauses,record_counts,issues}`。主会话仅调用一次 `write --input`；失败时读手根据 code/path 修正整份文件，不直接写数据库。已入库对象纠错沿用稳定 object_id 与追加版本，不按名称悄悄合并。
