请对比 CandidateProfile 和 JobAnalysis，输出 GapAnalysis JSON。

需要完成：
- matched_strengths：候选人已有且能匹配 JD 的优势。
- missing_information：JD 关注但简历中没有明确证据的信息，需要分层表达，避免重复。
- hard_skill_gaps：工具、技能、方法、产物类硬要求缺口，例如 Excel、Unity、配置表、玩法文档、竞品分析。
- soft_evidence_gaps：软性能力证据缺口，例如沟通协作、逻辑拆解、用户体验、主动推动。每项写清 requirement、evidence_needed、current_status、suggested_question。
- questions_to_user：需要向用户追问的问题，最多 5 个。

分类规则：
- 硬技能/方法可以做关键词证据匹配。
- 沟通、协作、逻辑思维、表达能力、关注细节、主动推动、用户体验意识这类要求不能当成硬关键词；必须寻找具体事例，例如对接对象、交付文档、反馈迭代、规则拆解、上线结果。
- 不要输出多条“未找到沟通 / 未找到协作”之类的重复项，应合并为“软性证据缺口：缺少可验证场景”。

追问规则：
- 问题必须具体，不能问“还有什么补充”。
- 每个问题都要说明 why_needed 和 related_jd_requirement。
- 如果某项 JD 要求没有在简历中出现，只能追问，不能当作候选人能力。
- 用户可以回答“没有 / 不清楚 / 跳过”，因此问题不能诱导编造。
