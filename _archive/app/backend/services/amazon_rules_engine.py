import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models.amazon_rules import AmazonRule


MODULE_TEXT_FIELDS = {
    "TITLE": ["title"],
    "BULLET": ["bullets"],
    "DESCRIPTION": ["description"],
    "A_PLUS": ["a_plus_text"],
    "REVIEW_REQUEST": ["review_request_text"],
    "AD_COPY": ["ad_copy"],
    "PRODUCT_CLAIM": ["claims", "title", "bullets", "description", "a_plus_text", "ad_copy"],
    "ACCOUNT_CONDUCT": ["account_conduct", "operation_intent", "seller_action_notes"],
}

EU_MARKETPLACES = {"DE", "FR", "IT", "ES", "NL", "SE", "PL", "BE", "EU"}
RULE_TYPE_RANK = {"SOFT_WARNING": 1, "MEDIUM_RISK": 2, "HIGH_RISK": 3, "HARD_BLOCK": 4}
RULE_TYPE_FROM_SCORE = [
    (90, "HARD_BLOCK"),
    (70, "HIGH_RISK"),
    (40, "MEDIUM_RISK"),
    (10, "SOFT_WARNING"),
]

DISCLAIMER_CN = (
    "系统检测到该内容可能存在亚马逊合规风险。该判断基于亚马逊公开政策规则和类目属性要求，"
    "不代表最终平台审核结果。建议修改后再发布。"
)


@dataclass
class RuleMatch:
    matched: bool
    matched_text: str = ""
    evidence: str = ""


def _rules_path() -> Path:
    return Path(__file__).resolve().parent.parent / "rules" / "amazon_rules.json"


def load_default_rules() -> list[dict[str, Any]]:
    with _rules_path().open("r", encoding="utf-8") as f:
        return json.load(f)


def _json_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(v) for v in parsed]
        except Exception:
            pass
        return [value]
    return [str(value)]


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(_normalize_text(item) for item in value)
    if isinstance(value, dict):
        return "\n".join(f"{k}: {_normalize_text(v)}" for k, v in value.items())
    return str(value)


def _rule_to_dict(rule: AmazonRule | dict[str, Any]) -> dict[str, Any]:
    if isinstance(rule, dict):
        return {
            "allowed_when": "",
            "forbidden_when": "",
            "message_en": "",
            "suggestion_en": "",
            "source_url": "",
            "active": True,
            "version": "1.0.0",
            **rule,
        }
    return {
        "id": rule.id,
        "marketplace": _json_list(rule.marketplace),
        "module": rule.module,
        "rule_type": rule.rule_type,
        "category": rule.category,
        "trigger_type": rule.trigger_type,
        "trigger_patterns": _json_list(rule.trigger_patterns),
        "allowed_when": rule.allowed_when or "",
        "forbidden_when": rule.forbidden_when or "",
        "risk_score": int(rule.risk_score or 0),
        "message_cn": rule.message_cn,
        "message_en": rule.message_en or "",
        "suggestion_cn": rule.suggestion_cn,
        "suggestion_en": rule.suggestion_en or "",
        "source_policy": rule.source_policy,
        "source_url": rule.source_url or "",
        "active": bool(rule.active),
        "version": rule.version or "1.0.0",
        "updated_at": rule.updated_at.isoformat() if rule.updated_at else None,
    }


def _marketplace_matches(rule_marketplaces: list[str], marketplace: str) -> bool:
    mp = (marketplace or "US").upper()
    normalized = {m.upper() for m in rule_marketplaces}
    if "GLOBAL" in normalized or mp in normalized:
        return True
    return "EU" in normalized and mp in EU_MARKETPLACES


def _fields_for_module(module: str, payload: dict[str, Any]) -> str:
    if module == "MAIN_IMAGE":
        return _normalize_text((payload.get("image_analysis") or {}).get("main_image", payload.get("image_analysis")))
    if module == "SECONDARY_IMAGE":
        return _normalize_text((payload.get("image_analysis") or {}).get("secondary_images", payload.get("image_analysis")))
    fields = MODULE_TEXT_FIELDS.get(module, [])
    return "\n".join(_normalize_text(payload.get(field)) for field in fields if payload.get(field) is not None)


def _flatten_image_signals(value: Any) -> set[str]:
    signals: set[str] = set()
    if isinstance(value, dict):
        for key, val in value.items():
            if isinstance(val, bool) and val:
                signals.add(str(key))
            elif isinstance(val, (str, int, float)) and val:
                signals.add(str(key))
                signals.add(str(val))
            elif isinstance(val, (dict, list)):
                signals.update(_flatten_image_signals(val))
    elif isinstance(value, list):
        for item in value:
            signals.update(_flatten_image_signals(item))
    elif isinstance(value, str):
        signals.add(value)
    return {s.strip().lower() for s in signals if s}


def _schema_error_signals(payload: dict[str, Any]) -> set[str]:
    attrs = payload.get("attributes") or {}
    raw_errors = (
        payload.get("schema_errors")
        or payload.get("product_type_schema_errors")
        or attrs.get("schema_errors")
        or attrs.get("_schema_errors")
        or []
    )
    if isinstance(raw_errors, dict):
        raw_errors = [raw_errors]
    signals: set[str] = set()
    for err in raw_errors if isinstance(raw_errors, list) else [raw_errors]:
        if isinstance(err, dict):
            for key in ("code", "type", "reason", "keyword", "message"):
                if err.get(key):
                    signals.add(str(err[key]).strip().lower())
        elif err:
            signals.add(str(err).strip().lower())

    required = payload.get("required_attributes") or attrs.get("_required_attributes") or []
    missing = [name for name in required if name not in attrs or attrs.get(name) in (None, "", [])]
    if missing:
        signals.add("missing_required_attribute")
        signals.update(f"missing_required_attribute:{name}" for name in missing)
    return signals


def _semantic_signals(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("semantic_signals") or payload.get("risk_signals") or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(item).strip().lower() for item in raw if str(item).strip()}


def _keyword_match(patterns: list[str], text: str) -> RuleMatch:
    lowered = text.lower()
    for pattern in patterns:
        needle = pattern.lower().strip()
        if needle and needle in lowered:
            return RuleMatch(True, pattern, f"keyword:{pattern}")
    return RuleMatch(False)


def _regex_match(patterns: list[str], text: str) -> RuleMatch:
    for pattern in patterns:
        try:
            found = re.search(pattern, text)
        except re.error:
            continue
        if found:
            return RuleMatch(True, found.group(0), f"regex:{pattern}")
    return RuleMatch(False)


def _signal_match(patterns: list[str], signals: set[str], prefix_match: bool = True) -> RuleMatch:
    for pattern in patterns:
        p = pattern.strip().lower()
        if not p:
            continue
        if p in signals:
            return RuleMatch(True, pattern, f"signal:{pattern}")
        if prefix_match and any(signal.startswith(p + ":") for signal in signals):
            return RuleMatch(True, pattern, f"signal:{pattern}")
    return RuleMatch(False)


def _semantic_match(patterns: list[str], text: str, signals: set[str]) -> RuleMatch:
    signal_hit = _signal_match(patterns, signals, prefix_match=False)
    if signal_hit.matched:
        return signal_hit
    lowered = re.sub(r"\s+", " ", text.lower())
    for pattern in patterns:
        words = [w for w in re.split(r"[^a-z0-9]+", pattern.lower()) if len(w) > 2]
        if words and sum(1 for word in words if word in lowered) >= max(1, len(words) - 1):
            return RuleMatch(True, pattern, f"semantic:{pattern}")
    return RuleMatch(False)


def _match_rule(rule: dict[str, Any], payload: dict[str, Any]) -> RuleMatch:
    trigger_type = rule["trigger_type"]
    module = rule["module"]
    patterns = _json_list(rule.get("trigger_patterns"))
    text = _fields_for_module(module, payload)

    if trigger_type == "KEYWORD":
        return _keyword_match(patterns, text)
    if trigger_type == "REGEX":
        return _regex_match(patterns, text)
    if trigger_type == "IMAGE_DETECTION":
        return _signal_match(patterns, _flatten_image_signals(payload.get("image_analysis") or {}))
    if trigger_type == "SCHEMA_VALIDATION":
        return _signal_match(patterns, _schema_error_signals(payload))
    if trigger_type in {"SEMANTIC", "CONTEXT_COMBINATION"}:
        combined = "\n".join([text, _normalize_text(payload.get("context")), _normalize_text(payload.get("attributes"))])
        return _semantic_match(patterns, combined, _semantic_signals(payload))
    return RuleMatch(False)


def _overall_level(score: int, blocked: bool, high_count: int, medium_count: int) -> str:
    if blocked or score >= 90:
        return "HARD_BLOCK"
    if high_count or score >= 70:
        return "HIGH_RISK"
    if medium_count or score >= 40:
        return "MEDIUM_RISK"
    if score >= 10:
        return "SOFT_WARNING"
    return "PASS"


def evaluate_amazon_compliance(input_data: dict[str, Any], rules: list[AmazonRule | dict[str, Any]]) -> dict[str, Any]:
    marketplace = str(input_data.get("marketplace") or "US").upper()
    active_rules = [
        _rule_to_dict(rule)
        for rule in rules
        if _rule_to_dict(rule).get("active", True)
        and _marketplace_matches(_json_list(_rule_to_dict(rule).get("marketplace")), marketplace)
    ]

    # Product type schema has priority, then all other copy/image rules.
    active_rules.sort(key=lambda r: 0 if r["module"] == "PRODUCT_TYPE_SCHEMA" else 1)

    violations: list[dict[str, Any]] = []
    for rule in active_rules:
        match = _match_rule(rule, input_data)
        if not match.matched:
            continue
        violations.append({
            "rule_id": rule["id"],
            "module": rule["module"],
            "rule_type": rule["rule_type"],
            "category": rule["category"],
            "trigger_type": rule["trigger_type"],
            "risk_score": rule["risk_score"],
            "matched_text": match.matched_text,
            "message_cn": rule["message_cn"],
            "message_en": rule.get("message_en", ""),
            "suggestion_cn": rule["suggestion_cn"],
            "suggestion_en": rule.get("suggestion_en", ""),
            "source_policy": rule["source_policy"],
            "source_url": rule.get("source_url", ""),
            "allowed_when": rule.get("allowed_when", ""),
            "forbidden_when": rule.get("forbidden_when", ""),
            "evidence": match.evidence,
        })

    high_count = sum(1 for item in violations if item["rule_type"] == "HIGH_RISK")
    hard_count = sum(1 for item in violations if item["rule_type"] == "HARD_BLOCK")
    medium_count = sum(1 for item in violations if item["rule_type"] == "MEDIUM_RISK")
    max_score = max([item["risk_score"] for item in violations], default=0)
    overall_score = min(100, max_score + min(10, max(0, len(violations) - 1) * 2))
    blocked = hard_count > 0 or high_count > 2
    review_required = medium_count > 0 or high_count > 0
    rewrite_suggestions = list(dict.fromkeys(item["suggestion_cn"] for item in violations if item.get("suggestion_cn")))

    return {
        "overall_risk_level": _overall_level(overall_score, blocked, high_count, medium_count),
        "overall_score": overall_score,
        "blocked": blocked,
        "review_required": review_required,
        "violations": violations,
        "rewrite_suggestions": rewrite_suggestions,
        "disclaimer_cn": DISCLAIMER_CN if violations else "",
        "rules_evaluated": len(active_rules),
        "rules_version": sorted({str(rule.get("version") or "1.0.0") for rule in active_rules}),
    }


def evaluateAmazonCompliance(input_data: dict[str, Any], rules: list[AmazonRule | dict[str, Any]]) -> dict[str, Any]:
    """Compatibility alias matching the product spec naming."""
    return evaluate_amazon_compliance(input_data, rules)


async def load_active_rules(db: AsyncSession | None = None) -> list[AmazonRule | dict[str, Any]]:
    if db is None:
        return load_default_rules()
    try:
        result = await db.execute(select(AmazonRule).where(AmazonRule.active == True).order_by(AmazonRule.id))  # noqa: E712
        rows = list(result.scalars().all())
        return rows or load_default_rules()
    except Exception:
        return load_default_rules()


async def seed_default_rules(db: AsyncSession) -> dict[str, int]:
    defaults = load_default_rules()
    existing_result = await db.execute(select(AmazonRule.id))
    existing_ids = {row[0] for row in existing_result.fetchall()}
    created = 0
    updated = 0
    now = datetime.now(timezone.utc)
    for rule in defaults:
        payload = {
            "id": rule["id"],
            "marketplace": json.dumps(rule.get("marketplace", []), ensure_ascii=False),
            "module": rule["module"],
            "rule_type": rule["rule_type"],
            "category": rule["category"],
            "trigger_type": rule["trigger_type"],
            "trigger_patterns": json.dumps(rule.get("trigger_patterns", []), ensure_ascii=False),
            "allowed_when": rule.get("allowed_when", ""),
            "forbidden_when": rule.get("forbidden_when", ""),
            "risk_score": int(rule.get("risk_score") or 0),
            "message_cn": rule["message_cn"],
            "message_en": rule.get("message_en", ""),
            "suggestion_cn": rule["suggestion_cn"],
            "suggestion_en": rule.get("suggestion_en", ""),
            "source_policy": rule["source_policy"],
            "source_url": rule.get("source_url", ""),
            "active": bool(rule.get("active", True)),
            "version": rule.get("version", "1.0.0"),
            "updated_at": now,
        }
        if rule["id"] in existing_ids:
            result = await db.execute(select(AmazonRule).where(AmazonRule.id == rule["id"]).limit(1))
            obj = result.scalar_one_or_none()
            if obj:
                for key, value in payload.items():
                    if key != "id":
                        setattr(obj, key, value)
                updated += 1
        else:
            db.add(AmazonRule(**payload))
            created += 1
    await db.commit()
    return {"created": created, "updated": updated, "total": len(defaults)}
