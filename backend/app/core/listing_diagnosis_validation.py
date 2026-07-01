from __future__ import annotations

"""Unified Listing diagnosis validation engine.

Internal engines are composed here so the seller-facing surface remains one
Listing diagnosis module.
"""

from typing import Any

from app.core.listing_mental_value import ClaimRiskEngine, ListingMentalValueEngine, _flatten


POSITIONS = [
    "title_front",
    "title_middle",
    "main_image",
    "image_2",
    "image_3",
    "image_4_6",
    "image_7",
    "bullet_1",
    "bullet_2",
    "bullet_3_5",
    "a_plus_top",
    "a_plus_middle",
    "a_plus_bottom",
    "backend_search_terms",
    "qa",
    "reviews",
]

POSITION_LABELS = {
    "title_front": "标题前段",
    "title_middle": "标题中段",
    "main_image": "主图1",
    "image_2": "副图2",
    "image_3": "副图3",
    "image_4_6": "副图4-6",
    "image_7": "副图7",
    "bullet_1": "Bullet 1",
    "bullet_2": "Bullet 2",
    "bullet_3_5": "Bullet 3-5",
    "a_plus_top": "A+首屏",
    "a_plus_middle": "A+中段",
    "a_plus_bottom": "A+尾部",
    "backend_search_terms": "后台 Search Terms",
    "qa": "Q&A",
    "reviews": "Review",
}

POSITION_ROLES = {
    "title_front": "搜索匹配 + 点击理由",
    "title_middle": "补充场景、参数、差异化",
    "main_image": "合规展示商品 + 搜索结果页点击吸引",
    "image_2": "首屏场景确认",
    "image_3": "效果 / 使用方式解释",
    "image_4_6": "证明链、参数、对比、安全、认证",
    "image_7": "FAQ、售后、安装、适配、疑虑消除",
    "bullet_1": "最大痛点 + 结果型卖点",
    "bullet_2": "信任、安全、核心证明",
    "bullet_3_5": "参数、适配、使用边界、成本便利",
    "a_plus_top": "核心疑问回答",
    "a_plus_middle": "技术、对比、证明",
    "a_plus_bottom": "售后、FAQ、品牌信任、风险解除",
    "backend_search_terms": "同义词、长尾词、拼写变体、后台补充词",
    "qa": "疑虑消除",
    "reviews": "真实反馈证据",
}

POSITION_METRICS = {
    "title_front": ["impressions", "keyword_rank", "ctr"],
    "title_middle": ["ctr", "cvr"],
    "main_image": ["ctr", "cpc"],
    "image_2": ["cvr", "acos"],
    "image_3": ["cvr", "add_to_cart"],
    "image_4_6": ["cvr", "add_to_cart"],
    "image_7": ["cvr", "purchase"],
    "bullet_1": ["cvr", "acos"],
    "bullet_2": ["cvr", "add_to_cart"],
    "bullet_3_5": ["cvr", "add_to_cart"],
    "a_plus_top": ["cvr", "add_to_cart"],
    "a_plus_middle": ["cvr", "add_to_cart"],
    "a_plus_bottom": ["purchase", "acos"],
    "backend_search_terms": ["impressions", "keyword_rank"],
    "qa": ["purchase", "cvr"],
    "reviews": ["purchase", "cvr"],
}


class ListingDiagnosisValidationEngine:
    version = "listing_diagnosis_validation:v1"

    def analyze(
        self,
        *,
        asin: str,
        marketplace: str,
        listing_data: dict[str, Any],
        ai_result: dict[str, Any] | None = None,
        ad_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ai_result = ai_result or {}
        ad_metrics = ad_metrics or {}
        mental = ListingMentalValueEngine().analyze(listing_data, ai_result)
        rule_check = PlatformRuleEngine().check(listing_data)
        keyword_mapping = KeywordPositionAnalysisEngine().analyze(ai_result.get("top20_keyword_position_data"))
        funnel = FunnelDiagnosisEngine().diagnose(
            listing_data=listing_data,
            rule_check=rule_check,
            mental_result=mental,
            ad_metrics=ad_metrics,
            keyword_mapping=keyword_mapping,
        )
        heatmap = PositionGapEngine().build(
            listing_data=listing_data,
            rule_check=rule_check,
            mental_result=mental,
            funnel=funnel,
        )
        buyer_language = BuyerLanguageRepairEngine().build(mental)
        top_actions = TopActionEngine().build(
            heatmap=heatmap,
            funnel=funnel,
            rule_check=rule_check,
            buyer_language=buyer_language,
        )
        validation_plan = ValidationPlanEngine().build(top_actions)
        evidence_strength = _bounded_int(
            max([funnel.get("evidence_strength", 0), *[item.get("evidence_strength", 0) for item in top_actions]] or [0])
        )
        confidence = _bounded_int(
            max([funnel.get("confidence", 0), *[item.get("confidence", 0) for item in top_actions]] or [0])
        )
        return {
            "engine_version": self.version,
            "asin": asin,
            "marketplace": marketplace,
            "diagnosis_type": "data_calibrated_diagnosis" if ad_metrics else "high_confidence_inference",
            "primary_bottleneck": funnel.get("primary_bottleneck") or "待录入",
            "secondary_bottleneck": funnel.get("secondary_bottleneck") or "待录入",
            "overall_health_score": PositionGapEngine().overall_score(heatmap, rule_check),
            "confidence": confidence,
            "evidence_strength": evidence_strength,
            "prediction_policy": "No uplift percentage shown without historical validation samples.",
            "rule_check": rule_check,
            "keyword_position_mapping": keyword_mapping,
            "top20_keyword_mapping_context": ai_result.get("top20_keyword_mapping_context") or {},
            "funnel_diagnosis": funnel.get("funnel_diagnosis", []),
            "position_gap_heatmap": heatmap,
            "buyer_language_repairs": buyer_language,
            "top_actions": top_actions[:3],
            "validation_plan": validation_plan,
            "writeback": {
                "asin_profile_required": True,
                "save_to_asin_operation_file": True,
                "fields": [
                    "diagnosis_time",
                    "diagnosis_snapshot",
                    "hypothesis",
                    "recommended_action",
                    "verification_plan",
                    "post_validation_result",
                ],
            },
        }


class PlatformRuleEngine:
    def check(self, listing_data: dict[str, Any]) -> dict[str, Any]:
        title = listing_data.get("title") or ""
        bullets = _flatten(listing_data.get("bullet_points"))
        image_texts = listing_data.get("ocr_image_texts") or {}
        all_text = " ".join([title, *bullets, *_flatten(image_texts), *_flatten(listing_data.get("aplus_content"))])
        claim_risk = ClaimRiskEngine().analyze(all_text)
        blocked: list[str] = []
        warnings: list[str] = []
        forbidden: list[str] = []
        allowed = ["revise_title", "revise_bullets", "revise_secondary_images", "revise_a_plus"]

        if len(title) > 75:
            warnings.append("title_over_75_characters")
        if _keyword_stuffing(title):
            warnings.append("title_keyword_stuffing_risk")
        if claim_risk.get("riskLevel") == "high":
            blocked.append("high_risk_claim_without_evidence")
            forbidden.append("use_high_risk_claim_without_evidence")
        main_text = ""
        if isinstance(image_texts, dict):
            main_text = str(image_texts.get("main") or image_texts.get("main_image") or "")
        if main_text.strip():
            blocked.append("main_image_text_logo_watermark_risk")
            forbidden.extend(["add_text_to_main_image", "add_logo_to_main_image", "add_scene_background_to_main_image"])
        if not bullets:
            warnings.append("missing_bullets")
        if not listing_data.get("backend_keywords"):
            warnings.append("backend_search_terms_not_provided")

        return {
            "rule_status": "block" if blocked else "warning" if warnings else "pass",
            "blocked_reasons": _dedupe(blocked),
            "warnings": _dedupe(warnings),
            "allowed_actions": _dedupe(allowed),
            "forbidden_actions": _dedupe(forbidden),
        }


class KeywordPositionAnalysisEngine:
    def analyze(self, top20_data: Any) -> list[dict[str, Any]]:
        if not isinstance(top20_data, list):
            return []
        rows = []
        for item in top20_data:
            if not isinstance(item, dict):
                continue
            keyword = item.get("keyword") or "待录入"
            rows.append({
                "keyword": keyword,
                "keyword_role": item.get("keyword_role") or "待录入",
                "buyer_intent": item.get("buyer_intent") or "待录入",
                "top1_5_position_pattern": item.get("top1_5_position_pattern") or {},
                "top16_20_position_pattern": item.get("top16_20_position_pattern") or {},
                "position_consistency_score": _bounded_int(item.get("position_consistency_score") or 0),
                "recommended_positions": item.get("recommended_positions") or [],
                "reason": item.get("reason") or "暂无",
                "data_source": item.get("data_source") or "top20_keyword_position_data",
            })
        return rows


class FunnelDiagnosisEngine:
    def diagnose(
        self,
        *,
        listing_data: dict[str, Any],
        rule_check: dict[str, Any],
        mental_result: dict[str, Any],
        ad_metrics: dict[str, Any],
        keyword_mapping: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if ad_metrics:
            primary, secondary, reason = self._from_ad_metrics(ad_metrics)
            confidence = 82
            evidence = 86
        else:
            primary, secondary, reason, confidence, evidence = self._from_listing(listing_data, rule_check, mental_result, keyword_mapping)
        return {
            "primary_bottleneck": primary,
            "secondary_bottleneck": secondary,
            "confidence": confidence,
            "evidence_strength": evidence,
            "funnel_diagnosis": [
                self._row(primary, "high", reason, evidence),
                self._row(secondary, "medium", "次级断点，需在主变量验证后复核。", max(40, evidence - 18)),
            ],
        }

    def _from_ad_metrics(self, ad_metrics: dict[str, Any]) -> tuple[str, str, str]:
        impressions = _num(ad_metrics.get("impressions"))
        ctr = _num(ad_metrics.get("ctr"))
        cvr = _num(ad_metrics.get("cvr"))
        add_to_cart = _num(ad_metrics.get("add_to_cart_rate"))
        purchase = _num(ad_metrics.get("purchase_rate"))
        if impressions is not None and impressions <= 0:
            return "search_match", "search_intent", "曝光不足，优先检查搜索意图和搜索匹配。"
        if impressions and ctr is not None and ctr < 0.003:
            return "click_decision", "search_match", "曝光存在但 CTR 偏低，优先检查点击判断。"
        if ctr is not None and cvr is not None and cvr < 0.03:
            return "first_screen_confirmation", "value_understanding", "CTR 存在但 CVR 偏低，优先检查首屏确认与卖点理解。"
        if add_to_cart is not None and purchase is not None and purchase < add_to_cart:
            return "objection_handling", "trust_building", "加购后购买不足，优先检查疑虑消除和信任证明。"
        return "value_understanding", "trust_building", "广告数据未指向单一断点。"

    def _from_listing(
        self,
        listing_data: dict[str, Any],
        rule_check: dict[str, Any],
        mental_result: dict[str, Any],
        keyword_mapping: list[dict[str, Any]],
    ) -> tuple[str, str, str, int, int]:
        title = listing_data.get("title") or ""
        bullets = _flatten(listing_data.get("bullet_points"))
        if "main_image_text_logo_watermark_risk" in rule_check.get("blocked_reasons", []):
            return "click_decision", "first_screen_confirmation", "主图存在平台规则风险，搜索结果页点击判断会被干扰。", 82, 88
        if len(title) > 75 or not title:
            return "click_decision", "search_match", "标题前段未稳定承接搜索匹配和点击理由。", 76, 82
        if keyword_mapping:
            return "search_match", "click_decision", "Top20 关键词区位证据需要优先映射到标题前段。", 76, 82
        if not bullets:
            return "value_understanding", "trust_building", "五点缺失，买家无法理解产品如何解决问题。", 70, 72
        priority = mental_result.get("priorityPosition")
        if priority in {"bullet_1", "bullet_2", "bullet_3", "bullet_4", "bullet_5"}:
            return "value_understanding", "trust_building", "五点承接弱，优先检查卖点理解。", 72, 74
        return "click_decision", "first_screen_confirmation", "当前为高置信断点推断，不是因果预测。", 68, 66

    def _row(self, stage: str, risk_level: str, diagnosis: str, evidence_strength: int) -> dict[str, Any]:
        return {
            "stage": stage,
            "risk_level": risk_level,
            "buyer_question": BUYER_QUESTIONS.get(stage, "暂无"),
            "diagnosis": diagnosis,
            "affected_metrics": FUNNEL_METRICS.get(stage, ["ctr", "cvr"]),
            "evidence_strength": _bounded_int(evidence_strength),
        }


class PositionGapEngine:
    def build(
        self,
        *,
        listing_data: dict[str, Any],
        rule_check: dict[str, Any],
        mental_result: dict[str, Any],
        funnel: dict[str, Any],
    ) -> list[dict[str, Any]]:
        texts = _position_texts(listing_data)
        primary = funnel.get("primary_bottleneck")
        rows = []
        for position in POSITIONS:
            current = texts.get(position, "")
            status = self._status(position, current, rule_check, primary)
            rows.append({
                "position": position,
                "position_id": position,
                "position_name": POSITION_LABELS[position],
                "position_type": "listing_position",
                "funnel_stage": POSITION_STAGE.get(position, "value_understanding"),
                "position_role": POSITION_ROLES[position],
                "current_status": status,
                "status": status,
                "keyword_intents_to_cover": _keyword_intents(mental_result),
                "risk_level": "high" if status in {"missing", "blocked_by_rule"} else "medium" if status in {"weak", "wrong_position"} else "low",
                "impact_direction": _impact_direction(position),
                "evidence_strength": 78 if status in {"missing", "weak", "blocked_by_rule"} else 56,
                "recommended_fix_type": _fix_type(position, status),
                "issue": _issue_text(position, status),
                "recommendation": "待录入" if status == "not_priority" else _recommendation_for_position(position),
                "impacted_ad_metrics": POSITION_METRICS.get(position, ["cvr"]),
            })
        return rows

    def overall_score(self, heatmap: list[dict[str, Any]], rule_check: dict[str, Any]) -> int:
        base = 78
        penalties = {"missing": 9, "weak": 6, "wrong_position": 7, "blocked_by_rule": 15}
        score = base - sum(penalties.get(row.get("current_status"), 0) for row in heatmap)
        if rule_check.get("rule_status") == "block":
            score -= 12
        return max(0, min(100, score))

    def _status(self, position: str, current: str, rule_check: dict[str, Any], primary_bottleneck: str) -> str:
        if position == "main_image" and "main_image_text_logo_watermark_risk" in rule_check.get("blocked_reasons", []):
            return "blocked_by_rule"
        if not current and position in {"title_front", "main_image", "bullet_1"}:
            return "missing"
        if not current and position in {"qa", "reviews", "backend_search_terms"}:
            return "not_priority"
        if not current:
            return "weak"
        if POSITION_STAGE.get(position) == primary_bottleneck:
            return "weak"
        return "covered"


class BuyerLanguageRepairEngine:
    def build(self, mental_result: dict[str, Any]) -> list[dict[str, Any]]:
        buyer_language = mental_result.get("buyerLanguage") or {}
        repairs = []
        for position, text in buyer_language.items():
            if not text:
                continue
            repairs.append({
                "original_seller_language": "待录入",
                "buyer_language_version": text,
                "benefit": mental_result.get("mentalValuePoint", {}).get("buyerMemorySentence") or "待录入",
                "proof_needed": ", ".join(mental_result.get("mentalValuePoint", {}).get("proofPoints", [])) or "待录入",
                "recommended_position": [position],
            })
        return repairs


class TopActionEngine:
    def build(
        self,
        *,
        heatmap: list[dict[str, Any]],
        funnel: dict[str, Any],
        rule_check: dict[str, Any],
        buyer_language: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates = [row for row in heatmap if row.get("current_status") in {"missing", "weak", "wrong_position", "blocked_by_rule"}]
        candidates.sort(key=lambda row: _priority_score(row, funnel))
        actions = []
        for index, row in enumerate(candidates[:3], start=1):
            action = self._action(index, row, funnel, rule_check, buyer_language)
            if action:
                actions.append(action)
        return actions

    def _action(
        self,
        priority: int,
        row: dict[str, Any],
        funnel: dict[str, Any],
        rule_check: dict[str, Any],
        buyer_language: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        position = row["position"]
        if position == "main_image" and "add_text_to_main_image" in rule_check.get("forbidden_actions", []):
            action_text = "按平台规则重拍或替换主图，不加文字、logo、水印或场景背景。"
        else:
            action_text = _recommendation_for_position(position)
        return {
            "priority": priority,
            "target_stage": row.get("funnel_stage"),
            "target_position": position,
            "position_name": row.get("position_name"),
            "current_problem": row.get("issue") or "暂无",
            "evidence": f"evidence_strength={row.get('evidence_strength', 0)}",
            "action": action_text,
            "do_not_change": _do_not_change(position),
            "expected_impact_direction": (row.get("impact_direction") or ["increase_cvr"])[0],
            "confidence": _bounded_int(funnel.get("confidence", 0)),
            "evidence_strength": _bounded_int(row.get("evidence_strength", 0)),
            "verification_metrics": POSITION_METRICS.get(position, ["ctr", "cvr"]),
            "verification_period_days": 7,
            "success_condition": _success_condition(position),
            "failure_branch": _failure_branch(position),
            "prediction_note": "当前为高置信断点推断，不是因果预测",
        }


class ValidationPlanEngine:
    def build(self, top_actions: list[dict[str, Any]]) -> dict[str, Any]:
        if not top_actions:
            return {
                "priority": 1,
                "target_stage": "待录入",
                "target_position": "待录入",
                "action": "待录入",
                "do_not_change": [],
                "expected_impact_direction": "待录入",
                "confidence": 0,
                "evidence_strength": 0,
                "verification_metrics": [],
                "verification_period_days": 7,
                "success_condition": "待录入",
                "failure_branch": "待录入",
                "budget_level": "由用户输入决定",
            }
        plan = dict(top_actions[0])
        plan["budget_level"] = "由用户输入决定"
        return plan


BUYER_QUESTIONS = {
    "demand_trigger": "Why do I need this product?",
    "search_intent": "What words would I search for?",
    "search_match": "Is this the product I searched for?",
    "click_decision": "Why should I click this product?",
    "first_screen_confirmation": "Did I click the right product?",
    "value_understanding": "How does this solve my problem?",
    "trust_building": "Can I believe this claim?",
    "objection_handling": "What concern stops me from buying?",
}

FUNNEL_METRICS = {
    "demand_trigger": ["impressions"],
    "search_intent": ["impressions", "keyword_rank"],
    "search_match": ["impressions", "keyword_rank", "ctr"],
    "click_decision": ["ctr", "cpc"],
    "first_screen_confirmation": ["cvr", "bounce_rate"],
    "value_understanding": ["cvr", "add_to_cart"],
    "trust_building": ["cvr", "purchase"],
    "objection_handling": ["purchase", "acos"],
}

POSITION_STAGE = {
    "title_front": "search_match",
    "title_middle": "click_decision",
    "main_image": "click_decision",
    "image_2": "first_screen_confirmation",
    "image_3": "value_understanding",
    "image_4_6": "trust_building",
    "image_7": "objection_handling",
    "bullet_1": "value_understanding",
    "bullet_2": "trust_building",
    "bullet_3_5": "value_understanding",
    "a_plus_top": "value_understanding",
    "a_plus_middle": "trust_building",
    "a_plus_bottom": "objection_handling",
    "backend_search_terms": "search_match",
    "qa": "objection_handling",
    "reviews": "trust_building",
}


def _position_texts(listing_data: dict[str, Any]) -> dict[str, str]:
    title = listing_data.get("title") or ""
    words = title.split()
    bullets = _flatten(listing_data.get("bullet_points"))
    images = listing_data.get("ocr_image_texts") or {}
    if not isinstance(images, dict):
        images = {}
    aplus = _flatten(listing_data.get("aplus_content"))
    return {
        "title_front": " ".join(words[:8]),
        "title_middle": " ".join(words[8:18]),
        "main_image": str(listing_data.get("main_image") or images.get("main") or images.get("main_image") or ""),
        "image_2": str(images.get("image_2") or images.get("副图2") or ""),
        "image_3": str(images.get("image_3") or images.get("副图3") or ""),
        "image_4_6": " ".join(str(images.get(key) or "") for key in ["image_4", "image_5", "image_6", "副图4", "副图5", "副图6"]),
        "image_7": str(images.get("image_7") or images.get("副图7") or ""),
        "bullet_1": bullets[0] if len(bullets) > 0 else "",
        "bullet_2": bullets[1] if len(bullets) > 1 else "",
        "bullet_3_5": " ".join(bullets[2:5]),
        "a_plus_top": aplus[0] if len(aplus) > 0 else "",
        "a_plus_middle": " ".join(aplus[1:4]),
        "a_plus_bottom": " ".join(aplus[4:]),
        "backend_search_terms": str(listing_data.get("backend_keywords") or ""),
        "qa": str(listing_data.get("qa") or ""),
        "reviews": str(listing_data.get("reviews") or ""),
    }


def _keyword_intents(mental_result: dict[str, Any]) -> list[str]:
    value = mental_result.get("mentalValuePoint", {})
    return _dedupe([
        value.get("primaryValuePoint") or "",
        *value.get("supportingBenefits", []),
    ])[:3]


def _impact_direction(position: str) -> list[str]:
    if position in {"title_front", "title_middle", "main_image"}:
        return ["increase_ctr", "reduce_cpc"]
    if position in {"backend_search_terms"}:
        return ["increase_impressions"]
    return ["increase_cvr", "reduce_acos"]


def _fix_type(position: str, status: str) -> str:
    if status == "blocked_by_rule":
        return "fix_platform_rule_blocker"
    if position.startswith("image"):
        return "add_or_revise_image"
    if position.startswith("bullet"):
        return "rewrite_buyer_language"
    if position.startswith("a_plus"):
        return "revise_a_plus_section"
    if position.startswith("title"):
        return "revise_title_segment"
    return "待录入"


def _issue_text(position: str, status: str) -> str:
    if status == "blocked_by_rule":
        return "平台规则禁止当前表达或素材形式。"
    if status == "missing":
        return f"{POSITION_LABELS[position]}缺失。"
    if status == "weak":
        return f"{POSITION_LABELS[position]}承接弱。"
    if status == "wrong_position":
        return f"{POSITION_LABELS[position]}区位错配。"
    if status == "not_priority":
        return "当前不优先。"
    return "已覆盖。"


def _recommendation_for_position(position: str) -> str:
    mapping = {
        "title_front": "标题前段保留核心产品词和明确点击理由。",
        "title_middle": "标题中段补充场景、差异点或关键参数。",
        "main_image": "主图仅做合规展示，不加文字、logo、水印或场景背景。",
        "image_2": "副图2承接使用场景确认。",
        "image_3": "副图3解释效果或使用方式。",
        "image_4_6": "副图4-6补充参数、证明、对比或安全证据。",
        "image_7": "副图7处理 FAQ、售后、安装或适配疑虑。",
        "bullet_1": "Bullet 1 写最大痛点和结果型卖点。",
        "bullet_2": "Bullet 2 写信任、安全或核心证明。",
        "bullet_3_5": "Bullet 3-5 写参数、适配、使用边界或成本便利。",
        "a_plus_top": "A+首屏回答核心疑问。",
        "a_plus_middle": "A+中段承接技术、对比、证明。",
        "a_plus_bottom": "A+尾部承接售后、FAQ、品牌信任和风险解除。",
        "backend_search_terms": "后台 Search Terms 补充同义词、长尾词和拼写变体，不重复标题强覆盖词。",
        "qa": "Q&A 补充购买前疑虑。",
        "reviews": "Review 用作真实反馈证据，不作为可直接修改区位。",
    }
    return mapping.get(position, "待录入")


def _do_not_change(position: str) -> list[str]:
    base = ["price", "ad_structure"]
    if position != "main_image":
        base.append("main_image")
    if not position.startswith("a_plus"):
        base.append("a_plus")
    if not position.startswith("title"):
        base.append("title")
    return _dedupe(base)


def _success_condition(position: str) -> str:
    if position in {"title_front", "title_middle", "main_image"}:
        return "CTR improves while CPC does not increase materially."
    return "CVR or add-to-cart improves without ACOS worsening materially."


def _failure_branch(position: str) -> str:
    if position in {"title_front", "title_middle"}:
        return "If CTR does not improve, reassess main_image, price, review count, and coupon."
    if position == "main_image":
        return "If CTR does not improve, reassess title_front, price, review count, and coupon."
    return "If CVR does not improve, reassess first_screen_confirmation, trust proof, price, and delivery."


def _priority_score(row: dict[str, Any], funnel: dict[str, Any]) -> float:
    stage_match = 1.4 if row.get("funnel_stage") == funnel.get("primary_bottleneck") else 1.0
    gap = {"blocked_by_rule": 1.5, "missing": 1.3, "weak": 1.1, "wrong_position": 1.2}.get(row.get("current_status"), 0.7)
    evidence = max(1, row.get("evidence_strength", 0)) / 100
    verifiability = 1.2 if row.get("position") in {"title_front", "title_middle", "main_image", "image_2", "bullet_1"} else 1.0
    return -(stage_match * gap * evidence * verifiability)


def _keyword_stuffing(title: str) -> bool:
    words = [word.strip(" ,;|").lower() for word in title.split() if word.strip(" ,;|")]
    if len(words) < 10:
        return False
    unique = len(set(words))
    return unique / len(words) < 0.55


def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_int(value: Any) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return 0


def _dedupe(items: list[Any]) -> list[Any]:
    result = []
    seen = set()
    for item in items:
        if item is None:
            continue
        value = str(item)
        if not value:
            continue
        key = value.lower()
        if key not in seen:
            result.append(item)
            seen.add(key)
    return result
