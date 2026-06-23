from __future__ import annotations
"""AI orchestration — PromptBuilder, ProviderRouter, AIParser.

The pipeline:
  Business Request → Capture & Parse → Standardized Input Schema
  → PromptBuilder → AIProviderRouter → Raw AI Response
  → AIParser → Structured Result → Save + Display
"""

from dataclasses import dataclass, field
from typing import Protocol


# ── Standardized Input Schema ──────────────────────────────

@dataclass
class AnalysisInput:
    """Normalized input passed to PromptBuilder after capture + parse."""
    module: str  # market_opportunity | competitor_analysis | prelaunch | conversion
    marketplace: str
    keyword: str | None = None
    asin: str | None = None
    listing_data: dict | None = None
    listing_materials: dict | None = None


# ── AI Provider Protocol ──────────────────────────────────

@dataclass
class AIResponse:
    raw: str
    provider: str
    model: str
    tokens_used: int = 0


class AIProvider(Protocol):
    """Interface every AI provider must satisfy."""

    async def complete(self, prompt: str, system: str | None = None) -> AIResponse: ...


# ── Parse Result ──────────────────────────────────────────

@dataclass
class ParseResult:
    raw_ai_response: str
    raw_ai_parsed: dict
    parse_status: str  # success | partial | failed
    missing_fields: list[str] = field(default_factory=list)
    mapped_fields: dict = field(default_factory=dict)
    field_completeness_score: float = 0.0
    parse_error: str | None = None


# ── AI Parser Protocol ────────────────────────────────────

class AIParser(Protocol):
    """Parses raw AI output into structured, validated results."""

    async def parse(self, response: AIResponse, expected_schema: dict) -> ParseResult: ...
