# 初读固定辅助：主会话

运行 `<专用 Python> <install>/scripts/prepare_task.py reading --input FILE`，严格 JSON 输入含 format_version=1、db_path、output_dir、task_context_file、preparation_files={records,overview}，可选 text_version_ids、target_chars=20000、window_chars=6000。全部路径绝对且在该合同目录对应子目录；新输出不覆盖。task_context_file 由主会话根据用户目标及材料范围先写，不预设交易架构。

沿用完整条款连续分段，超长条款由一个 reader 分窗全读；原文逐字导出，管理标题不混入正文。manifest 和 reader task 内部版本为 2；reader 的 input_files 仅含目录、原文窗口/精确上下文，不含词表、共享状态或完整格式；三部分 instructions 正文直接交付，角色不重复打开 task/manifest。

收齐笔记及真实范围后运行 `synthesis --input FILE`：format_version=1、db_path、manifest_file、output_dir、reader_reports 数组。每项 task_id、notes_file、read_ranges、unread_ranges、issues；范围项 {text_version_id,start_offset,end_offset} 为全文 Unicode 半开区间，notes 必须是对应 reader 分配输出。缺段、空笔记、未读、版本改变或范围声明不完整定位字段报错。检查声明不证明实际阅读。

输出两个 format_version=2、role=summarizer 的独立任务，固定 task_id 为 summarizer-records/summarizer-overview，purpose=records/overview，各自 instructions、binding 和 preparation 输出。单段 records 的 continue_reader_task_id 指原 reader，overview 为 null。二者使用相同笔记和固定原文，不互相依赖；records 拿完整正式身份及按需来源/构造规则，overview 不拿业务格式/词表/锚工具。

主会话调用两次正式 write；某份失败只续该份。已成功的结果及 ID 复用；回执丢失幂等重放原提交。概要修改追加 preparation，业务记录完整版本追加。两份均成功且实际读全后才能进入打标；不是根据文件名或旧概要猜完成。

`legal.initial_reading.check_reading_versions` 检查固定原文、素材/文本/条款版本；无关提交改变序号不使有效笔记失效。v1 manifest 不作为 v2 读取；旧成果恢复时重新导出 v2，复用明确验证有效的笔记及回执，不覆盖旧库或旧文件。
