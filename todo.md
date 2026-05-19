# 5维产品判断打分标准 - Implementation Plan

## Overview
Replace the ASIN Manager sub-page with a 5-Dimension Product Scoring System.
- 5 dimensions × 4 sub-items × 0-5 points = 100 total
- ≥70: ASIN机会池 (Opportunity Pool)
- <70: ASIN库 (ASIN Library)

## Files to Modify/Create

### Backend
1. **models/asin_analyses.py** - Add `score_5d_total` Float column and `score_5d_detail` String column
2. **routers/asin_analysis.py** - Add new `/five-dimension-score` endpoint with full 5维20项 AI prompt
3. **alembic migration** - Add new columns to asin_analyses table

### Frontend  
4. **src/components/FiveDimensionScore.tsx** - NEW: Radar chart + progress bars + detail panel for 5D scores
5. **src/pages/AsinManager.tsx** - Add tabs for ASIN库/机会池, add "5维评分" button per product, show score badges
6. **src/lib/workflow-api.ts** - Add `runFiveDimensionScore()` and `getFiveDimensionScore()` API functions

## 5维20项 Complete Standard

### 一、需求维（20分）
1. 痛点明确度 (0-5)
2. 使用频率 (0-5)
3. 需求刚性 (0-5)
4. 付费理由清晰度 (0-5)

### 二、场景维（20分）
1. 场景明确度 (0-5)
2. 场景触发强度 (0-5)
3. 场景扩展性 (0-5)
4. 场景可视化表达能力 (0-5)

### 三、竞争维（20分）
1. 同质化程度（反向项）(0-5)
2. 差异化锚点 (0-5)
3. 替代难度 (0-5)
4. 竞品弱点可攻击性 (0-5)

### 四、利润维（20分）
1. 毛利空间 (0-5)
2. 广告承受力 (0-5)
3. 定价合理性 (0-5)
4. 放大利润空间 (0-5)

### 五、趋势维（20分）
1. 需求增长趋势 (0-5)
2. 品类生命周期 (0-5)
3. 政策合规风险（反向项）(0-5)
4. 技术与供应链趋势 (0-5)

## Qualifying Threshold
- Total ≥ 70: Enter ASIN机会池
- Total < 70: Stay in ASIN库