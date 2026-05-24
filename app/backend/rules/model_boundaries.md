# AlignX Model Boundaries

This file defines which model family owns each responsibility in AlignX. The goal is to prevent provider conflicts and keep ASIN, Listing, keyword, vision, and history-retrieval workflows auditable.

## 1. DeepSeek: text reasoning and business decisions

DeepSeek is the primary text model for seller-facing analysis and final judgment.

Use DeepSeek for:
- ASIN competitor diagnosis and COSMO 8D+2 scoring.
- Listing diagnosis, Listing rewriting suggestions, and launch checks.
- Top40 market opportunity synthesis after the search snapshot is saved.
- Price-band, review-count, rating, BSR, bought-count, and opportunity interpretation.
- Strategy output: recommended entry band, next validation action, risks, and final seller decision.
- Turning structured evidence into concise Chinese business conclusions.

Do not use DeepSeek for:
- Image OCR or visual layout judgment when image URLs are available.
- Vector similarity search or historical recall.
- Reranking large candidate sets before the final prompt.
- Raw Amazon page scraping.

Production text variables:
- `AI_PROVIDER=deepseek`
- `OPENAI_BASE_URL=https://api.deepseek.com`
- `AI_DEFAULT_MODEL=deepseek-v4-flash`
- `AI_LIGHT_MODEL=deepseek-v4-flash`
- `AI_REASONING_MODEL=deepseek-v4-pro`
- `AI_DEEP_MODEL=deepseek-v4-pro`

## 2. Qwen Vision: visual evidence extraction

Qwen Vision is the visual understanding model. It supports Listing quality by reading image and A+ evidence that text scraping cannot reliably capture.

Use Qwen Vision for:
- Main image diagnosis: product visibility, background compliance, click clarity, props, visual noise.
- Secondary image structure: feature proof, scenario proof, dimensions, compatibility, before/after, trust proof.
- A+ image and brand story extraction when text is embedded inside images.
- Image OCR for claims, badges, warranty wording, medical/absolute claims, and risk phrases.
- Competitor image structure comparison.
- Pre-launch image checks before publishing.

Do not use Qwen Vision for:
- Final 8D+2 business judgment by itself.
- Large text-only diagnosis.
- Keyword vector retrieval.
- Price, BSR, rating, bought-count, or sales opportunity conclusions without DeepSeek or rules.

Production vision variables:
- `VISION_PROVIDER=qwen`
- `VISION_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`
- `VISION_API_KEY=<qwen/dashscope vision key>`
- `AI_VISION_MODEL=qwen2.5-vl-72b-instruct` or approved Qwen VL model.

## 3. SiliconFlow BGE-M3: semantic memory and matching

BGE-M3 embedding is the semantic indexing layer. It should make AlignX remember and retrieve relevant historical evidence before the reasoning model answers.

Use BGE-M3 embedding for:
- Matching a new ASIN/title/keyword to historical ASIN analyses.
- Matching buyer review pains to known pain clusters.
- Matching Listing modules to COSMO/Rufus semantic anchors.
- Finding similar competitor products, keywords, titles, and prior strategy records.
- Building retrieval context for DeepSeek before final analysis.
- Long-tail keyword clustering and synonym grouping across English/Chinese inputs.

Do not use BGE-M3 for:
- Final answer generation.
- Scoring or strategic conclusions by itself.
- Image interpretation.
- Scraping or parsing Amazon pages.

Production embedding variables:
- `EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1`
- `EMBEDDING_API_KEY=<siliconflow key>`
- `AI_EMBEDDING_MODEL=BAAI/bge-m3`

## 4. SiliconFlow BGE Reranker: evidence precision filter

BGE Reranker is the precision layer after embedding recall. It prevents irrelevant historical records from entering DeepSeek prompts.

Use BGE Reranker for:
- Reranking retrieved historical ASIN analyses before feeding them to DeepSeek.
- Selecting the most relevant review-pain examples for a specific Listing.
- Selecting the closest keyword intent records for ad validation.
- Ranking competitor examples for Top40 market opportunity analysis.
- Filtering noisy semantic matches when the embedding result set is too broad.

Do not use BGE Reranker for:
- Generating text.
- Creating embeddings.
- Image understanding.
- Business conclusions without DeepSeek/rules.

Production rerank variables:
- `RERANK_BASE_URL=https://api.siliconflow.cn/v1`
- `RERANK_API_KEY=<siliconflow key>`
- `RERANK_MODEL=BAAI/bge-reranker-v2-m3`

## 5. Workflow ownership

ASIN selection Top40:
1. Capture/search snapshot saves raw Top40 fields.
2. Rules summarize price/rating/review/bought-count bands.
3. BGE retrieves similar historical opportunities.
4. Reranker selects the most relevant history.
5. DeepSeek writes the opportunity conclusion.
6. Single-ASIN deep research is launched separately.

Competitor diagnosis:
1. ASIN page data is fetched by the existing ASIN/Listing pipeline.
2. BGE retrieves similar product and review history when available.
3. Reranker filters that evidence.
4. Qwen Vision analyzes images/A+ only when images are present and visual diagnosis is requested.
5. DeepSeek produces final 8D+2 scoring and strategy.
6. If DeepSeek fails, backend must mark `analysis_mode=rule_fallback`; never present fallback scores as full AI judgment.

Listing diagnosis:
1. User Listing fields and optional browser-parsed fields are structured.
2. BGE retrieves similar Listing mistakes, keyword intent, and review pains.
3. Qwen Vision checks main image/A+ evidence when images are available.
4. DeepSeek produces diagnosis, rewrite direction, and next validation plan.

Ad validation and feedback loop:
1. Ads/search terms are stored as structured data.
2. BGE matches terms to prior intent and pain clusters.
3. Reranker selects the strongest evidence.
4. DeepSeek decides whether to keep, pause, rewrite, or retest.

## 6. Conflict rules

- Text judgment must use DeepSeek unless explicitly marked as a vision-only or embedding-only operation.
- Vision output is evidence, not the final seller decision.
- Embedding output is recall, not the final seller decision.
- Reranker output is evidence ordering, not the final seller decision.
- If provider config returns `invalid_api_key`, `model_not_found`, or HTTP 401/403, stop and surface a configuration error. Do not silently convert it into a normal score.
- Fallback scores must be labeled with `analysis_mode=rule_fallback` and shown with a warning in the UI.
