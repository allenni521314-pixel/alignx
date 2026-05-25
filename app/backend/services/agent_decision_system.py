from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _level(score: float) -> str:
    if score >= 80:
        return "高"
    if score >= 65:
        return "中"
    return "低"


def _strength_label(score: float) -> str:
    if score >= 80:
        return "强"
    if score >= 60:
        return "中"
    return "弱"


def _stage(stages: list[dict], key: str) -> dict:
    return next((item for item in stages if item.get("key") == key), {})


def _priority(impact_area: str, confidence: str, evidence_strength_score: float) -> dict:
    impact_weight = {
        "conversion_trust": 35,
        "ranking_relevance": 30,
        "click": 28,
        "ad_efficiency": 26,
    }.get(impact_area, 22)
    confidence_weight = {"高": 25, "中": 18, "低": 10}.get(confidence, 12)
    score = round(min(100, impact_weight + confidence_weight + evidence_strength_score * 0.4))
    if score >= 80:
        level = "P0"
    elif score >= 65:
        level = "P1"
    else:
        level = "P2"
    return {
        "score": score,
        "level": level,
        "reason": "按影响范围、判断置信度、证据强度综合排序",
    }


def _evidence_strength(
    *,
    source_type: str,
    review_score: float,
    platform_score: float,
    causal_score: float,
    ad_clicks: float,
    timeline_count: int,
) -> dict:
    source_score = {
        "review_intent": review_score,
        "platform_semantic": platform_score,
        "launch_check": 75,
        "buyer_risk": min(review_score or 70, causal_score or 70),
    }.get(source_type, 65)
    sample_score = 90 if ad_clicks >= 100 else 65 if ad_clicks >= 50 else 40
    feedback_score = 85 if timeline_count >= 3 else 65 if timeline_count else 35
    final_score = round(source_score * 0.45 + sample_score * 0.35 + feedback_score * 0.2)
    return {
        "score": final_score,
        "level": _strength_label(final_score),
        "factors": {
            "source_quality": round(source_score),
            "ad_sample": round(sample_score),
            "feedback_history": round(feedback_score),
        },
        "explain": "由来源质量、广告样本量、历史回流记录共同决定",
    }


def _add_card(
    cards: list[dict],
    *,
    error: str,
    source_type: str,
    source_table: str,
    source_id: Any,
    evidence: str,
    impact_area: str,
    confidence: str,
    suggested_action: str,
    validation_hypothesis_id: str,
    review_score: float,
    platform_score: float,
    causal_score: float,
    ad_clicks: float,
    timeline_count: int,
) -> None:
    strength = _evidence_strength(
        source_type=source_type,
        review_score=review_score,
        platform_score=platform_score,
        causal_score=causal_score,
        ad_clicks=ad_clicks,
        timeline_count=timeline_count,
    )
    priority = _priority(impact_area, confidence, strength["score"])
    cards.append(
        {
            "id": f"evidence-{len(cards) + 1}",
            "error": error,
            "source_type": source_type,
            "source_table": source_table,
            "source_id": source_id,
            "evidence": evidence,
            "impact_area": impact_area,
            "confidence": confidence,
            "evidence_strength": strength,
            "priority": priority,
            "suggested_action": suggested_action,
            "validation_hypothesis_id": validation_hypothesis_id,
        }
    )


def build_agent_decision_system(product: dict, stages: list[dict]) -> dict:
    """Build the deterministic Agent decision layer before model calls exist.

    This keeps the decision contract stable: later AI models can enhance the
    evidence and wording, but the system still requires sources, actions,
    validation hypotheses, and feedback.
    """

    learning_memory = product.get("learning_memory", {}) or {}
    selection = _stage(stages, "selection")
    launch = _stage(stages, "launch_check")
    diagnosis = _stage(stages, "listing_diagnosis")
    ab_test = _stage(stages, "ab_test")
    ad_validation = _stage(stages, "ad_validation")
    review = _stage(stages, "review")

    report = diagnosis.get("result", {}).get("diagnosis_report", {}) or {}
    judgment = report.get("judgment_system", {}) or {}
    alignment = judgment.get("alignment_scores", {}) or {}
    keyword_coverage = report.get("keyword_coverage", {}) or {}
    cosmo_rufus = report.get("cosmo_rufus_analysis", {}) or {}
    missing_categories = keyword_coverage.get("missing_categories", {}) or {}
    missing_pain = missing_categories.get("pain_point", []) or []
    suggestions = report.get("suggestions", {}) or {}
    validation_items = (
        cosmo_rufus.get("validation_hypotheses", [])
        or judgment.get("sections", {})
            .get("ad_validation", {})
            .get("validation_items", [])
        or []
    )

    launch_result = launch.get("result", {}) or {}
    diagnosis_result = diagnosis.get("result", {}) or {}
    ad_result = ad_validation.get("result", {}) or {}
    timeline_events = review.get("result", {}).get("events", []) or []
    hypothesis_validations = ad_result.get("hypothesis_validations", []) or []
    assigned_hypothesis_validations = [
        item for item in hypothesis_validations if item.get("hypothesis_id") != "unassigned"
    ]
    primary_validation = (
        assigned_hypothesis_validations[0]
        if assigned_hypothesis_validations
        else hypothesis_validations[0]
        if hypothesis_validations
        else {}
    )
    primary_metrics = primary_validation.get("metrics", {}) if isinstance(primary_validation, dict) else {}

    review_score = _num(alignment.get("review_demand_alignment"))
    platform_score = _num(alignment.get("platform_semantic_alignment"))
    causal_score = _num(alignment.get("causal_conversion_alignment"))
    main_image_score = _num(launch_result.get("main_image_score"))
    risk_score = _num(diagnosis_result.get("risk_elimination"))
    ad_clicks = _num(primary_metrics.get("clicks") if primary_metrics else ad_result.get("clicks"))
    ad_cvr = _num(primary_metrics.get("cvr") if primary_metrics else ad_result.get("cvr"))
    ad_acos = _num(primary_metrics.get("acos") if primary_metrics else ad_result.get("acos"))
    timeline_count = len(timeline_events)

    evidence_cards: list[dict] = []

    if missing_pain:
        pain_terms = "、".join(missing_pain[:3])
        _add_card(
            evidence_cards,
            error="买家高频痛点没有被 Listing 充分承接",
            source_type="review_intent",
            source_table=diagnosis.get("source_table", "listing_diagnoses"),
            source_id=diagnosis.get("source_id"),
            evidence=f"评论需求对齐度 {review_score:.0f}，缺失痛点词：{pain_terms}",
            impact_area="conversion_trust",
            confidence=_level(review_score),
            suggested_action=f"在标题、五点和主图证据中补强 {pain_terms}，避免只写泛化除味。",
            validation_hypothesis_id="hypothesis-1",
            review_score=review_score,
            platform_score=platform_score,
            causal_score=causal_score,
            ad_clicks=ad_clicks,
            timeline_count=timeline_count,
        )

    if platform_score and platform_score < 80:
        _add_card(
            evidence_cards,
            error="平台语义识别还不够稳定",
            source_type="platform_semantic",
            source_table=diagnosis.get("source_table", "listing_diagnoses"),
            source_id=diagnosis.get("source_id"),
            evidence=f"Cosmo语义对齐度 {platform_score:.0f}，标题/图片/A+ 仍有表达错配风险",
            impact_area="ranking_relevance",
            confidence=_level(platform_score),
            suggested_action="统一标题、五点、图片和A+里的核心类目词、功能词、场景词，减少平台误判。",
            validation_hypothesis_id="hypothesis-2",
            review_score=review_score,
            platform_score=platform_score,
            causal_score=causal_score,
            ad_clicks=ad_clicks,
            timeline_count=timeline_count,
        )

    if main_image_score and main_image_score < 80:
        _add_card(
            evidence_cards,
            error="主图没有把核心卖点证据前置",
            source_type="launch_check",
            source_table=launch.get("source_table", "prelaunch_test_results"),
            source_id=launch.get("source_id"),
            evidence=f"上新检测主图分 {main_image_score:.0f}，低于上架前安全线 80",
            impact_area="click",
            confidence=_level(main_image_score),
            suggested_action="主图或首张副图补充活性炭滤芯、封闭除味、公寓场景的可视化证据。",
            validation_hypothesis_id="hypothesis-3",
            review_score=review_score,
            platform_score=platform_score,
            causal_score=causal_score,
            ad_clicks=ad_clicks,
            timeline_count=timeline_count,
        )

    if risk_score and risk_score < 80:
        _add_card(
            evidence_cards,
            error="购买犹豫点解释不足",
            source_type="buyer_risk",
            source_table=diagnosis.get("source_table", "listing_diagnoses"),
            source_id=diagnosis.get("source_id"),
            evidence=f"风险消除分 {risk_score:.0f}，耗材、更换、清洁成本等信任点需要更明确",
            impact_area="conversion_trust",
            confidence=_level(risk_score),
            suggested_action="在五点和A+加入滤芯更换周期、清洁方式、适配场景和售后承诺。",
            validation_hypothesis_id="hypothesis-4",
            review_score=review_score,
            platform_score=platform_score,
            causal_score=causal_score,
            ad_clicks=ad_clicks,
            timeline_count=timeline_count,
        )

    evidence_cards.sort(
        key=lambda card: (card["priority"]["score"], card["evidence_strength"]["score"]),
        reverse=True,
    )
    for index, card in enumerate(evidence_cards, start=1):
        card["rank"] = index

    validation_hypotheses: list[dict] = []
    for index, item in enumerate(validation_items[:2], start=1):
        ad_action = item.get("ad_action", {}) or {}
        validation_hypotheses.append(
            {
                "id": item.get("hypothesis_id") or item.get("id") or f"hypothesis-{index}",
                "hypothesis": item.get("hypothesis") or "Listing 表达补强后，点击率与转化率应同步提升",
                "basis": item.get("diagnosis_issue") or item.get("cosmo_relation") or "来自统一判断系统的诊断问题",
                "cosmo_relation": item.get("cosmo_relation", ""),
                "rufus_question": item.get("rufus_question", ""),
                "listing_action": item.get("suggested_listing_action") or suggestions.get("title_rewrite") or "补强Listing表达证据",
                "ad_test_keywords": item.get("ad_test_keywords") or ad_action.get("keywords", []) or ["cat litter box odor eliminator"],
                "match_types": ad_action.get("match_types", []) or ["phrase", "exact"],
                "budget_rule": "先小预算验证，单关键词至少获得30次点击，整组超过100次点击后再判断",
                "observation_window": "7-14天，避开大促和断货异常周期",
                "success_metrics": item.get("success_metrics", []) or ["CTR", "CVR", "ACOS"],
                "decision_rules": [
                    "CTR提升：说明点击表达更准",
                    "CVR提升：说明详情承接和信任更准",
                    "CTR提升但CVR不升：继续检查价格、评价和详情页承诺",
                    "CTR不升：回到关键词和主图表达重新校准",
                ],
            }
        )

    if not validation_hypotheses:
        validation_hypotheses.append(
            {
                "id": "hypothesis-1",
                "hypothesis": "核心表达补强后，广告点击率和转化率应优于当前基线",
                "basis": "来自Listing诊断、上新检测和广告验证数据的组合判断",
                "listing_action": "优先修正证据卡片里的必改项",
                "ad_test_keywords": ["cat litter box odor eliminator", "ammonia odor remover"],
                "match_types": ["phrase", "exact"],
                "budget_rule": "先小预算验证，单关键词至少获得30次点击，整组超过100次点击后再判断",
                "observation_window": "7-14天，避开大促和断货异常周期",
                "success_metrics": ["CTR", "CVR", "ACOS"],
                "decision_rules": [
                    "点击超过100后再判断",
                    "CVR高于8%且ACOS低于35%视为初步成立",
                ],
            }
        )

    validation_hit = ad_clicks >= 100 and ad_cvr >= 8 and (ad_acos == 0 or ad_acos <= 35)
    hit_status = "已命中" if validation_hit else "待验证" if ad_clicks < 100 else "未命中"
    hit_rate = 100 if validation_hit else 0
    validated_hypothesis_count = len([item for item in assigned_hypothesis_validations if item.get("hit_status") == "已命中"])
    completed_hypothesis_count = len([item for item in assigned_hypothesis_validations if item.get("hit_status") != "待验证"])
    hypothesis_hit_rate = (
        round(validated_hypothesis_count * 100 / completed_hypothesis_count)
        if completed_hypothesis_count
        else hit_rate
    )

    if validation_hit:
        reusable_learning = "除味机制表达与精准除味词广告验证方向成立，可进入数据回流沉淀。"
        next_iteration = "把命中关键词和高转化表达写入下一轮Listing优化，并扩展同类目词包。"
    elif ad_clicks < 100:
        reusable_learning = "广告点击样本不足，当前不能用转化率直接否定诊断结论。"
        next_iteration = "继续拉满关键词测试样本，点击超过100后再判断。"
    else:
        reusable_learning = "诊断假设未被广告数据支持，需要回到关键词、主图或价格承接重新校准。"
        next_iteration = "拆分主图表达、详情页信任点和价格承诺，重新建立A/B测试。"

    failure_reason_taxonomy = [
        {
            "key": "sample_not_enough",
            "label": "样本不足",
            "rule": "假设级点击少于100时，不允许直接判定诊断失败",
            "next_action": "继续小预算拉样本，或减少关键词分组噪音",
        },
        {
            "key": "keyword_mismatch",
            "label": "关键词意图错配",
            "rule": "点击样本充足但CTR低于0.4%时触发",
            "next_action": "拆分属性词、场景词、状态触发词，暂停泛意图词",
        },
        {
            "key": "image_click_gap",
            "label": "主图点击不足",
            "rule": "曝光超过1000且CTR低于0.25%时触发",
            "next_action": "把已验证痛点证据前置到主图或第一张副图",
        },
        {
            "key": "detail_trust_gap",
            "label": "详情页信任承接不足",
            "rule": "CTR不低但CVR低于8%时触发",
            "next_action": "补强五点、A+、风险解释、使用边界和售后承诺",
        },
        {
            "key": "price_promise_gap",
            "label": "价格与承诺强度不匹配",
            "rule": "CVR可接受但ACOS高于35%时触发",
            "next_action": "检查价格带、优惠、主卖点承诺强度和竞品促销",
        },
        {
            "key": "review_support_gap",
            "label": "评论信任不足",
            "rule": "转化低且评分、评论量弱于竞品时触发",
            "next_action": "降低承诺强度，补证据，避免广告承接超过评论信任",
        },
        {
            "key": "competitor_interference",
            "label": "竞品促销或排名干扰",
            "rule": "自身表达未变但CTR/CVR突然下滑时触发",
            "next_action": "复查Top竞品价格、券、排名和主图变化",
        },
    ]

    primary_failure_reason = primary_validation.get("failure_reason") if isinstance(primary_validation, dict) else None
    if primary_failure_reason:
        likely_failure_reason = primary_failure_reason
    elif ad_clicks < 100:
        likely_failure_reason = "sample_not_enough"
    elif not validation_hit and ad_cvr < 8:
        likely_failure_reason = "detail_trust_gap"
    elif not validation_hit and ad_acos > 35:
        likely_failure_reason = "price_promise_gap"
    else:
        likely_failure_reason = "none"

    action_priority = [
        {
            "rank": card["rank"],
            "level": card["priority"]["level"],
            "score": card["priority"]["score"],
            "action": card["suggested_action"],
            "source_evidence_id": card["id"],
            "expected_impact": card["impact_area"],
            "validation_hypothesis_id": card["validation_hypothesis_id"],
            "difficulty": "中",
            "verification_cost": "低",
        }
        for card in evidence_cards
    ]

    listing_version_contract = {
        "required_fields": [
            "version_id",
            "product_id",
            "round",
            "before_listing",
            "after_listing",
            "changed_fields",
            "change_reason",
            "source_evidence_ids",
            "validation_hypothesis_ids",
            "executed_at",
            "pre_metrics",
            "post_metrics",
            "hit_status",
            "failure_reason",
        ],
        "current_round": product.get("optimization_round") or 1,
        "next_snapshot_timing": "执行Listing修改前先保存before，修改后保存after，广告验证完成后补充post_metrics",
        "minimum_viable_contract": [
            "每次Listing修改必须绑定至少1个source_evidence_id",
            "每个广告验证记录必须绑定validation_hypothesis_id",
            "点击样本不足时只能输出待验证，不能输出未命中",
            "复盘结论必须写入hit_status和failure_reason",
        ],
        "current_gaps": [
            gap
            for gap, missing in [
                ("广告记录尚未绑定诊断假设", not assigned_hypothesis_validations),
                ("复盘记录尚未沉淀", timeline_count == 0),
                ("广告样本不足100点击", ad_clicks < 100),
            ]
            if missing
        ],
    }

    if evidence_cards:
        chief_decision = {
            "current_stage": "复盘优化" if validation_hit else "广告验证",
            "decision": "先修正关键错配，再进入下一轮放量" if validation_hit else "继续用广告小预算验证诊断假设",
            "why": evidence_cards[0]["evidence"],
            "next_action": next_iteration,
            "risk_if_ignored": "如果跳过证据修正，广告会继续为错误表达买流量，系统也无法沉淀有效命中率。",
            "confidence": _level(min([score for score in [review_score, platform_score, causal_score] if score] or [70])),
        }
    else:
        chief_decision = {
            "current_stage": "复盘优化" if validation_hit else "广告验证",
            "decision": "当前主链路基本打通，进入回流校准",
            "why": "现有数据没有暴露高优先级错配项",
            "next_action": next_iteration,
            "risk_if_ignored": "如果不回流，下一次判断仍会停留在单次分析，无法持续变准。",
            "confidence": _level(min([score for score in [review_score, platform_score, causal_score] if score] or [80])),
        }

    return {
        "version": "agent-decision-architecture-v1",
        "mode": "deterministic_rules_no_ai_call",
        "agent_roles": [
            {"key": "selection_agent", "name": "选品判断Agent", "responsibility": "判断ASIN是否值得进入机会池"},
            {"key": "launch_agent", "name": "上新检测Agent", "responsibility": "判断Listing上架前是否具备条件"},
            {"key": "buyer_intent_agent", "name": "买家意图Agent", "responsibility": "检查评论需求、痛点和期待是否被承接"},
            {"key": "platform_semantic_agent", "name": "平台语义Agent", "responsibility": "检查标题、图片、类目、关键词是否让平台正确理解"},
            {"key": "ad_validation_agent", "name": "广告验证Agent", "responsibility": "把诊断结论转成可验证的广告实验"},
            {"key": "review_agent", "name": "复盘校准Agent", "responsibility": "记录命中率、失败原因和下一轮动作"},
        ],
        "chief_decision": chief_decision,
        "error_evidence_cards": evidence_cards,
        "action_priority": action_priority,
        "validation_hypotheses": validation_hypotheses,
        "hit_rate_learning": {
            "status": hit_status,
            "hit_rate": hypothesis_hit_rate,
            "basis": (
                f"主验证假设 {primary_validation.get('hypothesis_id', 'unassigned')}："
                f"点击 {ad_clicks:.0f}，CVR {ad_cvr:.2f}%，ACOS {ad_acos:.2f}%；"
                f"已绑定假设 {len(assigned_hypothesis_validations)} 个，复盘记录 {len(timeline_events)} 条"
            ),
            "reusable_learning": reusable_learning,
            "next_iteration": next_iteration,
            "likely_failure_reason": likely_failure_reason,
            "hypothesis_validations": hypothesis_validations,
            "assigned_hypothesis_count": len(assigned_hypothesis_validations),
            "completed_hypothesis_count": completed_hypothesis_count,
        },
        "learning_memory": learning_memory,
        "listing_version_contract": listing_version_contract,
        "failure_reason_taxonomy": failure_reason_taxonomy,
        "readiness": {
            "selection_ready": selection.get("status") == "completed",
            "launch_ready": launch.get("status") == "completed" and _num(launch.get("score")) >= 75,
            "platform_aligned": platform_score >= 80,
            "buyer_intent_aligned": review_score >= 80 and not missing_pain,
            "ready_for_ad_test": diagnosis.get("status") == "completed" and ab_test.get("status") == "completed",
            "ready_for_review": validation_hit,
        },
    }
