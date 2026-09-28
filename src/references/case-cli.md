# 案件 CLI 用法

安装后从 `../runtime.json` 的 `commands["legal-case"]` 取绝对命令路径，以参数数组运行下列命令；示例中的 `python -m legal.case_cli` 仅供源码开发时替换使用。合同工作目录是进程工作目录，无需激活环境或设置 `PYTHONPATH`。所有命令将 `--db` 写在子命令后。每次 stdout 返回一份 UTF-8 JSON；成功退出 0，输入或业务校验失败退出 2，文件/数据库故障退出 3，对账已执行但有错误退出 4。错误格式为 `{ok:false,errors:[{code,path,message}],errors_truncated:false}`。

## 入库文件位置和命名

新合同先在指定工作根目录排他创建 `contract-YYYYMMDDTHHMMSSZ`，时间用 UTC；同秒已有目录则依次用 `-02`、`-03`。同一合同续做沿用原目录，旧合同工作目录不自动迁移。合同工作目录根部放 `contract.sqlite`，其余文件按下表存放；序号至少保留表中位数，持续递增，不覆盖已有文件。

| 位置 | 文件命名与用途 |
|---|---|
| `inputs/materials/` | `001-<原文件名>`、`002-<原文件名>`；按首次登记顺序复制原件并保持字节不变，补充材料使用下一序号 |
| `inputs/vocabulary/` | 保存正式词表文件或目录的逐字工作副本；`init --vocabulary` 指向副本本身 |
| `inputs/converters/` | `001/0001/config.json`、`001/0002/config.json`、`002/0001/config.json` 等；前段是素材号，后段是该素材的转换次数；所需非代码相对文件一并复制，源码和转换程序仍以安装位置的绝对路径引用 |
| `converted/001/0001/` | 固定文件名 `text.txt`、`metadata.json`；同一素材重转换用 `001/0002/`，下一素材首次转换用 `002/0001/`；每次 CLI 输出到新的空目录，已有文本和元数据复制到对应目录 |
| `groups/` | `0001/`、`0002/` 等；每次 `group --output-dir` 指向新的空目录，保留旧分组供追溯 |
| `tasks/` | `0001-preparation.json`、`0002-tagging.json`、`0003-extraction.json` 等；每个读手收到唯一输出路径 |
| `submissions/` | `0001-preparation.json`、`0002-tagging.json`、`0003-extraction.json`、`0004-correction.json` 等；每份交给 `write --input` 的文件独立保存 |
| `receipts/` | `0001-init.json`、`0002-register.json`、`0003-split.json`、`0004-write.json` 等；依实际调用顺序保存 CLI JSON 回执，失败回执加 `-error` 后缀 |
| `reports/` | `reconcile-0001.json`、`query-0001.json` 等结果快照及 `final-0001.md`；重跑追加新序号，不覆盖旧报告 |

同一合同运行时输入工作副本、任务、提交和输出文件均留在该合同工作目录内；已安装的源码与转换程序仍在工具位置。配置引用相对数据文件时，把依赖文件一并复制并保持相对关系。文件夹只用于组织和恢复，案件记录与实际提交状态仍以 `contract.sqlite` 为准。

```bash
python -m legal.case_cli init --db /path/contract.sqlite --vocabulary /path/vocabulary.json
python -m legal.case_cli register --db /path/contract.sqlite --original /path/original.pdf --text /path/text.txt --metadata /path/metadata.json
python -m legal.case_cli split --db /path/contract.sqlite --text-version TEXT_VERSION_ID
python -m legal.case_cli write --db /path/contract.sqlite --input /path/submission.json
python -m legal.case_cli group --db /path/contract.sqlite --output-dir /path/groups
python -m legal.case_cli reconcile --db /path/contract.sqlite
python -m legal.case_cli query --db /path/contract.sqlite --view progress
```

`init` 排他创建数据库并冻结词表与单位配置。`register` 将原始字节和转换文本同时保存；元数据可带 `material_id` 指明重转换。`split` 无损切出条款、地址及结构异常缺口。同一成功输入重提返回原回执并令 `replayed=true`，不增加记录。`write` 每个 JSON 文件整份校验、整份提交；成功回执含 `submission_id,content_hash,replayed,id_map,counts,covered_clauses,issues,overview_id`。原回执丢失时重提同内容即可取回。

单记录直接写入：

```bash
python -m legal.case_cli write --db /path/contract.sqlite --kind detail --local-id d1 --data-json '{"owner":{"object_id":"..."},"slot_id":"...","value":null}' --evidence-json '[{"path":"","source":{"level":1,"anchors":[{"record_id":"..."}]}}]' --submitted-by operator
```

修订另给 `--object-id`、`--previous-record-id`，撤销另给 `--status withdrawn --withdrawal-reason`；不能与 `--input` 混用。复杂互引使用完整文件。查询支持 `--view records|materials|clauses|vocabulary|overview|events|progress|gaps|report`、`--object`、`--record`、`--history`、`--include-withdrawn`、可重复 `--kind/--party/--unit/--slot/--source-level/--clause`、`--limit/--offset`、`--format json|markdown`、`--output`。相同过滤器取并，不同过滤器取交。`--view materials --object ID --format original --output FILE` 排他导出原件。查询返回 `result_status=found|no_record` 与质量状态；`no_record` 不等于原文无约定。

`group` 将每个 unit、无内容、无匹配的完整 article 或例外区间导出逐字 JSON，输出目录须为空；每条附 `context_clauses` 供读取上级标题，副本不产生第二份提取责任。多标签条款可出现在多个组，完整提取责任仍只分配一次。`reconcile` 保存六查报告：字符覆盖、锚、值候选、值往返、归类覆盖、称谓闭合。报告 `passed=false` 时退出 4，修正后再次调用；写入后旧报告状态为 `stale`。

完整记录格式、出处和值语法见 [data-formats.md](data-formats.md)。
