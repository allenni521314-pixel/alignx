# AlignX系统更新包 - 2026-05-14

## 更新内容概览

### 1. 🔧 抓取性能优化
- **文件**: `app/backend/services/amazon_scraper.py`
- **改进**: 
  - 全局超时控制
  - 跳过最慢的Playwright策略
  - 价格提取逻辑优化
  - A+内容提取增强

### 2. 🤖 AI服务优化
- **文件**: `app/backend/services/aihub.py`
- **改进**: 超时配置优化

### 3. ⚡ 因果服务基础优化
- **文件**: `app/backend/services/causal_service_base.py`
- **改进**: 默认使用最快的多模态模型

### 4. 🗣️ COSMO语义分析优化
- **文件**: `app/backend/routers/intent_matrix.py`
- **改进**: 
  - 关键词多样性要求（1词/2词/3词/长尾）
  - 自动分析生成真实搜索词
  - 长尾关键词占比40%以上

### 5. 📊 雷达图维度标注修复
- **文件**: 
  - `app/frontend/src/pages/ListingDiagnosis.tsx`
  - `app/frontend/src/pages/HealthReport.tsx`
- **改进**: 
  - 所有维度完整显示标注
  - 智能text-anchor调整
  - 深色文字确保可读性
  - 每个维度显示具体分数

### 6. 💰 ASIN选品价格带维度
- **文件**:
  - `app/backend/models/asin_analyses.py`
  - `app/backend/routers/asin_analysis.py`
  - `app/backend/alembic/versions/003_add_price_tier_to_asin_analysis.py`
- **新增字段**:
  - `score_5d_price_tier`: 价格带维度评分 (0-100)
  - `price_tier_category`: 价格带分类 (high/medium/low)
  - `price_tier_analysis`: 详细价格带分析JSON

### 7. 💾 因果系统持久化表
- **文件**: `app/backend/alembic/versions/001_add_causal_diagnosis_fields.py`
  - `human_state_body`: 人类状态体核心表
  - listing_diagnoses因果字段

- **文件**: `app/backend/alembic/versions/002_add_causal_persistence_tables.py`
  - `review_causal_validations`: 评论因果验证结果
  - `causal_ab_comparisons`: 因果A/B对比结果
  - `batch_causal_tasks`: 批量因果任务

### 8. 🔧 Alembic配置修复
- **文件**: `app/backend/alembic/env.py`
- **改进**: 支持从DATABASE_URL环境变量读取数据库连接

---

## 部署步骤

### 1. 覆盖文件
将压缩包中的文件按目录结构覆盖到项目对应位置

### 2. 执行数据库迁移
```bash
cd app/backend
# 设置你的数据库连接字符串
export DATABASE_URL="你的数据库连接字符串"
# 执行迁移
alembic upgrade head
```

### 3. 重启后端服务
```bash
# 根据你的部署方式重启后端
# 例如: pm2 restart alignx-backend
```

### 4. 重启前端服务
```bash
# 根据你的部署方式重启前端
# 例如: pm2 restart alignx-frontend
```

---

## 验证清单

- [ ] ASIN选品6维评分正常显示（含价格带）
- [ ] 雷达图所有10个维度标注完整
- [ ] COSMO语义分析关键词多样化（1/2/3/4词都有）
- [ ] 亚马逊价格抓取准确
- [ ] A+内容分析完整
- [ ] 3Ai抓取分析在1分钟内完成

---

## 文件清单
```
📦 alignx-updates/
├── 📄 README_UPDATE.md
├── app/
│   ├── backend/
│   │   ├── alembic/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   │       ├── 001_add_causal_diagnosis_fields.py
│   │   │       ├── 002_add_causal_persistence_tables.py
│   │   │       └── 003_add_price_tier_to_asin_analysis.py
│   │   ├── models/
│   │   │   └── asin_analyses.py
│   │   ├── routers/
│   │   │   ├── asin_analysis.py
│   │   │   └── intent_matrix.py
│   │   └── services/
│   │       ├── aihub.py
│   │       ├── amazon_scraper.py
│   │       └── causal_service_base.py
│   └── frontend/
│       └── src/
│           └── pages/
│               ├── HealthReport.tsx
│               └── ListingDiagnosis.tsx
```
