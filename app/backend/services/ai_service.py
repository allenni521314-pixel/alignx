from __future__ import annotations

from typing import Any


class AIService:
    """AI inference boundary for ASIN business verification.

    The first-stage implementation uses deterministic placeholders so the data
    loop can run before model routing is finalized. Model-backed implementations
    should keep the same method contracts and persist outputs through
    AI_DECISION_TRACE.
    """

    prompt_version = "asin_3x3_v1"
    model_name = "rule_engine_placeholder"

    async def generate_yesterday_report(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "conclusion": input_data.get("conclusion") or "暂无",
            "recommended_action": input_data.get("recommended_action") or "暂无",
            "reasoning_summary": input_data.get("reasoning_summary") or "暂无",
        }

    async def generate_today_decision(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "conclusion": input_data.get("conclusion") or "暂无",
            "recommended_action": input_data.get("recommended_action") or "暂无",
            "reasoning_summary": input_data.get("reasoning_summary") or "暂无",
        }

    async def run_intent_reception_engine(self, input_data: dict[str, Any]) -> dict[str, Any]:
        evidence_count = int(input_data.get("evidence_count") or 0)
        metric_snapshot = input_data.get("metric_snapshot") if isinstance(input_data.get("metric_snapshot"), dict) else {}
        has_listing = bool(input_data.get("has_listing"))
        has_safe_expression = bool(input_data.get("safe_expression"))
        blocked_expression = input_data.get("blocked_expression") or ""
        inventory = metric_snapshot.get("inventory")
        profit = metric_snapshot.get("profit")
        cvr = metric_snapshot.get("cvr")
        acos = metric_snapshot.get("acos")

        if blocked_expression:
            action = "Blocked"
            status = "Blocked"
            safety_status = "Blocked"
        elif inventory is not None and float(inventory or 0) <= 0:
            action = "Do Not Invest"
            status = "Blocked"
            safety_status = "Safe" if has_safe_expression else "Needs Evidence"
        elif evidence_count <= 0:
            action = "Do Not Invest"
            status = "Candidate"
            safety_status = "Safe" if has_safe_expression else "Needs Evidence"
        elif not has_listing:
            action = "Listing First"
            status = "Ready To Test"
            safety_status = "Safe" if has_safe_expression else "Needs Evidence"
        elif cvr is not None and float(cvr or 0) > 0 and (acos is None or float(acos or 0) <= 0.35):
            action = "Scale Test"
            status = "Ready To Test"
            safety_status = "Safe" if has_safe_expression else "Needs Evidence"
        elif profit is not None and float(profit or 0) < 0:
            action = "Do Not Invest"
            status = "Candidate"
            safety_status = "Safe" if has_safe_expression else "Needs Evidence"
        else:
            action = "Low-Bid Test"
            status = "Ready To Test"
            safety_status = "Safe" if has_safe_expression else "Needs Evidence"

        return {
            "position_reception_result": input_data.get("position_reception_result") or "待录入",
            "semantic_audit_result": input_data.get("semantic_audit_result") or "待录入",
            "buyer_language_result": input_data.get("buyer_language_result") or "待录入",
            "intent_evidence_status": "Supported" if evidence_count else "Unverified",
            "product_platform_safety_status": safety_status,
            "investment_value_status": "Worth Testing" if action in {"Listing First", "Low-Bid Test", "Scale Test"} else "Not Ready",
            "reception_gap": input_data.get("reception_gap") or ("待录入" if has_listing else "Listing 未形成可验证承接"),
            "safe_expression": input_data.get("safe_expression") or "待录入",
            "blocked_expression": blocked_expression,
            "recommended_action": action,
            "priority_score": input_data.get("priority_score"),
            "confidence_score": input_data.get("confidence_score"),
            "status": status,
        }

    async def generate_traffic_strategy(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "conclusion": input_data.get("conclusion") or "暂无",
            "recommended_action": input_data.get("recommended_action") or "暂无",
            "reasoning_summary": input_data.get("reasoning_summary") or "暂无",
        }

    async def run_effect_validation(self, input_data: dict[str, Any]) -> dict[str, Any]:
        return {
            "conclusion": input_data.get("status") or "Inconclusive",
            "recommended_action": input_data.get("recommended_action") or "暂无",
            "reasoning_summary": input_data.get("reasoning_summary") or "暂无",
        }
