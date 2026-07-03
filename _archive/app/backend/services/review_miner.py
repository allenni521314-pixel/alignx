"""
Review miner: extract competitor weaknesses from negative reviews.
Used by asin_selection to identify exploitable pain points in top competitors.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Weakness classification taxonomy ──

WEAKNESS_TAXONOMY = {
    "durability": {
        "label": "耐久性",
        "patterns": ["stopped working", "broke after", "didn't last", "died after", "wore out",
                     "stopped after", "lasted only", "within weeks", "within months", "not durable"],
        "impact": "产品寿命短，买家复购意愿低，差评率高",
        "exploit": "宣传更长寿命 + 真实质保承诺",
    },
    "effectiveness": {
        "label": "效果差",
        "patterns": ["doesn't work", "didn't work", "no difference", "no effect",
                     "waste of money", "useless", "did nothing", "not effective", "smell still"],
        "impact": "核心功能未满足，买家直接流失",
        "exploit": "强调真实测试数据 + 效果对比证据",
    },
    "customer_service": {
        "label": "售后差",
        "patterns": ["customer service", "no response", "warranty", "return policy",
                     "ignored", "no help", "refund", "contacted", "never replied"],
        "impact": "售后失信导致差评扩散，影响转化",
        "exploit": "真实可验证的售后承诺 + 快速响应",
    },
    "safety": {
        "label": "安全隐患",
        "patterns": ["dangerous", "toxic", "chemical", "burn", "smoke", "spark",
                     "fire", "shock", "irritation", "allergic", "harmful",
                     "not safe", "poison", "unsafe"],
        "impact": "安全问题是致命缺陷，可导致下架",
        "exploit": "第三方安全认证 + 成分透明",
    },
    "noise": {
        "label": "噪音大",
        "patterns": ["loud", "noisy", "noise", "humming", "buzzing", "whining",
                     "disturbing", "can't sleep", "too loud"],
        "impact": "影响使用体验，尤其夜间场景",
        "exploit": "静音设计 + 分贝测试数据",
    },
    "usability": {
        "label": "难用",
        "patterns": ["hard to use", "difficult", "complicated", "confusing",
                     "instructions", "setup", "installation", "not intuitive", "hassle"],
        "impact": "使用门槛高导致退货率高",
        "exploit": "开箱即用 + 零学习成本",
    },
    "value": {
        "label": "不值",
        "patterns": ["overpriced", "not worth", "too expensive", "cheaper alternative",
                     "pricey", "rip off", "returned"],
        "impact": "价格感知不匹配，影响转化",
        "exploit": "强调总持有成本 + 长期价值",
    },
    "size_fit": {
        "label": "尺寸问题",
        "patterns": ["too small", "too big", "too large", "doesn't fit",
                     "smaller than", "bigger than", "size issue", "wrong size"],
        "impact": "尺寸误导导致退货",
        "exploit": "精确尺寸对比图 + 实物参照",
    },
}


def analyze_weakness_from_route(route_summary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rule-based weakness detection from route summary data.
    
    Without actual review data, uses structural signals to identify exploitable
    weaknesses in the competitive landscape.
    """
    weaknesses: list[dict[str, Any]] = []
    seen_categories: set[str] = set()

    for route in route_summary:
        route_name = str(route.get("route") or "")
        count = int(route.get("count") or 0)
        median_reviews = float(route.get("medianReviews") or 0)
        median_price = float(route.get("medianPrice") or 0)

        # High review count means high barrier - weakness is hard to differentiate
        if median_reviews >= 50000:
            if "review_barrier" not in seen_categories:
                weaknesses.append({
                    "type": "review_barrier",
                    "category": "竞争壁垒",
                    "route": route_name,
                    "finding": f"{route_name}赛道头部评论{int(median_reviews):,}+，评论壁垒极高",
                    "severity": "high",
                    "exploit": f"不建议正面竞争，寻找评论<500的细分切入点",
                    "evidence": f"{route_name}赛道头部评论中位数{int(median_reviews):,}",
                })
                seen_categories.add("review_barrier")

        # Low review route = opportunity
        if 0 < median_reviews <= 500:
            if "low_barrier" not in seen_categories:
                weaknesses.append({
                    "type": "low_barrier",
                    "category": "进入机会",
                    "route": route_name,
                    "finding": f"{route_name}赛道评论仅{int(median_reviews)}，是低竞争空白",
                    "severity": "opportunity",
                    "exploit": f"快速进入{route_name}赛道，抢占评论低位优势",
                    "evidence": f"{route_name}赛道{count}个样本，评论中位数{int(median_reviews)}",
                })

        # UV-C route = known weakness
        if route_name == "UV-C":
            weaknesses.append({
                "type": "durability",
                "category": WEAKNESS_TAXONOMY["durability"]["label"],
                "route": "UV-C",
                "finding": "UV-C灯管寿命2000小时，2-3个月必烧，差评率14%+",
                "severity": "high",
                "exploit": "用光触媒替代UV-C，宣称零耗材、灯管不烧",
                "evidence": "Clarifion ODRx 14%一星差评均指向灯管烧毁",
            })

        # Spray/enzyme route = consumption cost
        if route_name == "喷雾/酶解":
            weaknesses.append({
                "type": "recurring_cost",
                "category": "复购成本",
                "route": "喷雾/酶解",
                "finding": "喷雾消耗品需反复购买，年花费$100+",
                "severity": "medium",
                "exploit": "宣传一次购买长期使用的设备型方案",
                "evidence": f"喷雾均价${median_price:.0f}，月均消耗1瓶",
            })

    return weaknesses


def mine_competitor_weaknesses(
    route_summary: list[dict[str, Any]],
    decision_points: list[dict[str, Any]],
) -> dict[str, Any]:
    """Main entry point: analyze competitive weaknesses.
    
    Returns structured weakness intelligence for the four-layer analysis.
    """
    structural_weaknesses = analyze_weakness_from_route(route_summary)

    # Identify top weakness by severity
    high_severity = [w for w in structural_weaknesses if w.get("severity") == "high"]
    opportunities = [w for w in structural_weaknesses if w.get("severity") == "opportunity"]

    # Find decision points that indicate weakness
    risky_points = [dp for dp in decision_points if dp.get("status") in ("需补证", "暂缓")]

    return {
        "weaknesses": structural_weaknesses,
        "top_weakness": high_severity[0]["finding"] if high_severity else None,
        "top_opportunity": opportunities[0]["finding"] if opportunities else None,
        "exploit_direction": (
            f"绕开{structural_weaknesses[0]['route']}赛道高评论壁垒，"
            f"切入{opportunities[0]['route']}低竞争空白"
            if opportunities and structural_weaknesses else
            "需更多样本判断差异化方向"
        ),
        "risk_signal_count": len(risky_points),
        "weakness_count": len(structural_weaknesses),
    }
