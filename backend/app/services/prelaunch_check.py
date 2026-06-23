"""Pre-launch check service — listing materials → AI position diagnosis."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import PrelaunchCheck
from app.schemas import PrelaunchCheckRequest, PrelaunchCheckResponse
from app.core.ai import AI
from app.core.prompts import build_prelaunch_prompt, PRELAUNCH_SYSTEM


async def analyze_prelaunch(req: PrelaunchCheckRequest, db: AsyncSession) -> PrelaunchCheckResponse:
    # Build materials dict
    materials = {
        "product_name": req.product_name,
        "title_draft": req.title_draft,
        "key_highlights": req.key_highlights,
        "bullet_points": [
            req.bullet_1, req.bullet_2, req.bullet_3, req.bullet_4, req.bullet_5,
        ],
    }

    # AI analysis
    ai_result = None
    try:
        ai = AI()
        prompt = build_prelaunch_prompt(materials)
        ai_data = await ai.complete_json(prompt=prompt, system=PRELAUNCH_SYSTEM)
        ai_result = ai_data
    except Exception as e:
        ai_result = {"error": str(e), "partial": True}

    # Save
    if ai_result and not ai_result.get("error"):
        report = PrelaunchCheck(
            user_id="default",
            product_name=req.product_name,
            marketplace=req.marketplace,
            title_draft=req.title_draft,
            key_highlights=req.key_highlights,
            bullet_1=req.bullet_1, bullet_2=req.bullet_2, bullet_3=req.bullet_3,
            bullet_4=req.bullet_4, bullet_5=req.bullet_5,
            main_image_path=req.main_image_path,
            image_2_path=req.image_2_path, image_3_path=req.image_3_path,
            image_4_path=req.image_4_path, image_5_path=req.image_5_path,
            image_6_path=req.image_6_path, image_7_path=req.image_7_path,
            aplus_images_json=req.aplus_images_json,
            admission_result=ai_result.get("admission_result"),
            conclusion=ai_result.get("conclusion"),
            position_diagnoses_json=ai_result.get("position_diagnoses"),
            next_action=ai_result.get("next_action"),
        )
    else:
        report = PrelaunchCheck(
            user_id="default", product_name=req.product_name, marketplace=req.marketplace,
            title_draft=req.title_draft, key_highlights=req.key_highlights,
            bullet_1=req.bullet_1, bullet_2=req.bullet_2, bullet_3=req.bullet_3,
            bullet_4=req.bullet_4, bullet_5=req.bullet_5,
            main_image_path=req.main_image_path,
            image_2_path=req.image_2_path, image_3_path=req.image_3_path,
            image_4_path=req.image_4_path, image_5_path=req.image_5_path,
            image_6_path=req.image_6_path, image_7_path=req.image_7_path,
            aplus_images_json=req.aplus_images_json,
            admission_result="pending",
            conclusion="素材已接收，AI 分析待完成",
        )

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
