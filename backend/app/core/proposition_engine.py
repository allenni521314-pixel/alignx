"""Proposition engine — 7 categories, 49 propositions.

P01 流量命题库
P02 主图命题库
P03 副图承接命题库
P04 价格带命题库
P05 信任命题库
P06 买家语言命题库
P07 需求不成立命题库

Each proposition has:
  - proposition_code (stable business primary key, never deleted)
  - controlled_variable
  - success/failure criteria
  - next_proposition_if_failed (chain)
"""

# 7 categories
PROPOSITION_CATEGORIES = {
    "P01": {"name": "流量命题库", "description": "Traffic-related propositions — CTR, impressions, keyword ranking"},
    "P02": {"name": "主图命题库", "description": "Main image propositions — click-through power, visual differentiation"},
    "P03": {"name": "副图承接命题库", "description": "Secondary image propositions — information delivery, trust building"},
    "P04": {"name": "价格带命题库", "description": "Price band propositions — positioning, perceived value, margin"},
    "P05": {"name": "信任命题库", "description": "Trust propositions — reviews, ratings, social proof, brand signals"},
    "P06": {"name": "买家语言命题库", "description": "Buyer language propositions — copy resonance, keyword-voice alignment"},
    "P07": {"name": "需求不成立命题库", "description": "Demand invalidation — product-market fit failure modes"},
}

# Each category gets 7 propositions (P01-001 through P01-007, etc.)
# Filled programmatically during DB seeding
PROPOSITIONS_PER_CATEGORY = 7
TOTAL_PROPOSITIONS = 49


def build_proposition_code(category: str, index: int) -> str:
    """P01 + 1 → P01-001"""
    return f"{category}-{index:03d}"
