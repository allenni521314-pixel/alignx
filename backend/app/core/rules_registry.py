from __future__ import annotations
"""Amazon platform rules registry — editable rule library."""

from app.core.compliance import BANNED_ABSOLUTE, BANNED_HEALTH, BANNED_ATTACK, BANNED_EXAGGERATION

# ── All rule categories in one editable registry ──

PLATFORM_RULES = {
    "compliance_banned_absolute": {
        "name": "绝对化禁用词",
        "description": "Best / No.1 / Guaranteed / 100% 等",
        "items": BANNED_ABSOLUTE,
        "risk": "high",
        "category": "compliance",
    },
    "compliance_banned_health": {
        "name": "医疗健康禁用词",
        "description": "Medical Grade / Kills Germs / FDA Approved 等",
        "items": BANNED_HEALTH,
        "risk": "high",
        "category": "compliance",
    },
    "compliance_banned_attack": {
        "name": "竞品攻击禁用词",
        "description": "Better Than All / Competitors Are Fake 等",
        "items": BANNED_ATTACK,
        "risk": "high",
        "category": "compliance",
    },
    "compliance_banned_exaggeration": {
        "name": "夸大效果禁用词",
        "description": "Removes All Odors / Works Forever 等",
        "items": BANNED_EXAGGERATION,
        "risk": "high",
        "category": "compliance",
    },
    "image_main": {
        "name": "主图规则",
        "description": "纯白底(RGB255)，产品占85%以上，无文字/logo/水印",
        "items": ["纯白底RGB255", "产品占85%以上", "禁止文字", "禁止logo", "禁止水印", "禁止边框", "禁止插图"],
        "risk": "medium",
        "category": "image",
    },
    "image_secondary": {
        "name": "副图规则",
        "description": "按已上传素材判断ASIN描述完整度",
        "items": [
            "已上传副图素材: ASIN描述完整度",
        ],
        "risk": "medium",
        "category": "image",
    },
    "aplus_rules": {
        "name": "A+内容规则",
        "description": "按已上传素材判断ASIN描述完整度",
        "items": [
            "已上传 A+ 素材: ASIN描述完整度",
        ],
        "risk": "medium",
        "category": "aplus",
    },
    "buyer_lang_rules": {
        "name": "买家语言转译规则",
        "description": "7条核心转译规则",
        "items": [
            "禁止只翻译词，要翻译购买动机",
            "卖家讲功能→买家要结果",
            "技术→买家能感知的好处",
            "不能说'高品质'→说为什么降低风险",
            "不能说'适合所有人'→锁定场景",
            "不堆砌形容词→给购买理由",
            "每个卖点回答一个买家问题",
        ],
        "risk": "low",
        "category": "buyer_lang",
    },
}


def get_rules():
    """Return all rules."""
    return PLATFORM_RULES


def update_rule_items(rule_id: str, items: list[str]):
    """Update items for a rule category."""
    if rule_id in PLATFORM_RULES:
        PLATFORM_RULES[rule_id]["items"] = items
        # Also sync back to compliance lists
        if rule_id == "compliance_banned_absolute":
            from app.core import compliance
            compliance.BANNED_ABSOLUTE[:] = items
        elif rule_id == "compliance_banned_health":
            from app.core import compliance
            compliance.BANNED_HEALTH[:] = items
        elif rule_id == "compliance_banned_attack":
            from app.core import compliance
            compliance.BANNED_ATTACK[:] = items
        elif rule_id == "compliance_banned_exaggeration":
            from app.core import compliance
            compliance.BANNED_EXAGGERATION[:] = items
        return True
    return False
