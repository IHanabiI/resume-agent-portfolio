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

HARD_REQUIREMENT_GROUPS: list[dict[str, object]] = [
    {
        "name": "表格配置与数值整理",
        "triggers": ["Excel", "配置表", "表格", "数值", "公式", "数据整理"],
        "evidence_needed": "用 Excel、飞书表格或配置表整理玩法规则、关卡参数、数值、反馈或版本内容的经历。",
        "question": "JD 提到 Excel / 配置表 / 数值整理。你是否用表格整理过玩法规则、关卡参数、数值、反馈或版本内容？请说明表格用途、字段或规则、你负责的部分，以及它是否被用于 Demo、文档、配置或迭代；如果没有，请回答“没有”。",
    },
    {
        "name": "玩法与系统设计",
        "triggers": ["玩法设计", "系统设计", "玩法", "系统", "机制", "规则", "活动玩法"],
        "evidence_needed": "从目标、规则、流程、状态、反馈、奖励或限制条件出发，设计一个玩法/系统/活动机制的案例。",
        "question": "JD 提到玩法设计或系统设计。你是否有一个完整的玩法、系统、活动或机制设计案例？请按“目标玩家/设计目标 - 核心规则 - 玩家操作流程 - 反馈/奖励 - 你产出的文档或原型 - 最终结果”说明；如果没有，请回答“没有”。",
    },
    {
        "name": "关卡 / 战斗 / 怪物设计",
        "triggers": ["关卡设计", "关卡", "战斗设计", "战斗", "怪物", "Boss", "敌人", "难度曲线"],
        "evidence_needed": "关卡、战斗、怪物、Boss、难度曲线或玩家挑战节奏相关的设计案例。",
        "question": "JD 提到关卡、战斗或怪物相关设计。你是否做过关卡流程、敌人/怪物机制、Boss 技能、战斗节奏或难度曲线设计？请说明设计目标、核心机制、玩家体验路径、你如何验证或调整；如果没有，请回答“没有”。",
    },
    {
        "name": "引擎 / 编辑器 / 原型实现",
        "triggers": ["Unity", "Unreal", "UE", "Godot", "编辑器", "蓝图", "Demo", "原型"],
        "evidence_needed": "使用 Unity、Unreal、Godot、编辑器、蓝图或其他工具制作 Demo、原型、关卡或可交互验证内容的经历。",
        "question": "JD 提到引擎、编辑器、Demo 或原型能力。你是否用 Unity / Unreal / Godot / 编辑器 / 蓝图做过可运行 Demo、关卡白盒、玩法原型或交互验证？请说明工具、你实现了什么、验证了什么设计问题；如果没有，请回答“没有”。",
    },
    {
        "name": "竞品拆解与体验分析",
        "triggers": ["竞品分析", "竞品", "体验分析", "用户体验", "玩家反馈", "反馈"],
        "evidence_needed": "拆解竞品玩法、整理玩家反馈、试玩记录、体验问题分析并提出优化方案的经历。",
        "question": "JD 提到竞品、用户体验或玩家反馈。你是否做过竞品玩法拆解、试玩记录、玩家反馈整理或体验问题分析？请说明你分析的对象、发现的问题、提出的优化建议和依据；如果没有，请回答“没有”。",
    },
]


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


def cluster_hard_requirements(items: list[str]) -> list[dict[str, object]]:
    active: list[dict[str, object]] = []
    joined = "\n".join(items)
    covered: set[str] = set()
    for group in HARD_REQUIREMENT_GROUPS:
        triggers = [str(term) for term in group["triggers"]]
        matched = [item for item in items if any(term.lower() in item.lower() or item.lower() in term.lower() for term in triggers)]
        if matched or any(term.lower() in joined.lower() for term in triggers):
            copy = dict(group)
            copy["requirements"] = matched or triggers[:2]
            active.append(copy)
            covered.update(item.lower() for item in matched)

    for item in items:
        if item.lower() in covered:
            continue
        active.append(
            {
                "name": item,
                "triggers": [item],
                "requirements": [item],
                "evidence_needed": f"能证明「{item}」的真实项目、课程、实习、作品或工具使用经历。",
                "question": (
                    f"JD 提到「{item}」。你是否有能证明这项要求的真实经历？"
                    "请说明具体场景、你的职责、产出物和可确认结果；如果没有，请回答“没有”。"
                ),
            }
        )
    return active


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
