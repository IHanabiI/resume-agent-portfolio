请对比 CandidateProfile 和 JobAnalysis，输出 GapAnalysis JSON。

需要完成：
- matched_strengths：候选人已有且能匹配 JD 的优势。
- missing_information：JD 关注但简历中没有明确证据的信息。
- questions_to_user：需要向用户追问的问题，最多 5 个。

追问规则：
- 问题必须具体，不能问“还有什么补充”。
- 每个问题都要说明 why_needed 和 related_jd_requirement。
- 如果某项 JD 要求没有在简历中出现，只能追问，不能当作候选人能力。
- 用户可以回答“没有 / 不清楚 / 跳过”，因此问题不能诱导编造。

