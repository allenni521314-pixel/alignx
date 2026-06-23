"""Pre-launch check service — listing materials → AI position diagnosis."""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.models import PrelaunchCheck
from app.schemas import PrelaunchCheckRequest, PrelaunchCheckResponse


async def analyze_prelaunch(
    req: PrelaunchCheckRequest,
    db: AsyncSession,
) -> PrelaunchCheckResponse:
    """Save materials and return placeholder. Full AI diagnosis in Phase 3."""

    report = PrelaunchCheck(
        user_id="default",
        product_name=req.product_name,
        marketplace=req.marketplace,
        title_draft=req.title_draft,
        key_highlights=req.key_highlights,
        bullet_1=req.bullet_1,
        bullet_2=req.bullet_2,
        bullet_3=req.bullet_3,
        bullet_4=req.bullet_4,
        bullet_5=req.bullet_5,
        main_image_path=req.main_image_path,
        image_2_path=req.image_2_path,
        image_3_path=req.image_3_path,
        image_4_path=req.image_4_path,
        image_5_path=req.image_5_path,
        image_6_path=req.image_6_path,
        image_7_path=req.image_7_path,
        aplus_images_json=req.aplus_images_json,
        admission_result="pending",
        conclusion="素材已接收，等待 AI 逐位置诊断",
    )
    db.add(report)
    await db.flush()

    return PrelaunchCheckResponse.model_validate(report, from_attributes=True)


async def list_checks(page: int, page_size: int, db: AsyncSession) -> dict:
    offset = (page - 1) * page_size
    q = select(PrelaunchCheck).order_by(desc(PrelaunchCheck.created_at)).offset(offset).limit(page_size)
    result = await db.execute(q)
    items = [PrelaunchCheckResponse.model_validate(r, from_attributes=True) for r in result.scalars().all()]
    count_q = select(PrelaunchCheck)
    count_result = await db.execute(count_q)
    total = len(count_result.scalars().all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


async def get_check(check_id: str, db: AsyncSession) -> PrelaunchCheckResponse | None:
    result = await db.execute(select(PrelaunchCheck).where(PrelaunchCheck.id == check_id))
    report = result.scalar_one_or_none()
    if not report:
        return None
    return PrelaunchCheckResponse.model_validate(report, from_attributes=True)
