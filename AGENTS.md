# AlignX Engineering Guardrails

## Scope
- 只按已提供的 PRD / 字段 / 对象 / 流程实现系统骨架。
- 当前任务是生产级工程补齐，不是新增功能开发，不是 UI 重设计，不是重构炫技。
- 保持最新左侧导航栏模块功能不变。

## Priorities
1. 昨日战报数据 staging + ASIN 归因。
2. Codex/Hermes 工程护栏。
3. AI 调用证据链 + 今日决策行为审计。
4. SP-API Product Type 字段版本预留。
5. Listing AI 可读性评分维度预留。

## Do Not Do
- 不新增无关功能。
- 不改变现有前台菜单结构。
- 不改变现有 UI 主风格。
- 不删除已有业务逻辑。
- 不绕过现有 ASIN 经营档案库架构。
- 不写假数据冒充真实生产能力。
- 不引入复杂 multi-agent 框架。
- 不做自部署大模型。
- 不直接接入 Shopify UCP。
- 不做大规模浏览器自动化抓后台。
- 不做传统 Amazon 工具对标页面。

## Frontend Text
- 前端只允许出现：字段标签、按钮、表头、状态、空态提示、表单占位、必要的操作反馈。
- 如信息缺失，使用“暂无 / 未设置 / 待录入”，不要推测。
- 所有新增内容必须能在需求里找到依据；没有依据就不要写。

## Required Checks
- `python3 scripts/engineering_guardrails.py`
- `python3 -m compileall backend/app backend/tests`
- `cd backend && /tmp/alignx-test-venv311/bin/python -m unittest discover -s tests`
- `cd frontend && npm run build`
- `cd frontend && npm run lint`
