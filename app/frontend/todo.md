# Data Workflow Integration - Implementation Plan

## Overview
Connect the entire AlignX data workflow into a true closed-loop system.

## Changes Required

### 1. Backend: Add `competitor_insights` table + Add lifecycle fields to products
- Create `competitor_insights` model & router (stores competitive analysis results per product)
- Add `lifecycle_stage` and `optimization_round` fields to `products` model/router

### 2. Frontend: `src/lib/workflow-api.ts` (NEW)
- Centralized helper functions for cross-module data flow
- `saveCompetitorInsights(productId, insights)` → POST to competitor_insights
- `getCompetitorInsights(productId)` → GET from competitor_insights
- `getListingDiagnosisForProduct(productId)` → GET from listing_diagnoses
- `getHealthReportForProduct(productId)` → GET from health_reports
- `getAdRecommendationsForProduct(productId)` → GET from ad_recommendations
- `getCosmoResultsForProduct(productId)` → GET from cosmo_results
- `updateProductLifecycle(productId, stage, round?)` → PUT products
- `saveConsumerIntentResult(data)` → POST to consumer_intent_results (new entity)

### 3. Frontend: CompetitorAnalysis.tsx
- After analysis completes, auto-save insights to `competitor_insights` via workflow-api

### 4. Frontend: ListingDiagnosis.tsx
- When starting diagnosis, fetch competitor_insights for context
- After diagnosis, update product lifecycle stage

### 5. Frontend: AdOptimizer.tsx  
- When generating recommendations, fetch listing diagnosis results as context
- After saving ad_recommendations, update product lifecycle stage

### 6. Frontend: ConsumerIntent.tsx
- Migrate from localStorage to `consumer_intent_results` entity
- Keep localStorage as fallback/cache

### 7. Frontend: Dashboard.tsx
- Replace mock data with real queries:
  - "正在验证策略数" → count ad_recommendations
  - "已完成优化轮次" → read product optimization_round
  - System suggestions → based on real data gaps
  - Verification feedback → based on recent ad_recommendations

### Files to create/modify:
1. `/workspace/app/frontend/src/lib/workflow-api.ts` (NEW)
2. `/workspace/app/frontend/src/pages/CompetitorAnalysis.tsx` (MODIFY)
3. `/workspace/app/frontend/src/pages/ListingDiagnosis.tsx` (MODIFY)
4. `/workspace/app/frontend/src/pages/AdOptimizer.tsx` (MODIFY)
5. `/workspace/app/frontend/src/pages/ConsumerIntent.tsx` (MODIFY)
6. `/workspace/app/frontend/src/pages/Dashboard.tsx` (MODIFY)