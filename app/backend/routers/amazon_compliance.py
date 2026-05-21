from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.auth import UserResponse
from services.amazon_rules_engine import (
    evaluate_amazon_compliance,
    load_active_rules,
    load_default_rules,
    seed_default_rules,
)

router = APIRouter(prefix="/api/v1/amazon-compliance", tags=["amazon-compliance"])


ModuleType = Literal[
    "TITLE",
    "BULLET",
    "DESCRIPTION",
    "A_PLUS",
    "MAIN_IMAGE",
    "SECONDARY_IMAGE",
    "REVIEW_REQUEST",
    "AD_COPY",
    "PRODUCT_CLAIM",
    "ACCOUNT_CONDUCT",
    "PRODUCT_TYPE_SCHEMA",
]

RuleType = Literal["HARD_BLOCK", "HIGH_RISK", "MEDIUM_RISK", "SOFT_WARNING"]
TriggerType = Literal["KEYWORD", "REGEX", "SEMANTIC", "IMAGE_DETECTION", "SCHEMA_VALIDATION", "CONTEXT_COMBINATION"]


class AmazonRulePayload(BaseModel):
    id: str
    marketplace: list[str] = Field(default_factory=lambda: ["GLOBAL"])
    module: ModuleType
    rule_type: RuleType
    category: str
    trigger_type: TriggerType
    trigger_patterns: list[str]
    allowed_when: str = ""
    forbidden_when: str = ""
    risk_score: int = Field(ge=0, le=100)
    message_cn: str
    message_en: str = ""
    suggestion_cn: str
    suggestion_en: str = ""
    source_policy: str
    source_url: str = ""
    active: bool = True
    version: str = "1.0.0"
    updated_at: str | None = None


class AmazonComplianceInput(BaseModel):
    marketplace: str = "US"
    product_type: str = ""
    title: str = ""
    bullets: str | list[str] = ""
    description: str = ""
    a_plus_text: str = ""
    image_analysis: dict[str, Any] = Field(default_factory=dict)
    review_request_text: str = ""
    ad_copy: str = ""
    claims: str | list[str] = ""
    attributes: dict[str, Any] = Field(default_factory=dict)
    schema_errors: list[Any] = Field(default_factory=list)
    semantic_signals: list[str] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    context: dict[str, Any] | str = Field(default_factory=dict)
    account_conduct: str = ""
    operation_intent: str = ""
    seller_action_notes: str = ""


class AmazonComplianceViolation(BaseModel):
    rule_id: str
    module: ModuleType
    rule_type: RuleType
    category: str
    trigger_type: TriggerType
    risk_score: int
    matched_text: str = ""
    message_cn: str
    message_en: str = ""
    suggestion_cn: str
    suggestion_en: str = ""
    source_policy: str
    source_url: str = ""
    allowed_when: str = ""
    forbidden_when: str = ""
    evidence: str = ""


class AmazonComplianceResponse(BaseModel):
    overall_risk_level: str
    overall_score: int
    blocked: bool
    review_required: bool
    violations: list[AmazonComplianceViolation]
    rewrite_suggestions: list[str]
    disclaimer_cn: str = ""
    rules_evaluated: int
    rules_version: list[str]


@router.post("/evaluate", response_model=AmazonComplianceResponse)
async def evaluate_amazon_compliance_api(
    payload: AmazonComplianceInput,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Evaluate Amazon compliance risk. This is a risk screen, not a compliance guarantee."""
    try:
        rules = await load_active_rules(db)
        result = evaluate_amazon_compliance(payload.model_dump(), rules)
        return AmazonComplianceResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Amazon合规规则评估失败: {e}") from e


@router.get("/rules", response_model=list[AmazonRulePayload])
async def list_amazon_rules(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rules = await load_active_rules(db)
    from services.amazon_rules_engine import _rule_to_dict

    return [AmazonRulePayload(**_rule_to_dict(rule)) for rule in rules]


@router.post("/rules/seed")
async def seed_amazon_rules(
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Seed or update the default Amazon compliance rules into the database."""
    return await seed_default_rules(db)


@router.get("/rules/default", response_model=list[AmazonRulePayload])
async def list_default_amazon_rules(current_user: UserResponse = Depends(get_current_user)):
    return [AmazonRulePayload(**rule) for rule in load_default_rules()]
