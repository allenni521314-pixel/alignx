"""
Intent Matrix Router.
Provides one-click ASIN/product analysis that combines COSMO 3-Layer 12-Dimension
semantic model + Rufus consumer intent engine, then outputs:
  1. Listing intent keyword placement plan (Title/Bullets/Description/Backend/A+)
  2. Ad intent keywords (SP exact/broad, SB brand, SD display)

COSMO 3-Layer 12-Dimension Model (Strictly Non-Overlapping):
  Layer 1 (对象层 Object Layer, 2 dims): isA, has_attribute
  Layer 2 (关系层 Relation Layer, 7 dims): used_for_function, capable_of, used_for_event, used_when, used_where, used_with, used_for_audience
  Layer 3 (状态层 State Layer, 3 dims): cause_positive, cause_negative, compared_to

The Relation Layer and State Layer are the core of conversion in the AI agent era,
going beyond traditional keyword matching to semantic understanding.
"""

import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.auth import UserResponse
from services.aihub import AIHubService
from schemas.aihub import GenTxtRequest, ChatMessage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intent-matrix", tags=["intent-matrix"])


# ---------- Request / Response Models ----------

class AnalyzeRequest(BaseModel):
    asin_or_name: str = ""
    category: str = ""
    marketplace: str = "US"


class ListingPlacement(BaseModel):
    keyword: str = ""
    placement: str = ""
    layer: str = ""
    layer_name: str = ""
    dimension: str = ""
    intent_type: str = ""
    reason: str = ""


class AdKeyword(BaseModel):
    keyword: str = ""
    match_type: str = ""
    ad_type: str = ""
    layer: str = ""
    layer_name: str = ""
    dimension: str = ""
    intent: str = ""
    priority: str = ""
    estimated_competition: str = ""


class AnalyzeResponse(BaseModel):
    product_name: str = ""
    category: str = ""
    listing_placements: list[ListingPlacement] = []
    listing_summary: str = ""
    ad_keywords: list[AdKeyword] = []
    ad_summary: str = ""
    cosmo_layers: dict = {}
    cross_layer_insights: list[dict] = []
    rufus_intents: list[dict] = []
    overall_strategy: str = ""


# ---------- 3-Layer 12-Dimension Mapping (Strictly Non-Overlapping) ----------

LAYER_DIMENSION_MAP = {
    "object_layer": {
        "name": "对象层",
        "name_en": "Object Layer",
        "dimensions": ["isA", "has_attribute"],
    },
    "relation_layer": {
        "name": "关系层",
        "name_en": "Relation Layer",
        "dimensions": ["used_for_function", "capable_of", "used_for_event", "used_when", "used_where", "used_with", "used_for_audience"],
    },
    "state_layer": {
        "name": "状态层",
        "name_en": "State Layer",
        "dimensions": ["cause_positive", "cause_negative", "compared_to"],
    },
}

LAYER_NAMES = {
    "object_layer": "对象层",
    "relation_layer": "关系层",
    "state_layer": "状态层",
}

# Reverse lookup: dimension -> (layer_key, layer_name)
DIM_TO_LAYER = {}
for layer_key, layer_info in LAYER_DIMENSION_MAP.items():
    for dim in layer_info["dimensions"]:
        DIM_TO_LAYER[dim] = (layer_key, layer_info["name"])


# ---------- AI Prompt ----------

COMBINED_ANALYSIS_PROMPT = """你是一位顶级Amazon COSMO语义算法专家，精通COSMO知识图谱的3层12维语义模型和Rufus消费者意图引擎。

## 核心理念
COSMO的3层12维模型不是传统关键词思维。在AI代理时代，**关系层和状态层**才是转化率的核心驱动力。
- 传统SEO只关注"产品是什么"（对象层）
- COSMO语义引擎关注"产品与消费者生活的关系"（关系层）和"产品引起的状态变化"（状态层）
- Rufus等AI购物代理通过理解关系和状态来推荐产品，而非简单关键词匹配

## COSMO 3层12维语义模型（严格不重叠）

### 第1层：对象层 Object Layer（2个维度）
描述产品本身"是什么"和"有什么属性"：
1. **isA** — 产品的品类归属、类型定义（"这是一个什么"）
   - 例：GaN charger, USB-C fast charger, portable power adapter
2. **has_attribute** — 产品的固有属性、规格、特征（"它有什么特点"）
   - 例：65W output, foldable plug, compact size, matte black finish

### 第2层：关系层 Relation Layer（7个维度）
描述产品与外部世界的语义关系——这是AI代理理解产品价值的核心：
3. **used_for_function** — 产品用于什么功能/目的（"用来做什么"）
   - 例：fast charging phones, powering laptops, replacing bulky chargers
4. **capable_of** — 产品能够做到什么（"能做到什么"）
   - 例：charges MacBook Air in 90 minutes, supports PD 3.0 protocol
5. **used_for_event** — 产品用于什么事件/活动（"在什么事件中使用"）
   - 例：business travel, back-to-school, holiday gifting, emergency prep
6. **used_when** — 产品在什么时间/时机使用（"什么时候用"）
   - 例：overnight charging, morning rush, during meetings, on the go
7. **used_where** — 产品在什么地点/空间使用（"在哪里用"）
   - 例：airport lounge, dorm room, coffee shop, bedside nightstand
8. **used_with** — 产品与什么搭配使用（"和什么一起用"）
   - 例：with iPhone 15, with MacBook Air, with MagSafe case, with USB-C cable
9. **used_for_audience** — 产品面向什么人群（"给谁用"）
   - 例：for business travelers, for college students, for Apple ecosystem users

### 第3层：状态层 State Layer（3个维度）
描述产品引起的状态变化——这是转化率的终极驱动力：
10. **cause_positive** — 产品带来什么正面状态/情感（"带来什么好处"）
    - 例：eliminates battery anxiety, saves 2 hours daily, feels premium
11. **cause_negative** — 产品消除/预防什么负面状态（"防止什么问题"）
    - 例：prevents overheating damage, no more tangled cables, stops slow charging frustration
12. **compared_to** — 产品相比什么有优势（"比什么好"）
    - 例：60% cheaper than Apple charger, 3x faster than included charger, half the size of competitors

## 任务
对以下产品进行COSMO 3层12维深度语义分析：

### 产品信息
- 产品: {product_name}
- 品类: {category}
- 站点: Amazon {marketplace}

## 输出要求

### 第一部分：Listing意图词句分配方案
为每个意图词句标注所属层级和维度。

放置位置规则：
- **Title**: 对象层(isA/has_attribute)的核心品类词 + 关系层的高搜索量功能词
- **Bullet Points**: 关系层(used_for_function/capable_of/used_with)的利益点 + 状态层(cause_positive)的情感诉求
- **Description/A+ Content**: 状态层(cause_positive/cause_negative/compared_to)的情感故事和对比
- **Backend Keywords**: 关系层(used_for_event/used_when/used_where/used_for_audience)的长尾场景词

### 第二部分：广告意图词句
广告类型：SP(精准/广泛/词组匹配)、SB(品牌广告)、SD(展示广告)

## 输出JSON格式
{{
  "product_name": "产品名称",
  "category": "品类",
  "listing_placements": [
    {{
      "keyword": "意图词句（美式英语）",
      "placement": "Title/Bullet Points/Description/Backend Keywords/A+ Content",
      "layer": "object_layer/relation_layer/state_layer",
      "dimension": "isA/has_attribute/used_for_function/capable_of/used_for_event/used_when/used_where/used_with/used_for_audience/cause_positive/cause_negative/compared_to",
      "intent_type": "primary/secondary/long_tail",
      "reason": "为什么放在这个位置（包含COSMO语义洞察）"
    }}
  ],
  "listing_summary": "Listing分配策略总结（重点说明关系层和状态层如何驱动转化）",
  "ad_keywords": [
    {{
      "keyword": "广告关键词（美式英语）",
      "match_type": "exact/broad/phrase",
      "ad_type": "SP/SB/SD",
      "layer": "object_layer/relation_layer/state_layer",
      "dimension": "12维中的一个",
      "intent": "搜索意图描述",
      "priority": "P0/P1/P2",
      "estimated_competition": "high/medium/low"
    }}
  ],
  "ad_summary": "广告策略总结",
  "cosmo_layers": {{
    "object_layer": {{
      "name": "对象层",
      "dimensions": {{
        "isA": {{ "keywords": ["kw1", "kw2", ...], "summary": "品类归属分析" }},
        "has_attribute": {{ "keywords": ["kw1", "kw2", ...], "summary": "属性特征分析" }}
      }},
      "layer_summary": "对象层整体分析：产品本身的定义和属性"
    }},
    "relation_layer": {{
      "name": "关系层",
      "dimensions": {{
        "used_for_function": {{ "keywords": [...], "summary": "..." }},
        "capable_of": {{ "keywords": [...], "summary": "..." }},
        "used_for_event": {{ "keywords": [...], "summary": "..." }},
        "used_when": {{ "keywords": [...], "summary": "..." }},
        "used_where": {{ "keywords": [...], "summary": "..." }},
        "used_with": {{ "keywords": [...], "summary": "..." }},
        "used_for_audience": {{ "keywords": [...], "summary": "..." }}
      }},
      "layer_summary": "关系层整体分析：产品与消费者生活的7种语义关系，这是AI代理时代转化率的核心"
    }},
    "state_layer": {{
      "name": "状态层",
      "dimensions": {{
        "cause_positive": {{ "keywords": [...], "summary": "..." }},
        "cause_negative": {{ "keywords": [...], "summary": "..." }},
        "compared_to": {{ "keywords": [...], "summary": "..." }}
      }},
      "layer_summary": "状态层整体分析：产品引起的状态变化，这是转化率的终极驱动力"
    }}
  }},
  "cross_layer_insights": [
    {{ "from_layer": "对象层", "to_layer": "关系层", "insight": "产品属性如何映射到使用关系" }},
    {{ "from_layer": "关系层", "to_layer": "状态层", "insight": "使用关系如何转化为状态变化（转化率核心路径）" }},
    {{ "from_layer": "对象层", "to_layer": "状态层", "insight": "产品属性直接引起的状态变化" }}
  ],
  "rufus_intents": [
    {{ "keyword": "消费者意图", "weight": 85, "source": "category_search/review_qa", "layer": "object_layer/relation_layer/state_layer", "dimension": "12维之一", "actionable": "可执行建议" }}
  ],
  "overall_strategy": "整体策略（重点阐述：传统SEO只优化对象层，而COSMO时代需要重点优化关系层和状态层来提升AI代理推荐的转化率）"
}}

## 关键要求（极其重要！AlignX的核心价值 = 最大化呈现关系词和状态触发词的全景图）

### 🔴 最重要：关键词生成规则（必须严格遵守！）
**绝对不要刻意生成2个词的固定模板！** 
- 关键词长度**必须多样化**：1词（如"charger"）、2词（如"fast charger"）、3词（如"65W fast charger"）、4词+（如"USB C fast charger 65W"）都要有
- 根据产品特性**自动分析**生成真实的Amazon搜索词，不是套用模板
- 长尾关键词（3-4词）占比应达到40%以上，这是真实流量的主要来源
- 每个维度的关键词必须是该产品在Amazon上真实用户会搜索的词句

### 数量要求（必须严格遵守！）
1. **Listing词句至少50个**，必须覆盖全部3层12个维度，每个维度都不能为空
2. **广告关键词至少30个**，重点覆盖关系层和状态层
3. **对象层(2维)**: 每维度至少5个关键词（isA至少5个, has_attribute至少5个）
4. **关系层(7维)**: 每维度至少5-8个关键词！这是核心差异化！
   - used_for_function: 至少6个（功能用途是最基础的关系）
   - capable_of: 至少5个（产品能力是转化关键）
   - used_for_event: 至少5个（事件场景覆盖越广越好）
   - used_when: 至少5个（时机触发词）
   - used_where: 至少5个（地点场景词）
   - used_with: 至少5个（搭配生态词）
   - used_for_audience: 至少5个（人群定位词）
5. **状态层(3维)**: 每维度至少6个关键词！这是转化终极驱动力！
   - cause_positive: 至少6个（正面状态触发词越多越好）
   - cause_negative: 至少6个（消除负面的词句是高转化率关键）
   - compared_to: 至少6个（对比优势词是决策临门一脚）
6. **keyword字段**必须是美式英语（这是Amazon搜索词）
7. **重点**：关系层+状态层的词句数量必须占总数的75%以上（这是COSMO和AlignX的核心价值——帮卖家最大化呈现关系和状态触发词的全景图）
8. cross_layer_insights必须包含3条跨层洞察
9. Rufus意图至少12个，重点覆盖关系层和状态层维度
10. 每个dimension严格只属于一个layer，不能重叠
11. **cosmo_layers中每个维度的keywords数组必须包含至少5个关键词**，这是全景图的基础数据
12. **关键词多样性验证**：检查所有关键词，确保1词、2词、3词、4词+的分布约为20%:40%:30%:10%</to_replace>
</Editor.edit_file_by_replace>

Now update the system message to emphasize maximizing relation+state coverage:

<Editor.edit_file_by_replace>
<file_name>/workspace/app/backend/routers/intent_matrix.py</file_name>
<to_replace>    system_msg = (
        f"你是Amazon COSMO 3层12维语义算法顶级专家。"
        f"COSMO 3层模型：对象层(isA, has_attribute)、关系层(used_for_function, capable_of, used_for_event, used_when, used_where, used_with, used_for_audience)、状态层(cause_positive, cause_negative, compared_to)。"
        f"2+7+3=12维，严格不重叠。关系层和状态层是AI代理时代转化率的核心。"
        f"你正在分析: {product_name}。"
        f"极其重要的语言规则：keyword字段用美式英语，但reason、summary、intent、actionable、insight、listing_summary、ad_summary、overall_strategy、layer_summary等所有描述性字段必须全部用中文输出！"
        f"只输出JSON。"
    )</to_replace>
<new_content>    system_msg = (
        f"你是Amazon COSMO 3层12维语义算法顶级专家。"
        f"COSMO 3层模型：对象层(isA, has_attribute)、关系层(used_for_function, capable_of, used_for_event, used_when, used_where, used_with, used_for_audience)、状态层(cause_positive, cause_negative, compared_to)。"
        f"2+7+3=12维，严格不重叠。关系层和状态层是AI代理时代转化率的核心。"
        f"你正在分析: {product_name}。"
        f"【最重要的任务】AlignX的核心价值是帮卖家把关系词和状态触发词尽可能全部呈现为全景图。"
        f"你必须为每个维度生成至少5-8个不同的关键词，特别是关系层7维和状态层3维。"
        f"关系层+状态层的词句必须占总数75%以上。cosmo_layers中每个维度的keywords数组至少5个词。"
        f"极其重要的语言规则：keyword字段用美式英语，但reason、summary、intent、actionable、insight、listing_summary、ad_summary、overall_strategy、layer_summary等所有描述性字段必须全部用中文输出！"
        f"只输出JSON。"
    )

## 语言要求（极其重要！）
- **keyword字段**: 美式英语（Amazon搜索关键词）
- **reason字段**: 必须用中文，解释为什么放在这个位置
- **listing_summary字段**: 必须用中文，总结Listing分配策略
- **ad_summary字段**: 必须用中文，总结广告策略
- **intent字段**: 必须用中文，描述搜索意图
- **actionable字段**: 必须用中文，给出可执行建议
- **summary字段**: 必须用中文，总结每个维度的分析
- **layer_summary字段**: 必须用中文，总结每层的分析
- **overall_strategy字段**: 必须用中文，给出整体策略
- **insight字段**: 必须用中文，给出跨层洞察
- 除了keyword以外的所有描述性文字，全部用中文输出！

只返回JSON，不要返回其他内容。"""


def _extract_json(text: str) -> dict:
    """Extract JSON from AI response text."""
    if not text or not text.strip():
        raise ValueError("Empty AI response")

    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    if start == -1:
        raise ValueError("No JSON object found")
    end = text.rfind("}") + 1
    if end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass

    json_text = text[start:]
    open_braces = json_text.count("{") - json_text.count("}")
    open_brackets = json_text.count("[") - json_text.count("]")
    suffix = "]" * max(0, open_brackets) + "}" * max(0, open_braces)
    try:
        return json.loads(json_text + suffix)
    except json.JSONDecodeError:
        raise ValueError(f"Failed to parse JSON: {text[:300]}")


def _enrich_layer_info(item: dict) -> dict:
    """Add layer_name based on dimension key."""
    dim = item.get("dimension", "")
    if dim in DIM_TO_LAYER:
        layer_key, layer_name = DIM_TO_LAYER[dim]
        if not item.get("layer"):
            item["layer"] = layer_key
        if not item.get("layer_name"):
            item["layer_name"] = layer_name
    else:
        layer = item.get("layer", "")
        if layer in LAYER_NAMES:
            item["layer_name"] = LAYER_NAMES[layer]
        elif not item.get("layer_name"):
            item["layer_name"] = ""
    return item


# ---------- API Endpoints ----------

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_intent_matrix(
    request: AnalyzeRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    One-click ASIN/product intent analysis using COSMO 3-Layer 12-Dimension model.
    Layer 1 Object (isA, has_attribute) + Layer 2 Relation (7 dims) + Layer 3 State (3 dims).
    """
    product_input = request.asin_or_name.strip()
    if not product_input:
        raise HTTPException(status_code=400, detail="请输入ASIN或产品名称")

    category = request.category.strip() or "Auto-detect"
    marketplace = request.marketplace or "US"

    is_asin = bool(re.match(r'^[A-Z0-9]{10}$', product_input.upper()))
    product_name = f"ASIN {product_input.upper()} (Amazon {marketplace})" if is_asin else product_input

    ai_service = AIHubService()

    prompt = COMBINED_ANALYSIS_PROMPT.format(
        product_name=product_name,
        category=category,
        marketplace=marketplace,
    )

    system_msg = (
        f"你是Amazon COSMO 3层12维语义算法顶级专家。"
        f"COSMO 3层模型：对象层(isA, has_attribute)、关系层(used_for_function, capable_of, used_for_event, used_when, used_where, used_with, used_for_audience)、状态层(cause_positive, cause_negative, compared_to)。"
        f"2+7+3=12维，严格不重叠。关系层和状态层是AI代理时代转化率的核心。"
        f"你正在分析: {product_name}。"
        f"极其重要的语言规则：keyword字段用美式英语，但reason、summary、intent、actionable、insight、listing_summary、ad_summary、overall_strategy、layer_summary等所有描述性字段必须全部用中文输出！"
        f"只输出JSON。"
    )

    ai_request = GenTxtRequest(
        messages=[
            ChatMessage(role="system", content=system_msg),
            ChatMessage(role="user", content=prompt),
        ],
        model="AI_DEFAULT_MODEL",
        temperature=0.3,
        max_tokens=16384,
    )

    data = None
    last_error = None
    for attempt in range(2):
        try:
            response = await ai_service.gentxt(ai_request)
            data = _extract_json(response.content)
            break
        except (ValueError, Exception) as e:
            last_error = e
            logger.warning(f"Intent matrix AI parse failed (attempt {attempt + 1}/2): {e}")
            if attempt == 0:
                ai_request.model = "AI_DEFAULT_MODEL"
                ai_request.max_tokens = 16384

    if data is None:
        raise HTTPException(status_code=500, detail=f"AI分析失败: {str(last_error)}")

    listing_placements = []
    for item in data.get("listing_placements", []):
        enriched = _enrich_layer_info(item)
        listing_placements.append(ListingPlacement(
            keyword=enriched.get("keyword", ""),
            placement=enriched.get("placement", ""),
            layer=enriched.get("layer", ""),
            layer_name=enriched.get("layer_name", ""),
            dimension=enriched.get("dimension", ""),
            intent_type=enriched.get("intent_type", ""),
            reason=enriched.get("reason", ""),
        ))

    ad_keywords = []
    for item in data.get("ad_keywords", []):
        enriched = _enrich_layer_info(item)
        ad_keywords.append(AdKeyword(
            keyword=enriched.get("keyword", ""),
            match_type=enriched.get("match_type", ""),
            ad_type=enriched.get("ad_type", ""),
            layer=enriched.get("layer", ""),
            layer_name=enriched.get("layer_name", ""),
            dimension=enriched.get("dimension", ""),
            intent=enriched.get("intent", ""),
            priority=enriched.get("priority", ""),
            estimated_competition=enriched.get("estimated_competition", ""),
        ))

    # Save to cosmo_results
    try:
        from services.cosmo_results import Cosmo_resultsService
        svc = Cosmo_resultsService(db)
        cosmo_layers = data.get("cosmo_layers", {})
        kw_summary = []
        for layer_data in cosmo_layers.values():
            if isinstance(layer_data, dict) and "dimensions" in layer_data:
                for dim_data in layer_data["dimensions"].values():
                    if isinstance(dim_data, dict) and "keywords" in dim_data:
                        kw_summary.extend(dim_data["keywords"][:3])
        kw_str = ", ".join(kw_summary)[:2000]

        raw_json = json.dumps(data, ensure_ascii=False)
        truncated = raw_json[:10000] if len(raw_json) > 10000 else raw_json

        await svc.create({
            "product_id": 0,
            "model_name": "intent-matrix-3L12D",
            "optimized_title": product_name[:500],
            "optimized_bullets": "",
            "optimized_keywords": kw_str,
            "analysis_reason": truncated,
        }, user_id=str(current_user.id))
    except Exception as e:
        logger.warning(f"Failed to save intent matrix result: {e}")

    return AnalyzeResponse(
        product_name=data.get("product_name", product_name),
        category=data.get("category", category),
        listing_placements=listing_placements,
        listing_summary=data.get("listing_summary", ""),
        ad_keywords=ad_keywords,
        ad_summary=data.get("ad_summary", ""),
        cosmo_layers=data.get("cosmo_layers", {}),
        cross_layer_insights=data.get("cross_layer_insights", []),
        rufus_intents=data.get("rufus_intents", []),
        overall_strategy=data.get("overall_strategy", ""),
    )