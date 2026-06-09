from __future__ import annotations


SOFT_REQUIREMENT_GROUPS: list[dict[str, object]] = [
    {
        "name": "沟通协作",
        "triggers": ["沟通", "协作", "团队", "跨部门", "跨团队", "对接", "配合", "推动"],
        "evidence_terms": ["沟通", "协作", "对接", "跨部门", "跨团队", "程序", "美术", "测试", "评审", "联调", "验收", "同步"],
        "evidence_needed": "与程序、美术、测试、运营、用户或其他成员对齐需求、规则、文档、反馈并推动落地的具体场景。",
        "question": "JD 强调沟通协作。你是否有和程序、美术、测试、运营或用户反馈方对接的经历？请说明具体事项、你交付了什么文档/规则/配置，以及最后如何落地或迭代；如果没有，请回答“没有”。",
    },
    {
        "name": "逻辑拆解与文档表达",
        "triggers": ["逻辑", "系统拆解", "拆解能力", "文档表达", "表达能力", "转化为可执行方案", "方案"],
        "evidence_terms": ["规则", "流程", "状态", "拆解", "结构", "系统", "逻辑", "文档", "PRD", "配置表", "方案"],
        "evidence_needed": "把玩法、系统、流程、规则、状态或需求拆成可执行方案、策划文档、配置表的经历。",
        "question": "JD 强调逻辑拆解和文档表达。你是否写过玩法规则、系统流程、关卡说明、数值/配置表或策划文档？请说明文档对象、核心规则、交付给谁使用，以及是否被实现或评审；如果没有，请回答“没有”。",
    },
    {
        "name": "用户体验与反馈迭代",
        "triggers": ["用户体验", "用户需求", "目标用户", "玩家", "反馈", "竞品", "体验", "持续迭代"],
        "evidence_terms": ["用户", "玩家", "反馈", "调研", "访谈", "竞品", "体验", "复盘", "迭代", "留存", "数据"],
        "evidence_needed": "调研目标用户/玩家、拆解竞品、整理反馈、发现体验问题并提出或验证优化方案的经历。",
        "question": "JD 强调用户体验、竞品动向或反馈迭代。你是否做过竞品拆解、玩家/用户反馈整理、试玩记录或体验优化？请说明你发现的问题、提出的改动和验证方式；如果没有，请回答“没有”。",
    },
    {
        "name": "主动推动与交付闭环",
        "triggers": ["独立", "主动", "推动", "落地", "执行力", "高标准", "关注细节", "闭环", "迭代"],
        "evidence_terms": ["推动", "落地", "上线", "交付", "闭环", "迭代", "优化", "复盘", "版本", "验收", "排期"],
        "evidence_needed": "从发现问题、提出方案、协调执行到交付/复盘的闭环经历。",
        "question": "JD 强调主动推动、关注细节或高标准交付。你是否有一次从发现问题到提出方案、协调实现、验收迭代的完整经历？请说明你的角色、推进动作和结果；如果没有，请回答“没有”。",
    },
]

SOFT_TRIGGER_TERMS = sorted(
    {term for group in SOFT_REQUIREMENT_GROUPS for term in group["triggers"]},
    key=len,
    reverse=True,
)

GENERIC_DOMAIN_TERMS = {
    "用户",
    "需求",
    "业务",
    "产品",
    "数据",
    "交付",
    "玩法",
    "系统",
    "配置",
    "文档",
    "竞品",
    "玩家",
    "反馈",
}


def is_soft_requirement(text: str) -> bool:
    value = text.strip()
    if not value:
        return False
    return any(term in value for term in SOFT_TRIGGER_TERMS)


def soft_group_for_requirement(text: str) -> dict[str, object] | None:
    value = text.strip()
    if not value:
        return None
    for group in SOFT_REQUIREMENT_GROUPS:
        triggers = group["triggers"]
        if any(str(term) in value for term in triggers):
            return group
    return None


def split_hard_and_soft_requirements(items: list[str]) -> tuple[list[str], list[str]]:
    hard: list[str] = []
    soft: list[str] = []
    seen_hard: set[str] = set()
    seen_soft: set[str] = set()
    for item in items:
        value = item.strip()
        if len(value) < 2:
            continue
        key = value.lower()
        if is_soft_requirement(value):
            if key not in seen_soft:
                seen_soft.add(key)
                soft.append(value)
        elif key not in seen_hard:
            seen_hard.add(key)
            hard.append(value)
    return hard, soft


def filter_actionable_hard_requirements(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        value = item.strip()
        key = value.lower()
        if not value or key in seen or is_soft_requirement(value):
            continue
        if value in GENERIC_DOMAIN_TERMS:
            continue
        seen.add(key)
        result.append(value)
    return result


def active_soft_groups(job_text: str) -> list[dict[str, object]]:
    active: list[dict[str, object]] = []
    for group in SOFT_REQUIREMENT_GROUPS:
        triggers = group["triggers"]
        if any(str(term) in job_text for term in triggers):
            active.append(group)
    return active


def has_soft_evidence(group: dict[str, object], context: str) -> bool:
    evidence_terms = group["evidence_terms"]
    return any(str(term).lower() in context.lower() for term in evidence_terms)
