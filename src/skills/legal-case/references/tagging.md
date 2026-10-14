# tagger

输入：不重叠的完整 article 批次及含独立规定的非 article 例外区间、当前条款版本、概要、冻结 unit 清单、输出文件路径。逐条款阅读标题、正文、子标题、条件、例外和表格后判断适用 unit；多标签保留所有对应 unit。章标题与共用引言可作上下文，不能只按章标题给内部 article 打标。输出 `phase=tagging` 的完整条款修订版本，保留原文、位置、编号和 text_version，写 `tags` 与 `classification`；无匹配条款补带锚的 `unmatched_unit` 缺口。无规定内容按其类别标记，后续完整提取仍需产出无内容记录。

本次 `covered_clauses=[]`。打标不是完整关系提取，不因已有事件或标签就跳过条款。tagger 只写分配文件；主会话 `write` 并取得新条款版本供分组和提取使用。

非空 tags 的必需来源路径是 `/tags`，classification 的是 `/classification`；也可用支持两者的根路径来源。仅给 `/tags/0`、`/tags/1` 不覆盖父数组 `/tags` 的判断。具体子路径可另列，仍按最长匹配生效。clause_revision/assemble 只做各自基础检查，正式 write 独立检查这些断言路径。

依据冻结单元的description判断规定的行为或机制，不只按标题关键词匹配。时长须看是哪项履行的期间，价款须看是否支付、责任或担保；选择已有合适单元，不将本应属责任救济的违约金硬归合同终止。无匹配时描述原规定和已核对单元的实际限制，不能把原文空栏叫作词表缺口。

主会话按 [handoff.md §1](handoff.md#1-tagging准备打标任务) 调用 `prepare_task.py tagging`，程序从 templates/tagger.md 生成三部分正文。主会话按回执交付 instructions，附本任务完整 active clause 快照、单元定义及适用构造资料的实际路径，无需重新寻找或展开模板。tagger 可用 clause_revision 保留全部固定 data、原 object_id 与前驱，新的 evidence 明确给出；不读取其他 tagger 产物或包内实现。缺材料/版本/安装问题交主会话，正常输入错误按 code/path 自行修正。

当前 tagging 导出的 `units.json` 直接是完整单元数组，逐项读取 id、description 等字段；无需按词表查询快照的 `items[0]` 结构访问。若任务明确另交完整 vocabulary 查询快照，其 units/slots/assignments/hash 才位于 items[0]，无额外包装。缺必需字段/类型错误报告路径及影响，合法空数组才可称为空。按白名单范围、用途和时机读资料，链接/相邻目录不自动授权，模板固定正文已展开不用重读。条款 item.data 是业务数据，完整 evidence/provenance 留在外层。构造时查 helper-tools 的对应函数/样例；只组织本任务数据，不重复实现匹配、修订或通用校验。完整诊断和原退出码保留，失败交原角色修正，额外材料交主会话补授权。

当前用 prepare_task tagging 输出独立责任条款、完整 units 定义、正式概要直接背景及固定 binding。通过 complete_task 构造 tagging 信封，角色只填修订/锚/真实缺口和显式 issues；修订全文由 clause_revision 保留，不自行手拼固定参数。
