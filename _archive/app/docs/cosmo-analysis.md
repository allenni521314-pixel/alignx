# Amazon COSMO 6维语义框架 — 对齐精准度分析报告

## 一、Amazon COSMO 原始框架概述

### 1.1 COSMO 是什么？
COSMO（Common Sense Knowledge Generation and Serving System）是亚马逊开发的 AI 框架，利用大语言模型（LLM）挖掘商品的常识知识，构建包含 **630万节点、2900万条边** 的知识图谱，覆盖 18 个主要品类。

### 1.2 COSMO 的 4 个基础关系类型
| 基础关系 | 含义 |
|---------|------|
| **usedFor** | 产品用于什么 |
| **capableOf** | 产品能做什么 |
| **isA** | 产品属于什么类别/类型 |
| **cause** | 产品引起/导致什么结果 |

### 1.3 COSMO 的 15 个细粒度规范关系
| 规范关系 | 含义 | 对应维度 |
|---------|------|---------|
| **used_for_function** | 产品的功能用途 | 功能 |
| **used_for_activity** | 产品用于什么活动 | 场景 |
| **used_for_event** | 产品用于什么事件/场合 | 场景 |
| **used_when** | 什么时候使用 | 场景 |
| **used_where** | 在哪里使用 | 场景 |
| **used_with** | 和什么一起使用 | 场景/功能 |
| **used_for_audience** | 目标受众是谁 | 身份 |
| **used_by** | 谁在使用 | 身份 |
| **isA** | 属于什么类别/风格 | 趋势 |
| **has_attribute** | 具有什么属性特征 | 趋势 |
| **capable_of** | 能够做什么 | 功能 |
| **cause_positive** | 带来什么正面效果 | 心理 |
| **cause_negative** | 可能带来什么负面效果 | 风险平衡 |
| **compared_to** | 与什么对比 | 风险平衡 |
| **requires** | 需要什么条件/配件 | 风险平衡 |

---

## 二、当前实现分析

### 2.1 当前 Prompt 中 6 个维度的描述

| 维度 | 当前描述 | 字数 |
|------|---------|------|
| **Function** | "What problems does this product solve? What is its purpose/utility?" | 简短，仅覆盖问题解决和用途 |
| **Scenario** | "When, where, and in what situations would someone use this?" | 仅覆盖时间/地点/情境 |
| **Identity** | "Who is this for? What role/lifestyle/self-image does it serve?" | 覆盖角色/生活方式/自我形象 |
| **Trend** | "Does it align with current aesthetics, lifestyle trends, platform hot topics, or category trends?" | 仅问是否对齐趋势 |
| **Psychology** | "What inner motivations drive the purchase? (security, comfort, status, efficiency, companionship)" | 列举了5个动机 |
| **Risk Balance** | "What concerns do buyers weigh before purchasing? (durability, value, safety, avoiding mistakes)" | 列举了4个顾虑 |

---

## 三、逐维度差距分析

### 3.1 功能（Function）
**COSMO 覆盖范围：** `used_for_function` + `capable_of` + `used_with`
- ❌ **缺失：** 产品的核心能力（capable_of）— 不仅是解决什么问题，还包括产品"能做到什么"
- ❌ **缺失：** 搭配使用场景（used_with）— 与其他产品的协同关系
- ❌ **缺失：** 功能差异化 — 相比同类产品的独特功能卖点
- ❌ **缺失：** 技术参数的消费者语言转化 — 如"65W GaN"→"charges your MacBook in 30 minutes"
- ❌ **缺失：** 多功能/一物多用的表达

**建议增加的 Prompt 引导：**
- 产品能做到什么（capability）
- 产品与什么搭配使用（complementary products）
- 产品的功能差异化卖点
- 将技术参数转化为消费者能感知的利益点
- 一物多用/多功能场景

### 3.2 场景（Scenario）
**COSMO 覆盖范围：** `used_for_event` + `used_for_activity` + `used_when` + `used_where` + `used_with`
- ❌ **缺失：** 具体活动类型（activity）— 如健身、露营、通勤
- ❌ **缺失：** 具体事件/场合（event）— 如生日、圣诞节、开学季
- ❌ **缺失：** 季节性使用场景
- ❌ **缺失：** 美国本土特有场景 — 如 Thanksgiving、tailgating、road trip、dorm room
- ❌ **缺失：** 使用频率和习惯 — 日常/偶尔/紧急

**建议增加的 Prompt 引导：**
- 具体活动（hiking, camping, commuting, working from home）
- 美国节日/文化事件（Black Friday, Super Bowl, Back to School）
- 季节性场景（summer BBQ, winter heating）
- 空间场景（apartment, dorm, RV, office cubicle）
- 使用频率和时机

### 3.3 身份（Identity）
**COSMO 覆盖范围：** `used_for_audience` + `used_by`
- ❌ **缺失：** 人口统计学细分 — 年龄段、性别、收入水平
- ❌ **缺失：** 生活阶段 — 大学生、新手妈妈、退休人士
- ❌ **缺失：** 职业身份 — 远程工作者、护士、卡车司机
- ❌ **缺失：** 兴趣社群 — TikTok用户、健身爱好者、极简主义者
- ❌ **缺失：** 美国特有身份标签 — first-time homeowner, pet parent, military spouse

**建议增加的 Prompt 引导：**
- 具体人口统计（Gen Z, millennials, boomers）
- 生活阶段（college freshman, new parent, empty nester）
- 职业角色（remote worker, nurse, teacher）
- 兴趣/价值观社群（eco-conscious, minimalist, tech enthusiast）
- 美国文化身份标签

### 3.4 趋势（Trend）
**COSMO 覆盖范围：** `isA` + `has_attribute`
- ❌ **缺失：** 具体的当前趋势关键词 — 如 "clean girl aesthetic", "quiet luxury"
- ❌ **缺失：** 平台趋势 — TikTok Made Me Buy It, Amazon's Choice
- ❌ **缺失：** 材质/技术趋势 — 如 bamboo, sustainable, AI-powered
- ❌ **缺失：** 色彩/设计趋势 — 如 earth tones, dopamine colors
- ❌ **缺失：** 品类热度趋势 — 该品类在Amazon上的搜索增长方向

**建议增加的 Prompt 引导：**
- 2024-2025 美国消费趋势关键词
- 社交媒体驱动的购买趋势
- 材质/可持续性趋势
- 设计美学趋势
- 品类增长方向和新兴子品类

### 3.5 心理（Psychology）
**COSMO 覆盖范围：** `cause_positive`（正面因果关系）
- ❌ **缺失：** 情感触发词 — 不仅是动机类别，还需要具体的情感表达
- ❌ **缺失：** 购买决策的情感路径 — 从"看到"到"想买"的心理链条
- ❌ **缺失：** 社交认同需求 — "别人都在用"、"网红推荐"
- ❌ **缺失：** 自我奖励心理 — "treat yourself"、"you deserve it"
- ❌ **缺失：** 焦虑缓解 — FOMO、解决痛点带来的释然感
- ❌ **缺失：** 美国消费者特有的心理触发 — independence, self-reliance, convenience obsession

**建议增加的 Prompt 引导：**
- 具体情感触发词和表达
- 社交证明和从众心理
- 自我奖励和享乐主义
- 焦虑/FOMO 缓解
- 美国文化价值观驱动的购买心理

### 3.6 风险平衡（Risk Balance）
**COSMO 覆盖范围：** `cause_negative` + `compared_to` + `requires`
- ❌ **缺失：** 具体的风险消除话术 — 不仅列出顾虑，还要给出消除方式
- ❌ **缺失：** 对比竞品的优势表达
- ❌ **缺失：** 退货/售后保障的表达
- ❌ **缺失：** 认证/合规的信任信号 — FDA, FCC, UL, BPA-free
- ❌ **缺失：** 社交证明 — 评价数、星级、"Amazon's Choice"
- ❌ **缺失：** 美国消费者特有的风险敏感点 — warranty, customer service, made in USA

**建议增加的 Prompt 引导：**
- 风险消除话术（not just concerns, but reassurance language）
- 竞品对比优势表达
- 保障和认证信号
- 社交证明和信任建立
- 美国消费者特有的信任触发点

---

## 四、优化建议总结

### 4.1 Prompt 结构优化
1. **每个维度增加 COSMO 规范关系映射** — 让 AI 明确知道要覆盖哪些关系类型
2. **增加美国本土化引导** — 每个维度都要有美国文化/消费习惯的具体引导
3. **增加示例** — 给每个维度提供 1-2 个示例，帮助 AI 理解期望的输出质量
4. **增加关键词数量** — 从 4-5 个增加到 5-8 个，覆盖更多语义空间
5. **增加关系类型标注** — 每个关键词标注对应的 COSMO 关系类型

### 4.2 输出格式优化
1. 每个关键词增加 `cosmo_relation` 字段（如 `used_for_function`, `capable_of`）
2. 每个维度增加 `search_volume_hint` 字段，提示搜索量级别
3. 增加 `competitor_gap` 字段，标注是否为竞品未覆盖的语义空间

---

*报告生成时间：2025年*
*数据来源：Amazon COSMO (SIGMOD/PODS 2024) 论文分析*
