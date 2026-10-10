# 入库读手辅助脚本

两个脚本按需用于已有任务，能直接生成正确 JSON 时可以不用。读手决定建模内容、引句、来源和完成声明；主会话调用正式 CLI 写入、接收回执及对账。辅助成功只表示任务文件处理成功。

## 调用与文件位置

主会话核验安装的 runtime.json，将其 python 启动路径、已安装脚本绝对路径和输入/输出绝对路径直接写在现有任务说明中。脚本位于本 skill 真实目录的 `scripts/find_quote.py` 和 `scripts/build_submission.py`；共用模块装入同一 .venv。保留环境内 Python 的启动路径，不把其符号链接解析到基础解释器。用参数数组运行，中文与空格路径保持一个参数。

```text
argv = [runtime.python, <已安装 find_quote.py 的绝对路径>,
        "--clauses", <完整条款快照绝对路径>,
        "--input", <引句请求绝对路径>, "--output", <新锚数组绝对路径>]

argv = [runtime.python, <已安装 build_submission.py 的绝对路径>,
        "--header", <信封文件绝对路径>,
        "--records", <锚数组绝对路径>, "--records", <业务记录数组绝对路径>,
        "--output", <任务分配的完整提交绝对路径>]
```

信封、引句请求和记录数组放在分配的合同 tasks 子目录；完整提交放指定 submissions 文件。脚本不分配目录、不创建父目录、不改变 cwd。读手无需搜索 runtime、README 或源码，不设置 sys.path、PYTHONPATH 或改用 PATH 中另一套程序；安装依赖缺失交回主会话。

脚本只读显式文件，不接受 --db，不访问 SQLite、正式 CLI、外部进程或网络。需补充原文、正式 ID 或版本时由主会话交付。这个文件约定不是操作系统权限隔离。

## find_quote.py：精确引句

--clauses 使用主会话导出的 `{case_id,checked_sequence,items}`；items 是保留 record_id/object_id/data.text 和原文地址的完整 clause 查询记录，不能用摘要或重新切分的片段代替。

--input 是非空数组；每项恰有 local_id、clause_record_id、quote，可另有正整数 occurrence。local_id 在请求中唯一，clause_record_id 指快照中的固定 UUID；quote 为非空逐字原句。示意（实际 UUID 从主会话交付取得）：

```json
[{"local_id":"payment-quote","clause_record_id":"11111111-1111-4111-8111-111111111111","quote":"甲应付款。","occurrence":1}]
```

唯一命中可省略 occurrence，输出使用 1；重复必须显式选定。匹配包含重叠：aaaa 中 aa 的序号 2 对应 [1,3)。位置按 Unicode 码点，左闭右开。中文、非 BMP 字符、CRLF、组合字符保持原样；不修复 OCR、不合并空白、不作 Unicode 归一化或近似匹配。

输出为标准 anchor 记录数组，可交给组装脚本：

```json
[{"local_id":"payment-quote","kind":"anchor","data":{"clause":{"record_id":"11111111-1111-4111-8111-111111111111"},"quote":"甲应付款。","occurrence":1},"evidence":[]}]
```

脚本不生成正式新 ID，不自动选择业务来源、覆盖路径、前提或关系。成功 stdout 附 case_id、checked_sequence 和 matches（local_id、clause_record_id、occurrence、相对条款的 start_offset/end_offset）；偏移不进入 anchor data，正式 write 重新计算地址。

| 失败码 | 处理 |
|---|---|
| ANCHOR_AMBIGUOUS | 查看 match_count 和 candidates，明确 occurrence；候选最多展示 100 处，candidates_truncated 表示截断，可选序号仍不限于前 100 处 |
| ANCHOR_NOT_FOUND | 核对版本和逐字引句，不能近似匹配或自动用整条款替代 |
| ANCHOR_OCCURRENCE | 填从 1 开始且不超匹配总数的整数 |
| REFERENCE_NOT_FOUND | 仅表示本次快照没有该版本，由主会话补材料 |
| DUPLICATE_LOCAL_ID / INVALID_ARGUMENT | 修正标识或快照冲突；同一 record_id 对应不同条款内容会被拒绝 |

任一请求失败，整份锚数组不写出。精确命中不证明引句足以支持法律判断。

## build_submission.py：组装与基础检查

--header 恰含既有 write 信封去掉 records 后的字段：format_version、case_id、vocabulary_hash、submitted_by、phase、covered_clauses、issues；仅 preparation 可有 overview。身份信息来自主会话，覆盖声明、issues 和概要由读手明确填写；不能省略让脚本补默认值。phase 支持 preparation/tagging/extraction/correction；非 extraction 覆盖声明为空，extraction 至少声明一个条款。

--records 至少一次；每个文件为完整标准单记录数组，字段见交付的 data-formats。按参数顺序拼接，保持各数组内部顺序，不排序、不去重。规范化到同一路径的重复文件被拒绝。批内前向 local_id 引用允许，不生成正式 ID，不改变 object_id/previous_record_id。

基础检查覆盖严格 JSON、信封结构、记录外层、批内 local_id 与修订对象唯一性、覆盖条款 object_id 唯一性，以及已定义引用位置的 local_id 存在性。位置包括 overview、条款/锚、节点参与者与值、关系端点、细节 owner/值、解释性引用、缺口、无内容及 evidence 的 anchors/premises。普通文本、未知键或无法识别的 data 不作同名键递归搜索。

输出仅含标准信封和 records，不夹带路径、版本、检查摘要或时间戳；保持业务字段和顺序，不补性质、模态、来源、槽值、null、issues 或覆盖声明。成功 stdout 固定附：

```json
{"checked":["json","envelope","record_envelopes","batch_ids","recognized_local_references"],"deferred_checks":["record_content","vocabulary_and_values","database_state","reference_targets","evidence","coverage","legal_meaning"]}
```

recognized_local_references 只涵盖按已知字段语法识别的引用。记录内部全部字段、槽适用性、值与单位、目标类型、来源覆盖、版本新旧、撤销依赖及提取完成条件仍交正式 write；未知结构属于待正式校验内容。文件成功不保证入库成功。

## 返回与失败修正

正常 stdout 为一个 JSON 对象。成功共有 ok:true、scope:"task_files"、output_file、record_count。失败为 ok:false、errors:[{code,path,message,...}]、errors_truncated，可含 file；按输入文件及数组顺序排列，最多返回 100 项。stderr 仅作诊断。退出码 0 为文件操作成功，2 为参数/格式/基础检查失败，3 为文件读写失败或 FILE_EXISTS。--help 为文本、退出 0、不读输入；未知参数、单值参数重复均为 INVALID_ARGUMENT，仅 --records 可重复。

所有检查结束后才写出，已有目标绝不覆盖；失败不留部分输出，不改输入。读手在当前任务内修正，再次组装使用主会话按既有规则分配的未占用路径。成功入库文件及回执不可改写。修订仍由读手给完整新记录及明确前驱，不从旧记录自动合并、刷新前驱或恢复对象。

脚本不改变权限：分段读手只写笔记，主体和事件仍由归纳读手认定。主会话处理摘要和 issues 的明确问题，每份完整提交调用一次已有 write，随后 reconcile；不增检查 agent、审批或完成状态。
