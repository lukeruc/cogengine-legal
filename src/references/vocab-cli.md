# 词表 CLI 用法

安装后从 `../runtime.json` 的 `commands["legal-vocab"]` 取绝对命令路径，以参数数组运行下列命令；示例中的 `python -m legal.vocab_cli` 仅供源码开发时替换使用。词表工作目录是进程工作目录，无需激活环境或设置 `PYTHONPATH`。`--vocabulary` 可放在子命令前或后。正式词表为 JSON 写法，文件名可为 `.json` 或 `.yaml`。读取和比较可使用目录，写入仅支持单文件。程序不内置业务词表。

```bash
python -m legal.vocab_cli init --vocabulary /path/vocabulary.json
python -m legal.vocab_cli list --vocabulary /path/vocabulary.json --kind unit
python -m legal.vocab_cli show --vocabulary /path/vocabulary.json --kind slot --id SLOT_ID
python -m legal.vocab_cli add --vocabulary /path/vocabulary.json --kind unit --entry-json '{"name":"付款","description":"支付价款"}'
python -m legal.vocab_cli remove --vocabulary /path/vocabulary.json --kind unit --id UNIT_ID
python -m legal.vocab_cli diff --left /path/old.json --right /path/new.json
python -m legal.vocab_cli aggregate --vocabulary /path/vocabulary.json --cases /path/cases.json --output /path/gaps.json
```

混合变更从一个严格 JSON 文件提交，不带子命令：

```bash
python -m legal.vocab_cli --vocabulary /path/vocabulary.json --input /path/change.json
```

文件结构：`{format_version:1,expected_hash,operations,orphan_slots?}`。新增操作 `{action:"add",kind:"unit|slot",local_id,entry,unit_ids?}`，ID 由工具生成。删除操作 `{action:"remove",kind:"unit|slot",id}`。单元删除导致已有槽失去全部归属时，在 `orphan_slots` 指明 `{slot_id,disposition:"remove|general|reassign",unit_ids?}`；`reassign` 需非空目标单元。缺少明确处置报 `ORPHAN_DISPOSITION_REQUIRED`，词表不变。哈希变化报 `HASH_CONFLICT`，应重新对照当前词表及人工意见。

成功变更回执含 `before_hash,after_hash,id_map,changes`。`diff` 分列条目与归属的增删；同 ID 改内容列入 `illegal_content_changes` 并退出 2。聚合清单为 `{format_version:1,cases:[路径,...]}`，相对路径以清单所在目录解析；任一案件不能读取则整份失败，不能把不完整报告交人审阅。聚合只提供冻结条目、缺口、出处和当前词表哈希，建议由读手形成。
