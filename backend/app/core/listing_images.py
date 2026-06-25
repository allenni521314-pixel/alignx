from __future__ import annotations

"""Listing image slot helpers."""

from typing import Any

MAX_LISTING_IMAGE_SLOTS = 7


def build_product_context(listing_data: dict[str, Any]) -> str:
    parts: list[str] = []
    title = listing_data.get("title")
    if title:
        parts.append(f"产品标题：{title}")

    bullets = listing_data.get("bullet_points") or []
    if isinstance(bullets, list) and bullets:
        bullet_text = "\n".join([f"- {item}" for item in bullets if item])
        if bullet_text:
            parts.append(f"五点：\n{bullet_text}")

    details = listing_data.get("product_details") or {}
    if isinstance(details, dict) and details:
        detail_text = "\n".join([f"{key}: {value}" for key, value in details.items() if value])
        if detail_text:
            parts.append(f"产品字段：\n{detail_text}")

    return "\n".join(parts)[:1500]


def build_image_slots(listing_data: dict[str, Any]) -> list[tuple[str, str]]:
    slots: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(slot: str, url: Any) -> None:
        if not isinstance(url, str) or not url.startswith("http"):
            return
        if url in seen:
            return
        seen.add(url)
        slots.append((slot, url))

    add("主图", listing_data.get("main_image"))

    image_urls = listing_data.get("image_urls") or []
    if isinstance(image_urls, list):
        for index, url in enumerate(image_urls, start=1):
            add(f"副图{index}", url)
            if len(slots) >= MAX_LISTING_IMAGE_SLOTS:
                break

    return slots[:MAX_LISTING_IMAGE_SLOTS]


async def extract_slot_image_texts(listing_data: dict[str, Any]) -> dict[str, str]:
    from app.core.vision import extract_text_from_images

    slots = build_image_slots(listing_data)
    if not slots:
        return {}

    urls = [url for _, url in slots]
    slots_by_url = {url: slot for slot, url in slots}
    by_url = await extract_text_from_images(
        urls,
        product_context=build_product_context(listing_data),
        slots_by_url=slots_by_url,
    )
    return {
        slot: by_url.get(url, "").strip()
        for slot, url in slots
        if by_url.get(url, "").strip()
    }


async def ensure_snapshot_image_texts(snapshot: Any, db: Any) -> dict[str, str]:
    current = getattr(snapshot, "ocr_image_texts", None)
    if current and _has_scene_fit_result(current):
        return current

    listing_data = {
        "title": getattr(snapshot, "title", None),
        "bullet_points": getattr(snapshot, "bullet_points", None),
        "product_details": getattr(snapshot, "product_details", None),
        "main_image": getattr(snapshot, "main_image", None),
        "image_urls": getattr(snapshot, "image_urls", None),
    }
    image_texts = await extract_slot_image_texts(listing_data)
    if image_texts:
        snapshot.ocr_image_texts = image_texts
        await db.flush()
    return image_texts


def _has_scene_fit_result(image_texts: Any) -> bool:
    if not isinstance(image_texts, dict):
        return False
    return any("产品场景吻合度" in str(value) for value in image_texts.values())
