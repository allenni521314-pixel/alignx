# AlignX Model Boundaries

This file defines which model family owns each responsibility in AlignX. The goal is to prevent provider conflicts and keep ASIN, Listing, keyword, vision, and history-retrieval workflows auditable.

## 0. Non-negotiable invocation chain

All production scoring workflows must follow the same evidence chain:

`Scraping facts -> rule structuring -> BGE-M3 semantic recall -> BGE rerank -> DeepSeek reasoning -> versioned snapshot -> ad validation feedback`

Model calls are not interchangeable:

- Scraping captures facts and never writes conclusions.
- Rules normalize facts and block impossible conclusions, such as out-of-stock items being treated as healthy sales.
- BGE-M3 retrieves semantic memory and similar evidence, but never scores by itself.
- BGE Reranker filters evidence, but never writes business advice.
- Qwen Vision extracts image/A+ evidence, but never makes the final seller decision.
- DeepSeek writes the final seller-facing judgment using only structured facts and selected evidence.

If any required fact source is missing, the result must lower confidence or switch to a labeled fallback. It must not silently invent the missing data.

## 1. DeepSeek: text reasoning and business decisions

DeepSeek is the primary text model for seller-facing analysis and final judgment.

Use DeepSeek for:
- ASIN competitor diagnosis and COSMO 10-dimension scoring.
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

Business modules must call text models through role aliases only:

- `AI_LIGHT_MODEL`: fast labels, minor summarization, UI assistance.
- `AI_REASONING_MODEL`: ASIN decisions, competitor strategy, ad validation decisions.
- `AI_DEEP_MODEL`: full Listing diagnosis, feedback-loop attribution, complex cross-module reasoning.

## 2. Qwen Vision/OCR: visual evidence extraction

Qwen Vision/OCR is the visual understanding and image-text extraction model. It supports Listing quality by reading main images, secondary images, A+ images, and image-embedded text that text scraping cannot reliably capture.

Use Qwen Vision for:
- Main image diagnosis: product visibility, background compliance, click clarity, props, visual noise.
- Secondary image structure: feature proof, scenario proof, dimensions, compatibility, before/after, trust proof.
- A+ image and brand story extraction when text is embedded inside images.
- Image OCR for claims, badges, warranty wording, medical/absolute claims, and risk phrases.
- OCR extraction for certification icons, comparison tables, dosage/spec labels, compatibility text, installation steps, and hidden compliance claims.
- Competitor image structure comparison.
- Pre-launch image checks before publishing.

Do not use Qwen Vision for:
- Final 10-dimension business judgment by itself.
- Large text-only diagnosis.
- Keyword vector retrieval.
- Price, BSR, rating, bought-count, or sales opportunity conclusions without DeepSeek or rules.

Production vision/OCR variables:
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
1. Scraping captures Top40/search snapshot and single-ASIN facts.
2. Rules summarize price/rating/review/bought-count/stock/BSR/organic/ad position bands.
3. BGE retrieves similar historical opportunities and keyword intent.
4. Reranker selects the most relevant evidence.
5. DeepSeek `AI_REASONING_MODEL` writes the 6D opportunity conclusion.
6. Snapshot is saved before the next module starts.

Competitor diagnosis:
1. ASIN page data is fetched by the existing ASIN/Listing pipeline.
2. BGE retrieves similar product and review history when available.
3. Reranker filters that evidence.
4. Qwen Vision/OCR analyzes images/A+ only when images are present and visual diagnosis is requested.
5. DeepSeek produces final 10-dimension scoring and strategy.
6. If DeepSeek fails, backend must mark `analysis_mode=rule_fallback`; never present fallback scores as full AI judgment.

Listing diagnosis:
1. Scraping/user input structures title, main image, secondary images, bullets, A+, reviews, stock and compliance facts.
2. Rules establish product identity, required attributes, scenario coverage and hard blockers.
3. BGE retrieves similar Listing mistakes, keyword intent and review pains.
4. Reranker filters semantic evidence before it enters the prompt.
5. Qwen Vision/OCR checks main image, secondary image, A+ evidence and image-embedded claims when images are available.
6. DeepSeek `AI_DEEP_MODEL` produces 10-dimension diagnosis, rewrite direction and next validation plan.
7. Versioned diagnosis snapshot is saved.

Ad validation and feedback loop:
1. Ads/search terms are stored as structured data.
2. BGE matches terms to prior intent and pain clusters.
3. Reranker selects the strongest evidence.
4. DeepSeek `AI_REASONING_MODEL` decides whether to keep, pause, rewrite, or retest.
5. DeepSeek `AI_DEEP_MODEL` is used only for cross-round attribution and weight correction.

## 6. Conflict rules

- Text judgment must use DeepSeek unless explicitly marked as a vision-only or embedding-only operation.
- Vision output is evidence, not the final seller decision.
- Embedding output is recall, not the final seller decision.
- Reranker output is evidence ordering, not the final seller decision.
- If provider config returns `invalid_api_key`, `model_not_found`, or HTTP 401/403, stop and surface a configuration error. Do not silently convert it into a normal score.
- Fallback scores must be labeled with `analysis_mode=rule_fallback` and shown with a warning in the UI.
- Business modules must use role aliases (`AI_REASONING_MODEL`, `AI_DEEP_MODEL`, `AI_VISION_MODEL`, `AI_EMBEDDING_MODEL`, `RERANK_MODEL`) instead of provider names.
