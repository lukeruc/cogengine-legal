# 入库角色的文件辅助工具

两个脚本按需用于已有任务，能直接生成正确 JSON 时可以不用。sub-agent 决定建模内容、引句、来源和完成声明；主会话调用正式 CLI 写入、接收回执及对账。辅助成功只表示任务文件处理成功。

## 主会话交付与角色调用

主会话核验安装的 runtime.json，并直接交付其 python 启动路径、已安装脚本绝对路径和输入/输出绝对路径直接写在现有任务说明中。脚本位于本 skill 真实目录的 `scripts/find_quote.py` 和 `scripts/build_submission.py`；共用模块装入同一 .venv。保留环境内 Python 的启动路径，不把其符号链接解析到基础解释器。用参数数组运行，中文与空格路径保持一个参数。

```text
argv = [runtime.python, <已安装 find_quote.py 的绝对路径>,
        "--clauses", <完整条款快照绝对路径>,
        "--input", <引句请求绝对路径>, "--output", <新锚数组绝对路径>]

argv = [runtime.python, <已安装 build_submission.py 的绝对路径>,
        "--header", <信封文件绝对路径>,
        "--records", <锚数组绝对路径>, "--records", <业务记录数组绝对路径>,
        "--output", <任务分配的完整提交绝对路径>]
```

信封、引句请求和记录数组放在分配的合同 tasks 子目录；完整提交放指定 submissions 文件。脚本不分配目录、不创建父目录、不改变 cwd。sub-agent 无需搜索 runtime、README 或源码，不设置 sys.path、PYTHONPATH 或改用 PATH 中另一套程序；安装依赖缺失交回主会话。

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

--header 恰含既有 write 信封去掉 records 后的字段：format_version、case_id、vocabulary_hash、submitted_by、phase、covered_clauses、issues；仅 preparation 可有 overview。身份信息来自主会话，覆盖声明、issues 和概要由 sub-agent 明确填写；不能省略让脚本补默认值。phase 支持 preparation/tagging/extraction/correction；非 extraction 覆盖声明为空，extraction 至少声明一个条款。

--records 至少一次；每个文件为完整标准单记录数组，字段见交付的 data-formats。按参数顺序拼接，保持各数组内部顺序，不排序、不去重。规范化到同一路径的重复文件被拒绝。批内前向 local_id 引用允许，不生成正式 ID，不改变 object_id/previous_record_id。

基础检查覆盖严格 JSON、信封结构、记录外层、批内 local_id 与修订对象唯一性、覆盖条款 object_id 唯一性，以及已定义引用位置的 local_id 存在性。位置包括 overview、条款/锚、节点参与者与值、关系端点、细节 owner/值、解释性引用、缺口、无内容及 evidence 的 anchors/premises。普通文本、未知键或无法识别的 data 不作同名键递归搜索。

输出仅含标准信封和 records，不夹带路径、版本、检查摘要或时间戳；保持业务字段和顺序，不补性质、模态、来源、槽值、null、issues 或覆盖声明。成功 stdout 固定附：

```json
{"checked":["json","envelope","record_envelopes","batch_ids","recognized_local_references"],"deferred_checks":["record_content","vocabulary_and_values","database_state","reference_targets","evidence","coverage","legal_meaning"]}
```

recognized_local_references 只涵盖按已知字段语法识别的引用。记录内部全部字段、槽适用性、值与单位、目标类型、来源覆盖、版本新旧、撤销依赖及提取完成条件仍交正式 write；未知结构属于待正式校验内容。文件成功不保证入库成功。

## 返回与失败修正

正常 stdout 为一个 JSON 对象。成功共有 ok:true、scope:"task_files"、output_file、record_count。失败为 ok:false、errors:[{code,path,message,...}]、errors_truncated，可含 file；按输入文件及数组顺序排列，最多返回 100 项。stderr 仅作诊断。退出码 0 为文件操作成功，2 为参数/格式/基础检查失败，3 为文件读写失败或 FILE_EXISTS。--help 为文本、退出 0、不读输入；未知参数、单值参数重复均为 INVALID_ARGUMENT，仅 --records 可重复。

所有检查结束后才写出，已有目标绝不覆盖；失败不留部分输出，不改输入。sub-agent 在当前任务内修正，再次组装使用主会话按既有规则分配的未占用路径。成功入库文件及回执不可改写。修订仍由 sub-agent 给完整新记录及明确前驱，不从旧记录自动合并、刷新前驱或恢复对象。

脚本不改变权限：reader 只写笔记，主体和事件仍由 summarizer 认定。主会话处理摘要和 issues 的明确问题，每份完整提交调用一次已有 write，随后 reconcile；不增检查 agent、审批或完成状态。

## 公开内存 API

用主会话给出的专用 Python 启动路径调用；`from legal.reader_helpers import ...` 正常导入已安装模块即可，不读取实现、不修改 sys.path 或环境。库函数不打印日志、不读库、不联网、不启动进程；只有明确文件函数读写指定文件。每个构造返回独立普通 dict/list，保留输入，返回值与输入不共享可变子结构。

`UNSET` 表示参数缺席，不能存入 JSON。下面可选参数默认 UNSET；显式 None 仍为 null，但不允许 null 的结构字段会报错。来源级、数值、单位、身份、性质、模态、issues 和完成声明均由调用方决定，不猜默认值。

| 函数 | 必需参数与结果 |
|---|---|
| `read_json(path)` | 绝对路径，严格 JSON；重复键、BOM、非有限数拒绝，返回原 JSON 数据，不推断用途 |
| `read_text(path)` | 绝对路径，UTF-8 严格解码原字节；不归一化换行或 Unicode，返回 str |
| `write_json(path, value)` | 绝对路径，先完整序列化再排他写入，返回路径 str；不创建父目录、不覆盖、不包装提交 |
| `quote_from_span(snapshot, *, local_id, clause_record_id, start, end)` | 固定完整 snapshot 与条款内 Unicode 码点半开区间，返回 find_quote 请求项，含正确 occurrence |
| `ref(*, object_id=UNSET, record_id=UNSET, local_id=UNSET, value_path=UNSET)` | 三 ID 恰给一种；value_path 只能配固定版本/local_id，指 /value 或后代；目标类型仍正式检查 |
| `source(*, level, **fields)` | 显式级别与正式来源字段；校验字段/固定引用/格式参数结构，不代选级别或证明推断 |
| `evidence(*, path, source)` | 显式 JSON Pointer 与来源，返回 {path,source}；不补根路径、不扩大覆盖 |
| `record(*, local_id, kind, data, evidence, object_id=UNSET, previous_record_id=UNSET, status=UNSET, withdrawal_reason=UNSET)` | 完整单记录与既有外层检查；缺省 status 保持缺席；修订明确同时给对象和前驱 |
| `node(*, local_id, node_kind, fields, evidence)` | fields 是其余 data，不能重定义 node_kind；调用 record |
| `relation(*, local_id, relation_kind, fields, evidence)` | fields 显式给实际 unit/端点等，不能重定义 relation_kind；不补 modality 或性质 |
| `reference(*, local_id, reference_kind, from_ref, to_ref, fields, evidence)` | fields 仅其余 data，不得重定义 reference_kind/from/to |
| `detail(*, local_id, owner, slot_id, value, evidence)` | 完整 detail；value 可明确 None，不因漏参补 null |
| `clause_revision(*, local_id, clause, tags, classification, evidence)` | 完整 active clause 查询记录；复制完整 data，只替换 tags/classification，使用其 object_id/record_id 为对象/前驱；新 evidence 必填 |
| `header(*, format_version, case_id, vocabulary_hash, submitted_by, phase, covered_clauses, issues, overview=UNSET)` | 必填参数无默认，返回不含 records 的现有信封 |
| `assemble(*, header, record_groups)` | 一或多份记录 list，按给定顺序合并，与原 build_submission 共用纯检查；返回提交，不写文件、不分配正式 ID |

node/relation/reference/detail 为薄封装，完整内部内容、目标类型、值兼容、来源覆盖和语义由正式 write 独立校验。修正用通用 record 给完整 data/evidence 和明确前驱；gap、no_content 同样用 record。参与者、端点与六种值继续普通字典/列表，不增加专用对象系统。

quote_from_span 要求 `0 <= start < end <= len(clause.text)`，布尔不是整数；在 aaaa 中 [1,3) 返回 aa/occurrence=2。偏移是同一固定条款原文的码点，不是 JSON 物理行、UTF-8 字节或重新排版行号。窗口位置先换算回条款；不自动猜范围，不截句修错。返回引句请求后仍经 find_quote 生成锚，正式 write 重新核验。

clause_revision 不接受 unclassified；ordinary 对应非空 tags，no_content/unmatched 对应空 tags。它不沿用原 evidence、不生成 gap、不判断数据库当前版本、不改变 original_number 的缺席/null。query 的 evidence/provenance 等包装字段不进入 data 或新记录。

write_json 只接受普通 JSON 类型及字符串键；拒绝 NaN/Infinity、Decimal、日期对象、集合、tuple、自定义对象和循环数据，不隐式转成文本。业务十进制由调用方给字符串。缩进及末尾换行是文件排版，不改变字段中的 CR/LF/CRLF、原句和 Unicode。

## 经验证的固定样例与短调用

本 skill 的 examples/quote_requests.py、preparation.py、tagging.py、extraction.py 是可调用的 `build` 样例；fixture.json 使用虚构原文及 UUID，不是本合同数据。主会话交付本角色需要的实际绝对路径，明确调用参数；reader 不必加载无关样例。summarizer 对应 preparation，tagger 对应 tagging，extractor 对应 extraction。样例演示 I、II、III 级的不同处理，不能据样例一律指定来源级。

使用主会话交付的快照选定原句位置、形成请求，例如短调用片段：

```python
from legal.reader_helpers import read_json, quote_from_span, write_json
snapshot = read_json(clauses_path)  # 主会话交付的绝对路径
request = quote_from_span(snapshot, local_id="payment-quote",
                          clause_record_id=clause_record_id, start=start, end=end)
write_json(new_requests_path, [request])
```

随后用既有 find_quote.py 处理 requests，保留完整 stdout、stderr 和原进程退出码。业务 data 可用普通 Python 多行字符串，不手工 JSON 转义；用上表函数及 `assemble`/`write_json` 输出。也可运行交付的样例（例为 tagger，全部参数来自本次任务）：

```python
import runpy
from legal.reader_helpers import read_json, write_json
build = runpy.run_path(tagging_example_path)["build"]
document = build(snapshot=read_json(clauses_path), anchors=read_json(anchors_path),
                 unit_id=selected_unit_id, case_id=case_id,
                 vocabulary_hash=vocabulary_hash, submitted_by=submitted_by)
write_json(new_submission_path, document)
```

样例的固定虚构内容仅供格式演示；真实任务自行填本合同业务数据和判断，不能无条件复用样例的单元、来源、完整声明或法律结论。样例运行不要求主动阅读库实现，也不授权读取别的任务。

库失败抛 `legal.formats.Invalid` 或 `InvalidBatch`，含 code/path/message；Invalid 用 `.item()`，InvalidBatch 用 `.items` 获取诊断，不吞异常。参数/范围错误 INVALID_ARGUMENT，快照无版本 REFERENCE_NOT_FOUND，序列化 INVALID_JSON，路径/读写 FILE_ERROR，已存在 FILE_EXISTS；重复/引用/来源沿用既有码。按明确输入错误自行修正；资料缺失、安装故障、说明与程序矛盾交主会话。原两个脚本仍按上述 stdout 和退出码处理。新路径由主会话按原规则分配，不能为了重试覆盖成功产物。
