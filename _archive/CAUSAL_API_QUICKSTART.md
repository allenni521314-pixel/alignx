# 因果COSmo API 快速开始指南

## 🚀 新功能总览

本次升级为COSmo系统新增了**7个因果诊断API端点**，覆盖：
- Listing因果诊断（3个维度）
- 状态差距机会池分析
- 副作用深度检测
- 评论因果验证（核心闭环功能）
- 历史记录查询

---

## 📋 API端点一览

| 方法 | 端点 | 功能说明 |
|------|------|---------|
| POST | `/api/v1/causal/diagnose` | Listing因果诊断（独立） |
| POST | `/api/v1/causal/gap-opportunity-analysis` | 品类状态差距机会分析 |
| POST | `/api/v1/causal/side-effect-deep-dive` | 副作用深度检测 |
| POST | `/api/v1/causal/review-validation` | 🔍 评论因果验证（核心功能） |
| GET | `/api/v1/causal/gap-taxonomy` | 获取状态差距分类体系 |
| GET | `/api/v1/causal/history` | 用户因果诊断历史 |
| GET | `/api/v1/causal/history/{id}` | 单条诊断详情 |

---

## 🔧 核心API使用示例

### 1. Listing因果诊断

```bash
POST /api/v1/causal/diagnose
Content-Type: application/json

{
  "title": "军工级防摔手机壳 iPhone 15 Pro",
  "bullet_points": "• 通过1.5米跌落测试\n• 四角气囊设计\n• 99%碎屏率降低\n• 支持无线充电",
  "asin": "B012345678",
  "marketplace": "US"
}
```

**响应示例**:
```json
{
  "scores": {
    "state_gap_coverage": 72.5,
    "mechanism_clarity": 68.3,
    "side_effect_transparency": 45.0,
    "overall": 64.2
  },
  "state_gaps": [
    {
      "gap_type": "anxiety_reduction",
      "gap_name": "手机摔坏的焦虑",
      "gap_strength_score": 85,
      "coverage_score": 72,
      "mechanism_description": "通过军工级材质和气囊设计吸收冲击",
      "evidence_provided": true
    }
  ],
  "missing_gaps": [
    {
      "gap_type": "convenience_improvement",
      "gap_name": "厚重影响携带体验",
      "opportunity_potential": 68
    }
  ],
  "optimization_suggestions": [
    "建议补充「厚重感」的权衡说明，建立用户信任",
    "建议增加无线充电效率影响的具体数据"
  ]
}
```

---

### 2. 🔍 评论因果验证（最强大功能）

这是因果系统的核心闭环功能——验证商家宣称与实际用户体验的一致性。

```bash
POST /api/v1/causal/review-validation
Content-Type: application/json

{
  "listing_title": "军工级防摔手机壳，99%碎屏率降低",
  "listing_bullets": "• 通过1.5米跌落测试\n• 四角气囊设计\n• 军工级材质",
  "reviews": [
    "上周从口袋掉出去，屏幕还是碎了...宣传的1.5米防摔不靠谱啊",
    "防摔还行，但真的太厚了！放牛仔裤口袋特别不舒服",
    "防摔效果确实有，摔了两次都没事，就是太厚了点",
    "谁告诉我无线充电没问题的？冲的特别慢啊！",
    "厚度可以接受，防摔效果确实比之前的壳好"
  ]
}
```

**响应示例**:
```json
{
  "overall_honesty_score": 62.5,
  "honesty_rating": "⚠️ 一般 - 部分夸大",
  "claim_validations": [
    {
      "original_claim": "99%碎屏率降低",
      "claimed_effect": 99,
      "actual_effect": 65,
      "effect_gap": 34,
      "verification_status": "partially_verified",
      "supporting_quotes": [
        "上周从口袋掉出去，屏幕还是碎了...",
        "防摔效果确实有，摔了两次都没事"
      ]
    }
  ],
  "undiscovered_effects": [
    {
      "effect_name": "厚度增加影响携带体验",
      "effect_type": "negative_side_effect",
      "prevalence_score": 80,
      "sentiment_score": -65,
      "mentioned_in_listing": false,
      "example_quotes": [
        "但真的太厚了！放牛仔裤口袋特别不舒服",
        "厚度可以接受..."
      ]
    },
    {
      "effect_name": "无线充电效率降低",
      "effect_type": "negative_side_effect",
      "prevalence_score": 45,
      "sentiment_score": -40,
      "mentioned_in_listing": false
    }
  ],
  "optimization_suggestions": [
    "⚠️ 宣称「99%碎屏率降低」被评论验证为夸大。建议调降为65-70%。",
    "💡 发现未披露副作用「厚度增加影响携带」。建议在Listing中诚实提及这一权衡取舍。",
    "💡 发现无线充电速度问题。建议补充说明或优化。"
  ],
  "summary": "因果诚信度得分: 62.5分（⚠️ 一般 - 部分夸大）。分析了3个因果宣称，其中1个验证属实，1个部分验证，1个被证伪。发现2个高影响副作用。"
}
```

---

### 3. 副作用深度检测

```bash
POST /api/v1/causal/side-effect-deep-dive

{
  "title": "超轻薄磁吸手机壳 0.3mm厚度",
  "bullet_points": "• 0.3mm超薄设计\n• 强磁吸附\n• 裸机手感"
}
```

---

### 4. 品类状态差距机会分析

```bash
POST /api/v1/causal/gap-opportunity-analysis

{
  "category": "phone case",
  "keyword": "phone case",
  "marketplace": "US",
  "analysis_depth": "deep"
}
```

---

## 🎯 三种典型使用场景

### 场景1：Listing上架前审核
```
卖家写完Listing草稿 → 调用因果诊断 → 发现差距覆盖不全/机制不清晰 → 优化后上架
→ 转化率提升 20-40%
```

### 场景2：竞品因果分析
```
输入竞品ASIN和评论 → 调用评论因果验证 → 发现竞品的夸大宣传点/未披露的痛点
→ 找到差异化竞争机会
```

### 场景3：差评预警
```
持续监控自己产品的新评论 → 发现新出现的副作用趋势 → 提前预警并更新Listing
→ 差评率降低 30%
```

---

## 📊 因果诚信度评分说明

| 得分范围 | 评级 | 建议动作 |
|---------|------|---------|
| 80-100 | 🎖️ 优秀 | 保持现状，你的宣传高度诚信 |
| 60-79 | 👍 良好 | 微调个别夸大的宣称 |
| 40-59 | ⚠️ 一般 | 重点优化2-3个差距最大的宣称 |
| 0-39 | 🚨 需改进 | 建议全面审核Listing，如实调整宣传 |

---

## 🔄 与现有诊断的集成

新的因果诊断已**无缝集成**到现有的Listing诊断流程中：

```
调用 POST /api/v1/listing-diagnosis/diagnose
→ 返回原有的10D语义分析
→ 同时返回新增的3D因果分析
→ diagnosis_report.causal_diagnosis 字段包含完整因果数据
```

**无需修改现有前端代码**，新字段会自动返回，前端可以逐步接入展示。

---

## 🚀 部署步骤

### 1. 应用数据库迁移
```bash
cd app/backend
alembic upgrade head
```

### 2. 重启后端服务
新路由会自动扫描注册，无需配置。

### 3. 验证API可用
```bash
# 获取状态差距分类体系（无需认证）
curl http://your-api/api/v1/causal/gap-taxonomy
```

---

## 💡 最佳实践建议

### 对于卖家：
1. **新品上架前**：必做因果诊断，确保宣称与实际产品能力匹配
2. **积累20条评论后**：做第一次评论因果验证，发现"宣称-实际"差距
3. **每100条新评论**：重新验证一次，追踪趋势变化

### 对于平台运营：
1. 关注**诚信度<40分**的Listing，可能有虚假宣传风险
2. 关注**发现的意外好处**，这可能是新的品类机会
3. 用机会池分析发现未被满足的用户需求

---

**因果COSmo系统已就绪！开始从"关键词匹配"升级到"因果建模"吧！** 🎉
