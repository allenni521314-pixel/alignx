"""
AI Gateway router.

These endpoints expose a safe model-switching layer for AlignX agents without
changing current business modules or frontend navigation.
"""

import logging

from dependencies.auth import get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from schemas.auth import UserResponse
from services.ai_gateway import AgentRequest, AgentResponse, AIGatewayService, AIGatewayStatus
from services.model_invocation_contract import judgment_standard_summary

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai-gateway", tags=["ai-gateway"])


@router.get("/status", response_model=AIGatewayStatus)
async def get_ai_gateway_status():
    """Return provider/model configuration status without exposing secrets."""
    return AIGatewayService().status()


@router.get("/judgment-standard")
async def get_judgment_standard():
    """Return the unified evidence, decision, and learning standard for AlignX agents."""
    return judgment_standard_summary()


@router.post("/agent", response_model=AgentResponse)
async def run_ai_agent(request: AgentRequest, _current_user: UserResponse = Depends(get_current_user)):
    """
    Run an AlignX decision agent.

    By default requests use `dry_run=true`, so this endpoint can be tested before
    adding any real model API key. Set `dry_run=false` after configuring a provider.
    """
    try:
        return await AIGatewayService().run_agent(request)
    except RuntimeError as exc:
        logger.warning("AI Gateway unavailable: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("AI Gateway request failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
