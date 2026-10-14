# 主会话：固定启动与合同准备

先执行 SKILL.md 的 runtime 固定片段。成功后用回执中的 python 执行安装 scripts/prepare_task.py；全部参数用数组，输入通过 `--input` 的绝对 JSON 文件或 `-`/stdin 传递，保存完整 stdout、stderr 和退出码。失败退出 2，成功退出 0；失败的 remaining_paths 是本次清理未成功的实际残留，不可派发。

## 工作区配置

安装首次产生 `workspaces.json`：

```json
{"format_version":1,"workspaces":[{"workspace_root":"/absolute/session/workspace","contract_root":"/absolute/contracts","vocabulary_list":"/absolute/install/vocabularies/workspace-1.txt"}]}
```

根仅这两个字段，每项仅这三个字段。用户直接维护，主会话按明确要求编辑。工作区是会话打开目录，精确匹配且必须存在；列表必须在本安装 vocabularies 内。没有配置不向上搜索。升级保留配置和列表；runtime.json 字段不变。

列表严格 UTF-8，LF/CRLF，每行一个绝对词表文件路径，忽略空白行，首个非空行默认。不支持注释、引号、变量、~、相对路径、重复规范路径；除行结束符外路径空格不剥离。明确选择须在列表中，只加载选中词表内容；第一项失效不跳选第二项。新增登记追加末尾，只有明确要求才重排默认；空列表首项自然成为默认，应报告。取消登记不删除文件。

## 新合同

```json
{"format_version":1,"runtime_file":"/absolute/install/runtime.json","workspace_root":"/absolute/session/workspace","materials":[{"path":"/absolute/original.md"}]}
```

用 `case --input FILE`。可选 vocabulary（已登记绝对文件）、contract_root（本次工作根）；materials 项可带 converter_config。缺选中词表或非法输入时不建合同目录。成功 result 为 contract_dir、db_path、copied，每项 source/target/sha256；不执行 init/preprocess/register。固定程序创建 contract-UTC，冲突加 -02/-03，复制原件与冻结前词表副本、配置及明确非代码文件，安装代码保持绝对引用。主会话接着逐次调用正式 CLI 并保存回执。

续做已有合同不用 case，沿用旧目录、旧库及冻结词表。初始化或独立预处理仅用 runtime，不要求工作区登记词表。

## 阶段入口

- reading：db_path、output_dir、task_context_file、preparation_files={records,overview}；可选 text_version_ids、target_chars=20000、window_chars=6000。详见 reading-inputs。
- synthesis：db_path、manifest_file、output_dir、reader_reports；见 reading-inputs。两种归纳任务各有独立绑定及输出。
- tagging：db_path、output_dir、task_context_file、plans；每项 task_id/responsible_clauses/context_clauses/output_file，责任不交。
- extraction：同上，plans 另含 unit_id/group_file；可选 clause_ids，责任并集必须等于所选范围。详见 handoff。

以上输入均含整数 format_version=1，仅允许适用字段。全部文件/目录绝对路径；task_context_file 是主会话已写好的 tasks 下非空 UTF-8 总体说明，输出目录为 tasks 下新/空子目录，提交输出未占用。成功 files 列本次产物，result={manifest_file,tasks}；每个 task 给 task_id/role/purpose/task_file/instructions_file/binding_file/output_file。reader 无 binding。

主会话直接交付三部分 instructions 正文，补第三部分的业务关注并确认白名单，不让子任务重复打开管理任务或模板。后续正式概要正文直接作为共同背景，注明 overview_id/text_versions；保留每次派发采用版本，不静默更新旧派发。
