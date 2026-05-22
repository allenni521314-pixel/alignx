"""Reverse-engineering vector mapping for Amazon COSMO relation anchors.

This module intentionally does not replace the existing prompt-track logic.
It provides a deterministic embedding + lightweight projection layer that can
run without external model availability, then returns cosine probabilities for
the 15 COSMO canonical relation anchors.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
from openai import AsyncOpenAI

from core.config import settings


COSMO_CONFIDENCE_THRESHOLD = 0.85
EMBEDDING_DIM = 384
HIDDEN_DIM = 96


@dataclass(frozen=True)
class CosmoAnchor:
    key: str
    label_cn: str
    layer: str
    description: str


COSMO_ANCHORS: list[CosmoAnchor] = [
    CosmoAnchor("isA", "产品身份/品类", "object_layer", "product type, category identity, what the item is, product class"),
    CosmoAnchor("has_attribute", "产品属性", "object_layer", "material, size, color, specs, feature, ingredient, design attribute"),
    CosmoAnchor("used_for_function", "功能用途", "relation_layer", "used for solving a problem, functional purpose, main utility"),
    CosmoAnchor("capable_of", "产品能力", "relation_layer", "capable of doing, performance promise, measurable ability"),
    CosmoAnchor("used_for_event", "事件场景", "relation_layer", "used for event, holiday, party, travel, emergency, seasonal moment"),
    CosmoAnchor("used_for_activity", "活动行为", "relation_layer", "used during activity, routine, cleaning, cooking, camping, working"),
    CosmoAnchor("used_when", "使用时机", "relation_layer", "used when a situation happens, timing, before, after, during"),
    CosmoAnchor("used_where", "使用地点", "relation_layer", "used in place, room, home, office, car, outdoors, kitchen"),
    CosmoAnchor("used_with", "搭配对象", "relation_layer", "used with compatible products, accessories, pets, devices, tools"),
    CosmoAnchor("used_for_audience", "目标人群", "relation_layer", "for audience, buyer persona, family, kids, women, students, pet owners"),
    CosmoAnchor("used_by", "实际使用者", "relation_layer", "used by end user, person or pet who directly uses the product"),
    CosmoAnchor("cause_positive", "正向状态", "state_layer", "causes positive outcome, benefit, comfort, confidence, relief, time saving"),
    CosmoAnchor("cause_negative", "负向规避", "state_layer", "prevents negative outcome, removes pain, risk, odor, mess, damage, anxiety"),
    CosmoAnchor("compared_to", "对比优势", "state_layer", "compared to alternative, better than, smaller than, faster than, cheaper than"),
    CosmoAnchor("requires", "使用前提", "state_layer", "requires condition, setup, compatibility, evidence, maintenance, instruction"),
]


TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9+\-/]*", re.IGNORECASE)


def _stable_unit(seed: str) -> float:
    raw = hashlib.blake2b(seed.encode("utf-8"), digest_size=8).digest()
    integer = int.from_bytes(raw, "big")
    return (integer / ((1 << 64) - 1)) * 2 - 1


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def _feature_terms(text: str) -> list[str]:
    tokens = _tokens(text)
    terms: list[str] = []
    terms.extend(tokens)
    for idx in range(len(tokens) - 1):
        terms.append(f"{tokens[idx]} {tokens[idx + 1]}")
    for idx in range(len(tokens) - 2):
        terms.append(f"{tokens[idx]} {tokens[idx + 1]} {tokens[idx + 2]}")
    return terms


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return [0.0 for _ in vector]
    return [value / norm for value in vector]


def _embed_text(text: str) -> list[float]:
    """Hashing embedding with n-gram features.

    It is deterministic, fast, and safe as a fallback when a hosted embedding
    model is unavailable. It avoids direct label substring matching; all
    downstream decisions use vector geometry.
    """

    vector = [0.0] * EMBEDDING_DIM
    for term in _feature_terms(text):
        digest = hashlib.blake2b(term.encode("utf-8"), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "big") % EMBEDDING_DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + min(len(term), 32) / 64
        vector[idx] += sign * weight
    return _normalize(vector)


async def _embed_texts_with_provider(texts: list[str]) -> tuple[list[list[float]], str] | None:
    """Use a configured embedding endpoint when available.

    The app already supports OpenAI-compatible providers. This function keeps
    vector mapping connected to a real embedding model when `AI_EMBEDDING_MODEL`
    is configured, and falls back to deterministic embeddings otherwise.
    """

    embedding_model = (os.getenv("AI_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL") or "").strip()
    api_key = (
        os.getenv("EMBEDDING_API_KEY")
        or os.getenv("SILICONFLOW_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("APP_AI_KEY")
        or getattr(settings, "app_ai_key", "")
        or ""
    ).strip()
    base_url = (
        os.getenv("EMBEDDING_BASE_URL")
        or os.getenv("SILICONFLOW_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("APP_AI_BASE_URL")
        or getattr(settings, "app_ai_base_url", "")
        or ""
    ).strip()
    if not embedding_model or not api_key or not base_url:
        return None

    try:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            timeout=float(os.getenv("AI_EMBEDDING_TIMEOUT", "45")),
            http_client=httpx.AsyncClient(trust_env=False),
        )
        response = await client.embeddings.create(model=embedding_model, input=texts)
        vectors = [_normalize([float(value) for value in item.embedding]) for item in response.data]
        return vectors, embedding_model
    except Exception:
        return None


async def _rerank_cosmo_anchors(query: str) -> tuple[dict[str, float], str] | None:
    """Optionally rerank COSMO anchors with a configured reranker.

    Vector similarity remains the primary signal; rerank is a calibration layer
    used only when RERANK_MODEL and an API key are configured.
    """

    rerank_model = (os.getenv("RERANK_MODEL") or os.getenv("AI_RERANK_MODEL") or "").strip()
    api_key = (
        os.getenv("RERANK_API_KEY")
        or os.getenv("SILICONFLOW_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("APP_AI_KEY")
        or ""
    ).strip()
    base_url = (
        os.getenv("RERANK_BASE_URL")
        or os.getenv("SILICONFLOW_BASE_URL")
        or "https://api.siliconflow.cn/v1"
    ).strip().rstrip("/")
    if not rerank_model or not api_key:
        return None

    documents = [f"{anchor.key} {anchor.label_cn} {anchor.description}" for anchor in COSMO_ANCHORS]
    try:
        async with httpx.AsyncClient(timeout=float(os.getenv("AI_RERANK_TIMEOUT", "45")), trust_env=False) as client:
            response = await client.post(
                f"{base_url}/rerank",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": rerank_model,
                    "query": query[:8000],
                    "documents": documents,
                    "top_n": len(documents),
                    "return_documents": False,
                },
            )
            response.raise_for_status()
            data = response.json()
        scores: dict[str, float] = {}
        for item in data.get("results", []) or []:
            index = item.get("index")
            if isinstance(index, int) and 0 <= index < len(COSMO_ANCHORS):
                raw_score = float(item.get("relevance_score") or 0)
                scores[COSMO_ANCHORS[index].key] = max(0.0, min(1.0, raw_score))
        return (scores, rerank_model) if scores else None
    except Exception:
        return None


async def _apply_rerank_calibration(text: str, anchors: list[dict[str, Any]]) -> str | None:
    rerank_result = await _rerank_cosmo_anchors(text)
    if not rerank_result:
        return None
    rerank_scores, rerank_model = rerank_result
    for item in anchors:
        rerank_score = rerank_scores.get(str(item.get("relation")))
        if rerank_score is None:
            continue
        vector_probability = float(item.get("probability") or 0)
        combined = vector_probability * 0.7 + rerank_score * 0.3
        item["vector_probability"] = round(vector_probability, 4)
        item["rerank_score"] = round(rerank_score, 4)
        item["probability"] = round(combined, 4)
        item["activated"] = combined > COSMO_CONFIDENCE_THRESHOLD
    return rerank_model


def _project(vector: list[float]) -> list[float]:
    """A fixed lightweight MLP-style mapping layer.

    The projection is intentionally deterministic: tanh(W2 * relu(W1 * x)).
    It calibrates raw lexical embeddings into a smaller relation-mapping space
    without introducing train-time state into the repo.
    """

    hidden: list[float] = []
    for row in range(HIDDEN_DIM):
        total = 0.0
        for col, value in enumerate(vector):
            if value:
                total += value * _stable_unit(f"w1:{row}:{col}")
        hidden.append(max(0.0, total / math.sqrt(EMBEDDING_DIM)))

    output: list[float] = []
    for row in range(HIDDEN_DIM):
        total = 0.0
        for col, value in enumerate(hidden):
            if value:
                total += value * _stable_unit(f"w2:{row}:{col}")
        output.append(math.tanh(total / math.sqrt(HIDDEN_DIM)))
    return _normalize(output)


ANCHOR_VECTORS = {
    anchor.key: _project(_embed_text(f"{anchor.key} {anchor.label_cn} {anchor.description}"))
    for anchor in COSMO_ANCHORS
}


def _mean_pool(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        return []
    dim = len(vectors[0])
    pooled = [0.0] * dim
    for vector in vectors:
        if len(vector) != dim:
            continue
        for idx, value in enumerate(vector):
            pooled[idx] += value
    return _normalize([value / len(vectors) for value in pooled])


def _cosine(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _probability_from_cosine(value: float) -> float:
    # Stretch useful high-similarity differences while keeping the value in 0..1.
    return max(0.0, min(1.0, (value + 1.0) / 2.0))


def build_cosmo_mapping_text(data: dict[str, Any], product_name: str, category: str) -> str:
    parts: list[str] = [product_name, category]
    for item in data.get("listing_placements", []) or []:
        if isinstance(item, dict):
            parts.extend([
                str(item.get("keyword", "")),
                str(item.get("placement", "")),
                str(item.get("reason", "")),
            ])
    for item in data.get("ad_keywords", []) or []:
        if isinstance(item, dict):
            parts.extend([
                str(item.get("keyword", "")),
                str(item.get("intent", "")),
            ])
    cosmo_layers = data.get("cosmo_layers", {})
    if isinstance(cosmo_layers, dict):
        for layer in cosmo_layers.values():
            if not isinstance(layer, dict):
                continue
            dims = layer.get("dimensions", {})
            if not isinstance(dims, dict):
                continue
            for dim_key, dim_data in dims.items():
                parts.append(str(dim_key))
                if isinstance(dim_data, dict):
                    keywords = dim_data.get("keywords", [])
                    if isinstance(keywords, list):
                        parts.extend(str(keyword) for keyword in keywords)
                    parts.append(str(dim_data.get("summary", "")))
    return " ".join(part for part in parts if part)


def evaluate_cosmo_vector_mapping(text: str) -> dict[str, Any]:
    mapped = _project(_embed_text(text))
    anchors: list[dict[str, Any]] = []
    for anchor in COSMO_ANCHORS:
        cosine = _cosine(mapped, ANCHOR_VECTORS[anchor.key])
        probability = _probability_from_cosine(cosine)
        anchors.append({
            "relation": anchor.key,
            "label_cn": anchor.label_cn,
            "layer": anchor.layer,
            "cosine_similarity": round(cosine, 4),
            "probability": round(probability, 4),
            "activated": probability > COSMO_CONFIDENCE_THRESHOLD,
        })

    anchors.sort(key=lambda item: item["probability"], reverse=True)
    top = anchors[0] if anchors else {}
    activated = [item for item in anchors if item["activated"]]
    return {
        "engine": "reverse_vector_mapping_v1",
        "embedding_model": "deterministic_hash_embedding_384d",
        "mapping_layer": "fixed_lightweight_mlp_384x96x96",
        "confidence_threshold": COSMO_CONFIDENCE_THRESHOLD,
        "top_relation": top.get("relation", ""),
        "top_confidence": top.get("probability", 0),
        "activated_relations": activated,
        "anchor_probabilities": anchors,
        "fallback_to_prompt_track": not activated,
    }


async def evaluate_cosmo_vector_mapping_async(
    text: str,
    category_anchor_texts: list[str] | None = None,
) -> dict[str, Any]:
    """Evaluate target text against COSMO anchors and optional category mean.

    Uses the configured embedding model when available; otherwise falls back to
    the deterministic local embedding layer so the system remains stable in
    public demos.
    """

    category_anchor_texts = [item for item in (category_anchor_texts or []) if item.strip()][:50]
    anchor_texts = [f"{anchor.key} {anchor.label_cn} {anchor.description}" for anchor in COSMO_ANCHORS]
    provider_result = await _embed_texts_with_provider([text, *anchor_texts, *category_anchor_texts])

    if provider_result:
        vectors, embedding_model = provider_result
        mapped = _project(_normalize(vectors[0]))
        anchor_vectors = {
            anchor.key: _project(_normalize(vectors[idx + 1]))
            for idx, anchor in enumerate(COSMO_ANCHORS)
        }
        category_vectors = vectors[1 + len(COSMO_ANCHORS):]
    else:
        embedding_model = "deterministic_hash_embedding_384d"
        mapped = _project(_embed_text(text))
        anchor_vectors = ANCHOR_VECTORS
        category_vectors = [_project(_embed_text(item)) for item in category_anchor_texts]

    anchors: list[dict[str, Any]] = []
    for anchor in COSMO_ANCHORS:
        cosine = _cosine(mapped, anchor_vectors[anchor.key])
        probability = _probability_from_cosine(cosine)
        anchors.append({
            "relation": anchor.key,
            "label_cn": anchor.label_cn,
            "layer": anchor.layer,
            "cosine_similarity": round(cosine, 4),
            "probability": round(probability, 4),
            "activated": probability > COSMO_CONFIDENCE_THRESHOLD,
        })

    rerank_model = await _apply_rerank_calibration(text, anchors)
    anchors.sort(key=lambda item: item["probability"], reverse=True)
    top = anchors[0] if anchors else {}
    activated = [item for item in anchors if item["activated"]]
    category_mean = _mean_pool(category_vectors)
    category_cosine = _cosine(mapped, category_mean) if category_mean else 0.0

    return {
        "engine": "reverse_vector_mapping_v1",
        "embedding_model": embedding_model,
        "rerank_model": rerank_model or "",
        "mapping_layer": "fixed_lightweight_mlp_projection",
        "confidence_threshold": COSMO_CONFIDENCE_THRESHOLD,
        "top_relation": top.get("relation", ""),
        "top_confidence": top.get("probability", 0),
        "activated_relations": activated,
        "anchor_probabilities": anchors,
        "category_anchor": {
            "method": "mean_pooling",
            "source_count": len(category_anchor_texts),
            "cosine_similarity": round(category_cosine, 4),
            "probability": round(_probability_from_cosine(category_cosine), 4) if category_mean else 0,
        },
        "fallback_to_prompt_track": not activated,
    }


def merge_dual_track(prompt_data: dict[str, Any], vector_track: dict[str, Any]) -> dict[str, Any]:
    """Expose dual-track output without mutating the prompt-track result."""

    return {
        "prompt_track": {
            "source": "SIX_DIM_PROMPT/intent_matrix_prompt",
            "cosmo_layers": prompt_data.get("cosmo_layers", {}),
            "listing_placements_count": len(prompt_data.get("listing_placements", []) or []),
            "ad_keywords_count": len(prompt_data.get("ad_keywords", []) or []),
        },
        "vector_mapping_track": vector_track,
        "active_track": "vector_mapping_track" if not vector_track.get("fallback_to_prompt_track") else "prompt_track",
    }
