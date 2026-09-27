# 案件 CLI 用法

从完整交付目录运行 `python -m legal.case_cli <命令> ...`。所有命令将 `--db` 写在子命令后。每次 stdout 返回一份 UTF-8 JSON；成功退出 0，输入或业务校验失败退出 2，文件/数据库故障退出 3，对账已执行但有错误退出 4。错误格式为 `{ok:false,errors:[{code,path,message}],errors_truncated:false}`。

```bash
python -m legal.case_cli init --db /path/case.sqlite --vocabulary /path/vocabulary.json
python -m legal.case_cli register --db /path/case.sqlite --original /path/original.pdf --text /path/text.txt --metadata /path/metadata.json
python -m legal.case_cli split --db /path/case.sqlite --text-version TEXT_VERSION_ID
python -m legal.case_cli write --db /path/case.sqlite --input /path/submission.json
python -m legal.case_cli group --db /path/case.sqlite --output-dir /path/groups
python -m legal.case_cli reconcile --db /path/case.sqlite
python -m legal.case_cli query --db /path/case.sqlite --view progress
```

`init` 排他创建数据库并冻结词表与单位配置。`register` 将原始字节和转换文本同时保存；元数据可带 `material_id` 指明重转换。`split` 无损切出条款、地址及结构异常缺口。同一成功输入重提返回原回执并令 `replayed=true`，不增加记录。`write` 每个 JSON 文件整份校验、整份提交；成功回执含 `submission_id,content_hash,replayed,id_map,counts,covered_clauses,issues,overview_id`。原回执丢失时重提同内容即可取回。

单记录直接写入：

```bash
python -m legal.case_cli write --db /path/case.sqlite --kind detail --local-id d1 --data-json '{"owner":{"object_id":"..."},"slot_id":"...","value":null}' --evidence-json '[{"path":"","source":{"level":1,"anchors":[{"record_id":"..."}]}}]' --submitted-by operator
```

修订另给 `--object-id`、`--previous-record-id`，撤销另给 `--status withdrawn --withdrawal-reason`；不能与 `--input` 混用。复杂互引使用完整文件。查询支持 `--view records|materials|clauses|vocabulary|overview|events|progress|gaps|report`、`--object`、`--record`、`--history`、`--include-withdrawn`、可重复 `--kind/--party/--unit/--slot/--source-level/--clause`、`--limit/--offset`、`--format json|markdown`、`--output`。相同过滤器取并，不同过滤器取交。`--view materials --object ID --format original --output FILE` 排他导出原件。查询返回 `result_status=found|no_record` 与质量状态；`no_record` 不等于原文无约定。

`group` 将每个 unit、无内容、无匹配的条款导出逐字 JSON，输出目录须为空；多标签条款可出现于多个上下文文件，完整提取责任仍只分配一次。`reconcile` 保存六查报告：字符覆盖、锚、值候选、值往返、归类覆盖、称谓闭合。报告 `passed=false` 时退出 4，修正后再次调用；写入后旧报告状态为 `stale`。

完整记录格式、出处和值语法见 [data-formats.md](data-formats.md)。
