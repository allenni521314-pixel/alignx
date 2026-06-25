from __future__ import annotations
"""Pre-launch check service — listing materials → AI position diagnosis."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import PrelaunchCheck
from app.schemas import PrelaunchCheckRequest, PrelaunchCheckResponse
from app.core.ai import AI
from app.core.prompts import build_prelaunch_prompt, PRELAUNCH_SYSTEM
from app.constants import DEFAULT_USER_ID


async def analyze_prelaunch(req: PrelaunchCheckRequest, db: AsyncSession, user_id: str | None = None) -> PrelaunchCheckResponse:
    uid = user_id or DEFAULT_USER_ID
    materials = {
        "product_name": req.product_name, "title_draft": req.title_draft,
        "key_highlights": req.key_highlights,
        "bullet_points": [req.bullet_1, req.bullet_2, req.bullet_3, req.bullet_4, req.bullet_5],
    }

    image_slots = req.image_slots or []
    if image_slots:
        # Map slot names to AI-friendly position names
        slot_label_map = {
            "main": "main_image", "img2": "image_2", "img3": "image_3",
            "img4": "image_4", "img5": "image_5", "img6": "image_6", "img7": "image_7",
            "aplus1": "aplus_1", "aplus2": "aplus_2", "aplus3": "aplus_3",
            "aplus4": "aplus_4", "aplus5": "aplus_5", "aplus6": "aplus_6",
            "aplus7": "aplus_7", "aplus8": "aplus_8", "aplus9": "aplus_9",
        }
        # Build uploaded positions list for AI
        uploaded = []
        for s in image_slots:
            slot = s.get("slot", "")
            pos = slot_label_map.get(slot, slot)
            uploaded.append({"position": pos, "file": s.get("name", ""), "slot_id": slot})
        materials["uploaded_images"] = uploaded
        materials["image_count"] = len(uploaded)
        # Also flag which positions are explicitly NOT uploaded
        all_positions = list(slot_label_map.values())
        missing = [p for p in all_positions if p not in [u["position"] for u in uploaded]]
        materials["missing_images"] = missing

    # ── Vision OCR: extract text from uploaded images ──
    if image_slots:
        try:
            from app.core.vision import extract_text_from_base64_list
            b64_list = [
                {"url": f"data:image/jpeg;base64,{s.get('base64', '')}", "slot": s.get("slot", "")}
                for s in image_slots if s.get("base64")
            ][:5]
            if b64_list:
                ocr_results = await extract_text_from_base64_list(b64_list)
                if ocr_results:
                    materials["ocr_texts"] = {r["slot"]: r["text"] for r in ocr_results if r.get("text")}
        except Exception:
            pass

    # ── Compliance check ──
    from app.core.compliance import check_compliance
    texts_to_check = {
        "title": req.title_draft or "",
        "highlights": req.key_highlights or "",
        "bullet_1": req.bullet_1 or "", "bullet_2": req.bullet_2 or "",
        "bullet_3": req.bullet_3 or "", "bullet_4": req.bullet_4 or "",
        "bullet_5": req.bullet_5 or "",
    }
    violations = {}
    for field, text in texts_to_check.items():
        if text:
            hits = check_compliance(text)
            if hits:
                violations[field] = hits
    if violations:
        materials["compliance_violations"] = violations

    # ── Top 20 market context for cross-validation ──
    try:
        from app.core.scraperapi import ScraperAPIProvider
        import re
        keyword = materials.get("product_name", "")[:60]
        # If product name is Chinese, use English title_draft or highlights as keyword
        if re.search(r'[\u4e00-\u9fff]', keyword):
            alt = (req.title_draft or req.key_highlights or "").strip()
            if alt and not re.search(r'[\u4e00-\u9fff]', alt):
                keyword = alt[:60]
        provider = ScraperAPIProvider()
        capture = await provider.capture_top20_by_keyword(keyword, req.marketplace)
        if capture.capture_status != "failed" and capture.extracted_fields:
            materials["market_context"] = capture.extracted_fields
            materials["market_context_note"] = f"Top 20 results for '{keyword}' on {req.marketplace}"
    except Exception:
        pass

    ai_result = None
    try:
        ai = AI()
        ai_data = await ai.complete_json(prompt=build_prelaunch_prompt(materials), system=PRELAUNCH_SYSTEM, max_tokens=8192)
        ai_result = ai_data
    except Exception as e:
        ai_result = {"error": str(e), "partial": True}

    if ai_result and not ai_result.get("error"):
        report = PrelaunchCheck(
            user_id=uid, product_name=req.product_name, marketplace=req.marketplace,
            title_draft=req.title_draft, key_highlights=req.key_highlights,
            bullet_1=req.bullet_1, bullet_2=req.bullet_2, bullet_3=req.bullet_3,
            bullet_4=req.bullet_4, bullet_5=req.bullet_5,
            main_image_path=req.main_image_path,
            image_2_path=req.image_2_path, image_3_path=req.image_3_path,
            image_4_path=req.image_4_path, image_5_path=req.image_5_path,
            image_6_path=req.image_6_path, image_7_path=req.image_7_path,
            admission_result=ai_result.get("admission_result"),
            conclusion=ai_result.get("conclusion"),
            position_diagnoses_json=ai_result.get("position_diagnoses"),
            next_action=ai_result.get("next_action"),
        )
    else:
        raise Exception(ai_result.get("error", "AI 分析未返回有效结果"))

    db.add(report)
    await db.flush()
    return PrelaunchCheckResponse.model_validate(report, from_attributes=True)


async def list_checks(page: int, page_size: int, db: AsyncSession) -> dict:
    offset = (page - 1) * page_size
    q = select(PrelaunchCheck).order_by(desc(PrelaunchCheck.created_at)).offset(offset).limit(page_size)
    r = await db.execute(q)
    items = [PrelaunchCheckResponse.model_validate(x, from_attributes=True) for x in r.scalars().all()]
    total = len((await db.execute(select(PrelaunchCheck))).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_check(check_id: str, db: AsyncSession) -> PrelaunchCheckResponse | None:
    r = await db.execute(select(PrelaunchCheck).where(PrelaunchCheck.id == check_id))
    report = r.scalar_one_or_none()
    return PrelaunchCheckResponse.model_validate(report, from_attributes=True) if report else None
