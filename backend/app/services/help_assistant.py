from __future__ import annotations
"""Independent Help Assistant module for product support and tickets."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ai import AI
from app.models import HelpFaqItem, HelpMessage, HelpTicket, User
from app.schemas import HelpChatRequest, HelpTicketCreate


SYSTEM_PROMPT = """You are AlignX Help Assistant, a customer support assistant inside the AlignX logged-in application.

AlignX is an independent software service developed by Shenzhen Lingxi Zhigan Technology Co., Ltd. for Amazon sellers. AlignX helps sellers validate operational decisions before scaling investment in products, listings, advertising and inventory.

Your role is customer support, onboarding guidance, product help, troubleshooting and policy explanation. You are not an Amazon representative, not a legal advisor, not a financial advisor, and not a business decision maker.

You must follow these rules:
1. Answer in the user's selected language.
2. Be clear, concise and accurate.
3. Use official AlignX FAQ and policy content first.
4. Do not claim AlignX is affiliated with, endorsed by, certified by, authorized by, or officially sponsored by Amazon.
5. Do not ask for or accept Amazon Seller Central passwords.
6. Do not request buyer personal information unless a specific authorized feature explicitly requires it and policy allows it.
7. Do not provide instructions for ranking manipulation, review manipulation, unauthorized scraping, fake traffic, fake orders, or bypassing Amazon authorization.
8. Do not guarantee sales growth, ranking improvement, ACOS reduction, conversion rate increase, profit increase or any specific business outcome.
9. Do not make final business decisions for the user.
10. For operation questions, guide users to the relevant AlignX validation module and explain that decisions should be based on data.
11. If you are unsure, say you are not sure and offer to create a support ticket.
12. If the issue involves billing, privacy, data deletion, security, authorization failure, data sync failure or account closure, offer to create a support ticket.
13. Keep data use purpose-limited. Do not access or infer data outside the user's authorization.
14. If users ask about data use, explain that AlignX uses seller-authorized data only for operation validation, ASIN records, listing review, advertising analysis and result tracking.
15. If users ask whether AlignX collects Seller Central passwords, state clearly that AlignX does not collect Seller Central passwords.
16. If users ask whether AlignX is Amazon official, state clearly that AlignX is an independent software service and is not affiliated with, endorsed by, or officially sponsored by Amazon unless explicitly stated.
17. If users ask for legal advice, tax advice or financial advice, state that you cannot provide professional advice and recommend consulting a qualified professional.
18. When relevant, provide links to Privacy Policy, Terms of Service, Data Use Policy, Security and Contact pages.
"""


FAQ_ITEMS = [
    ("Data Use", "zh", "AlignX 会使用哪些数据？", "AlignX 主要使用卖家授权的经营数据，例如商品、Listing、库存、广告、销售和表现数据，用于 ASIN 经营档案、Listing 检查、广告分析和效果复盘。", ["数据", "使用哪些数据", "授权数据"]),
    ("Data Use", "en", "What data does AlignX use?", "AlignX mainly uses seller-authorized business data such as product, listing, inventory, advertising, sales and performance data for ASIN records, listing review, advertising analysis and result tracking.", ["data", "authorized data"]),
    ("Amazon Authorization", "zh", "AlignX 会收集 Seller Central 密码吗？", "不需要。AlignX 不要求你提供 Seller Central 登录密码。Amazon 数据接入应通过卖家授权方式完成，你也可以根据授权设置撤销或断开连接。", ["密码", "Seller Central", "登录密码"]),
    ("Amazon Authorization", "en", "Does AlignX collect my Seller Central password?", "No. AlignX does not ask for your Seller Central password. Amazon seller data access should be completed through seller authorization, and you may revoke or disconnect authorization according to the authorization settings.", ["password", "seller central"]),
    ("Privacy And Security", "zh", "你们是不是 Amazon 官方？", "不是。AlignX 是由深圳灵曦智感科技有限公司开发的独立软件服务，面向 Amazon 卖家提供经营验证能力。除非另有明确说明，AlignX 与 Amazon 不存在官方关联、官方背书或官方赞助关系。", ["官方", "Amazon 官方", "背书"]),
    ("Privacy And Security", "en", "Are you Amazon official?", "No. AlignX is an independent software service developed by Shenzhen Lingxi Zhigan Technology Co., Ltd. for Amazon sellers. Unless explicitly stated, AlignX is not affiliated with, endorsed by, or officially sponsored by Amazon.", ["official", "amazon", "endorsed"]),
    ("Data Upload", "zh", "如何上传广告报表？", "你可以进入「执行记录」或「昨日战报」页面上传 CSV 广告报表。未识别或无法归因的数据会先进入 staging，用户确认后再进入正式分析。", ["上传", "广告报表", "CSV"]),
    ("Data Upload", "en", "How do I upload advertising reports?", "Open Execution Records or Yesterday Report and upload a CSV advertising report. Unrecognized or unresolved rows should enter staging first and only move into formal analysis after user confirmation.", ["upload", "advertising report", "csv"]),
    ("ASIN Records", "zh", "如何查看 ASIN 经营档案？", "你可以在账号中心或相关 ASIN 页面查看 ASIN 经营档案。档案用于记录诊断、建议、执行动作、验证结果和后续认知更新。", ["ASIN", "经营档案", "档案"]),
    ("ASIN Records", "en", "How do I check an ASIN record?", "Open the relevant ASIN record page or account area. ASIN records are used to track diagnoses, suggestions, execution actions, validation results and learning updates.", ["asin", "record", "profile"]),
    ("Billing", "zh", "账单或付款问题怎么办？", "账单、付款、发票或充值问题需要创建人工客服工单。请说明问题类型和当前页面，客服会根据工单记录处理。", ["账单", "付款", "发票", "充值"]),
    ("Billing", "en", "How do I handle billing issues?", "Billing, payment, invoice and recharge issues should be handled through a support ticket. Please include the issue type and current page.", ["billing", "payment", "invoice"]),
]


TICKET_KEYWORDS = {
    "billing": ["账单", "付款", "发票", "充值", "billing", "payment", "invoice"],
    "privacy_request": ["删除数据", "关闭账号", "撤销授权", "data deletion", "delete data", "close account", "revoke"],
    "security_issue": ["安全", "泄露", "security", "leak"],
    "amazon_authorization": ["授权失败", "连接失败", "authorization failed", "connect failed"],
    "data_upload": ["上传失败", "同步失败", "upload failed", "sync failed"],
    "bug_report": ["bug", "报错", "错误", "error"],
}

OPERATION_KEYWORDS = ["要不要投", "预算要不要加", "怎么改", "能不能做", "为什么没转化", "should i invest", "increase budget", "how should i change", "why no conversion"]


@dataclass
class HelpAnswer:
    answer: str
    source: str
    should_create_ticket: bool = False
    suggested_issue_type: str = "other"
    message_id: str | None = None


def _normalize(text: str) -> str:
    return text.lower().strip()


async def ensure_faq_seeded(db: AsyncSession) -> None:
    existing = (await db.execute(select(HelpFaqItem.id).limit(1))).scalar_one_or_none()
    if existing:
        return
    for category, language, question, answer, keywords in FAQ_ITEMS:
        db.add(HelpFaqItem(category=category, language=language, question=question, answer=answer, keywords=keywords))
    await db.flush()


async def list_faq(language: str, db: AsyncSession) -> list[HelpFaqItem]:
    await ensure_faq_seeded(db)
    result = await db.execute(select(HelpFaqItem).where(HelpFaqItem.language == language).order_by(HelpFaqItem.category))
    return list(result.scalars().all())


def _ticket_issue_type(message: str) -> str | None:
    text = _normalize(message)
    for issue_type, keywords in TICKET_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            return issue_type
    if any(keyword in text for keyword in ["人工", "客服", "support", "human"]):
        return "other"
    return None


def _operation_boundary(message: str, language: str) -> str | None:
    text = _normalize(message)
    if not any(keyword in text for keyword in OPERATION_KEYWORDS):
        return None
    if language == "en":
        return "This requires ASIN data, listing readiness, advertising performance and execution records. Please open the Operation Validation or Advertising Budget Review module to generate a validation result. I can explain report fields, but I should not provide an investment decision without supporting data."
    return "这个问题需要结合 ASIN 数据、Listing 承接、广告表现和执行记录判断。你可以进入「经营验证」或「广告预算复盘」页面生成验证结果。我可以帮你解释报告字段，但不会在没有数据依据的情况下直接给出投入结论。"


async def _match_faq(message: str, language: str, db: AsyncSession) -> HelpFaqItem | None:
    text = _normalize(message)
    for item in await list_faq(language, db):
        terms = [item.question, *(item.keywords or [])]
        if any(_normalize(term) in text or text in _normalize(term) for term in terms):
            return item
    return None


async def chat(req: HelpChatRequest, db: AsyncSession, user_id: str) -> HelpAnswer:
    language = "en" if req.language == "en" else "zh"
    await ensure_faq_seeded(db)
    db.add(HelpMessage(user_id=user_id, language=language, page_url=req.page_url, role="user", message=req.message, source="user"))

    issue_type = _ticket_issue_type(req.message)
    if issue_type:
        answer = "This issue should be handled through a support ticket. Please create a ticket and include the page URL and error details." if language == "en" else "这个问题需要创建人工客服工单。请提交工单，并附上当前页面和错误信息。"
        msg = HelpMessage(user_id=user_id, language=language, page_url=req.page_url, role="assistant", message=answer, source="fallback")
        db.add(msg)
        await db.flush()
        return HelpAnswer(answer=answer, source="fallback", should_create_ticket=True, suggested_issue_type=issue_type, message_id=msg.id)

    boundary = _operation_boundary(req.message, language)
    if boundary:
        msg = HelpMessage(user_id=user_id, language=language, page_url=req.page_url, role="assistant", message=boundary, source="fallback")
        db.add(msg)
        await db.flush()
        return HelpAnswer(answer=boundary, source="fallback", should_create_ticket=False, message_id=msg.id)

    faq = await _match_faq(req.message, language, db)
    if faq:
        msg = HelpMessage(user_id=user_id, language=language, page_url=req.page_url, role="assistant", message=faq.answer, source="faq")
        db.add(msg)
        await db.flush()
        return HelpAnswer(answer=faq.answer, source="faq", message_id=msg.id)

    prompt = f"Language: {language}\nCurrent page: {req.page_url or 'Not set'}\nUser question: {req.message}\n\nAnswer only as AlignX product support. If unsure, offer to create a support ticket."
    try:
        ai = AI(provider="deepseek")
        result = await ai.complete(prompt=prompt, system=SYSTEM_PROMPT, model="deepseek-chat", temperature=0.2, max_tokens=800)
        answer = result.raw.strip()
        source = "deepseek"
    except Exception:
        answer = "I am not sure about this issue. Please create a support ticket so support can review it." if language == "en" else "我暂时无法确认这个问题。请创建客服工单，人工客服可以进一步查看。"
        source = "fallback"
    should_ticket = source == "fallback"
    msg = HelpMessage(user_id=user_id, language=language, page_url=req.page_url, role="assistant", message=answer, source=source)
    db.add(msg)
    await db.flush()
    return HelpAnswer(answer=answer, source=source, should_create_ticket=should_ticket, message_id=msg.id)


async def create_ticket(req: HelpTicketCreate, db: AsyncSession, user_id: str) -> HelpTicket:
    user = await db.get(User, user_id)
    ticket = HelpTicket(
        user_id=user_id,
        user_email=user.email if user else None,
        issue_type=req.issue_type,
        priority=req.priority,
        language=req.language,
        page_url=req.page_url,
        user_message=req.user_message,
        screenshots=req.screenshots or [],
        status="open",
    )
    db.add(ticket)
    await db.flush()
    return ticket


async def list_tickets(db: AsyncSession, user_id: str) -> list[HelpTicket]:
    result = await db.execute(select(HelpTicket).where(HelpTicket.user_id == user_id).order_by(HelpTicket.created_at.desc()))
    return list(result.scalars().all())
