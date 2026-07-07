from __future__ import annotations

import asyncio
import html
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models import DailyReportPushLog, User
from app.services.reports import generate_today_decisions, generate_yesterday_report


settings = get_settings()


async def send_all_daily_reports(db: AsyncSession) -> dict:
    users = (
        (await db.execute(
            select(User)
            .where(User.email != "local@alignx.dev")
            .where(User.email.contains("@"))
            .order_by(User.created_at.asc())
        ))
        .scalars()
        .all()
    )
    results = []
    for user in users:
        results.append(await send_user_daily_report(db, user))

    return {
        "total": len(users),
        "sent": sum(1 for item in results if item["status"] == "sent"),
        "skipped": sum(1 for item in results if item["status"] == "skipped"),
        "failed": sum(1 for item in results if item["status"] == "failed"),
        "items": results,
    }


async def send_user_daily_report(db: AsyncSession, user: User) -> dict:
    report_date = datetime.utcnow().strftime("%Y-%m-%d")
    duplicate = await _sent_today(db, user.id, report_date)
    if duplicate:
        return {"user_id": user.id, "email": user.email, "status": "skipped"}

    if not settings.sendgrid_api_key:
        await _log(db, user.id, report_date, user.email, "skipped", "SENDGRID_API_KEY 未设置")
        return {"user_id": user.id, "email": user.email, "status": "skipped"}

    try:
        yesterday = await generate_yesterday_report(db, user_id=user.id)
        today = await generate_today_decisions(db, user_id=user.id)
        subject = f"AlignX 日报 {report_date}"
        content = render_daily_report_html(yesterday, today)
        await asyncio.to_thread(_send_email, user.email, subject, content)
        await _log(db, user.id, report_date, user.email, "sent", None, sent_at=datetime.utcnow())
        return {"user_id": user.id, "email": user.email, "status": "sent"}
    except Exception as exc:
        await _log(db, user.id, report_date, user.email, "failed", str(exc))
        return {"user_id": user.id, "email": user.email, "status": "failed"}


async def _sent_today(db: AsyncSession, user_id: str, report_date: str) -> bool:
    result = await db.execute(
        select(DailyReportPushLog)
        .where(DailyReportPushLog.user_id == user_id)
        .where(DailyReportPushLog.report_date == report_date)
        .where(DailyReportPushLog.status == "sent")
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _log(
    db: AsyncSession,
    user_id: str,
    report_date: str,
    email: str,
    status: str,
    error_message: str | None,
    sent_at: datetime | None = None,
) -> None:
    db.add(
        DailyReportPushLog(
            user_id=user_id,
            report_date=report_date,
            email=email,
            status=status,
            error_message=error_message,
            sent_at=sent_at,
        )
    )
    await db.flush()


def _send_email(to_email: str, subject: str, html_content: str) -> None:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail

    message = Mail(
        from_email=(settings.report_from_email, settings.report_from_name),
        to_emails=to_email,
        subject=subject,
        html_content=html_content,
    )
    SendGridAPIClient(settings.sendgrid_api_key).send(message)


def render_daily_report_html(yesterday: dict, today: dict) -> str:
    summary = yesterday.get("summary") or {}
    validation = yesterday.get("validation_stats") or {}
    today_summary = today.get("summary") or {}
    active_problems = yesterday.get("active_problems") or []
    pending = today.get("pending") or []

    return f"""<!doctype html>
<html>
  <body>
    <h1>AlignX 日报</h1>
    <table>
      <tbody>
        <tr><th>日期</th><td>{_text(yesterday.get("date"))}</td></tr>
        <tr><th>执行记录</th><td>{_text(summary.get("total_executions"))}</td></tr>
        <tr><th>广告花费</th><td>{_money(summary.get("ad_spend"))}</td></tr>
        <tr><th>待验证</th><td>{_text(today_summary.get("pending"))}</td></tr>
        <tr><th>测试中</th><td>{_text(today_summary.get("running"))}</td></tr>
        <tr><th>已验证有效</th><td>{_text(today_summary.get("effective"))}</td></tr>
        <tr><th>有效</th><td>{_text(validation.get("effective"))}</td></tr>
        <tr><th>无效</th><td>{_text(validation.get("ineffective"))}</td></tr>
      </tbody>
    </table>
    <h2>问题</h2>
    {_items(active_problems, ("asin", "problem", "next_action"))}
    <h2>今日决策</h2>
    {_items(pending, ("asin", "hypothesis", "history_signal"))}
  </body>
</html>"""


def _items(items: list[dict], keys: tuple[str, ...]) -> str:
    if not items:
        return "<p>暂无</p>"
    rows = []
    for item in items[:10]:
        values = " / ".join(_text(item.get(key)) for key in keys)
        rows.append(f"<li>{values}</li>")
    return "<ul>" + "".join(rows) + "</ul>"


def _text(value) -> str:
    if value is None or value == "":
        return "暂无"
    return html.escape(str(value))


def _money(value) -> str:
    if value is None or value == "":
        return "暂无"
    try:
        return f"${float(value):.2f}"
    except (TypeError, ValueError):
        return _text(value)
