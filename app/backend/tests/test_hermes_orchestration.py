import asyncio

from services.agent_chain import (
    HERMES_MODEL_ROUTING_POLICY,
    HermesOrchestrationRequest,
    NODE_DEFINITIONS,
    _normalize_dispatch_plan,
    run_hermes_orchestration,
)


def test_normalize_hermes_dispatch_plan_filters_unknown_nodes():
    plan = _normalize_dispatch_plan(
        {
            "dispatch_order": [
                {"node": "launch_check", "priority": "P0", "status": "ready", "reason": "待录入"},
                {"node": "unknown_agent", "priority": "P0", "status": "ready"},
            ],
            "run_now": ["launch_check", "unknown_agent"],
            "blocked_by": "待录入",
        },
        mode="live",
    )

    assert [step.node for step in plan.dispatch_order] == ["launch_check"]
    assert plan.run_now == ["launch_check"]
    assert plan.blocked_by == ["待录入"]


def test_hermes_dry_run_does_not_execute_nodes():
    chain = {
        "stages": [
            {"key": "selection", "status": "completed"},
            {"key": "launch_check", "status": "missing"},
        ],
    }

    response = asyncio.run(run_hermes_orchestration(chain, HermesOrchestrationRequest(dry_run=True)))

    assert response.plan.mode == "dry_run"
    assert response.plan.run_now == ["launch_check"]
    assert response.executed_nodes == []


def test_hermes_model_routing_policy_defines_stage_boundaries():
    assert NODE_DEFINITIONS["selection"].execution_roles == [
        "scraping",
        "rules",
        "embedding_recall",
        "evidence_rerank",
        "text_reasoning",
    ]
    assert "image_generation" in NODE_DEFINITIONS["selection"].forbidden_model_roles
    assert "vision_ocr" in NODE_DEFINITIONS["launch_check"].execution_roles
    assert "image_generation" in HERMES_MODEL_ROUTING_POLICY["model_roles"]
    assert HERMES_MODEL_ROUTING_POLICY["stage_routes"]["ad_validation"]["default_depth"] == "standard"
