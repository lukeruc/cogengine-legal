# 数据格式与完整提交

从完整目录使用本文件。以下为版本 1 的严格 JSON 格式；正式 ID 为 UUID。出处与关系的中文语义由阅读原文的人判断。已存在案件的 case_id 和 vocabulary_hash 先用案件 query 取得。

当事人性质代码：obligor、recipient、power_holder、power_subject、permission_holder、permission_counterparty、protected_party、restricted_party。模态代码：obligation、power、permission、immunity；可为 null。

## 2. 通用类型与规范化

### 2.1 输入规则

| 类型 | 精确规则 |
|---|---|
| 字符串 | Unicode 字符串；不得含无法编码为 UTF-8 的孤立代理码点。原文允许空白、换行、组合字符，禁止隐式规范化 |
| 非空字符串 | 必须至少含一个非空白字符；检查不改写保存内容 |
| 整数 | JSON 整数，布尔值不能充当整数；各字段另规定上下界 |
| 十进制字符串 | 见下方正则的整串匹配；不接受指数、加号、分组符 |
| UUID | 小写、带连字符的规范 UUID 字符串；工具新生成 UUID v4；不从名称推导 |
| SHA-256 | 恰好 64 个小写十六进制字符 |
| 时间戳 | UTC，`YYYY-MM-DDTHH:MM:SS.ffffffZ`；仅供管理记录 |
| 路径 | 输入文件路径由调用方提供；相对路径按调用时工作目录解释；清单内路径按清单文件所在目录解释 |
| JSON Pointer | 空串表示整个 `data`；其他以 `/` 开头，按 `~0/~1` 解码。拒绝非法转义、数组的 `-`、非规范下标以及不存在的路径 |

十进制的正则为：

```text
-?(0|[1-9][0-9]*)(\.[0-9]+)?
```

所有契约对象只接受列出的字段。可选字段缺席才使用默认值；`null` 只有明确允许时合法。数组保留顺序；声明为集合的数组拒绝重复，默认不擅自去重。所有 `format_version` 必须是整数 `1`。JSON 文件不接受注释、尾逗号、重复键、非有限数字、UTF-8 BOM 或尾随第二个值。JSON 数字仅用于已规定的整数位置；合同数值始终是字符串。

管理文本，例如 `issues`、异常说明、人工意见，不作为法律断言，不自动生成模型字段。

### 2.2 哈希

定义规范序列化为：对象键按 Unicode 码点排序，保留非 ASCII 字符，不输出多余空白，数组保序，输出 UTF-8；等价于标准库 `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)` 的字节输出。不得先做 Unicode NFC、换行转换或浮点转换。

- **write 提交**：对通过静态格式检查的完整输入对象序列化后 SHA-256；包含 `phase/issues/overview` 等实际提供字段；在补默认值、分配 ID、解析 local 引用之前计算。缺席字段与显式默认值是不同提交内容。
- **词表**：先补齐条目的空列表默认值；unit/slot 按 ID 排序，assignment 按 `(unit_id,slot_id)` 排序；条目内部的 examples、aliases、replaces 保持原顺序，再规范序列化。目录与单文件等价内容得到相同逻辑哈希。
- **单位配置**：单位按 code 排序后规范序列化；包含配置版本、别名等全部内容。
- **原件**：直接对输入字节计算；**全文**：对解码后未修改文本的 UTF-8 字节计算。读文本时保留 CR、LF、CRLF，不使用会统一换行的读取方式。
- **register**：对 `{operation:"register",original_hash,text_hash,metadata}` 的规范序列化计算；metadata 排除原件、文本、元数据文件路径提示。原始路径只在首次成功记录保存，重提不改写它。
- **split**：对 `{operation:"split",text_version_id,algorithm_version}` 计算；当前 algorithm_version 为 `contract_v3.article.4`。旧提交保留旧版本标识。

同一案件的哈希唯一性包括命令种类，防止跨命令误命中。成功回执查找在依赖当前版本的验证之前；并发执行须在取得写事务后再查一次。哈希命中后回执中的生成 ID、顺序、时间及计数均复用，只将 `replayed` 置为 true。

## 3. 写入信封、字段与引用

### 3.1 信封

| 字段 | 必需 | 类型、默认值及约束 |
|---|---|---|
| `format_version` | 是 | 1 |
| `case_id` | 是 | UUID，与目标案件一致 |
| `vocabulary_hash` | 是 | SHA-256，与冻结快照一致 |
| `submitted_by` | 是 | 非空字符串 |
| `phase` | 是 | preparation/tagging/extraction/correction |
| `covered_clauses` | 是 | `{object_id,record_id}` 数组；二者确属同一条款；object_id 不重复 |
| `records` | 是 | §3.2 记录数组；可以为空，但不能用空提交声明提取完成 |
| `issues` | 是 | 非空字符串的数组，可以为空 |
| `overview` | 否 | 仅 preparation：`{text_versions:[业务引用],body:非空字符串,authored_by:非空字符串}`；版本列表非空、不重复 |

非 extraction 的 covered_clauses 必须为空。extraction 必须至少声明一个负责条款；correction 可修正相同业务对象，但不会凭此新增提取完成记录。preparation 可仅更新概要，不伪造事件。CLI 不验证提交者字符串是否真是指定 agent；事件的认定权属于 skill 的职责约束，验收须检查任务交接。

初读分段任务及 Markdown 笔记是 tasks 中的工作文件，不是本交换格式的写入记录，不逐份 write；主读范围不声明 extraction 完成。一个归纳读手（单段由原读手兼任）形成一份 preparation，主体/事件同一性按原文统一判断，笔记与概要不能充当正式断言来源前提。执行与导出规则见 [preparation.md](../skills/legal-case/references/preparation.md) 和 [reading-inputs.md](../skills/legal-case/references/reading-inputs.md)。

### 3.2 单记录

必填 `local_id,kind,data,evidence`。local_id 是非空字符串，批内唯一，不解析其命名含义。可选 `object_id,previous_record_id` 必须同时出现；同时缺席为新对象，同时出现为修订。status 默认 active；只接受 active/withdrawn。仅 withdrawn 必须有非空 withdrawal_reason；active 不接受该字段。

新增对象不得 withdrawn。撤销时 data 和 evidence 须与所撤销前驱的已解析内容相等（对象键顺序不影响相等），不得夹带内容修改；撤销理由单独保存。新对象和修订均返回 local_id 映射。同一 object_id 在一个文件中最多出现一次。

write 接受 clause、anchor、node、relation、detail、reference、gap、no_content；material/text_version 只能由 register 建立。空合同容器只能由 init 建立；write 可修订该唯一容器并补有依据的名称，不能另外创建合同容器。

material/text_version/gap 不允许修订、撤销或恢复。其余记录以 `object_id` 与最新 `previous_record_id` 追加完整版本；节点的 node_kind 和关系的 relation_kind 不允许原 ID 改类，改类需撤销旧对象、新建对象。唯一合同容器是案件身份，不能撤销；可以修订其有依据的名称。

### 3.3 三类引用

本节所称“业务引用”和“固定引用”是既有对象引用/版本引用的简写，不增加模型对象。

| 引用位置 | 输入 | 入库后 |
|---|---|---|
| 业务引用 | 恰有 `object_id` 或 `local_id` | `{object_id}`；按当前有效版本解析 |
| 固定引用 | 恰有 `record_id` 或 `local_id` | `{record_id}`；锁定原版本 |
| 值内部分引用 | `{record_id,value_path}`，或在允许固定引用处 `{local_id,value_path}` | `{record_id,value_path}`；路径必须指向目标 data 中 `/value` 本身或其后代 |

固定 local_id 指向本批生成的记录版本，包括修订版本。value_path 只能用于 detail 或 node:defined_value；指向中间 object/list 容器合法，指向名称、出处等非 value 字段非法。`/value2` 不是 `/value` 后代。对象引用不能带 value_path。

固定到历史记录的**业务**引用仍须检查目标对象当前未撤销；固定**证据**引用可以指向后来被撤销的对象。不能通过把业务目标改写成 record_id 绕过撤销依赖校验。锚的条款引用、来源锚、推断前提、历史缺口的位置引用属于证据引用；引用索引依路径和类型判别，不只看是 object_id 还是 record_id。

引用目标不可解析报 REFERENCE_NOT_FOUND，类别不符报 REFERENCE_TYPE_MISMATCH，业务目标撤销报 WITHDRAWN_TARGET。同批引用先分配全部 ID，再校验候选最终视图，无需输入排序。

### 3.4 data 精确字段表

下表 `*` 表示必填。其余字段缺席才取说明中的默认值。`node_kind/relation_kind/reference_kind` 是结构判别字段，不能省略。

| kind | 字段与约束 |
|---|---|
| clause | `text_version*` 业务引用；`sequence*` 正整数；`text*` 原样字符串；`start_offset*,end_offset*` 非负整数；`tags*` UUID 集合；`classification*` unclassified/ordinary/no_content/unmatched；`original_number` 字符串或 null，默认 null |
| anchor | `clause*` 固定条款引用；`quote*` 非空原样字符串（全空白引文也允许，只要非零长度）；`occurrence` 正整数，唯一匹配时默认 1 |
| node:subject | `node_kind*` subject；`canonical_name*` 非空字符串；`identifiers` 默认 []，每项恰为 `{scheme:非空字符串,value:非空字符串}` |
| node:event | `node_kind*` event；`name*,description*` 非空字符串；`participants*` 数组，项恰为 `{subject:主体业务引用,role:非空字符串}`；`object` 为 text/reference 值；`batch_or_stage` 非空字符串。原文未给参与者可用 []，不能补造 |
| node:defined_value | `node_kind*` defined_value；`name*` 非空字符串；`value*` §5 值；`scope` 非空业务目标引用数组，缺席表示合同范围 |
| node:external_benchmark | `node_kind*` external_benchmark；`name*,description*` 非空字符串；不接受 value 字段 |
| node:contract | `node_kind*` contract；`name` 非空字符串；init 仅含 node_kind |
| relation:party | `relation_kind*` party；`unit_id*` 快照 UUID；`parties*` 恰两个 `{subject,nature,functional_labels?}`；subject 指主体，nature 取本文开头的八种当事人性质代码；functional_labels 为非空字符串数组，默认 []；`modality` 四值或 null，默认 null |
| relation:contract | `relation_kind*` contract；`unit_id*`；`subject*` 唯一合同容器业务引用；`modality` 同上；禁止 parties |
| detail | `owner*` 关系业务引用；`slot_id*` 快照 UUID；`value*` 符合槽结构或显式 null |
| reference | `reference_kind*,from*,to*` 及 §3.5 对应字段；不得混用其他引用类型的专属字段 |
| gap | `clause*` 固定条款引用；`gap_kind*` unmatched_unit/missing_slot/structure_anomaly；`description*,reported_by*` 非空字符串；`suggested_unit_id` 快照 UUID；`related_object` 固定引用 |
| no_content | `clause*` 业务条款引用；`reason*` 非空字符串 |

条款必须满足 `0 <= start_offset <= end_offset <= len(text_version.text)`、text 等于原文切片、tags 属于冻结词表。ordinary 的 tags 非空；其余 classification 的 tags 为空。初次 split 为 unclassified；打标不得改动原文、地址和编号。一般 correction 可修正切分边界，之后以字符覆盖对账检验整组。

parties 必须引用两个不同主体对象；不强制八性质配对，也不依模态补性质。redirect 后两端归入同一节点的情形作为身份冲突展示，工具不得自动删除原关系。

一个关系允许同槽多条 detail；查询全部返回，不取最后一条、不自动覆盖。不通过添加数据库唯一约束禁止合同中并存的规定。

### 3.5 解释性引用的完整类型约束

“规定”在本表严格指 relation 或 detail，不是新记录类别。所有业务引用可取当前对象；只有表内明示的位置可固定版本。

| reference_kind | from | to | 其他字段 |
|---|---|---|---|
| appellation | 固定 clause | 业务 node:subject | 必填 label 非空；scope 可为 material 或 node:contract 的业务引用，默认本合同 |
| role | 业务 node:contract | 业务 node:subject | label 必填非空 |
| composition | 业务 node:contract | 业务 material | label 必填非空 |
| definition | 业务 relation/detail，或固定 clause | 业务 node:defined_value | term 必填非空 |
| event_of | 业务 node:event | 业务 relation | 无 |
| scope | 业务 relation/detail | relation/detail/clause/node 的引用数组，允许固定版本及 value_path | exclude 同类数组，默认 []；to 和 exclude 至少一个非空，各自不重复、交集为空 |
| priority | relation/detail/clause 的业务引用或固定引用 | 同左 | 无 |
| amendment | relation/detail/clause 的业务引用或固定引用 | 同左 | 无 |
| redirect | 业务 node | 相同 node_kind 的业务 node | 两端原始 ID 不同；不得成环 |
| distinct | 业务 node | 业务 node | 两端 ID 不同；允许不同 node_kind；不产生重定向 |

业务 scope 固定到旧版本时，返回该版本内容，不解释成当前值。不同版本即不同目标；工具不把同一对象的不同历史值自动合并。

## 4. 出处覆盖及推断

### 4.1 来源结构

| level | 必填字段 | 禁止混入 |
|---|---|---|
| 1 | `level,anchors`；anchors 非空固定 anchor 引用数组 | II 级格式参数、III 级推断字段 |
| 2 | `level,anchors,surface,format_contract,format_parameters`；surface 非空；其余见 §6 | premises/explanation/asserted_by |
| 3 | `level,premises,explanation,asserted_by`；premises 非空固定记录引用数组，说明、署名非空 | 用 anchors 取代 premises、格式参数 |

每条 evidence 恰有 path 与 source；同一记录的 path 不重复，必须能在 data 定位。父路径的来源覆盖其后代；后代单独给出来源时，以最长匹配路径解释该字段，父路径不掩盖后代来源级。`/a` 不覆盖 `/ab`。

必需覆盖的断言字段：

- node：除 node_kind 及空列表外的所有已填写内容。contract 空容器无断言；其 name 后补即要来源。
- relation：unit_id、每个 subject/nature、每个功能标签、非空 modality；contract 型的 subject 同样要来源。
- detail：owner、slot_id、value，包括 value:null。
- reference：from/to 及 label/term/scope/exclude 的实际内容。
- gap：clause、gap_kind、description 及可选业务指向；reported_by 为管理署名。
- no_content：clause 与 reason。
- clause：tags 非空时覆盖标签判断；已分类时覆盖 classification。text/address/number 是原文定位字段，不需自己为自己作证。split 创建的 unclassified 无来源。

record_id、kind、local_id、status、withdrawal_reason 等管理字段不要求法律出处。anchor 的 evidence 必须 []；锚可指旧条款版本来说明新标签。一个根路径来源可以覆盖同源内容；关系三部分无需为相同引文机械重复填写，但每一部分必须可计算出有效覆盖。

### 4.2 原文与前提

锚出现序号按重叠匹配计算，例如 `aaaa` 中 `aa` 有 0、1、2 三个起点。唯一匹配给 occurrence=2 也报错；不连续引文即使含省略号也按连续字符串验证，不作特殊容错。

每个来源 III 的每个前提必须是带断言来源的记录或 anchor；禁止以 overview、material、text_version、无依据的空合同容器充当前提。遍历其实际来源，所有叶分支都须落到可验证锚；递归栈发现环即报 SOURCE_CYCLE，即便同一环另有一条出路也不能把循环论证当依据。共享非循环子图可以复用，不算环。

来源 I/II 的 anchors 固定版本。语义依据与引文出现位置可以不同：appellation 的 from 固定出现处；其 anchors 还可包含别处定义。机械称谓检查要求 label 是 from 条款的子串，且至少一个来源锚或可追溯前提锚落在该出现条款；不要求每一身份定义锚都含该 label。歧义同名对象并存展示，不据字符串强制合并。

出处查询对每一固定前提返回 `current_record_id` 与 `changed/withdrawn`，不替换该前提内容。原文根链为 anchor → clause → text_version → material；每步的 ID、条款顺序及引文位置均能取得。

## 5. 值语法与单位

### 5.1 基础与容器

所有值恰由 form 或 type 判别；不能同时出现。完整字段如下：

| 形态 | 必填 | 可选及限制 |
|---|---|---|
| quantity | `form:"quantity",amount,unit` | 非空 amount 为十进制字符串；有原文留空依据时可 null，仍保留已知 unit；unit 必须存在于冻结配置 |
| time/date | `form:"time",kind:"date",value,precision` | boundary_text 非空；precision year/month/day；非空值为 YYYY/YYYY-MM/YYYY-MM-DD，年份 0001—9999，日历合法；原文日期栏明确留空时 value 可 null |
| time/relative | `form:"time",kind:"relative",event,offset,relation` | event 业务事件引用；offset 量且为时间单位；relation before/after/within_before/within_after/at；boundary_text 可选 |
| time/duration | `form:"time",kind:"duration",length` | length 非负时间量；boundary_text 可选 |
| time/interval | `form:"time",kind:"interval",start,end` | start/end 可各自为 date、relative 或指事件的 reference 值；boundary_text 可选；不接受 duration 或嵌套 interval |
| condition/event | `form:"condition",operator:"event",event` | 业务事件引用 |
| condition/all、any | `form:"condition",operator,operands` | 至少一个 condition 值；保序 |
| condition/not | `form:"condition",operator:"not",operand` | 恰一个 condition 值 |
| condition/compare | `form:"condition",operator:"compare",left,comparison,right` | comparison eq/ne/lt/le/gt/ge；两边为 quantity、time 或指向这两类值的 reference |
| condition/count | `form:"condition",operator:"count",condition,comparison,number,mode` | condition 为条件值；number 非负整数，原文次数栏留空时可 null；mode continuous/total；period 可为 duration/interval |
| formula | `form:"formula",operator,operands` | add/subtract/multiply/divide/min/max；减除恰两项，其余至少两项；叶 quantity/reference，可递归 formula |
| text | `form:"text",surface` | surface 非空原样字符串；normalized 非空字符串可选 |
| reference | `form:"reference",target` | 默认业务引用；可固定 detail/defined_value 及 value_path；目标类别受使用位置或槽声明限制 |
| object | `type:"object",fields` | fields 为字段名→值的对象，与 value_schema 对应 |
| list | `type:"list",items` | items 为值数组，允许 []；每项使用同一项声明 |

相对时间除 at 外非空 offset 必须非负，以 relation 表方向；at 允许有符号量。interval 只接收已经表明起止的端点；原文确有端点栏但留空可按下文 null 规则记载，原文未提供端点不能补造一个 null。工具不计算现实到期日。

按本轮用户裁决，**所有有原文依据的留空值位置均允许 null**，包括 detail.value、defined_value.value、容器成员及列表项。它是原文留空的值，不是第七种 form。先识别 null，再跳过该位置的 form/one_of 匹配，但仍要求来源覆盖且至少有一个可追溯锚定位字段说明及空白；III 级不能凭无空白原文的推断创造 null。required_fields 要求键存在，带有依据的 null 满足存在性；可选键缺席仍与显式 null 区分。

null 不用于关系端点、引用 ID、槽 ID、算子等结构标识。明确可空的标量位置为 quantity.amount、time/date.value、condition/count.number；quantity 的单位已知但金额留空时保留 `{form:"quantity",amount:null,unit:"CNY"}`，不丢掉币种。整体值、容器成员、算式操作数、时间量/端点等值位置也可按上述规则为 null，计算保持未定，不按零处理。text.surface 是原文转录，不用 null 代替原始文本；文本型字段本身留空时该整个 text 值取 null。条件、时间中需要实际事件 ID 的结构仍须给出该 ID；不能为漏识别事件填 null。引用一个值留空的定义值仍是合法引用，查询同时显示目标 value=null。机械检查验证 null 位置有可追溯出处；原文是否确实留空属于提取判断，不另加一个自动判空的语义检查器。

formula 引用仅指 detail 值、defined_value 或 external_benchmark，不允许主体/事件/条款作数值叶。比较引用不能指 external_benchmark 的现实数值。类型检查沿引用读取结构，遇到值依赖环报 VALUE_CYCLE；该规则不禁止 event_of 等语义图中的非求值环。

单位可判定时，加减/min/max 的量纲必须一致；乘除保留表达式，不创建新单位。比例与无量纲量允许参与金额乘除。不能从单位信息判定的外部基准公式只检查叶类型并返回未求值结构；不联网补数值。除数为明确零量时报 INVALID_VALUE；不对现实未知分母作断言。

### 5.2 槽结构语法

value_schema 每层恰一种：

- `{form}`：form 属于六形态；quantity 可带非空且不重复的 allowed_units；text 可带非空且不重复的 enum；reference 可带非空且不重复的 target_kinds。禁止把约束加到其他形态。
- `{type:"object",fields,required_fields}`：fields 为非空字段名到子结构的映射；required_fields 默认为 []，是 fields 键的无重复子集。未声明字段拒绝。
- `{type:"list",items}`：items 为一份子结构。
- `{one_of:[结构...]}`：至少两个分支；先分别匹配，恰一分支通过才通过，零或多个均报 INVALID_VALUE。

text 的 enum 比较 normalized（已填时）否则比较 surface；枚举匹配不改变来源级。reference 的 target_kinds 使用 `material`、`text_version`、`clause`、`anchor`、`node:subject`、`node:event`、`node:defined_value`、`node:external_benchmark`、`node:contract`、`relation`、`detail`、`reference`。解析固定版本时以该版本类型和值为准，同时检查业务目标未撤销。quantity 的 allowed_units 精确比较代码，不用别名自动替换。

### 5.3 单位配置契约

结构为 `{format_version:1,version:非空字符串,units:[...]}`；每项字段恰为 `code,name,dimension,scale,reference_unit,aliases`。code/name/dimension/reference_unit 非空；scale 正十进制字符串；aliases 为无重复非空字符串列表。code 全配置唯一；reference_unit 必须存在且同 dimension；基准单位指向自身且 scale=1，其余直接指基准，不使用多级换算链。

首版配置版本 `units.v1` 的确定内容如下；未列出的单位不被 v1 量值接受，仍可按原文文本表示，不伪造换算。配置扩展独立升版本，旧案不变。每行除明确指定外，scale=`"1"`、reference_unit=code、aliases=[]：

| code | name | dimension | 特殊参数 |
|---|---|---|---|
| CNY | 人民币元 | currency:CNY | aliases=[元,人民币元] |
| USD | 美元 | currency:USD | aliases=[美元] |
| EUR | 欧元 | currency:EUR | aliases=[欧元] |
| GBP | 英镑 | currency:GBP | aliases=[英镑] |
| JPY | 日元 | currency:JPY | aliases=[日元] |
| HKD | 港元 | currency:HKD | aliases=[港元,港币] |
| day | 日（未区分计日规则） | time:day | aliases=[日,天] |
| calendar_day | 自然日 | time:calendar_day | aliases=[自然日] |
| business_day | 工作日 | time:business_day | aliases=[工作日] |
| month | 月 | time:month | aliases=[月] |
| year | 年 | time:year | aliases=[年] |
| hour | 小时 | time:hour | aliases=[小时] |
| minute | 分钟 | time:minute | aliases=[分钟] |
| second | 秒 | time:second | aliases=[秒] |
| ratio | 比例 | ratio | 无 |
| percent | 百分比 | ratio | scale="0.01"，reference_unit=ratio，aliases=[%,％] |
| count | 次数 | count | aliases=[次] |

各时间单位不自动互换，包括 month/year，不混入未约定的计期规则。此表是工具能力范围，不声称覆盖全部国际计量标准；币种代码只是固定配置，不查询汇率。

时间类型接受 dimension 为 `time:` 前缀的单位，货币采用 `currency:`，比例为 ratio，计数为 count。未知代码报 UNKNOWN_UNIT；未配置单位可以用原文文本保留并报告表达问题，不能临时扩配置。正式配置扩展须有工具版本和测试，不通过案内词表治理偷改。

## 6. 格式契约算法

### 6.1 decimal.v1

参数恰为 `decimal_places,group_separator,decimal_separator,sign_style,scale,unit_surface,unit_position,prefix,suffix,number_unit_separator`，全部必填。decimal_places 非负整数；scale 正十进制字符串；group_separator 为 `""`、`,`、` ` 或 `，`；decimal_separator 为 `.` 或 `,` 且不得等于非空 group_separator；sign_style minus/plus/none；unit_position before/after；其他字段字符串。

surface 按 prefix + 数字/单位排列 + suffix 分解。前后字面量与分隔必须逐字匹配；数字只有一段，整数部分至少一位，每组三位（首组一至三位），小数部分恰 decimal_places 位，小数位为 0 时不允许小数分隔符。minus 允许负数前 `-`、非负数无符号；plus 对非负数要求 `+`、负数要求 `-`；none 禁止符号且值非负。禁止指数和括号负数。

独立解析所得十进制数乘 scale，必须与被来源覆盖的 quantity.amount 数值相等，且单位代码由该 quantity 提供；参数 unit_surface 只描述原文单位写法。再用 amount/scale 还原，要求恰能用规定小数位表达，不能四舍五入；按符号、分组、单位位置、前后字面量生成 surface，必须逐字符相等。prefix/suffix/unit_surface/number_unit_separator 不得含 ASCII 数字；年月日等汉字单位可以保留。用整数系数及十进制位数作精确运算，或配置足以精确容纳本次输入的 Decimal 上下文；禁止默认28位精度导致悄悄舍入。测试须含超过28位的金额。

II 级 evidence.path 必须直接指向整个非空 quantity 值且 amount 非 null；不能只指 amount 或一个含多个量的复合根。surface 必须是至少一个引用锚 quote 的连续子串。decimal.v1 只证明显式格式与倍率一致，单位或倍率与合同原文的语义是否相符仍需可追溯和语义验收，不宣称机械推断了“万元”的含义。

### 6.2 date.v1

参数恰为 `precision,component_widths,separators,prefix,suffix`。precision 与目标 date 一致；year/month/day 对应 1/2/3 个组件、0/1/2 个 separators；年份宽度 4，月日宽度为 1 或 2。组件只接受 ASCII 数字，按宽度输出（宽度 1 表示不补零，而非只能一位）；分隔与前后字面量逐字相等。

按表层解析日历组件，验证合法性，再形成规范日期；与目标值一致后反向输出，恰等 surface 才通过。suffix 可承载 `日`、`月`、`年`，不能把日期数字放在字面量里。evidence.path 直接指整个 time/date 值且其 value 非 null，surface 要出现在锚 quote 中。不接受相对日期、农历推算或含糊补月补日。显式留空按普通有锚来源表达，不伪造机械变换。

### 6.3 确定样例

| 契约与参数要点 | surface | 目标 | 预期 |
|---|---|---|---|
| decimal，2 位，`,` 分组，`.` 小数，minus，scale=1，单位 USD 在后，中间空格 | `1,234.50 USD` | 1234.50 USD | 通过；改目标 1234.51 必失败 |
| decimal，0 位，无分组，scale=10000，单位 万元 在后 | `12万元` | 120000 CNY | 通过；改 scale=1000 必失败 |
| decimal，2 位且其他同首例 | `12,34.50 USD` | 1234.50 USD | 分组错误，失败 |
| date，day，[4,1,1]，分隔 年/月，后缀 日 | `2026年9月5日` | 2026-09-05/day | 通过；不得丢失原表层 |
| date，day，[4,2,2]，分隔 `-`/`-` | `2026-02-29` | 同名 date | 非法日期，失败 |
