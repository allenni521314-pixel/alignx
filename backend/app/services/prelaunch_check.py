from __future__ import annotations
"""Pre-launch check service — listing materials → AI position diagnosis."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import PrelaunchCheck
from app.schemas import PrelaunchCheckRequest, PrelaunchCheckResponse
from app.services.access import require_user_id, user_scoped
from app.services.prelaunch_ai_pipeline import run_prelaunch_ai_pipeline


async def analyze_prelaunch(req: PrelaunchCheckRequest, db: AsyncSession, user_id: str | None = None) -> PrelaunchCheckResponse:
    uid = require_user_id(user_id)
    pipeline_result = await run_prelaunch_ai_pipeline(req=req, db=db, user_id=uid)
    ai_result = pipeline_result.ai_result
    saved_images = _saved_image_fields(req)

    if ai_result and not ai_result.get("error"):
        report = PrelaunchCheck(
            user_id=uid, product_name=req.product_name, marketplace=req.marketplace,
            title_draft=req.title_draft, key_highlights=req.key_highlights,
            bullet_1=req.bullet_1, bullet_2=req.bullet_2, bullet_3=req.bullet_3,
            bullet_4=req.bullet_4, bullet_5=req.bullet_5,
            main_image_path=saved_images["main_image_path"],
            image_2_path=saved_images["image_2_path"], image_3_path=saved_images["image_3_path"],
            image_4_path=saved_images["image_4_path"], image_5_path=saved_images["image_5_path"],
            image_6_path=saved_images["image_6_path"], image_7_path=saved_images["image_7_path"],
            aplus_images_json=saved_images["aplus_images_json"],
            admission_result=ai_result.get("admission_result"),
            conclusion=ai_result.get("conclusion"),
            position_diagnoses_json=ai_result.get("position_diagnoses"),
            next_action=ai_result.get("next_action"),
        )
    else:
        raise Exception(pipeline_result.ai_error or "AI 分析未返回有效结果")

    db.add(report)
    await db.flush()
    return PrelaunchCheckResponse.model_validate(report, from_attributes=True)


def _saved_image_fields(req: PrelaunchCheckRequest) -> dict:
    fields = {
        "main_image_path": req.main_image_path,
        "image_2_path": req.image_2_path,
        "image_3_path": req.image_3_path,
        "image_4_path": req.image_4_path,
        "image_5_path": req.image_5_path,
        "image_6_path": req.image_6_path,
        "image_7_path": req.image_7_path,
        "aplus_images_json": req.aplus_images_json or [],
    }
    slot_to_field = {
        "main": "main_image_path",
        "img2": "image_2_path",
        "img3": "image_3_path",
        "img4": "image_4_path",
        "img5": "image_5_path",
        "img6": "image_6_path",
        "img7": "image_7_path",
    }
    aplus_images = list(fields["aplus_images_json"] or [])
    for item in req.image_slots or []:
        if not isinstance(item, dict):
            continue
        slot = item.get("slot")
        base64_value = item.get("base64")
        if not slot or not base64_value:
            continue
        url = f"data:image/jpeg;base64,{base64_value}"
        if slot in slot_to_field:
            fields[slot_to_field[slot]] = url
        elif str(slot).startswith("aplus"):
            aplus_images.append({
                "slot": slot,
                "name": item.get("name") or "",
                "url": url,
            })
    fields["aplus_images_json"] = aplus_images
    return fields


async def list_checks(page: int, page_size: int, db: AsyncSession, user_id: str | None = None) -> dict:
    uid = require_user_id(user_id)
    offset = (page - 1) * page_size
    q = user_scoped(select(PrelaunchCheck), PrelaunchCheck, uid)
    q = q.order_by(desc(PrelaunchCheck.created_at)).offset(offset).limit(page_size)
    r = await db.execute(q)
    items = [PrelaunchCheckResponse.model_validate(x, from_attributes=True) for x in r.scalars().all()]
    total_q = user_scoped(select(PrelaunchCheck), PrelaunchCheck, uid)
    total = len((await db.execute(total_q)).scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_check(check_id: str, db: AsyncSession, user_id: str | None = None) -> PrelaunchCheckResponse | None:
    uid = require_user_id(user_id)
    q = user_scoped(select(PrelaunchCheck), PrelaunchCheck, uid)
    r = await db.execute(q.where(PrelaunchCheck.id == check_id))
    report = r.scalar_one_or_none()
    return PrelaunchCheckResponse.model_validate(report, from_attributes=True) if report else None
