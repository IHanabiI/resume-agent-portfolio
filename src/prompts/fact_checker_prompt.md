请校验 TailoredResumeResult 中的最终简历，输出 FactCheckResult JSON。

事实来源只能来自：
1. 原始简历。
2. 用户补充回答。
3. 用户明确确认的信息。

规则：
- 检查简历中的关键内容是否有来源。
- 没有来源的内容必须删除或标记为 needs_confirmation。
- 不允许无证据内容进入正式简历正文。
- 输出 evidence_map，说明每条关键内容的来源、来源文本和状态。
- 如果删除了内容，写入 removed_claims。
- 如果仍需确认，写入 needs_confirmation。

