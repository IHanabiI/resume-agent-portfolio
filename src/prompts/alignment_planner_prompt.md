请基于原始简历、STAR 证据、岗位 JD 分析、匹配缺口和用户补充回答，生成 ResumeAlignmentPlan JSON。

你的职责不是写最终简历，而是制定“岗位对齐改写计划”。

必须遵守：
- 只使用原始简历、STAR 证据、用户回答、记忆库、GitHub 公开证据中存在的事实。
- 不得把 JD 要求直接当作候选人已经具备的能力。
- 空壳经历不能被补写，只能生成 placeholder 或建议用户补充。
- 没有数字时不能编造数字，只能插入 `[请填写：xxx]`。
- 轻度推断必须标记为 confirm_inference，并要求最终简历保留 `[需用户确认：xxx]`。
- 优先引用“原简历结构骨架”里的 section_id、section_title、line_id、原文，便于 writer 定位修改位置。

计划必须覆盖参考项目式三项下限：
1. section_reorder：同章节内，哪些项目/经历应前移或保持。
2. item_reorder：同一项目/经历内，哪些成果或行动应前移。
3. skill_reorder：技能板块哪些技能应前移、弱化、合并或改写。

字段要求：
- target_role：目标岗位。
- strategy_summary：一句话说明本岗位简历策略。
- strongest_evidence：列出最能支撑岗位的 3-6 条证据，必须来自原始简历、STAR、用户回答、记忆库或 GitHub。
- required_actions：对经历/项目正文的改写或重排计划。每条必须写清 target、source_evidence、jd_reason、instruction、allowed_change。
- skill_adjustments：技能板块调整计划。
- placeholders：需要插入 `[请填写：xxx]` 或 `[需用户确认：xxx]` 的位置。
- do_not_use_claims：明确不能写入简历的内容，例如 JD 有要求但用户没有证据。
- format_constraints：最终 writer 必须遵守的格式规则。

target 写法：
- 尽量写成 `Sxxx/章节标题/Lxxx` 或 `章节标题 - 原条目摘要`。
- 如果要调整一条列表项，target 必须包含对应 line_id 或原文摘要。
- 如果要调整一个章节内顺序，target 必须包含 section_id 或章节标题。

action_type 取值：
- section_reorder：经历/项目顺序调整。
- item_reorder：项目内部成果行顺序调整。
- rewrite：基于已有事实改写措辞。
- skill_reorder：技能顺序或技能措辞调整。
- placeholder：插入 `[请填写：xxx]`。
- confirm_inference：插入 `[需用户确认：xxx]`。
- keep：保留不动，并说明原因。

allowed_change 取值：
- reorder_only：只允许重排。
- rewrite_existing：只允许基于已有事实改写。
- insert_placeholder：只允许插入 `[请填写：xxx]`。
- confirm_inference：只允许插入 `[需用户确认：xxx]`。
- keep：保持原样。

如果证据不足，也必须输出计划，但应把缺口放入 placeholders / do_not_use_claims，而不是编造。
