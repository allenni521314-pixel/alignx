from __future__ import annotations

"""Listing image slot helpers."""

from typing import Any

MAX_LISTING_IMAGE_SLOTS = 7


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
    by_url = await extract_text_from_images(urls)
    return {
        slot: by_url.get(url, "").strip()
        for slot, url in slots
        if by_url.get(url, "").strip()
    }


async def ensure_snapshot_image_texts(snapshot: Any, db: Any) -> dict[str, str]:
    current = getattr(snapshot, "ocr_image_texts", None)
    if current:
        return current

    listing_data = {
        "main_image": getattr(snapshot, "main_image", None),
        "image_urls": getattr(snapshot, "image_urls", None),
    }
    image_texts = await extract_slot_image_texts(listing_data)
    if image_texts:
        snapshot.ocr_image_texts = image_texts
        await db.flush()
    return image_texts
