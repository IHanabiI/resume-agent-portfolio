请分析目标岗位 JD，并输出 JobAnalysis JSON。

需要提取：
- job_title：岗位名称。
- core_responsibilities：核心职责。
- required_skills：必备技能。
- preferred_skills：加分技能。
- keywords：适合融入简历的关键词。
- recruiter_focus：招聘方最可能关注的能力、经历或成果。

规则：
- 只基于 JD 文本分析。
- 不要把 JD 要求当成候选人已经具备的能力。
- 技能和关键词要具体，不要泛泛输出“能力强”“经验丰富”。

