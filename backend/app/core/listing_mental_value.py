from __future__ import annotations
"""Listing mental value engine.

Independent rules layer before buyer-language rewrite:
facts -> human drivers -> one mental value point -> risk -> position fit.
"""

from dataclasses import dataclass
import re
from typing import Any


HIGH_RISK_ALTERNATIVES = {
    "safe for pets": ["Designed for pet areas", "Made for pet spaces", "Ozone-free design for pet areas"],
    "safe for family": ["Designed for everyday home areas", "Made for home spaces"],
    "no harmful ozone": ["No ozone design", "Made without ozone", "Ozone-free"],
    "no ozone emissions": ["Made without ozone", "Ozone-free design"],
    "works while pets are present": ["No empty-room ozone routine", "No room-clearing ozone treatment", "Designed for everyday pet areas"],
    "kills bacteria": ["Helps reduce odors", "Helps freshen odor-prone areas"],
    "100% odor removal": ["Helps reduce everyday odors", "Freshens odor-prone spaces"],
    "completely eliminates odors": ["Helps reduce everyday odors", "Freshens odor-prone spaces"],
    "completely eliminates pet odors": ["Helps reduce everyday pet odors", "Freshens odor-prone pet spaces"],
    "guaranteed odor removal": ["Helps reduce everyday odors", "Freshens odor-prone spaces"],
    "non-toxic": ["Ozone-free", "No strong perfume smell"],
    "medical grade": ["待录入"],
}

MEDIUM_RISK_PHRASES = {
    "better fit for pet homes",
    "alternative to ozone machines",
    "no empty-room ozone routine",
    "helps freshen small spaces over time",
}

LOW_RISK_PHRASES = {
    "no filters",
    "usb powered",
    "wall-mount",
    "wall mount",
    "helps reduce odors",
    "freshens litter box areas",
    "no strong perfume smell",
    "no refills",
    "ozone-free",
    "no ozone",
}

POSITION_NAMES = {
    "title": "标题",
    "item_highlight": "亮点描述",
    "bullet_1": "五点1",
    "bullet_2": "五点2",
    "bullet_3": "五点3",
    "bullet_4": "五点4",
    "bullet_5": "五点5",
    "image_4": "副图4",
    "a_plus_3": "A+模块3",
    "backend_keywords": "后台关键词",
}


def _flatten(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        texts: list[str] = []
        for item in value.values():
            texts.extend(_flatten(item))
        return texts
    if isinstance(value, list):
        texts = []
        for item in value:
            texts.extend(_flatten(item))
        return texts
    return [str(value)]


def _first(items: list[str], fallback: str = "待录入") -> str:
    return next((item for item in items if item), fallback)


def _contains(text: str, *needles: str) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        value = item.strip()
        key = value.lower()
        if value and key not in seen:
            result.append(value)
            seen.add(key)
    return result


@dataclass
class ProductFactExtractor:
    listing_data: dict[str, Any]

    def extract(self) -> dict[str, Any]:
        title = self.listing_data.get("title") or ""
        bullets = _flatten(self.listing_data.get("bullet_points"))
        details = _flatten(self.listing_data.get("product_details"))
        image_texts = _flatten(self.listing_data.get("ocr_image_texts"))
        aplus = _flatten(self.listing_data.get("aplus_content"))
        all_texts = _dedupe([title, *bullets, *details, *image_texts, *aplus])
        text = " ".join(all_texts)

        product_type = "Pet odor eliminator" if _contains(text, "pet", "litter", "odor") else "LED headlight bulbs" if _contains(text, "led", "headlight", "halogen") else "待录入"

        core_function = []
        if _contains(text, "odor", "freshen", "deodor"):
            core_function.append("odor control")
        if _contains(text, "headlight", "beam", "halogen"):
            core_function.append("halogen replacement")

        use_cases = []
        for needle, label in [
            ("litter box", "litter box areas"),
            ("pet cage", "pet cages"),
            ("pet corner", "pet corners"),
            ("bathroom", "bathrooms"),
            ("shoe cabinet", "shoe cabinets"),
            ("closet", "storage closets"),
            ("halogen", "halogen replacement"),
            ("night driving", "night driving"),
        ]:
            if needle in text.lower():
                use_cases.append(label)

        differentiators = []
        for needle, label in [
            ("no ozone", "No ozone"),
            ("ozone-free", "Ozone-free"),
            ("no filter", "No filters"),
            ("filterless", "No filters"),
            ("no refill", "No refills"),
            ("usb", "USB powered"),
            ("wall", "Wall-mount"),
            ("photocatalyst", "Photocatalyst"),
            ("photo-catalyst", "Photocatalyst"),
            ("focused beam", "Focused beam"),
            ("clear beam", "Clear beam"),
        ]:
            if needle in text.lower():
                differentiators.append(label)

        certifications = []
        for cert in ["FCC", "CE", "RoHS"]:
            if cert.lower() in text.lower():
                certifications.append(cert)

        physical_specs = re.findall(r"\d+(?:\.\d+)?\s*[×x]\s*\d+(?:\.\d+)?\s*[×x]\s*\d+(?:\.\d+)?\s*(?:in|inch|inches|cm|mm)", text, flags=re.I)

        unsupported_claims = ClaimRiskEngine().find_high_risk_phrases(text)

        missing_evidence = []
        for claim in unsupported_claims:
            if claim in {"safe for pets", "safe for family", "no harmful ozone", "no ozone emissions", "works while pets are present", "non-toxic"}:
                missing_evidence.append(claim)

        return {
            "productType": product_type,
            "coreFunction": _dedupe(core_function),
            "useCases": _dedupe(use_cases),
            "targetUsers": ["pet homes"] if _contains(text, "pet", "litter") else [],
            "differentiators": _dedupe(differentiators),
            "convenienceFactors": [item for item in _dedupe(differentiators) if item in {"USB powered", "Wall-mount", "No filters", "No refills"}],
            "costFactors": [item for item in _dedupe(differentiators) if item in {"No filters", "No refills"}],
            "technicalProofs": [item for item in _dedupe(differentiators) if item in {"Photocatalyst", "Focused beam", "Clear beam"}],
            "certifications": certifications,
            "physicalSpecs": physical_specs,
            "unsupportedClaims": unsupported_claims,
            "competitors": [],
            "usageBoundaries": ["small spaces"] if _contains(text, "small space", "small-space") else [],
            "missingEvidence": _dedupe(missing_evidence),
            "evidenceTexts": all_texts,
        }


class HumanDriverEngine:
    def analyze(self, product_facts: dict[str, Any]) -> dict[str, Any]:
        facts = " ".join(_flatten(product_facts)).lower()
        gain = []
        avoidance = []

        if _contains(facts, "odor", "freshen"):
            gain.append(self._driver("comfort_gain", product_facts, "获得更清新的宠物区域或小空间体验。"))
            avoidance.append(self._driver("embarrassment_avoidance", product_facts, "避免宠物味或小空间异味带来的负面感受。"))
        if _contains(facts, "usb", "wall", "no filters", "no refills"):
            gain.append(self._driver("convenience_gain", product_facts, "获得更省事的使用方式。"))
        if _contains(facts, "no filters", "no refills"):
            gain.append(self._driver("cost_saving_gain", product_facts, "降低滤芯、补充装或耗材成本。"))
            avoidance.append(self._driver("hidden_cost_avoidance", product_facts, "避免后续耗材成本。"))
        if _contains(facts, "no ozone", "ozone-free"):
            avoidance.append(self._driver("safety_avoidance", product_facts, "避免对臭氧方案的安全担忧。"))
            avoidance.append(self._driver("hassle_avoidance", product_facts, "避免清场、通风或臭氧处理流程。"))
        if _contains(facts, "headlight", "beam", "halogen"):
            gain.append(self._driver("performance_gain", product_facts, "获得更清晰的夜间照明表现。"))
            avoidance.append(self._driver("risk_of_harm_avoidance", product_facts, "避免刺眼眩光或错误适配带来的风险。"))
            avoidance.append(self._driver("wrong_purchase_avoidance", product_facts, "避免买错规格或不适配。"))

        gain = self._unique_driver(gain)
        avoidance = self._unique_driver(avoidance)
        primary_type = "mixed" if gain and avoidance else "gain" if gain else "avoidance" if avoidance else "mixed"
        primary = avoidance[0]["driver"] if avoidance and primary_type in {"avoidance", "mixed"} else gain[0]["driver"] if gain else "driver_missing"
        secondary = gain[0]["driver"] if gain and primary != gain[0]["driver"] else avoidance[0]["driver"] if avoidance else "待录入"
        flags = []
        if not gain and not avoidance:
            flags.append("driver_missing")
        elif gain and not avoidance:
            flags.append("avoidance_gap")
        elif avoidance and not gain:
            flags.append("gain_gap")

        return {
            "gainDrivers": gain,
            "avoidanceDrivers": avoidance,
            "primaryDriverType": primary_type,
            "primaryDriver": primary,
            "secondaryDriver": secondary,
            "driverConclusion": " / ".join(flags) if flags else "趋利与避害均有承接" if primary_type == "mixed" else "待录入",
        }

    def _driver(self, driver: str, product_facts: dict[str, Any], buyer_meaning: str) -> dict[str, Any]:
        evidence = _dedupe(_flatten(product_facts.get("differentiators")) + _flatten(product_facts.get("useCases")) + _flatten(product_facts.get("coreFunction")))
        return {
            "driver": driver,
            "confidence": 0.82 if evidence else 0.45,
            "evidenceFromListing": evidence[:5],
            "evidenceFromProductFacts": evidence[:5],
            "buyerMeaning": buyer_meaning,
        }

    def _unique_driver(self, drivers: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen = set()
        result = []
        for item in drivers:
            if item["driver"] not in seen:
                result.append(item)
                seen.add(item["driver"])
        return result


class MentalValuePointEngine:
    def decide(self, product_facts: dict[str, Any], driver_analysis: dict[str, Any]) -> dict[str, Any]:
        facts = " ".join(_flatten(product_facts)).lower()
        rejected = []
        flags = []

        if _contains(facts, "headlight", "halogen", "beam"):
            primary = "Clearer halogen upgrade without harsh glare"
            memory = "Upgrade from dim halogen lights to clearer night driving without harsh glare."
            supporting = ["Clear beam", "Halogen replacement"]
            proof = [item for item in product_facts.get("technicalProofs", []) if item in {"Focused beam", "Clear beam"}]
            boundary = ["for specified bulb models"] if _contains(facts, "model", "fit") else ["not universal unless proven"]
        elif _contains(facts, "pet", "litter", "odor") and _contains(facts, "no ozone", "ozone-free"):
            primary = "No-ozone, no-refill pet odor removal for small spaces"
            memory = "Freshens litter box areas and pet spaces without ozone, filters or refills."
            supporting = [item for item in ["No filters", "No refills"] if item in product_facts.get("differentiators", [])]
            proof = [item for item in ["No ozone", "Ozone-free", "No filters", "No refills", "USB powered"] if item in product_facts.get("differentiators", [])]
            boundary = product_facts.get("usageBoundaries") or ["small spaces"]
            rejected.extend([
                {"valuePoint": "Small spaces", "reason": "scenario_list_not_value"},
                {"valuePoint": "Ozone-Free Odor Control", "reason": "seller_language_primary"},
            ])
        elif product_facts.get("coreFunction") and (driver_analysis.get("gainDrivers") or driver_analysis.get("avoidanceDrivers")):
            primary = f"{_first(product_facts.get('coreFunction', []))} for {_first(product_facts.get('useCases', []), 'target use case')}"
            memory = primary
            supporting = product_facts.get("differentiators", [])[:2]
            proof = product_facts.get("technicalProofs", []) + product_facts.get("differentiators", [])[:3]
            boundary = product_facts.get("usageBoundaries", [])
            if " " not in primary:
                flags.append("weak_purchase_motivation")
        else:
            primary = "needs_seller_clarification"
            memory = "needs_seller_clarification"
            supporting = []
            proof = []
            boundary = []
            flags.append("needs_seller_clarification")

        if len(supporting) > 2:
            supporting = supporting[:2]
            flags.append("mental_focus_loss")

        if primary.lower() in {"photocatalyst", "ozone-free", "small spaces"}:
            flags.append("seller_language_primary")

        value_type = driver_analysis.get("primaryDriverType") or "mixed"
        confidence = 0.84 if primary != "needs_seller_clarification" and proof else 0.52 if primary != "needs_seller_clarification" else 0.2

        return {
            "primaryValuePoint": primary,
            "buyerMemorySentence": memory,
            "valueType": value_type,
            "supportingBenefits": supporting,
            "proofPoints": _dedupe(proof),
            "usageBoundary": boundary,
            "rejectedValuePoints": rejected,
            "confidence": confidence,
            "issueTypes": flags,
        }


class ClaimRiskEngine:
    def analyze(self, text: str, evidence_provided: bool = False) -> dict[str, Any]:
        high = self.find_high_risk_phrases(text)
        medium = [phrase for phrase in MEDIUM_RISK_PHRASES if phrase in text.lower()]
        if high:
            level = "medium" if evidence_provided else "high"
        elif medium:
            level = "medium"
        else:
            level = "low"
        alternatives = []
        for phrase in high:
            alternatives.extend(HIGH_RISK_ALTERNATIVES.get(phrase, ["待录入"]))
        return {
            "riskLevel": level,
            "riskPhrases": high + medium,
            "evidenceRequired": bool(high),
            "saferAlternatives": _dedupe(alternatives),
        }

    def find_high_risk_phrases(self, text: str) -> list[str]:
        lowered = (text or "").lower()
        return [phrase for phrase in HIGH_RISK_ALTERNATIVES if phrase in lowered]

    def sanitize(self, text: str) -> tuple[str, list[str]]:
        result = text
        rejected = []
        for phrase, alternatives in HIGH_RISK_ALTERNATIVES.items():
            if phrase in result.lower():
                rejected.append(phrase)
                result = re.sub(re.escape(phrase), alternatives[0], result, flags=re.I)
        return result, rejected


class BuyerLanguageEngine:
    def translate(self, mental_value: dict[str, Any], product_facts: dict[str, Any]) -> dict[str, str]:
        primary = mental_value.get("primaryValuePoint") or "待录入"
        if primary == "No-ozone, no-refill pet odor removal for small spaces":
            return {
                "title": "Gleeda Pet Odor Eliminator, No Ozone, No Filters, USB Powered",
                "item_highlight": "Freshens litter box areas, pet cages and bathrooms with no ozone, no filters or refills",
                "bullet_1": "Keeps Pet Areas Fresh: Helps reduce everyday odors around litter box areas, small pet cages, pet corners, shoe cabinets, bathrooms and other small spaces.",
                "bullet_2": "No Ozone Design: Freshens small pet spaces without ozone, making it a better fit for pet homes than room-clearing ozone odor machines.",
                "bullet_3": "No Strong Perfume Smell: Freshens the air without heavy fragrances, sprays or scent cover-ups, so your home smells cleaner instead of perfumed.",
                "bullet_4": "No Filters, No Refills: No carbon bags, fragrance cartridges or replacement filters to buy, replace or maintain.",
                "bullet_5": "Plug In And Place Anywhere: Compact USB-powered wall-mount design fits near litter boxes, pet cages, bathrooms, shoe cabinets and other odor spots.",
            }
        if primary == "Clearer halogen upgrade without harsh glare":
            return {
                "title": "LED Headlight Bulbs for Halogen Replacement, Clear Beam",
                "item_highlight": "Clearer night driving with a focused beam, not harsh glare",
                "bullet_1": "Clearer Night Driving: Upgrade dim halogen lights with a focused beam for easier road visibility.",
                "bullet_2": "Focused Beam Pattern: Helps reduce harsh glare when installed in compatible housings.",
                "bullet_3": "Halogen Replacement Fit: Check your bulb model before purchase.",
                "bullet_4": "Plug-In Setup: Designed for direct replacement where compatible.",
                "bullet_5": "Use Boundary: For specified bulb models, not universal unless proven.",
            }
        return {
            "title": primary[:75],
            "item_highlight": mental_value.get("buyerMemorySentence") or primary,
            "bullet_1": mental_value.get("buyerMemorySentence") or primary,
            "bullet_2": ", ".join(product_facts.get("differentiators", [])[:3]) or "待录入",
            "bullet_3": "待录入",
            "bullet_4": "待录入",
            "bullet_5": "待录入",
        }


class PositionAllocationEngine:
    def allocate(
        self,
        listing_data: dict[str, Any],
        product_facts: dict[str, Any],
        driver_analysis: dict[str, Any],
        mental_value: dict[str, Any],
        buyer_language: dict[str, str],
    ) -> list[dict[str, Any]]:
        risk_engine = ClaimRiskEngine()
        bullets = _flatten(listing_data.get("bullet_points"))
        image_texts = listing_data.get("ocr_image_texts") or {}
        positions = [
            ("title", listing_data.get("title") or ""),
            ("item_highlight", listing_data.get("item_highlight") or ""),
            ("bullet_1", bullets[0] if len(bullets) > 0 else ""),
            ("bullet_2", bullets[1] if len(bullets) > 1 else ""),
            ("bullet_3", bullets[2] if len(bullets) > 2 else ""),
            ("bullet_4", bullets[3] if len(bullets) > 3 else ""),
            ("bullet_5", bullets[4] if len(bullets) > 4 else ""),
            ("image_4", image_texts.get("副图4") or image_texts.get("image_4") or ""),
            ("a_plus_3", _first(_flatten(listing_data.get("aplus_content")), "")),
            ("backend_keywords", listing_data.get("backend_keywords") or ""),
        ]
        rows = []
        for idx, (position, current) in enumerate(positions, start=1):
            suggested = buyer_language.get(position) or self._fallback_for_position(position, mental_value)
            suggested, rejected_from_suggested = risk_engine.sanitize(suggested)
            current_risk = risk_engine.analyze(current)
            suggested_risk = risk_engine.analyze(suggested)
            risk = current_risk if current_risk["riskLevel"] == "high" else suggested_risk
            issue_types = self._issue_types(position, current, mental_value, risk)
            score = self._score(current, risk, issue_types, mental_value)
            status = self._status(score, risk)
            rows.append({
                "position": position,
                "position_id": position,
                "position_name": POSITION_NAMES[position],
                "position_type": "text",
                "currentText": current or "暂无",
                "content_text": current or None,
                "score": score,
                "status": status,
                "issueTypes": issue_types,
                "humanDriver": {
                    "gainDrivers": [item["driver"] for item in driver_analysis.get("gainDrivers", [])],
                    "avoidanceDrivers": [item["driver"] for item in driver_analysis.get("avoidanceDrivers", [])],
                    "primaryDriverType": driver_analysis.get("primaryDriverType"),
                    "primaryDriver": driver_analysis.get("primaryDriver"),
                    "explanation": driver_analysis.get("driverConclusion"),
                },
                "mentalValuePoint": {
                    "primaryValuePoint": mental_value.get("primaryValuePoint"),
                    "buyerMemorySentence": mental_value.get("buyerMemorySentence"),
                    "supportingBenefits": mental_value.get("supportingBenefits", []),
                    "proofPoints": mental_value.get("proofPoints", []),
                },
                "buyerLanguageProblem": self._buyer_language_problem(current),
                "positionProblem": self._position_problem(position, current),
                "complianceRisk": risk,
                "suggestedRewrite": suggested,
                "recommendation": suggested,
                "reason": self._reason(position, mental_value, risk),
                "placementAdvice": self._placement_advice(position),
                "rejectedPhrases": _dedupe(risk.get("riskPhrases", []) + rejected_from_suggested),
                "validationMetrics": ValidationMetricMapper().metrics_for(position),
                "impacted_ad_metrics": ValidationMetricMapper().metrics_for(position),
                "priority": idx,
            })
        return rows

    def _fallback_for_position(self, position: str, mental_value: dict[str, Any]) -> str:
        if position == "image_4":
            return "尺寸和安装"
        if position == "a_plus_3":
            return "解释产品差异和使用边界"
        if position == "backend_keywords":
            return "补充场景词、同义词、长尾词"
        return mental_value.get("buyerMemorySentence") or "待录入"

    def _issue_types(self, position: str, current: str, mental_value: dict[str, Any], risk: dict[str, Any]) -> list[str]:
        issues = []
        if not current:
            issues.append("missing")
        if risk["riskLevel"] == "high":
            issues.append("high_risk_requires_evidence")
        if position == "title" and len(current) > 75:
            issues.append("title_too_long")
        if mental_value.get("primaryValuePoint") == "needs_seller_clarification":
            issues.append("needs_seller_clarification")
        issues.extend(mental_value.get("issueTypes", []))
        if position == "item_highlight" and current and len(current.split(",")) >= 3:
            issues.append("scenario_list_not_value")
        return _dedupe(issues)

    def _score(self, current: str, risk: dict[str, Any], issue_types: list[str], mental_value: dict[str, Any]) -> int:
        score = 5
        if not current:
            score -= 2
        if risk["riskLevel"] == "high":
            score -= 3
        elif risk["riskLevel"] == "medium":
            score -= 1
        if "needs_seller_clarification" in issue_types:
            score -= 2
        if mental_value.get("confidence", 0) < 0.5:
            score -= 1
        return max(0, min(5, score))

    def _status(self, score: int, risk: dict[str, Any]) -> str:
        if risk["riskLevel"] == "high":
            return "high_risk_requires_evidence"
        if score >= 4:
            return "usable"
        if score == 3:
            return "usable_but_optimize"
        if score >= 1:
            return "rewrite_needed"
        return "not_recommended"

    def _buyer_language_problem(self, current: str) -> str:
        if not current:
            return "暂无"
        if _contains(current, "photocatalyst", "voc sensor", "advanced"):
            return "当前表达偏技术词，未先说明买家结果。"
        return "待录入"

    def _position_problem(self, position: str, current: str) -> str:
        if not current:
            return "缺失"
        if position == "title" and len(current) > 75:
            return "标题超过 75 字符。"
        return "待录入"

    def _reason(self, position: str, mental_value: dict[str, Any], risk: dict[str, Any]) -> str:
        if risk["riskLevel"] == "high":
            return "存在高风险表达，未提供证据前不能进入建议改写。"
        return f"{POSITION_NAMES[position]}需要承接主心智价值点：{mental_value.get('primaryValuePoint', '待录入')}。"

    def _placement_advice(self, position: str) -> str:
        mapping = {
            "title": "产品身份识别 + 核心搜索词 + 最强差异点。",
            "item_highlight": "买家结果 + 差异点 + 避免的痛点。",
            "bullet_1": "核心效果。",
            "bullet_2": "核心差异。",
            "bullet_3": "替代方案对比。",
            "bullet_4": "成本和省心。",
            "bullet_5": "安装和使用门槛。",
            "image_4": "尺寸、参照物、安装方式。",
            "a_plus_3": "认知教育和使用边界。",
            "backend_keywords": "补充场景词、同义词、长尾词。",
        }
        return mapping[position]


class ValidationMetricMapper:
    def metrics_for(self, position: str) -> list[str]:
        if position in {"title", "item_highlight"}:
            return ["CTR", "CVR"]
        if position.startswith("bullet") or position.startswith("image") or position.startswith("a_plus"):
            return ["CVR", "加购率"]
        if position == "backend_keywords":
            return ["广告相关性", "自然排名"]
        return ["CVR"]


class ListingMentalValueEngine:
    version = "listing_mental_value:v1"

    def analyze(self, listing_data: dict[str, Any], ai_result: dict[str, Any] | None = None) -> dict[str, Any]:
        product_facts = ProductFactExtractor(listing_data or {}).extract()
        human_driver = HumanDriverEngine().analyze(product_facts)
        mental_value = MentalValuePointEngine().decide(product_facts, human_driver)
        buyer_language = BuyerLanguageEngine().translate(mental_value, product_facts)
        positions = PositionAllocationEngine().allocate(
            listing_data or {},
            product_facts,
            human_driver,
            mental_value,
            buyer_language,
        )
        priority = self._priority_position(positions, ai_result or {})
        return {
            "engineVersion": self.version,
            "productFacts": product_facts,
            "humanDriverAnalysis": human_driver,
            "mentalValuePoint": mental_value,
            "buyerLanguage": buyer_language,
            "positionDiagnoses": positions,
            "priorityPosition": priority.get("position"),
            "priorityAction": priority.get("suggestedRewrite"),
            "impactedAdMetrics": priority.get("validationMetrics", ["CTR", "CVR"]),
            "overallConclusion": self._overall(mental_value, human_driver),
            "currentStatus": "mental_value_evaluated",
        }

    def _priority_position(self, rows: list[dict[str, Any]], ai_result: dict[str, Any]) -> dict[str, Any]:
        high_risk = [row for row in rows if row["complianceRisk"]["riskLevel"] == "high"]
        if high_risk:
            return high_risk[0]
        ordered = sorted(rows, key=lambda row: (row["score"], row["priority"]))
        return ordered[0] if ordered else {
            "position": ai_result.get("priority_position") or "title",
            "suggestedRewrite": ai_result.get("priority_action") or "待录入",
            "validationMetrics": ai_result.get("impacted_ad_metrics") or ["CTR", "CVR"],
        }

    def _overall(self, mental_value: dict[str, Any], human_driver: dict[str, Any]) -> str:
        primary = mental_value.get("primaryValuePoint") or "待录入"
        driver = human_driver.get("primaryDriverType") or "mixed"
        return f"主心智价值点：{primary}。驱动力类型：{driver}。"
