请基于候选人原始简历、岗位 JD、匹配缺口和用户补充回答，生成 TailoredResumeResult JSON。

必须遵守：
- 最终简历不能编造事实。
- 不得把 JD 中的要求直接写成候选人能力。
- 用户只说“了解”，不能写成“熟练”或“精通”。
- 用户只说“参与”，不能写成“负责”或“主导”。
- 没有量化数据时，不能添加百分比、金额、人数、增长率、效率提升幅度。
- 可以优化表达，但不能改变事实。
- 用户回答“没有 / 不清楚 / 跳过”的内容不能进入正式简历正文。

输出要求：
- resume_markdown：完整定制简历正文，Markdown 格式。
- opener_markdown：给 HR/招聘方的第一条沟通开场白，Markdown 格式；只能引用简历、记忆库、GitHub 或用户回答中存在的事实。
- changelog_markdown：改动说明，Markdown 格式；逐条说明改了哪里、为什么改、依据哪个 JD 要求；如果有缺失数据，使用 `[请填写：xxx]`；如果是轻度推断，使用 `[需用户确认：xxx]`。
- optimization_notes：说明做了哪些优化。
- integrated_keywords：列出自然融入的 JD 关键词。
- still_missing_info：仍建议补充的信息。
- evidence_map：每条关键简历内容对应来源。
